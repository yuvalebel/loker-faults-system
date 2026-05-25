"""
Add demo faults from various schools and regions
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
from datetime import datetime, timedelta
import random
from dotenv import load_dotenv
import os

load_dotenv()

# Database connections
POSTGRES_URL = os.getenv('DATABASE_URL', 'postgresql://team41:xBjwE7X6BjQjARSGTFcWOg7TJ0ZiQbyq@dpg-d615mm24d50c73eh9o0g-a.oregon-postgres.render.com/studentlocker')
SQLITE_URL = 'sqlite:///faults_system.db'

postgres_engine = create_engine(POSTGRES_URL, echo=False, pool_pre_ping=True)
sqlite_engine = create_engine(SQLITE_URL, echo=False)

# School to region mapping (using REAL mapping from flask_app.py)
SCHOOL_MAPPING = {
    'שש שנתי אשל הנשיא': 'South', 'חטיבת הביניים סוסיא': 'South', 'טכני חיל האוויר': 'South',
    'אמית ברוכין': 'Center', 'אולפנת קרני שומרון': 'Center', 'להבה': 'Center',
    'בעברית תיכון אוניברסי': 'Jerusalem', 'אמי״ת בנים מודיעין': 'Jerusalem', 'תבל רמות': 'Jerusalem',
    'ישיבת שעלבים': 'Jerusalem', 'ענבר': 'Jerusalem', 'נשמת התורה': 'Jerusalem',
    'מכון לב': 'Jerusalem', 'אמי"ת מעלה אדומים': 'Jerusalem', 'אולפנת שעלבים': 'Jerusalem',
    'אורט תעשייה אווירית': 'Center', 'לאורו נלך': 'Center', 'מיכה רייסר': 'Center',
    'צמרות': 'Center', 'אולפנת צביה לוד': 'Center', 'מקיף י׳ אלברט איינשטיי': 'Center',
    'אולפנת יבנה': 'Center', 'אמירים (מקיף ה)': 'Center', "מקיף ז' רביבים": 'Center',
    'אמי"ת בנות מודיעין': 'Center', 'נתיבות רבקה': 'Center', 'סמינר שושנים': 'Center',
    'קינג סולומון הכפר הירו': 'Center', 'פלך': 'Center', 'בר אילן': 'Center',
    'שובו': 'Center', 'בית ספר יצחק שמיר': 'Center', 'מאיר שלו': 'Center',
    'אולפנת רמלה': 'Center', 'קריית חינוך חטיבה': 'North', 'אלדד נתניה': 'North',
    'אולפנית מירון': 'North', 'תיכון נשר': 'North', 'אולפנית אמונה אלישבע': 'North',
    'כרמים': 'North', 'אולפנת סגולה': 'North', 'אסיף': 'North', 'שבילים': 'North',
    'חטיבת יונתן': 'Lowland', 'גולדה': 'Lowland', 'אולפנית ישורון': 'Lowland', 'רמון': 'Lowland'
}

SEVERITY_MAP = {
    "תקלה במנעול": 5,
    "הקוד לא עובד": 4,
    "נזק לדלת": 3,
    "מפתח אבוד": 2,
    "אחר": 1
}

# Load students from PostgreSQL
print("🔄 Loading students from PostgreSQL...")
query = """
    SELECT DISTINCT
        s.id,
        s."fname",
        s."lname",
        s."studentId",
        sc.name as school_name
    FROM "Student" s
    LEFT JOIN "School" sc ON s."schoolId" = CAST(sc.id AS TEXT)
    ORDER BY sc.name, s."fname"
"""

with postgres_engine.connect() as conn:
    students_df = pd.read_sql(query, conn)

print(f"✅ Loaded {len(students_df)} students")
print(f"\n📊 Schools in database:")
school_counts = students_df['school_name'].value_counts()
for school, count in school_counts.items():
    region = SCHOOL_MAPPING.get(school, 'Unknown')
    print(f"  - {school} ({region}): {count} students")

# Select students from various schools across ALL regions
# Will auto-select from available schools in database
print("\n🔍 Finding schools with students...")

available_schools = students_df['school_name'].dropna().unique()
print(f"Found {len(available_schools)} schools with students:")
for school in available_schools:
    count = len(students_df[students_df['school_name'] == school])
    region = SCHOOL_MAPPING.get(school, 'Unknown')
    print(f"  - {school} ({region}): {count} students")

# Select diverse schools from different regions
target_schools = []
regions_covered = set()

for school in available_schools:
    region = SCHOOL_MAPPING.get(school, 'Unknown')
    student_count = len(students_df[students_df['school_name'] == school])
    
    # Skip if we already have this region and have enough schools
    if region in regions_covered and len([s for s in target_schools if s[1] == region]) >= 2:
        continue
    
    # Add 3-6 faults per school
    num_faults = min(random.randint(3, 6), student_count)
    target_schools.append((school, region, num_faults))
    regions_covered.add(region)
    
    # Stop after 10 schools for variety
    if len(target_schools) >= 10:
        break

print(f"\n✅ Selected {len(target_schools)} schools for demo faults")


demo_faults = []

print(f"\n🔧 Creating demo faults...")

for school_name, region, num_faults in target_schools:
    # Get students from this school
    school_students = students_df[students_df['school_name'] == school_name]
    
    if school_students.empty:
        print(f"  ⚠️  No students found for {school_name}, skipping...")
        continue
    
    print(f"\n  📍 {school_name} ({region}) - creating {num_faults} faults")
    
    # Select random students (may repeat for recurring faults)
    selected_students = school_students.sample(min(num_faults, len(school_students)), replace=False)
    
    for idx, student in selected_students.iterrows():
        # Random fault type
        fault_type = random.choice(list(SEVERITY_MAP.keys()))
        severity = SEVERITY_MAP[fault_type]
        
        # Random chance for books stuck (20%)
        books_stuck = random.random() < 0.2
        is_urgent = books_stuck
        
        # Random age (0-7 days ago)
        days_ago = random.randint(0, 7)
        created_at = datetime.utcnow() - timedelta(days=days_ago)
        
        # Random locker ID
        locker_id = f"L-{random.randint(100, 999)}"
        
        # Some description variety
        descriptions = [
            "תקלה דווחה על ידי התלמיד",
            "הבעיה חוזרת על עצמה",
            "דורש טיפול מיידי",
            "נמצא בבדיקה",
            None
        ]
        description = random.choice(descriptions)
        
        demo_faults.append({
            'student_id_ext': student['id'],
            'student_name': f"{student['fname']} {student['lname']}",
            'school_name': school_name,
            'locker_id': locker_id,
            'fault_type': fault_type,
            'severity': severity,
            'books_stuck': books_stuck,
            'is_urgent': is_urgent,
            'is_recurring': False,  # Will be auto-detected by system
            'status': 'Open',
            'description': description,
            'created_at': created_at
        })
        
        flag = "📚" if books_stuck else "  "
        print(f"    {flag} {student['fname']} {student['lname']}: {fault_type} (חומרה {severity})")

print(f"\n💾 Inserting {len(demo_faults)} faults into SQLite...")

# Insert into SQLite
Session = sessionmaker(bind=sqlite_engine)
session = Session()

try:
    for fault in demo_faults:
        insert_query = text("""
            INSERT INTO faults (
                student_id_ext, locker_id, fault_type, severity,
                books_stuck, is_urgent, is_recurring, status,
                description, created_at
            ) VALUES (
                :student_id_ext, :locker_id, :fault_type, :severity,
                :books_stuck, :is_urgent, :is_recurring, :status,
                :description, :created_at
            )
        """)
        
        session.execute(insert_query, {
            'student_id_ext': fault['student_id_ext'],
            'locker_id': fault['locker_id'],
            'fault_type': fault['fault_type'],
            'severity': fault['severity'],
            'books_stuck': fault['books_stuck'],
            'is_urgent': fault['is_urgent'],
            'is_recurring': fault['is_recurring'],
            'status': fault['status'],
            'description': fault['description'],
            'created_at': fault['created_at']
        })
    
    session.commit()
    print(f"✅ Successfully added {len(demo_faults)} demo faults!")
    
    # Show summary
    print("\n📊 Summary by school:")
    for school_name, region, num_faults in target_schools:
        school_faults = [f for f in demo_faults if f['school_name'] == school_name]
        urgent_count = sum(1 for f in school_faults if f['books_stuck'])
        print(f"  - {school_name} ({region}): {len(school_faults)} faults ({urgent_count} עם ספרים נעולים)")
    
except Exception as e:
    print(f"❌ Error: {e}")
    session.rollback()
finally:
    session.close()

print("\n✅ Done! Run the Flask app and check the 'Manage Faults' tab")
