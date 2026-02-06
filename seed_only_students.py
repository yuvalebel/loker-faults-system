"""
Seed only students (schools already exist)
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import random

load_dotenv()

POSTGRES_URL = os.getenv('DATABASE_URL')
engine = create_engine(POSTGRES_URL, echo=False)

HEBREW_FIRST_NAMES = [
    'יוסף', 'דוד', 'משה', 'אברהם', 'שרה', 'רבקה', 'רחל', 'לאה',
    'דניאל', 'מיכאל', 'נועה', 'תמר', 'אור', 'עדי', 'שירה', 'יעל',
    'אליה', 'אריאל', 'נועם', 'רוני', 'מאיר', 'חנה', 'דינה', 'מרים'
]

HEBREW_LAST_NAMES = [
    'כהן', 'לוי', 'מזרחי', 'ביטון', 'פרץ', 'שלום', 'אברהם', 'דוד',
    'יוסף', 'חיים', 'משה', 'בן דוד', 'אזולאי', 'עמר', 'חדד', 'ניסים'
]

def seed_students(students_per_school=20):
    """Generate students for existing schools"""
    
    # Get existing schools
    with engine.connect() as conn:
        result = conn.execute(text('SELECT id, name FROM "School" ORDER BY id'))
        schools = [(row[0], row[1]) for row in result]
    
    print(f"Found {len(schools)} schools")
    print(f"Generating {students_per_school} students per school ({len(schools) * students_per_school} total)...")
    
    CLASSES = ['ז', 'ח', 'ט', 'י', 'יא', 'יב']
    
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            student_counter = 1
            school_counter = 0
            
            for school_id, school_name in schools:
                school_counter += 1
                print(f"  [{school_counter}/{len(schools)}] {school_name[:30]}")
                
                for _ in range(students_per_school):
                    fname = random.choice(HEBREW_FIRST_NAMES)
                    lname = random.choice(HEBREW_LAST_NAMES)
                    student_id_num = str(100000000 + student_counter).zfill(9)
                    class_grade = random.choice(CLASSES)
                    class_number = str(random.randint(1, 6))
                    phone = f"05{random.randint(0, 9)}-{random.randint(1000000, 9999999)}"
                    email = f"{fname.lower()}.{lname.lower()}@student.example.com"
                    
                    conn.execute(
                        text('''
                            INSERT INTO "Student" 
                            (id, fname, lname, "studentId", class, "classNumber", 
                             "parentPhone", email, "schoolId", "createdAt", "updatedAt") 
                            VALUES 
                            (:id, :fname, :lname, :studentId, :class, :classNumber,
                             :phone, :email, :schoolId, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        '''),
                        {
                            'id': str(student_counter),
                            'fname': fname,
                            'lname': lname,
                            'studentId': student_id_num,
                            'class': class_grade,
                            'classNumber': class_number,
                            'phone': phone,
                            'email': email,
                            'schoolId': str(school_id)
                        }
                    )
                    
                    student_counter += 1
            
            trans.commit()
            print(f"\n✅ Successfully generated {student_counter - 1} students!")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    seed_students(students_per_school=20)
