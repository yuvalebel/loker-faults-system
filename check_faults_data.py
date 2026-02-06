"""
Check if there are any faults and test the join
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# SQLite - check faults
sqlite_engine = create_engine('sqlite:///faults_system.db')
postgres_engine = create_engine(os.getenv('DATABASE_URL'))

print("=" * 80)
print("CHECKING FAULTS DATA")
print("=" * 80)

with sqlite_engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM faults'))
    count = result.scalar()
    print(f"\n✓ Total faults in SQLite: {count}")
    
    if count > 0:
        result = conn.execute(text('SELECT id, student_id_ext, fault_type, status FROM faults LIMIT 5'))
        print("\nSample faults:")
        for row in result:
            print(f"  ID: {row[0]}, Student: {row[1]}, Type: {row[2]}, Status: {row[3]}")
        
        # Get student IDs from faults
        result = conn.execute(text('SELECT DISTINCT student_id_ext FROM faults'))
        student_ids = [row[0] for row in result]
        print(f"\n✓ Unique student IDs in faults: {student_ids[:5]}")
        
        # Now check if these students exist in PostgreSQL
        if student_ids:
            student_ids_str = "','".join(map(str, student_ids[:5]))
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
            
            with postgres_engine.connect() as pg_conn:
                result = pg_conn.execute(text(query))
                print("\n✓ Student info from PostgreSQL:")
                for row in result:
                    print(f"  ID: {row[0]}, Name: {row[1]}, StudentID: {row[2]}, School: {row[3]}")
