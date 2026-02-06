"""
Check seeding status
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL = os.getenv('DATABASE_URL')
engine = create_engine(POSTGRES_URL)

with engine.connect() as conn:
    # Check schools
    result = conn.execute(text('SELECT COUNT(*) FROM "School"'))
    school_count = result.fetchone()[0]
    print(f"Schools: {school_count}")
    
    if school_count > 0:
        result = conn.execute(text('SELECT name FROM "School" LIMIT 10'))
        print("\nSample schools:")
        for row in result:
            print(f"  - {row[0]}")
    
    # Check students
    result = conn.execute(text('SELECT COUNT(*) FROM "Student"'))
    student_count = result.fetchone()[0]
    print(f"\nStudents: {student_count}")
