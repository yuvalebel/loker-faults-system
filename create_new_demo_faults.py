"""
Clear old faults and create new demo faults with current students
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import random
from datetime import datetime, timedelta

load_dotenv()

# Engines
sqlite_engine = create_engine('sqlite:///faults_system.db')
postgres_engine = create_engine(os.getenv('DATABASE_URL'))

print("=" * 80)
print("CREATING NEW DEMO FAULTS")
print("=" * 80)

# Step 1: Clear old faults
print("\n🗑️  Clearing old faults...")
with sqlite_engine.connect() as conn:
    trans = conn.begin()
    conn.execute(text('DELETE FROM faults'))
    trans.commit()
print("✅ Old faults cleared")

# Step 2: Get current students
print("\n📚 Getting current students from PostgreSQL...")
with postgres_engine.connect() as conn:
    result = conn.execute(text('''
        SELECT id, fname, lname, "studentId", class, "classNumber"
        FROM "Student"
        LIMIT 50
    '''))
    students = list(result)

if not students:
    print("❌ No students found! Run seed_batch.py first.")
    exit(1)

print(f"✅ Found {len(students)} students")

# Step 3: Create demo faults
print("\n🔧 Creating demo faults...")

fault_types = [
    "תקלה במנעול",
    "נזק לדלת", 
    "הקוד לא עובד",
    "ספרים תקועים",
    "מפתח אבוד",
    "אחר"
]

descriptions = [
    "המנעול לא נפתח אחרי הזנת הקוד הנכון",
    "הדלת לא נסגרת עד הסוף",
    "הקוד שקיבלתי לא עובד בכלל",
    "הספרים שלי תקועים בפנים ואני צריך אותם לשיעור",
    "איבדתי את המפתח של הלוקר",
    "ידית הדלת שבורה",
    "יש חריץ בדלת",
    "המנעול תקוע ולא זז",
    "הלוקר לא נועל כמו שצריך"
]

severity_map = {
    "תקלה במנעול": 5,
    "ספרים תקועים": 4,
    "הקוד לא עובד": 4,
    "נזק לדלת": 3,
    "מפתח אבוד": 2,
    "אחר": 1
}

statuses = ['Open', 'InProgress', 'Resolved', 'Closed']
technicians = ['דני', 'יוסי', 'משה', 'אבי', 'רון']

num_faults = min(20, len(students))

with sqlite_engine.connect() as conn:
    trans = conn.begin()
    
    for i in range(num_faults):
        student = random.choice(students)
        fault_type = random.choice(fault_types)
        severity = severity_map[fault_type]
        books_stuck = random.random() < 0.2
        is_urgent = random.random() < 0.3
        status = random.choices(statuses, weights=[40, 30, 20, 10])[0]
        description = random.choice(descriptions)
        
        days_ago = random.randint(0, 30)
        created_at = datetime.now() - timedelta(days=days_ago)
        
        resolved_at = None
        if status in ['Resolved', 'Closed']:
            resolved_days = random.randint(1, days_ago) if days_ago > 0 else 0
            resolved_at = created_at + timedelta(days=resolved_days)
        
        technician = None
        if status in ['InProgress', 'Resolved', 'Closed']:
            technician = random.choice(technicians)
        
        conn.execute(text('''
            INSERT INTO faults 
            (student_id_ext, fault_type, severity, books_stuck, is_urgent, 
             status, description, created_at, resolved_at, assigned_technician)
            VALUES 
            (:student_id, :fault_type, :severity, :books_stuck, :is_urgent,
             :status, :description, :created_at, :resolved_at, :technician)
        '''), {
            'student_id': student[0],  # student.id
            'fault_type': fault_type,
            'severity': severity,
            'books_stuck': books_stuck,
            'is_urgent': is_urgent,
            'status': status,
            'description': description,
            'created_at': created_at,
            'resolved_at': resolved_at,
            'technician': technician
        })
    
    trans.commit()

print(f"✅ Created {num_faults} demo faults")

# Summary
with sqlite_engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*), status FROM faults GROUP BY status"))
    print("\n📊 Summary by status:")
    for row in result:
        print(f"  {row[1]}: {row[0]}")

print("\n✅ Done! Refresh your Streamlit app to see the faults.")
print("=" * 80)
