"""
Test student insertion directly
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import random

load_dotenv()

POSTGRES_URL = os.getenv('DATABASE_URL')
engine = create_engine(POSTGRES_URL, echo=True)

HEBREW_FIRST_NAMES = ['יוסף', 'דוד', 'משה', 'שרה', 'רחל']
HEBREW_LAST_NAMES = ['כהן', 'לוי', 'מזרחי']
CLASSES = ['ז', 'ח', 'ט']

# Get a school first
with engine.connect() as conn:
    result = conn.execute(text('SELECT id, name FROM "School" LIMIT 1'))
    school = result.fetchone()
    school_id = school[0]
    school_name = school[1]
    print(f"Using school: {school_name} (ID: {school_id}, type: {type(school_id)})")

# Try to insert one student
print("\nInserting test student...")
with engine.connect() as conn:
    trans = conn.begin()
    try:
        fname = random.choice(HEBREW_FIRST_NAMES)
        lname = random.choice(HEBREW_LAST_NAMES)
        student_id_num = "100000001"
        class_grade = random.choice(CLASSES)
        class_number = "1"
        phone = "050-1234567"
        email = f"{fname}.{lname}@test.com"
        
        print(f"Data: id='999999', fname='{fname}', schoolId='{school_id}' (type: {type(school_id)})")
        
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
                'id': '999999',
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
        
        trans.commit()
        print("✅ Test student inserted successfully!")
        
    except Exception as e:
        trans.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
