"""
Test the fixed faults query
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import pandas as pd

load_dotenv()
postgres_url = os.getenv('DATABASE_URL')
postgres_engine = create_engine(postgres_url)

# Simulate getting student IDs (using some we know exist)
student_ids_str = "40','41','42"

query = f"""
    SELECT 
        s.id,
        s.fname || ' ' || s.lname as student_name,
        s."studentId",
        sc.name as school_name
    FROM "Student" s
    LEFT JOIN "School" sc ON s."schoolId" = CAST(sc.id AS TEXT)
    WHERE s.id IN ('{student_ids_str}')
"""

with postgres_engine.connect() as conn:
    df = pd.read_sql(query, conn)

print("✅ Fixed faults query results:")
print("=" * 100)
print(df.to_string(index=False))
print("\n" + "=" * 100)
print("\nFormatted for display:")
for _, row in df.iterrows():
    print(f"שם: {row['student_name']:<20} | ת.ז: {row['studentId']:<15} | בית ספר: {row['school_name']}")
