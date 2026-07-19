"""
Flask Faults System
===================
Reads students/lockers LIVE from the Adon Locker production DB (read-only)
via db.py, writes faults to our own Postgres.

DB config comes from env vars:
    OUR_DATABASE_URL          — our Postgres (Render). Holds `faults`.
    ADON_LOCKER_DATABASE_URL  — Netanel's Supabase. Read-only.
"""

import os
from collections import Counter
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, render_template_string, request
from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import db as adon_db
from auth import init_auth
from bot_api import bot_bp, init_bot_api

load_dotenv()

# ============================================================================
# FLASK APP
# ============================================================================

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False  # Hebrew

# Trust X-Forwarded-* headers from Traefik so url_for(_external=True) builds https URLs
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Wire up Google OAuth + the global before_request login guard.
# Public paths (/auth/*, /api/health, /static/*) are exempted inside init_auth.
init_auth(app)

# ============================================================================
# OUR DATABASE (faults only)
# ============================================================================

our_engine = adon_db.get_our_engine()
Base = declarative_base()


class Fault(Base):
    __tablename__ = "faults"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id_ext = Column(String, nullable=False)
    locker_id = Column(String, nullable=True)
    fault_type = Column(String, nullable=False)
    severity = Column(Integer, nullable=False)
    books_stuck = Column(Boolean, default=False)
    is_urgent = Column(Boolean, default=False)
    is_recurring = Column(Boolean, default=False)
    status = Column(String, default="Open")
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    assigned_technician = Column(String, nullable=True)
    technician_notes = Column(String, nullable=True)


Base.metadata.create_all(our_engine)
OurSession = sessionmaker(bind=our_engine)

# ============================================================================
# SCHOOL → REGION MAPPING (DYNAMIC)
# School names come live from Netanel's DB; region overrides are kept in
# school_regions.json next to this file. See db.get_school_regions().
# ============================================================================


def get_school_region(school_name):
    """Region for a school name, 'Unknown' if not classified."""
    return adon_db.get_region_for_school(school_name)


def school_mapping():
    """Live {school_name: region} dict, refreshed via TTL cache in db.py."""
    return adon_db.get_school_regions()


# ============================================================================
# TECHNICIANS
# ============================================================================

TECHNICIANS = [
    {"id": 1, "name": "טכנאי 1", "home_region": "Center"},
    {"id": 2, "name": "טכנאי 2", "home_region": "Jerusalem"},
    {"id": 3, "name": "טכנאי 3", "home_region": "North"},
    {"id": 4, "name": "טכנאי 4", "home_region": "South"},
]

REGION_PROXIMITY = {
    "South":     {"South": 0, "Lowland": 1, "Jerusalem": 2, "Center": 3, "North": 4},
    "Jerusalem": {"Jerusalem": 0, "Center": 1, "South": 2, "Lowland": 2, "North": 3},
    "Center":    {"Center": 0, "Jerusalem": 1, "Lowland": 1, "North": 2, "South": 3},
    "North":     {"North": 0, "Center": 1, "Lowland": 2, "Jerusalem": 2, "South": 4},
    "Lowland":   {"Lowland": 0, "Center": 1, "North": 1, "Jerusalem": 2, "South": 2},
    "Unknown":   {"South": 2, "Jerusalem": 2, "Center": 2, "North": 2, "Lowland": 2},
}

SEVERITY_MAP = {
    "מנעול התקלקל": 5,
    "הקודן לא עובד": 4,
    "נזק לדלת": 3,
    "לוקר לא נסגר": 3,
    "ציר דלת שבור": 3,
    "אין מנעול": 2,
    "אחר": 1,
    # Legacy names — kept until the one-shot migration runs in production.
    "תקלה במנעול": 5,
    "הקוד לא עובד": 4,
    "מפתח אבוד": 2,
}


def get_severity(fault_type):
    return SEVERITY_MAP.get(fault_type, 1)


# ============================================================================
# STUDENT LOOKUP HELPERS (live from Adon Locker DB via db.py + TTL cache)
# ============================================================================

def _students_dataframe() -> pd.DataFrame:
    """Convenience: live students as a DataFrame for the scheduling logic."""
    rows = adon_db.get_all_students()
    if not rows:
        return pd.DataFrame(
            columns=[
                "id", "fname", "lname", "studentId", "class",
                "classNumber", "parentPhone", "email", "school_name",
            ]
        )
    return pd.DataFrame(rows)


# Wire the bot API blueprint (token-authenticated /api/bot/* surface).
# A bot fault is created exactly like a form fault (severity derived from
# fault_type, no technician assigned on creation), so only these are injected.
init_bot_api(
    OurSession=OurSession,
    Fault=Fault,
    get_severity=get_severity,
)
app.register_blueprint(bot_bp)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/students", methods=["GET"])
def get_students():
    """Live list of students from Adon Locker DB."""
    students_df = _students_dataframe()
    if students_df.empty:
        return jsonify([])

    students_df = students_df.copy()
    students_df["display_name"] = (
        students_df["fname"].fillna("") + " " + students_df["lname"].fillna("")
        + " | ת.ז: " + students_df["studentId"].fillna("")
        + " | " + students_df["school_name"].fillna("אין בית ספר")
    )
    # Replace pandas NaN with None so the JSON output is spec-compliant (browsers
    # reject literal `NaN`). Going via to_json/json.loads roundtrip handles all
    # column types correctly, including nested datetimes and numerics.
    import json as _json
    return jsonify(_json.loads(students_df.to_json(orient="records", force_ascii=False)))


@app.route("/api/faults", methods=["GET"])
def get_faults():
    """All faults from our DB, enriched with student info from Adon Locker DB."""
    session = OurSession()
    try:
        faults = session.query(Fault).order_by(Fault.created_at.desc()).all()
        students_df = _students_dataframe()

        result = []
        for fault in faults:
            fault_dict = {
                "id": fault.id,
                "student_id_ext": fault.student_id_ext,
                "locker_id": fault.locker_id,
                "fault_type": fault.fault_type,
                "severity": fault.severity,
                "books_stuck": fault.books_stuck,
                "is_urgent": fault.is_urgent,
                "is_recurring": getattr(fault, "is_recurring", False),
                "status": fault.status,
                "description": fault.description,
                # Mark naive UTC datetimes with 'Z' so the browser converts to local.
                "created_at": (fault.created_at.isoformat() + "Z") if fault.created_at else None,
                "resolved_at": (fault.resolved_at.isoformat() + "Z") if fault.resolved_at else None,
                "assigned_technician": fault.assigned_technician,
                "technician_notes": getattr(fault, "technician_notes", None),
            }

            student_info = students_df[students_df["id"] == fault.student_id_ext] if not students_df.empty else None
            if student_info is not None and not student_info.empty:
                student = student_info.iloc[0]
                fault_dict["student_name"] = f"{student['fname']} {student['lname']}"
                fault_dict["studentId"] = student["studentId"]
                fault_dict["parentPhone"] = student.get("parentPhone")
                school_name = student.get("school_name", "N/A")
                fault_dict["school_name"] = school_name
                fault_dict["region"] = school_mapping().get(school_name, "Unknown")
            else:
                fault_dict["student_name"] = "Unknown"
                fault_dict["studentId"] = "N/A"
                fault_dict["school_name"] = "N/A"
                fault_dict["region"] = "Unknown"

            # Locker enrichment for the mobile / detail views (cached upstream)
            if fault.locker_id:
                locker = adon_db.get_locker_by_id(fault.locker_id)
                if locker:
                    fault_dict["locker_info"] = {
                        "cabinet_name": locker.get("cabinet_name"),
                        "cell_number": locker.get("cell_number"),
                        "lock_type": locker.get("lock_type"),
                        "student_code": locker.get("student_code"),
                        "master_code": locker.get("master_code"),
                        "lock_number": locker.get("lock_number"),
                        "lock_code": locker.get("lock_code"),
                        "lock_code2": locker.get("lock_code2"),
                    }

            result.append(fault_dict)

        return jsonify(result)
    finally:
        session.close()


@app.route("/api/faults", methods=["POST"])
def create_fault():
    """Create a new fault. Auto-detects 'recurring' against this student's history."""
    data = request.get_json()

    session = OurSession()
    try:
        severity = get_severity(data["fault_type"])
        is_urgent = data.get("books_stuck", False)

        previous = session.query(Fault).filter(
            Fault.student_id_ext == data["student_id_ext"],
            Fault.fault_type == data["fault_type"],
            Fault.status == "Closed",
        ).first()
        is_recurring = previous is not None

        new_fault = Fault(
            student_id_ext=data["student_id_ext"],
            locker_id=data.get("locker_id"),
            fault_type=data["fault_type"],
            severity=severity,
            books_stuck=data.get("books_stuck", False),
            is_urgent=is_urgent,
            is_recurring=is_recurring,
            status="Open",
            description=data.get("description"),
        )

        session.add(new_fault)
        session.commit()
        session.refresh(new_fault)

        return jsonify({
            "success": True,
            "fault_id": new_fault.id,
            "is_recurring": is_recurring,
            "message": f'תקלה נוצרה בהצלחה{" (זוהתה כתקלה חוזרת)" if is_recurring else ""}',
        })
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


def _notify_bot_fault_resolved(fault, session):
    """Tell the BOT this fault was resolved — WhatsApp to the customer + 'טופל' on
    the bot's console (incident boundary + closing note, bot-side).

    Shared by EVERY close path (Shilo 2026-07-16: some close buttons were wired,
    some weren't — the customer only got the resolved-WhatsApp from the technician
    screen). Server-side on the status TRANSITION, so present and future buttons
    are all covered. Best-effort: a bot hiccup must never fail the status update.
    The bot dedups by fault_id, so a double trigger (e.g. the technician screen's
    explicit notify + this hook) sends at most ONE WhatsApp.
    Returns (ok: bool, detail: str).
    """
    import requests

    try:
        student = adon_db.get_student_by_id(fault.student_id_ext) or {}
        phone = student.get("parentPhone")
        if not phone:
            return False, "no_parent_phone"

        locker = adon_db.get_locker_by_id(fault.locker_id) if fault.locker_id else None
        locker = locker or {}

        payload = {
            "phone": phone,
            "student_name": f"{student.get('fname') or ''} {student.get('lname') or ''}".strip(),
            "school_name": student.get("school_name") or "",
            "cabinet_name": locker.get("cabinet_name") or "",
            "cell_number": locker.get("cell_number") or "",
            "student_code": locker.get("student_code") or "",
            "fault_id": fault.id,
        }

        bot_url = os.environ.get("BOT_NOTIFY_URL")
        faults_api_key = os.environ.get("FAULTS_API_KEY")
        if not bot_url or not faults_api_key:
            return False, "bot_not_configured"

        resp = requests.post(
            bot_url.rstrip("/") + "/api/notify",
            json=payload,
            headers={"X-API-Key": faults_api_key},
            timeout=10,
        )
        if resp.ok:
            return True, f"bot_status_{resp.status_code}"
        return False, f"bot_error_{resp.status_code}"
    except requests.RequestException as e:
        return False, f"bot_unreachable: {e}"
    except Exception as e:  # never let the notify break the close itself
        return False, str(e)

def _notify_bot_fault_status(fault, new_status):
    """Internal status sync to the bot (2026-07-19, operator-controlled notify).

    Fires on EVERY status transition, both directions (close AND reopen). The bot
    updates its conversation cards/console silently — it never messages the
    customer from this call. The customer WhatsApp goes out ONLY via
    /api/faults/notify-resolved (the dedicated button) -> bot /api/notify.
    Best-effort: a bot hiccup never fails the status update itself.
    Returns (ok: bool, detail: str).
    """
    import requests

    try:
        student = adon_db.get_student_by_id(fault.student_id_ext) or {}
        phone = student.get("parentPhone")
        if not phone:
            return False, "no_parent_phone"

        bot_url = os.environ.get("BOT_NOTIFY_URL")
        faults_api_key = os.environ.get("FAULTS_API_KEY")
        if not bot_url or not faults_api_key:
            return False, "bot_not_configured"

        resp = requests.post(
            bot_url.rstrip("/") + "/api/fault-status",
            json={"fault_id": fault.id, "phone": phone, "status": new_status},
            headers={"X-API-Key": faults_api_key},
            timeout=10,
        )
        if resp.ok:
            return True, f"bot_status_{resp.status_code}"
        return False, f"bot_error_{resp.status_code}"
    except requests.RequestException as e:
        return False, f"bot_unreachable: {e}"
    except Exception as e:  # never let the sync break the status update itself
        return False, str(e)


@app.route("/api/update_status", methods=["POST"])
def update_status():
    data = request.get_json()
    session = OurSession()
    try:
        fault = session.query(Fault).filter(Fault.id == data["fault_id"]).first()
        if not fault:
            return jsonify({"success": False, "error": "Fault not found"}), 404

        old_status = fault.status
        new_status = data["status"]
        fault.status = new_status

        if new_status == "Closed" and not fault.resolved_at:
            fault.resolved_at = datetime.utcnow()
        elif new_status == "Open":
            fault.resolved_at = None

        if "technician" in data:
            fault.assigned_technician = data["technician"]

        session.commit()

        # Status transition → SILENT bot sync (2026-07-19): the bot updates its
        # cards/console; the customer WhatsApp is the operator's dedicated button.
        bot_synced = None
        if new_status != old_status:
            ok, detail = _notify_bot_fault_status(fault, new_status)
            bot_synced = {"ok": ok, "detail": detail}

        return jsonify({"success": True, "message": "סטטוס עודכן בהצלחה", "bot_synced": bot_synced})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@app.route("/api/faults/update", methods=["POST"])
def update_fault_with_notes():
    """Update fault status, technician, and technician notes."""
    data = request.get_json()
    session = OurSession()
    try:
        fault = session.query(Fault).filter(Fault.id == data["fault_id"]).first()
        if not fault:
            return jsonify({"success": False, "error": "Fault not found"}), 404

        old_status = fault.status
        if "status" in data:
            new_status = data["status"]
            fault.status = new_status
            if new_status == "Closed" and not fault.resolved_at:
                fault.resolved_at = datetime.utcnow()
            elif new_status == "Open":
                fault.resolved_at = None

        if "technician_notes" in data:
            fault.technician_notes = data["technician_notes"]
        if "technician" in data:
            fault.assigned_technician = data["technician"]

        session.commit()

        # Status transition → SILENT bot sync (same hook as /api/update_status).
        bot_synced = None
        if "status" in data and data["status"] != old_status:
            ok, detail = _notify_bot_fault_status(fault, data["status"])
            bot_synced = {"ok": ok, "detail": detail}

        return jsonify({
            "success": True,
            "message": "התקלה עודכנה בהצלחה",
            "bot_synced": bot_synced,
            "fault": {
                "id": fault.id,
                "status": fault.status,
                "technician_notes": fault.technician_notes,
                "resolved_at": (fault.resolved_at.isoformat() + "Z") if fault.resolved_at else None,
            },
        })
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@app.route("/api/faults/notify-resolved", methods=["POST"])
def notify_resolved():
    """Send the 'fault resolved' WhatsApp to the customer — via the bot's number.

    Called by the technician UI after closing a fault. We assemble the fields the
    approved WhatsApp template needs and POST them to the bot's /api/notify, which
    sends the message from the official Adon Locker number. The FAULTS_API_KEY and
    the bot URL stay server-side (this route is behind the OAuth guard).
    """
    data = request.get_json(silent=True) or {}
    fault_id = data.get("fault_id")

    session = OurSession()
    try:
        fault = session.query(Fault).filter(Fault.id == fault_id).first()
        if not fault:
            return jsonify({"success": False, "error": "Fault not found"}), 404

        # Single source of truth (2026-07-16): the same helper every close path uses.
        ok, detail = _notify_bot_fault_resolved(fault, session)
        if ok:
            return jsonify({"success": True, "detail": detail})
        if detail == "no_parent_phone":
            return jsonify({"success": False, "error": detail}), 400
        if detail == "bot_not_configured":
            return jsonify({"success": False, "error": detail}), 503
        return jsonify({"success": False, "error": detail}), 502
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


# ============================================================================
# SCHEDULING ALGORITHM (unchanged business logic)
# ============================================================================

def run_scheduling_algorithm(faults_df, num_technicians):
    """
    Weighted Engineering Heuristic for technician assignment.

    Priority Score (per school) = 0.35*N + 0.25*U + 0.25*T + 0.15*R
      N  — Batching (35%): clustered faults at one school amortise travel (Benjaafar)
      U  — RCM (25%): functional severity (1=aesthetic, 5=blocking) (WBDG)
      T  — Max-Min Fairness (25%): wait time builds priority (Ghaderi)
      R  — Service Recovery (15%): recurring failures get a boost (Matos)

    TOC override (Theory of Constraints): if any fault at the school is
    `books_stuck` OR `is_urgent`, score is set to a sentinel that forces
    that school to the front of the queue.

    Assignment is then done in three phases:
      Phase 1 — anchor each tech to the next-highest-scoring school
      Phase 2 — each tech absorbs all unassigned schools in their region
      Phase 3 — overflow goes to the least-loaded tech
    """
    if faults_df.empty:
        return {}

    now = datetime.utcnow()
    faults_df["age_days"] = faults_df["created_at"].apply(
        lambda x: (now - x).total_seconds() / 86400 if x else 0
    )

    school_metrics = faults_df.groupby("school_name").agg({
        "fault_id": "count",
        "severity": "mean",
        "age_days": "max",
        "is_recurring": "max",
        "is_urgent": "max",
        "books_stuck": "max",
        "region": "first",
    }).reset_index()

    school_metrics.columns = [
        "school_name", "fault_count", "avg_severity", "max_age_days",
        "has_recurring", "has_urgent", "has_books_stuck", "region",
    ]

    # Normalise each component to a [1, 5] scale so weights are comparable.
    school_metrics["N"] = school_metrics["fault_count"].apply(lambda x: min(x, 5))
    school_metrics["U"] = school_metrics["avg_severity"]
    # Fairness: 12-day gradient instead of 5 — gives meaningful priority growth
    # across a full school fortnight before saturating.
    school_metrics["T"] = school_metrics["max_age_days"].apply(
        lambda x: min(1 + (max(x, 0) / 3), 5)
    )
    school_metrics["R"] = school_metrics["has_recurring"].apply(lambda x: 5 if x else 1)

    school_metrics["priority_score"] = (
        0.35 * school_metrics["N"]
        + 0.25 * school_metrics["U"]
        + 0.25 * school_metrics["T"]
        + 0.15 * school_metrics["R"]
    )
    # TOC override: blockers (books locked inside the locker, or marked urgent)
    # jump the entire queue regardless of other components.
    toc_blocker = (school_metrics["has_urgent"] == True) | (school_metrics["has_books_stuck"] == True)
    school_metrics.loc[toc_blocker, "priority_score"] = 10000

    school_metrics = school_metrics.sort_values("priority_score", ascending=False).reset_index(drop=True)
    school_metrics["assigned"] = False

    assignments = {}
    technician_workload = {}
    tech_primary_region = {}

    for i in range(1, num_technicians + 1):
        tech_name = f"טכנאי {i}"
        assignments[tech_name] = []
        technician_workload[tech_name] = 0
        tech_primary_region[tech_name] = None

    total_faults = len(faults_df)
    workload_cap = (total_faults / num_technicians) * 1.5

    # Phase 1: Anchor seeding
    num_anchors = min(num_technicians, len(school_metrics))
    for i in range(num_anchors):
        school = school_metrics.iloc[i]
        tech_name = f"טכנאי {i + 1}"
        school_name = school["school_name"]
        region = school["region"]
        num_faults = school["fault_count"]

        assignments[tech_name].append({
            "school_name": school_name,
            "region": region,
            "priority_score": float(school["priority_score"]),
            "num_faults": int(num_faults),
            "is_urgent": bool(school["has_urgent"]),
            "avg_severity": float(school["avg_severity"]),
            "oldest_fault_days": float(school["max_age_days"]),
            "faults": faults_df[faults_df["school_name"] == school_name].to_dict(orient="records"),
            "assignment_type": "Phase 1 - Anchor",
        })

        technician_workload[tech_name] += num_faults
        tech_primary_region[tech_name] = region
        school_metrics.loc[i, "assigned"] = True

    # Phase 2: Strict region exhaustion
    for tech_name, primary_region in tech_primary_region.items():
        if not primary_region:
            continue
        region_schools = school_metrics[
            (~school_metrics["assigned"]) & (school_metrics["region"] == primary_region)
        ]
        for idx, school in region_schools.iterrows():
            num_faults = school["fault_count"]
            if technician_workload[tech_name] + num_faults <= workload_cap:
                school_name = school["school_name"]
                assignments[tech_name].append({
                    "school_name": school_name,
                    "region": primary_region,
                    "priority_score": float(school["priority_score"]),
                    "num_faults": int(num_faults),
                    "is_urgent": bool(school["has_urgent"]),
                    "avg_severity": float(school["avg_severity"]),
                    "oldest_fault_days": float(school["max_age_days"]),
                    "faults": faults_df[faults_df["school_name"] == school_name].to_dict(orient="records"),
                    "assignment_type": "Phase 2 - Region Absorbed",
                })
                technician_workload[tech_name] += num_faults
                school_metrics.loc[idx, "assigned"] = True

    # Phase 3: Global leftovers
    unassigned_schools = school_metrics[~school_metrics["assigned"]]
    for idx, school in unassigned_schools.iterrows():
        num_faults = school["fault_count"]
        school_name = school["school_name"]
        region = school["region"]
        best_tech = min(technician_workload.items(), key=lambda x: x[1])[0]

        assignments[best_tech].append({
            "school_name": school_name,
            "region": region,
            "priority_score": float(school["priority_score"]),
            "num_faults": int(num_faults),
            "is_urgent": bool(school["has_urgent"]),
            "avg_severity": float(school["avg_severity"]),
            "oldest_fault_days": float(school["max_age_days"]),
            "faults": faults_df[faults_df["school_name"] == school_name].to_dict(orient="records"),
            "assignment_type": "Phase 3 - Overflow Leftover",
        })
        technician_workload[best_tech] += num_faults
        school_metrics.loc[idx, "assigned"] = True

    return assignments


@app.route("/api/technicians", methods=["GET"])
def get_technicians():
    """Technicians list with current workload + most-frequent active region."""
    session = OurSession()
    try:
        open_faults = session.query(Fault).filter(
            Fault.status == "Open",
            Fault.assigned_technician != None,  # noqa: E711
        ).all()

        students_df = _students_dataframe()

        workload = {}
        for fault in open_faults:
            tech = fault.assigned_technician
            if tech not in workload:
                workload[tech] = {"count": 0, "regions": []}
            workload[tech]["count"] += 1
            if not students_df.empty:
                si = students_df[students_df["id"] == fault.student_id_ext]
                if not si.empty:
                    sn = si.iloc[0].get("school_name", "Unknown")
                    workload[tech]["regions"].append(school_mapping().get(sn, "Unknown"))

        result = []
        for tech in TECHNICIANS:
            tech_name = tech["name"]
            wl = workload.get(tech_name, {"count": 0, "regions": []})
            if wl["regions"]:
                current_region = Counter(wl["regions"]).most_common(1)[0][0]
            else:
                current_region = tech["home_region"]
            result.append({
                "id": tech["id"],
                "name": tech_name,
                "home_region": tech["home_region"],
                "current_region": current_region,
                "open_faults": wl["count"],
            })

        return jsonify({"success": True, "technicians": result})
    finally:
        session.close()


@app.route("/api/suggest_technician", methods=["POST"])
def suggest_technician():
    """Rank technicians by region proximity + current workload."""
    data = request.get_json()
    fault_id = data.get("fault_id")

    session = OurSession()
    try:
        fault = session.query(Fault).filter(Fault.id == fault_id).first()
        if not fault:
            return jsonify({"success": False, "error": "Fault not found"}), 404

        students_df = _students_dataframe()

        fault_region = "Unknown"
        if not students_df.empty:
            si = students_df[students_df["id"] == fault.student_id_ext]
            if not si.empty:
                sn = si.iloc[0].get("school_name", "Unknown")
                fault_region = school_mapping().get(sn, "Unknown")

        open_faults = session.query(Fault).filter(
            Fault.status == "Open",
            Fault.assigned_technician != None,  # noqa: E711
        ).all()
        workload = {}
        for of in open_faults:
            tech = of.assigned_technician
            if tech not in workload:
                workload[tech] = {"count": 0, "regions": []}
            workload[tech]["count"] += 1
            if not students_df.empty:
                si2 = students_df[students_df["id"] == of.student_id_ext]
                if not si2.empty:
                    sn2 = si2.iloc[0].get("school_name", "Unknown")
                    workload[tech]["regions"].append(school_mapping().get(sn2, "Unknown"))

        prox = REGION_PROXIMITY.get(
            fault_region,
            {k: 2 for k in ["South", "Jerusalem", "Center", "North", "Lowland"]},
        )

        ranked = []
        for tech in TECHNICIANS:
            tech_name = tech["name"]
            wl = workload.get(tech_name, {"count": 0, "regions": []})
            if wl["regions"]:
                current_region = Counter(wl["regions"]).most_common(1)[0][0]
            else:
                current_region = tech["home_region"]

            dist = prox.get(current_region, 3)
            score = dist * 3 + wl["count"]

            ranked.append({
                "id": tech["id"],
                "name": tech_name,
                "current_region": current_region,
                "open_faults": wl["count"],
                "distance_score": dist,
                "total_score": score,
            })

        ranked.sort(key=lambda x: x["total_score"])
        return jsonify({
            "success": True,
            "fault_region": fault_region,
            "ranked_technicians": ranked,
        })
    finally:
        session.close()


@app.route("/api/assign_fault", methods=["POST"])
def assign_fault():
    data = request.get_json()
    fault_id = data.get("fault_id")
    technician_name = data.get("technician_name")

    session = OurSession()
    try:
        fault = session.query(Fault).filter(Fault.id == fault_id).first()
        if not fault:
            return jsonify({"success": False, "error": "Fault not found"}), 404

        fault.assigned_technician = technician_name
        session.commit()
        return jsonify({"success": True, "message": f"התקלה הוקצתה ל-{technician_name}"})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@app.route("/api/schedule", methods=["POST"])
def schedule_technicians():
    data = request.get_json()
    num_technicians = data.get("num_technicians", 1)

    session = OurSession()
    try:
        open_faults = session.query(Fault).filter(Fault.status == "Open").all()
        if not open_faults:
            return jsonify({
                "success": True,
                "message": "אין תקלות פתוחות",
                "assignments": [],
            })

        students_df = _students_dataframe()

        faults_data = []
        for fault in open_faults:
            student_name = "Unknown"
            school_name = "Unknown"
            if not students_df.empty:
                student_info = students_df[students_df["id"] == fault.student_id_ext]
                if not student_info.empty:
                    school_name = student_info.iloc[0].get("school_name", "Unknown")
                    student_name = f"{student_info.iloc[0]['fname']} {student_info.iloc[0]['lname']}"

            # Lock type drives which equipment the technician needs to bring.
            # adon_db.get_locker_by_id is TTL-cached so this stays cheap.
            lock_type = None
            if fault.locker_id:
                locker = adon_db.get_locker_by_id(fault.locker_id)
                if locker:
                    lock_type = locker.get("lock_type")

            region = get_school_region(school_name)
            faults_data.append({
                "fault_id": fault.id,
                "student_name": student_name,
                "school_name": school_name,
                "region": region,
                "fault_type": fault.fault_type,
                "severity": fault.severity,
                "is_urgent": fault.is_urgent,
                "books_stuck": fault.books_stuck,
                "is_recurring": getattr(fault, "is_recurring", False),
                "created_at": fault.created_at,
                "lock_type": lock_type,
            })

        df = pd.DataFrame(faults_data)
        tech_assignments = run_scheduling_algorithm(df, num_technicians)

        assignments = []
        # Persist assignments back to the DB so the /technician filter reflects them.
        fault_by_id = {f.id: f for f in open_faults}
        for tech_name, schools in tech_assignments.items():
            tech_id = int(tech_name.split()[-1])
            total_score = sum(s["priority_score"] for s in schools)
            total_faults = sum(s["num_faults"] for s in schools)

            all_faults = []
            for school in schools:
                all_faults.extend(school["faults"])
                for f in school["faults"]:
                    fid = f.get("fault_id")
                    if fid in fault_by_id:
                        fault_by_id[fid].assigned_technician = tech_name

            assignments.append({
                "technician_id": tech_id,
                "schools": schools,
                "total_score": total_score,
                "total_faults": total_faults,
                "faults": all_faults,
            })

        session.commit()

        return jsonify({
            "success": True,
            "num_technicians": num_technicians,
            "assignments": assignments,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()


@app.route("/api/student_locker/<student_id>", methods=["GET"])
def get_student_locker(student_id):
    """Live lookup of the student's current locker from Adon Locker DB."""
    locker = adon_db.get_locker_by_student_id(str(student_id))
    return jsonify({"locker": locker})


@app.route("/api/locker/<locker_id>", methods=["GET"])
def get_locker(locker_id):
    """Live lookup of a locker by its ID from Adon Locker DB."""
    locker = adon_db.get_locker_by_id(str(locker_id))
    return jsonify({"locker": locker})


@app.route("/reports")
def reports_page():
    return render_template("reports.html")


@app.route("/technician")
def technician_page():
    return render_template("technician.html")


# ---------------------------------------------------------------------------
# Admin: allowed-emails management (restricted to ADMIN_EMAILS)
# ---------------------------------------------------------------------------

def _admin_guard():
    from auth import is_admin, current_user
    user = current_user() or {}
    if not is_admin(user.get("email")):
        return jsonify({"error": "Forbidden — admin only"}), 403
    return None


@app.route("/admin")
def admin_page():
    from auth import is_admin, current_user
    user = current_user() or {}
    if not is_admin(user.get("email")):
        return render_template_string(
            "<div style='font-family:sans-serif;direction:rtl;text-align:center;padding:60px;'>"
            "<h2>🚫 גישה לאדמין בלבד</h2>"
            "<p>המייל {{ email }} לא ברשימת המנהלים.</p>"
            "<a href='/'>חזרה למערכת</a></div>",
            email=user.get("email", "?"),
        ), 403
    return render_template("admin.html")


@app.route("/api/admin/emails", methods=["GET"])
def admin_list_emails():
    guard = _admin_guard()
    if guard:
        return guard
    from auth import _allowed_emails, admin_emails, current_user
    emails = sorted(_allowed_emails())
    admins = admin_emails()
    return jsonify({
        "emails": [{"email": e, "is_admin": e in admins} for e in emails],
        "current_user": (current_user() or {}).get("email"),
    })


@app.route("/api/admin/emails", methods=["POST"])
def admin_add_email():
    guard = _admin_guard()
    if guard:
        return guard
    from auth import _allowed_emails, write_allowed_emails
    data = request.get_json(silent=True) or {}
    new_email = (data.get("email") or "").strip().lower()
    if not new_email or "@" not in new_email:
        return jsonify({"error": "כתובת מייל לא תקינה"}), 400
    emails = _allowed_emails()
    if new_email in emails:
        return jsonify({"error": "המייל כבר ברשימה"}), 400
    emails.add(new_email)
    write_allowed_emails(emails)
    return jsonify({"success": True, "email": new_email})


@app.route("/api/admin/emails/<path:email>", methods=["DELETE"])
def admin_remove_email(email):
    guard = _admin_guard()
    if guard:
        return guard
    from auth import _allowed_emails, write_allowed_emails, admin_emails, current_user
    email = email.strip().lower()
    if email in admin_emails():
        return jsonify({"error": "אי אפשר למחוק חשבון מנהל מהממשק. ערוך ב-ADMIN_EMAILS אם צריך."}), 400
    if email == (current_user() or {}).get("email", "").lower():
        return jsonify({"error": "אי אפשר להסיר את עצמך"}), 400
    emails = _allowed_emails()
    if email not in emails:
        return jsonify({"error": "המייל לא ברשימה"}), 404
    emails.discard(email)
    write_allowed_emails(emails)
    return jsonify({"success": True})


@app.route("/api/reports/stats", methods=["GET"])
def reports_stats():
    """Aggregated stats for the dashboard. Optional ?school=<name> filter."""
    school_filter = (request.args.get("school") or "").strip()

    df = pd.read_sql("SELECT * FROM faults", our_engine)

    # Enrich with school via Adon Locker DB (cached)
    students = adon_db.get_all_students()
    id_to_school = {s["id"]: (s.get("school_name") or "") for s in students}
    if not df.empty:
        df["school_name"] = df["student_id_ext"].map(id_to_school).fillna("לא ידוע")

    all_schools = sorted({v for v in id_to_school.values() if v})

    if school_filter and not df.empty:
        df = df[df["school_name"] == school_filter]

    def value_counts(series, default_label="ללא"):
        if series.empty:
            return []
        return [
            {"label": (str(k) if k is not None and str(k).lower() != "nan" else default_label), "count": int(v)}
            for k, v in series.value_counts().items()
        ]

    total = len(df)
    open_count = int((df.get("status", pd.Series(dtype=object)) == "Open").sum()) if total else 0
    closed_count = int((df.get("status", pd.Series(dtype=object)) == "Closed").sum()) if total else 0
    urgent_open = 0
    if total and "is_urgent" in df.columns:
        urgent_open = int(((df["status"] == "Open") & (df["is_urgent"].astype(bool))).sum())

    by_type = value_counts(df["fault_type"]) if total else []
    by_severity = value_counts(df["severity"]) if total else []

    by_month = []
    if total and "created_at" in df.columns:
        ts = pd.to_datetime(df["created_at"], errors="coerce").dropna()
        if not ts.empty:
            counts = ts.dt.strftime("%Y-%m").value_counts().sort_index()
            by_month = [{"label": k, "count": int(v)} for k, v in counts.items()][-12:]

    # Only useful when looking at the org as a whole
    by_school = value_counts(df["school_name"], default_label="לא ידוע") if (total and not school_filter) else []

    by_technician = []
    if total:
        open_df = df[df["status"] == "Open"]
        if not open_df.empty:
            techs = open_df["assigned_technician"].fillna("לא הוקצה")
            by_technician = [{"label": str(k), "count": int(v)} for k, v in techs.value_counts().items()]

    return jsonify({
        "total": total,
        "open": open_count,
        "closed": closed_count,
        "urgent_open": urgent_open,
        "by_type": by_type,
        "by_severity": by_severity,
        "by_month": by_month,
        "by_school": by_school,
        "by_technician": by_technician,
        "available_schools": all_schools,
        "current_filter": school_filter,
    })


@app.route("/api/reports/export", methods=["GET"])
def reports_export():
    """Download all faults as an Excel file, enriched with student details."""
    import io
    from flask import send_file
    df = pd.read_sql("SELECT * FROM faults ORDER BY created_at DESC", our_engine)

    # Enrich with student name + readable ת.ז from Adon Locker DB
    students = adon_db.get_all_students()
    id_to_name = {
        s["id"]: f"{s.get('fname') or ''} {s.get('lname') or ''}".strip() or "לא ידוע"
        for s in students
    }
    id_to_tz = {s["id"]: s.get("studentId") or "" for s in students}
    id_to_school = {s["id"]: s.get("school_name") or "" for s in students}
    df["student_name"] = df["student_id_ext"].map(id_to_name).fillna("לא ידוע")
    df["student_tz"] = df["student_id_ext"].map(id_to_tz).fillna("")
    df["student_school"] = df["student_id_ext"].map(id_to_school).fillna("")
    df = df.drop(columns=["student_id_ext"])

    # Lock type — single SQL pulls every locker's closet type at once
    from sqlalchemy import text as _sql
    with adon_db.get_adon_engine().connect() as conn:
        lock_rows = conn.execute(_sql(
            'SELECT l.id, c.type FROM "Locker" l JOIN "Closet" c ON c.id = l."closetId"'
        )).fetchall()
    id_to_locktype = {
        r[0]: ("דיגיטלי" if r[1] == "Electronic" else "מכני" if r[1] == "Mechanical" else (r[1] or ""))
        for r in lock_rows
    }
    df["lock_type"] = df["locker_id"].map(id_to_locktype).fillna("")

    # Reorder so identifying info comes first
    front = ["id", "student_name", "student_tz", "student_school", "locker_id", "lock_type"]
    df = df[front + [c for c in df.columns if c not in front]]

    rename_map = {
        "id": "מספר תקלה", "student_name": "שם תלמיד",
        "student_tz": "ת.ז תלמיד", "student_school": "בית ספר",
        "locker_id": "מזהה לוקר", "lock_type": "סוג מנעול",
        "fault_type": "סוג תקלה", "severity": "חומרה", "books_stuck": "ספרים תקועים",
        "is_urgent": "דחוף", "status": "סטטוס", "description": "תיאור",
        "created_at": "נפתחה ב", "resolved_at": "נסגרה ב",
        "assigned_technician": "טכנאי", "is_recurring": "חוזרת",
        "technician_notes": "הערות טכנאי",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="תקלות", index=False)
    buf.seek(0)
    from datetime import datetime as _dt
    fname = f"faults-{_dt.now().strftime('%Y-%m-%d')}.xlsx"
    return send_file(
        buf, as_attachment=True, download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/health", methods=["GET"])
def health():
    """Liveness probe for Render."""
    return jsonify({"status": "ok"})


# ============================================================================
# DEV ENTRYPOINT
# In production gunicorn imports `app` directly — this block is only for
# local `python flask_app.py` runs.
# ============================================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, host="0.0.0.0", port=port)
