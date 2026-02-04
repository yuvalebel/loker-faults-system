from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('DATABASE_URL')

engine = create_engine(url)
conn = engine.connect()

# Check tables
result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
tables = [row[0] for row in result]

print("=" * 50)
print("DATABASE CONNECTION TEST")
print("=" * 50)
print(f"✓ Connected to: {url[:60]}...")
print(f"\nTables found: {len(tables)}")
for table in tables:
    print(f"  - {table}")

# Check if students table exists
if 'Student' in tables:
    result = conn.execute(text('SELECT COUNT(*) FROM "Student"'))
    count = result.fetchone()[0]
    print(f"\n✓ Student table has {count} records")
    
    # Show sample
    result = conn.execute(text('SELECT fname, lname, "studentId" FROM "Student" LIMIT 3'))
    print("\nSample students:")
    for row in result:
        print(f"  - {row[0]} {row[1]} (ID: {row[2]})")
else:
    print("\n✗ Student table NOT found!")

conn.close()
