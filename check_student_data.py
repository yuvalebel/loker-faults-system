"""
Check sample student data
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT 
            s.id,
            s.fname,
            s.lname,
            s."studentId",
            s.class,
            s."classNumber",
            sc.name as school_name
        FROM "Student" s
        LEFT JOIN "School" sc ON s."schoolId" = CAST(sc.id AS TEXT)
        LIMIT 5
    '''))
    
    print("Sample student data:")
    print("=" * 80)
    for row in result:
        print(f"ID: {row[0]}")
        print(f"Name: {row[1]} {row[2]}")
        print(f"StudentID: {row[3]}")
        print(f"Class: {row[4]}'{row[5]}")
        print(f"School: {row[6]}")
        print("-" * 80)
