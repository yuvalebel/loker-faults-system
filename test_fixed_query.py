"""
Test the fixed student query
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    result = conn.execute(text('''
        SELECT DISTINCT
            s.id,
            s."fname",
            s."lname",
            s."studentId",
            s.class,
            s."classNumber",
            s."parentPhone",
            s.email,
            sc.name as school_name
        FROM "Student" s
        LEFT JOIN "School" sc ON s."schoolId" = CAST(sc.id AS TEXT)
        ORDER BY s."fname", s."lname"
        LIMIT 5
    '''))
    
    print("✅ Fixed student query results:")
    print("=" * 80)
    for row in result:
        # Simulate display_name
        display_name = f"{row[1]} {row[2]} | ת.ז: {row[3]} | {row[8] if row[8] else 'אין בית ספר'}"
        print(f"Display: {display_name}")
        print(f"Class: {row[4]}' {row[5]}")
        print("-" * 80)
