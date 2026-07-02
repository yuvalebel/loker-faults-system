"""
Bot API surface — a token-authenticated blueprint for the external WhatsApp bot.

Everything under /api/bot/* bypasses the Google-OAuth guard (see auth.py) and is
instead authenticated with a static shared token in the `X-API-Key` header
(env var BOT_API_KEY). The bot is a separate server that cannot log in with
Google, so it needs this separate surface.

Two routes:
  POST /api/bot/fault         — open a fault from the bot (same flow as the form)
  GET  /api/bot/fault-status  — censored status for the customer (NO codes)

The outbound direction (faults system -> bot, "fault resolved" WhatsApp) lives in
flask_app.py (/api/faults/notify-resolved), because it runs behind the OAuth UI.

Shared pieces (Fault model, session, helpers) are injected by flask_app via
init_bot_api() to avoid a circular import.
"""

import os
import re
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, jsonify, request

import db as adon_db

bot_bp = Blueprint("bot_api", __name__)

# fault_type values the bot is allowed to send. Anything else -> 400.
# (Matches the current form's fault types; severity is derived from these.)
ALLOWED_FAULT_TYPES = {
    "אחר",
    "אין מנעול",
    "לוקר לא נסגר",
    "מנעול התקלקל",
    "נזק לדלת",
}

# How far back a Closed fault still counts as "recently resolved" for status.
_RESOLVED_WINDOW_DAYS = 14

# Injected by flask_app.init_bot_api() — set once at startup.
_deps: dict = {}


def init_bot_api(**deps):
    """Wire in the shared objects owned by flask_app (Fault, OurSession, helpers)."""
    _deps.update(deps)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _token_ok(provided: str, expected: str) -> bool:
    """Constant-time-ish comparison; both must be non-empty."""
    if not provided or not expected:
        return False
    # hmac.compare_digest guards against timing side-channels.
    import hmac
    return hmac.compare_digest(str(provided), str(expected))


def require_bot_token(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        expected = os.environ.get("BOT_API_KEY", "")
        provided = request.headers.get("X-API-Key", "")
        if not _token_ok(provided, expected):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Student / locker resolution helpers
# ---------------------------------------------------------------------------

def _norm_phone(phone) -> str:
    """Canonical phone for matching across formats.

    Strips dashes/spaces/+, drops a leading '00' international prefix, and rewrites
    Israel's 972 country code to a local leading 0. Foreign numbers keep their full
    international digits, so they match as long as both sides use the same form.
    Examples: '068-7911012' -> '0687911012'; '+972-587911012' -> '0587911012'.
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("972"):
        digits = "0" + digits[3:]
    return digits


def _find_students_by_phone(phone) -> list[dict]:
    target = _norm_phone(phone)
    if not target:
        return []
    return [
        s for s in adon_db.get_all_students()
        if _norm_phone(s.get("parentPhone")) == target
    ]


def _full_name(student: dict) -> str:
    return f"{student.get('fname') or ''} {student.get('lname') or ''}".strip()


def _norm_name(name) -> str:
    """Loose name key: trimmed, single-spaced, niqqud/quotes stripped, lowercased."""
    s = str(name or "").strip()
    s = re.sub(r"[֑-ׇ]", "", s)  # Hebrew niqqud / cantillation
    s = s.replace('"', "").replace("'", "").replace("״", "").replace("׳", "")
    s = re.sub(r"\s+", " ", s)
    return s.lower()


def _name_matches(query, full_name) -> bool:
    """Flexible match: exact, substring either way, or all query tokens present.

    Lets a customer type just a first name, the full name, or with minor spacing
    differences and still resolve to the right sibling on a shared parent phone.
    """
    q = _norm_name(query)
    n = _norm_name(full_name)
    if not q or not n:
        return False
    if q == n or q in n or n in q:
        return True
    n_tokens = set(n.split())
    return all(t in n_tokens for t in q.split())


def _match_summary(students: list[dict]) -> list[dict]:
    """Non-sensitive fields the bot shows the customer to disambiguate — no ת.ז."""
    return [
        {
            "student_name": _full_name(s),
            "school_name": s.get("school_name"),
            "class": (f"{s.get('class') or ''}{s.get('classNumber') or ''}".strip() or None),
        }
        for s in students
    ]


# ---------------------------------------------------------------------------
# POST /api/bot/fault — open a fault from the bot
# ---------------------------------------------------------------------------

@bot_bp.route("/api/bot/fault", methods=["POST"])
@require_bot_token
def bot_create_fault():
    data = request.get_json(silent=True) or {}

    parent_phone = (data.get("parent_phone") or "").strip()
    if not parent_phone:
        return jsonify({"ok": False, "error": "parent_phone חובה"}), 400

    fault_type = data.get("fault_type")
    if fault_type not in ALLOWED_FAULT_TYPES:
        return jsonify({
            "ok": False,
            "error": "fault_type לא חוקי",
            "allowed": sorted(ALLOWED_FAULT_TYPES),
        }), 400

    student_name = (data.get("student_name") or "").strip() or None
    locker_id = (data.get("locker_id") or "").strip() or None

    # --- Resolve the student by name + parent phone (the bot has no ת.ז).
    # If the bot did send a locker_id it's the cleanest connector and wins. ---
    student = None
    if locker_id:
        locker = adon_db.get_locker_by_id(locker_id)
        if locker and locker.get("current_student_id"):
            student = adon_db.get_student_by_id(locker["current_student_id"])

    if student is None:
        matches = _find_students_by_phone(parent_phone)
        if student_name:
            named = [s for s in matches if _name_matches(student_name, _full_name(s))]
            if named:  # only narrow when the name actually matched someone
                matches = named
        if len(matches) == 0:
            return jsonify({"ok": False, "error": "student_not_found"}), 404
        if len(matches) > 1:
            # Several kids on this phone and the name didn't single one out.
            return jsonify({
                "ok": False,
                "error": "multiple_matches",
                "matches": _match_summary(matches),
            }), 409
        student = matches[0]

    student_id_ext = student["id"]

    # --- Resolve the locker if the bot didn't hand us one ---
    if not locker_id:
        locker = adon_db.get_locker_by_student_id(student_id_ext)
        locker_id = locker["locker_id"] if locker else None

    # --- Create the fault exactly like the form does ---
    # A bot fault must behave identically to a form fault; it just enters from a
    # different place. The form derives severity from fault_type and does NOT
    # assign a technician on creation (that happens later in the scheduling
    # screen) — so neither do we. assigned_technician stays null here.
    Fault = _deps["Fault"]
    OurSession = _deps["OurSession"]
    get_severity = _deps["get_severity"]

    session = OurSession()
    try:
        severity = get_severity(fault_type)  # derived from fault_type, like the form
        books_stuck = bool(data.get("books_stuck", False))
        is_urgent = books_stuck

        previous = session.query(Fault).filter(
            Fault.student_id_ext == student_id_ext,
            Fault.fault_type == fault_type,
            Fault.status == "Closed",
        ).first()
        is_recurring = previous is not None

        new_fault = Fault(
            student_id_ext=student_id_ext,
            locker_id=locker_id,
            fault_type=fault_type,
            severity=severity,
            books_stuck=books_stuck,
            is_urgent=is_urgent,
            is_recurring=is_recurring,
            status="Open",
            description=data.get("description"),
        )
        session.add(new_fault)
        session.commit()
        session.refresh(new_fault)

        return jsonify({
            "ok": True,
            "fault_id": new_fault.id,
            "status": new_fault.status,
            "is_recurring": is_recurring,
            "assigned_technician": new_fault.assigned_technician,
        })
    except Exception as e:  # noqa: BLE001 — surface the reason to the bot
        session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        session.close()


# ---------------------------------------------------------------------------
# GET /api/bot/fault-status — censored status for the customer (NO codes)
# ---------------------------------------------------------------------------

@bot_bp.route("/api/bot/fault-status", methods=["GET"])
@require_bot_token
def bot_fault_status():
    phone = request.args.get("phone")
    name = request.args.get("name")

    if not phone:
        return jsonify({"ok": False, "error": "phone נדרש"}), 400

    students = _find_students_by_phone(phone)
    if name and len(students) > 1:
        named = [s for s in students if _name_matches(name, _full_name(s))]
        if named:
            students = named
    student_ids = [s["id"] for s in students]

    not_found = {"found": False, "message": "לא נמצאה תקלה רשומה על המספר הזה."}
    if not student_ids:
        return jsonify(not_found)

    Fault = _deps["Fault"]
    OurSession = _deps["OurSession"]

    session = OurSession()
    try:
        faults = session.query(Fault).filter(
            Fault.student_id_ext.in_(student_ids)
        ).all()

        if any(f.status == "Open" for f in faults):
            return jsonify({
                "found": True,
                "status": "open",
                "message": "התקלה שלך רשומה במערכת. טכנאי יגיע בימים הקרובים לטפל בה.",
            })

        cutoff = datetime.utcnow() - timedelta(days=_RESOLVED_WINDOW_DAYS)
        if any(
            f.status == "Closed" and f.resolved_at and f.resolved_at >= cutoff
            for f in faults
        ):
            return jsonify({
                "found": True,
                "status": "resolved",
                "message": "התקלה שדיווחת עליה טופלה. תודה על הסבלנות 🙏",
            })

        return jsonify(not_found)
    finally:
        session.close()
