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
from flask import Flask, jsonify, render_template, request
from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import db as adon_db
from auth import init_auth

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
    "תקלה במנעול": 5,
    "הקוד לא עובד": 4,
    "נזק לדלת": 3,
    "מפתח אבוד": 2,
    "אחר": 1,
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


@app.route("/api/update_status", methods=["POST"])
def update_status():
    data = request.get_json()
    session = OurSession()
    try:
        fault = session.query(Fault).filter(Fault.id == data["fault_id"]).first()
        if not fault:
            return jsonify({"success": False, "error": "Fault not found"}), 404

        new_status = data["status"]
        fault.status = new_status

        if new_status == "Closed" and not fault.resolved_at:
            fault.resolved_at = datetime.utcnow()
        elif new_status == "Open":
            fault.resolved_at = None

        if "technician" in data:
            fault.assigned_technician = data["technician"]

        session.commit()
        return jsonify({"success": True, "message": "סטטוס עודכן בהצלחה"})
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
        return jsonify({
            "success": True,
            "message": "התקלה עודכנה בהצלחה",
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


# ============================================================================
# SCHEDULING ALGORITHM (unchanged business logic)
# ============================================================================

def run_scheduling_algorithm(faults_df, num_technicians):
    """
    3-Stage Scheduling Algorithm (Strict Region Exhaustion).
    Phase 1: anchor seeding by top priority schools.
    Phase 2: each tech absorbs all unassigned schools in their primary region.
    Phase 3: any leftovers go to the most idle tech globally.
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
        "region": "first",
    }).reset_index()

    school_metrics.columns = [
        "school_name", "fault_count", "avg_severity", "max_age_days",
        "has_recurring", "has_urgent", "region",
    ]

    school_metrics["N"] = school_metrics["fault_count"].apply(lambda x: min(x, 5))
    school_metrics["U"] = school_metrics["avg_severity"]
    school_metrics["T"] = school_metrics["max_age_days"].apply(lambda x: min(max(x, 1), 5))
    school_metrics["R"] = school_metrics["has_recurring"].apply(lambda x: 5 if x else 1)

    school_metrics["priority_score"] = (
        0.35 * school_metrics["N"]
        + 0.25 * school_metrics["U"]
        + 0.25 * school_metrics["T"]
        + 0.15 * school_metrics["R"]
    )
    school_metrics.loc[school_metrics["has_urgent"] == True, "priority_score"] = 10000

    school_metrics = school_metrics.sort_values("priority_score", ascending=False).reset_index(drop=True)
    school_metrics["assigned"] = False

    assignments = {}
    technician_workload = {}
    tech_primary_region = {}

    for i in range(1, num_technicians + 1):
        tech_name = f"Technician {i}"
        assignments[tech_name] = []
        technician_workload[tech_name] = 0
        tech_primary_region[tech_name] = None

    total_faults = len(faults_df)
    workload_cap = (total_faults / num_technicians) * 1.5

    # Phase 1: Anchor seeding
    num_anchors = min(num_technicians, len(school_metrics))
    for i in range(num_anchors):
        school = school_metrics.iloc[i]
        tech_name = f"Technician {i + 1}"
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
            })

        df = pd.DataFrame(faults_data)
        tech_assignments = run_scheduling_algorithm(df, num_technicians)

        assignments = []
        for tech_name, schools in tech_assignments.items():
            tech_id = int(tech_name.split()[-1])
            total_score = sum(s["priority_score"] for s in schools)
            total_faults = sum(s["num_faults"] for s in schools)

            all_faults = []
            for school in schools:
                all_faults.extend(school["faults"])

            assignments.append({
                "technician_id": tech_id,
                "schools": schools,
                "total_score": total_score,
                "total_faults": total_faults,
                "faults": all_faults,
            })

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
