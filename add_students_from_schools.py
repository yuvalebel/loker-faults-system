"""
Add students from different schools to PostgreSQL database
This will give us variety for demo faults across regions
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
import random
import uuid

load_dotenv()

POSTGRES_URL = os.getenv('DATABASE_URL')
engine = create_engine(POSTGRES_URL, echo=False, pool_pre_ping=True)

# Hebrew first and last names for variety
FIRST_NAMES = [
    'יוסף', 'משה', 'אברהם', 'דוד', 'שלמה', 'אליהו', 'יצחק', 'יעקב',
    'שרה', 'רבקה', 'רחל', 'לאה', 'מרים', 'דבורה', 'אסתר', 'רות',
    'נועה', 'תמר', 'שירה', 'מיכל', 'דניאל', 'אריאל', 'עמר', 'רון'
]

LAST_NAMES = [
    'כהן', 'לוי', 'מזרחי', 'פרץ', 'ביטון', 'אוחיון', 'דהן', 'אזולאי',
    'יוסף', 'אברהם', 'יצחק', 'שלום', 'בן דוד', 'עמר', 'משה', 'דוד'
]

# Select schools from different regions (not the 3 we already have)
TARGET_SCHOOLS = [
    # Jerusalem - 3 schools
    ('בעברית תיכון אוניברסי', 'Jerusalem', 10),
    ('ישיבת שעלבים', 'Jerusalem', 8),
    ('מכון לב', 'Jerusalem', 8),
    
    # Center - 3 schools
    ('אמית ברוכין', 'Center', 10),
    ('צמרות', 'Center', 8),
    ('בר אילן', 'Center', 8),
    
    # North - 2 schools
    ('תיכון נשר', 'North', 10),
    ('כרמים', 'North', 8),
    
    # Lowland - 2 schools
    ('גולדה', 'Lowland', 8),
    ('רמון', 'Lowland', 8),
]

Session = sessionmaker(bind=engine)
session = Session()

try:
    print("🔄 Getting existing schools from database...")
    
    # First, get or create schools
    for school_name, region, num_students in TARGET_SCHOOLS:
        # Check if school exists
        result = session.execute(
            text("SELECT id FROM \"School\" WHERE name = :name"),
            {"name": school_name}
        )
        school_row = result.fetchone()
        
        if school_row:
            school_id = school_row[0]
            print(f"  ✅ School exists: {school_name} (ID: {school_id})")
        else:
            # Create school
            result = session.execute(
                text("INSERT INTO \"School\" (name) VALUES (:name) RETURNING id"),
                {"name": school_name}
            )
            school_id = result.fetchone()[0]
            session.commit()
            print(f"  ➕ Created school: {school_name} (ID: {school_id})")
        
        # Now add students to this school
        print(f"    Adding {num_students} students...")
        for i in range(num_students):
            student_uuid = str(uuid.uuid4())
            fname = random.choice(FIRST_NAMES)
            lname = random.choice(LAST_NAMES)
            student_id = f"{random.randint(100000000, 999999999)}"
            class_name = random.choice(['ט', 'י', 'יא', 'יב'])
            class_number = random.randint(1, 5)
            phone = f"05{random.randint(0, 9)}-{random.randint(1000000, 9999999)}"
            email = f"{fname.lower()}.{lname.lower()}@school.com"
            
            session.execute(
                text("""
                    INSERT INTO "Student" (
                        "id", "fname", "lname", "studentId", "class", "classNumber",
                        "parentPhone", "email", "schoolId"
                    ) VALUES (
                        :id, :fname, :lname, :studentId, :class, :classNumber,
                        :phone, :email, :schoolId
                    )
                """),
                {
                    "id": student_uuid,
                    "fname": fname,
                    "lname": lname,
                    "studentId": student_id,
                    "class": class_name,
                    "classNumber": class_number,
                    "phone": phone,
                    "email": email,
                    "schoolId": str(school_id)
                }
            )
        
        session.commit()
        print(f"    ✅ Added {num_students} students to {school_name}")
    
    print(f"\n✅ Successfully added students from {len(TARGET_SCHOOLS)} schools!")
    print("\n📊 Summary by region:")
    
    region_counts = {}
    for school_name, region, num_students in TARGET_SCHOOLS:
        if region not in region_counts:
            region_counts[region] = []
        region_counts[region].append((school_name, num_students))
    
    for region, schools in region_counts.items():
        total = sum(s[1] for s in schools)
        print(f"\n  {region}: {total} students")
        for school, count in schools:
            print(f"    - {school}: {count} students")
    
except Exception as e:
    print(f"❌ Error: {e}")
    session.rollback()
finally:
    session.close()

print("\n✅ Done! Students added to PostgreSQL database.")
