"""
Database access layer.

Two separate engines:
  * OUR_DB             — our own Postgres (Render). Read+write. Holds `faults`.
  * ADON_LOCKER_DB     — Netanel's Supabase Postgres. READ-ONLY.
                          Holds students, lockers, schools, closets, complexes, locks.

Reads from ADON_LOCKER_DB use raw SQL to map the production schema (see
docs/schema_mapping.md) into the dict shape the frontend already expects.

A short-TTL cache wraps the read queries to bound load on Netanel's DB.
"""

import os
from datetime import datetime, timedelta
from threading import Lock as ThreadLock
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

_our_engine: Optional[Engine] = None
_adon_engine: Optional[Engine] = None


def get_our_engine() -> Engine:
    """Engine for our own Postgres (Render). Holds the `faults` table."""
    global _our_engine
    if _our_engine is None:
        url = os.environ["OUR_DATABASE_URL"]
        # Render exposes Postgres URLs starting with `postgres://`; SQLAlchemy
        # 2.x requires `postgresql://`.
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        _our_engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    return _our_engine


def get_adon_engine() -> Engine:
    """Engine for Netanel's Supabase. READ-ONLY by convention."""
    global _adon_engine
    if _adon_engine is None:
        url = os.environ["ADON_LOCKER_DATABASE_URL"]
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        _adon_engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=300,
            # Defence in depth: even if a misuse tries to write, fail fast.
            execution_options={"postgresql_readonly": True},
        )
    return _adon_engine


# ---------------------------------------------------------------------------
# TTL cache (60s) — replaces the old startup-only RAM load
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = int(os.environ.get("ADON_CACHE_TTL_SECONDS", "60"))
_cache: dict = {}
_cache_lock = ThreadLock()


def _cache_get(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if datetime.utcnow() > expires_at:
            _cache.pop(key, None)
            return None
        return value


def _cache_set(key: str, value):
    with _cache_lock:
        _cache[key] = (value, datetime.utcnow() + timedelta(seconds=_CACHE_TTL_SECONDS))


def invalidate_cache():
    """Clear the in-memory cache (useful for tests or admin actions)."""
    with _cache_lock:
        _cache.clear()


# ---------------------------------------------------------------------------
# Read queries against ADON_LOCKER_DB (production schema)
#
# Output shapes match what flask_app.py / templates/index.html expect.
# See docs/schema_mapping.md for column-level mapping.
# ---------------------------------------------------------------------------

_STUDENTS_SQL = text("""
    SELECT
        s.id,
        s.fname,
        s.lname,
        s."studentId"          AS "studentId",
        s.class                AS class,
        s."classNumber"        AS "classNumber",
        s."parentPhone"        AS "parentPhone",
        s.email,
        sch.name               AS school_name
    FROM "Student" s
    LEFT JOIN "School" sch ON sch.id = s."schoolId"
    ORDER BY s.fname, s.lname
""")

_LOCKER_BASE_SQL = """
    SELECT
        l.id                        AS locker_id,
        sch.name                    AS school_name,
        c.name                      AS cabinet_name,
        l."lockerNumber"::text      AS cell_number,
        CASE c.type
            WHEN 'Electronic' THEN 'digital'
            WHEN 'Mechanical' THEN 'mechanical'
        END                         AS lock_type,
        l."userCode"                AS student_code,
        l."masterCode"              AS master_code,
        lk."lockNumber"             AS lock_number,
        l."studentId"               AS current_student_id,
        CASE
            WHEN l.status = 'Faulty'           THEN 'faulty'
            WHEN l."orderStatus" = 'Busy'      THEN 'in_use'
            ELSE 'available'
        END                         AS status,
        l.notes                     AS notes
    FROM "Locker" l
    JOIN "School" sch ON sch.id = l."schoolId"
    JOIN "Closet" c   ON c.id   = l."closetId"
    LEFT JOIN "Lock" lk ON lk.id = l."lockId"
"""

_LOCKER_BY_ID_SQL = text(_LOCKER_BASE_SQL + ' WHERE l.id = :locker_id LIMIT 1')

# Returns the first locker assigned to a student. In rare cases a student may
# have more than one locker (`Student.locker` is an array in the schema); we
# pick the most recently updated one.
_LOCKER_BY_STUDENT_SQL = text(
    _LOCKER_BASE_SQL
    + ' WHERE l."studentId" = :student_id ORDER BY l."updatedAt" DESC LIMIT 1'
)


def _row_to_dict(row) -> dict:
    return dict(row._mapping)


def get_all_students() -> list[dict]:
    """All students, fetched live from Adon Locker DB. Cached for TTL seconds."""
    cached = _cache_get("students")
    if cached is not None:
        return cached

    with get_adon_engine().connect() as conn:
        rows = conn.execute(_STUDENTS_SQL).fetchall()
    students = [_row_to_dict(r) for r in rows]
    _cache_set("students", students)
    return students


def get_locker_by_id(locker_id: str) -> Optional[dict]:
    """Single locker by its cuid. None if not found."""
    if not locker_id:
        return None
    cache_key = f"locker_id:{locker_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached or None  # cache stores {} for misses to avoid re-querying

    with get_adon_engine().connect() as conn:
        row = conn.execute(_LOCKER_BY_ID_SQL, {"locker_id": locker_id}).fetchone()
    locker = _row_to_dict(row) if row else None
    _cache_set(cache_key, locker if locker is not None else {})
    return locker


def get_locker_by_student_id(student_id: str) -> Optional[dict]:
    """Most recently updated locker assigned to the given student. None if not found."""
    if not student_id:
        return None
    cache_key = f"locker_student:{student_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached or None

    with get_adon_engine().connect() as conn:
        row = conn.execute(
            _LOCKER_BY_STUDENT_SQL, {"student_id": student_id}
        ).fetchone()
    locker = _row_to_dict(row) if row else None
    _cache_set(cache_key, locker if locker is not None else {})
    return locker


def get_student_by_id(student_id: str) -> Optional[dict]:
    """Quick lookup of a single student from the cached students list."""
    if not student_id:
        return None
    for s in get_all_students():
        if s["id"] == student_id:
            return s
    return None


# ---------------------------------------------------------------------------
# School regions — names come live from Adon Locker DB, region overrides
# are stored locally in school_regions.json (editable by humans).
# ---------------------------------------------------------------------------

import json
from pathlib import Path

_SCHOOL_REGIONS_FILE = Path(__file__).parent / "school_regions.json"


def _load_region_overrides() -> dict[str, str]:
    """Read the local JSON file mapping school_name -> region. Empty if missing."""
    if not _SCHOOL_REGIONS_FILE.exists():
        return {}
    try:
        return json.loads(_SCHOOL_REGIONS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_school_regions() -> dict[str, str]:
    """
    Live map of {school_name: region}.

    School names are pulled from Netanel's DB (so any school he adds shows
    up automatically). Regions come from school_regions.json, which we
    maintain. Schools we haven't classified return 'Unknown'.
    """
    cached = _cache_get("school_regions")
    if cached is not None:
        return cached

    overrides = _load_region_overrides()
    with get_adon_engine().connect() as conn:
        names = [r[0] for r in conn.execute(text('SELECT name FROM "School" ORDER BY name')).fetchall()]

    result = {name: overrides.get(name, "Unknown") for name in names}
    _cache_set("school_regions", result)
    return result


def get_region_for_school(school_name: Optional[str]) -> str:
    """Convenience: region for a single school name, 'Unknown' if not found."""
    if not school_name:
        return "Unknown"
    return get_school_regions().get(school_name, "Unknown")
