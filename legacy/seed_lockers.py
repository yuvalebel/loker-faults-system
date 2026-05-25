"""Seed the lockers table with dummy data based on the real schools & students."""
import random
import sqlite3
from datetime import datetime, timedelta

random.seed(42)  # reproducible

DB = 'faults_system.db'
ACADEMIC_YEAR = 'תשפ"ו'
STATUS_DISTRIBUTION = [('in_use', 0.60), ('available', 0.30), ('faulty', 0.10)]

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Clear any existing lockers (safe on re-run)
cur.execute('DELETE FROM lockers')

cur.execute('SELECT DISTINCT school_name FROM students WHERE school_name IS NOT NULL')
schools = sorted([r[0] for r in cur.fetchall()])

cur.execute("SELECT id FROM students")
student_ids = [r[0] for r in cur.fetchall()]
random.shuffle(student_ids)
student_pool = iter(student_ids)

FLOWER_NAMES = [
    'נרקיס', 'כלנית', 'רקפת', 'שושן', 'סביון', 'חבצלת',
    'חמנית', 'עירית', 'פעמונית', 'לבנדר', 'פרג', 'דליה',
]
CELL_NUMBERS = [
    101, 102, 103,
    201, 202, 203,
    301, 302, 303,
]  # 3 rows × 3 cols per cabinet = 9 cells

# Assign lock-type profile per school — most are single-type, 2 are mixed.
# 6 digital-only, 5 mechanical-only, 2 mixed (50/50).
random.shuffle(schools)
school_profiles = {}
profiles = (['digital'] * 6) + (['mechanical'] * 5) + (['mixed'] * 2)
profiles = profiles[:len(schools)]
for school, profile in zip(schools, profiles):
    school_profiles[school] = profile

rows = []
counter = 1
# Flowers assigned to schools so each school has its own set of flower-cabinets
flower_pool = list(FLOWER_NAMES)
random.shuffle(flower_pool)
flower_iter = iter(flower_pool)

for school in schools:
    profile = school_profiles[school]
    n_cabinets = random.randint(2, 3)
    school_cabinets = []
    for idx in range(n_cabinets):
        try:
            flower = next(flower_iter)
        except StopIteration:
            flower_iter = iter(random.sample(FLOWER_NAMES, len(FLOWER_NAMES)))
            flower = next(flower_iter)
        # Each school gets a single numbered cabinet per flower (e.g. "נרקיס 1")
        cabinet_name = f'{flower} 1'
        school_cabinets.append(cabinet_name)

    # Fill each cabinet with the 9 fixed cells
    cells = [(cab, cell) for cab in school_cabinets for cell in CELL_NUMBERS]

    for cabinet, cell in cells:
        locker_id = f'L-{counter:04d}'
        counter += 1
        cell_number = str(cell)

        # roll status
        r = random.random()
        cum = 0
        status = 'available'
        for s, p in STATUS_DISTRIBUTION:
            cum += p
            if r <= cum:
                status = s
                break

        # Lock type follows school profile (mixed → 50/50)
        if profile == 'digital':
            is_digital = True
        elif profile == 'mechanical':
            is_digital = False
        else:
            is_digital = random.random() < 0.5
        if is_digital:
            lock_type = 'digital'
            student_code = f'{random.randint(0, 999999):06d}'
            master_code = f'{random.randint(0, 999999):06d}'
            lock_number = None
        else:
            lock_type = 'mechanical'
            # Combination dial: 3 numbers in range 00–39, formatted XX-XX-XX
            parts = [f'{random.randint(0, 39):02d}' for _ in range(3)]
            student_code = '-'.join(parts)
            master_code = None
            # Lock serial: usually 8 digits, occasionally 6 or 7
            digits = random.choices([8, 7, 6], weights=[0.8, 0.1, 0.1])[0]
            low = 10 ** (digits - 1)
            high = (10 ** digits) - 1
            lock_number = str(random.randint(low, high))

        current_student_id = None
        assigned_at = None
        if status == 'in_use':
            try:
                current_student_id = next(student_pool)
                days_ago = random.randint(30, 200)
                assigned_at = (datetime.utcnow() - timedelta(days=days_ago)).isoformat()
            except StopIteration:
                status = 'available'

        notes = None
        if status == 'faulty':
            notes = random.choice([
                'דלת חורקת', 'מנעול תקוע', 'סימון שחור חסר',
                'ממתין לבדיקת טכנאי', 'סוללה חלשה'
            ])

        rows.append((
            locker_id, school, cabinet, cell_number, lock_type,
            student_code, master_code, lock_number,
            current_student_id, status, ACADEMIC_YEAR, assigned_at, notes
        ))

cur.executemany('''
    INSERT INTO lockers (
        locker_id, school_name, cabinet_name, cell_number, lock_type,
        student_code, master_code, lock_number,
        current_student_id, status, academic_year, assigned_at, notes
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', rows)
conn.commit()

cur.execute('SELECT COUNT(*), status FROM lockers GROUP BY status')
print('Seeded lockers by status:', cur.fetchall())
cur.execute('SELECT COUNT(*), lock_type FROM lockers GROUP BY lock_type')
print('Seeded lockers by lock_type:', cur.fetchall())
cur.execute('''
    SELECT school_name,
           SUM(CASE WHEN lock_type='digital' THEN 1 ELSE 0 END) AS digital,
           SUM(CASE WHEN lock_type='mechanical' THEN 1 ELSE 0 END) AS mechanical
    FROM lockers GROUP BY school_name ORDER BY school_name
''')
print('Per school (digital / mechanical):')
for school, d, m in cur.fetchall():
    profile = school_profiles.get(school, '?')
    print(f'  [{profile:10}] {school:30} {d}/{m}')

conn.close()
