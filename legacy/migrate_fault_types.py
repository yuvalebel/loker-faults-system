"""One-shot migration: rename legacy fault_type strings to the new vocabulary.

Run once after deploying the new FAULT_TYPES list in templates/index.html.

Old → New:
    תקלה במנעול          → מנעול התקלקל
    מפתח אבוד            → אין מנעול
    הקוד לא עובד         → הקודן לא עובד
    מסך לא מגיב          → אחר
    בעיה בסוללה          → אחר
    תקלה בלוח הקלדה      → אחר
    נעילת חירום          → אחר

Usage:
    python legacy/migrate_fault_types.py            # dry-run (shows what would change)
    python legacy/migrate_fault_types.py --apply    # actually writes
"""
import os
import sys
import sqlite3

# Force UTF-8 on stdout so Hebrew + arrow chars don't crash on cp1255 consoles (Windows).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

DB_PATH = os.environ.get("OUR_DATABASE_URL", "sqlite:///./data/faults_system.db")
if DB_PATH.startswith("sqlite:///"):
    DB_PATH = DB_PATH.replace("sqlite:///", "", 1)

RENAMES = {
    "תקלה במנעול": "מנעול התקלקל",
    "מפתח אבוד": "אין מנעול",
    "הקוד לא עובד": "הקודן לא עובד",
    "מסך לא מגיב": "אחר",
    "בעיה בסוללה": "אחר",
    "תקלה בלוח הקלדה": "אחר",
    "נעילת חירום": "אחר",
}


def main():
    apply = "--apply" in sys.argv
    if not os.path.exists(DB_PATH):
        print(f"DB not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    total = 0
    for old, new in RENAMES.items():
        cur.execute("SELECT COUNT(*) FROM faults WHERE fault_type = ?", (old,))
        n = cur.fetchone()[0]
        if n == 0:
            continue
        total += n
        action = "WILL UPDATE" if not apply else "UPDATING"
        print(f"  {action} {n:>4} rows: {old!r}  →  {new!r}")
        if apply:
            cur.execute("UPDATE faults SET fault_type = ? WHERE fault_type = ?", (new, old))

    if apply:
        conn.commit()
        print(f"\nDone. {total} rows updated.")
    else:
        print(f"\nDry-run: {total} rows would be updated. Re-run with --apply to commit.")

    conn.close()


if __name__ == "__main__":
    main()
