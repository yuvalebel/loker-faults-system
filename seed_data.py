"""
Seed Students Data - Smart Scheduling Algorithm
================================================
This script generates student data for specific schools only.
The students table will have school_name but NOT a Region column.
Region mapping is handled in the app logic layer.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import random

# Load environment variables
load_dotenv()

# PostgreSQL Connection
POSTGRES_URL = os.getenv('DATABASE_URL', 'postgresql://team41:xBjwE7X6BjQjARSGTFcWOg7TJ0ZiQbyq@dpg-d615mm24d50c73eh9o0g-a.oregon-postgres.render.com/studentlocker')
engine = create_engine(POSTGRES_URL, echo=False)

# ============================================================================
# TARGET SCHOOLS - Only these schools will have students
# ============================================================================

target_schools = [
    'שש שנתי אשל הנשיא', 'חטיבת הביניים סוסיא', 'טכני חיל האוויר', 'אמית ברוכין',
    'אולפנת קרני שומרון', 'להבה', 'בעברית תיכון אוניברסי', 'אמי״ת בנים מודיעין',
    'תבל רמות', 'ישיבת שעלבים', 'ענבר', 'נשמת התורה', 'מכון לב',
    'אמי"ת מעלה אדומים', 'אולפנת שעלבים', 'אורט תעשייה אווירית', 'לאורו נלך',
    'מיכה רייסר', 'צמרות', 'אולפנת צביה לוד', 'מקיף י׳ אלברט איינשטיי',
    'אולפנת יבנה', 'אמירים (מקיף ה)', "מקיף ז' רביבים", 'אמי"ת בנות מודיעין',
    'נתיבות רבקה', 'סמינר שושנים', 'קינג סולומון הכפר הירו', 'פלך', 'בר אילן',
    'שובו', 'בית ספר יצחק שמיר', 'מאיר שלו', 'אולפנת רמלה', 'קריית חינוך חטיבה',
    'אלדד נתניה', 'אולפנית מירון', 'תיכון נשר', 'אולפנית אמונה אלישבע',
    'כרמים', 'אולפנת סגולה', 'אסיף', 'שבילים', 'חטיבת יונתן', 'גולדה',
    'אולפנית ישורון', 'רמון'
]

# Hebrew first names
HEBREW_FIRST_NAMES = [
    'יוסף', 'דוד', 'משה', 'אברהם', 'שרה', 'רבקה', 'רחל', 'לאה',
    'דניאל', 'מיכאל', 'נועה', 'תמר', 'אור', 'עדי', 'שירה', 'יעל',
    'אליה', 'אריאל', 'נועם', 'רוני', 'מאיר', 'חנה', 'דינה', 'מרים',
    'יהונתן', 'שמואל', 'בנימין', 'אסתר', 'דבורה', 'רות', 'נעמי', 'קרן',
    'איתן', 'עומר', 'גיל', 'תום', 'עידו', 'אדם', 'רוני', 'טל',
    'מיה', 'עדן', 'איה', 'נוי', 'שני', 'עמית', 'רונן', 'גל'
]

HEBREW_LAST_NAMES = [
    'כהן', 'לוי', 'מזרחי', 'ביטון', 'פרץ', 'שלום', 'אברהם', 'דוד',
    'יוסף', 'חיים', 'משה', 'בן דוד', 'אזולאי', 'עמר', 'חדד', 'ניסים',
    'אוחנה', 'אלבז', 'מלכה', 'בוחבוט', 'אסולין', 'ששון', 'טולדנו', 'אוחיון',
    'בן שמעון', 'אמסלם', 'אלמליח', 'וקנין', 'שבת', 'שטרית', 'בן חמו', 'גבאי',
    'זוהר', 'ברוך', 'שמעון', 'סעדון', 'אברג\'יל', 'מימון', 'סויסה', 'אלקיים'
]

# ============================================================================
# SEED FUNCTIONS
# ============================================================================

def clear_existing_data():
    """Clear existing students and schools"""
    print("🗑️  Clearing existing data...")
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        try:
            # Clear students first (due to foreign keys)
            conn.execute(text('DELETE FROM "Student"'))
            conn.execute(text('DELETE FROM "School"'))
            trans.commit()
            print("✅ Cleared existing students and schools")
        except Exception as e:
            trans.rollback()
            print(f"❌ Error clearing data: {e}")
            raise

def seed_schools():
    """Insert target schools into the database"""
    print(f"\n📚 Seeding {len(target_schools)} schools...")
    
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            school_ids = {}
            for idx, school_name in enumerate(target_schools, start=1):
                if idx % 10 == 0:
                    print(f"  Processed {idx}/{len(target_schools)} schools...")
                
                # Insert school and get its ID
                result = conn.execute(
                    text('INSERT INTO "School" (id, name) VALUES (:id, :name) RETURNING id'),
                    {'id': idx, 'name': school_name}
                )
                school_id = result.fetchone()[0]
                school_ids[school_name] = school_id
                
            trans.commit()
            print(f"✅ Successfully seeded {len(school_ids)} schools")
            return school_ids
        except Exception as e:
            trans.rollback()
            print(f"❌ Error seeding schools: {e}")
            import traceback
            traceback.print_exc()
            raise
            trans.rollback()
            print(f"❌ Error seeding schools: {e}")
            raise

def seed_students(school_ids, students_per_school=20):
    """Generate students for target schools only"""
    print(f"\n👥 Generating {students_per_school} students per school...")
    
    CLASSES = ['ז', 'ח', 'ט', 'י', 'יא', 'יב']  # Middle and High school
    
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            student_counter = 1
            school_counter = 0
            
            for school_name, school_id in school_ids.items():
                school_counter += 1
                print(f"  Processing school {school_counter}/47: {school_name[:20]}...")
                
                for _ in range(students_per_school):
                    # Generate student data
                    fname = random.choice(HEBREW_FIRST_NAMES)
                    lname = random.choice(HEBREW_LAST_NAMES)
                    
                    # Generate unique student ID (9 digits as TEXT)
                    student_id_num = str(100000000 + student_counter).zfill(9)
                    
                    # Random class
                    class_grade = random.choice(CLASSES)
                    class_number = str(random.randint(1, 6))
                    
                    # Generate phone number (Israeli format)
                    phone = f"05{random.randint(0, 9)}-{random.randint(1000000, 9999999)}"
                    
                    # Generate email
                    email = f"{fname.lower()}.{lname.lower()}@student.example.com"
                    
                    # Insert student (all fields as TEXT to match schema)
                    # NOTE: id is TEXT, not integer! schoolId is also TEXT (cast from int)
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
                            'id': str(student_counter),  # TEXT type
                            'fname': fname,
                            'lname': lname,
                            'studentId': student_id_num,
                            'class': class_grade,
                            'classNumber': class_number,
                            'phone': phone,
                            'email': email,
                            'schoolId': str(school_id)  # Cast to TEXT
                        }
                    )
                    
                    student_counter += 1
            
            trans.commit()
            print(f"✅ Successfully generated {student_counter - 1} students across all schools")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Error seeding students: {e}")
            raise

def print_summary():
    """Print summary of seeded data"""
    print("\n" + "=" * 70)
    print("📊 SEEDING SUMMARY")
    print("=" * 70)
    
    with engine.connect() as conn:
        # Count schools
        school_count = conn.execute(text('SELECT COUNT(*) FROM "School"')).scalar()
        print(f"  🏫 Total Schools: {school_count}")
        
        # Count students
        student_count = conn.execute(text('SELECT COUNT(*) FROM "Student"')).scalar()
        print(f"  👥 Total Students: {student_count}")
        
        # Count students per school
        print(f"\n  📈 Students per school: {student_count // school_count if school_count > 0 else 0}")
        
        # Sample schools
        print("\n  🎓 Sample Schools:")
        schools = conn.execute(text('SELECT name FROM "School" LIMIT 5')).fetchall()
        for school in schools:
            print(f"     - {school[0]}")

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🌱 STUDENT DATA SEEDER - Smart Scheduling Algorithm")
    print("=" * 70)
    print("\nThis script will:")
    print("  1. Clear existing students and schools")
    print(f"  2. Seed {len(target_schools)} target schools")
    print("  3. Generate students for each school")
    print("\n⚠️  WARNING: This will DELETE all existing data!")
    
    response = input("\n▶ Continue? (yes/no): ").lower()
    
    if response not in ['yes', 'y']:
        print("❌ Aborted")
        exit()
    
    try:
        # Step 1: Clear existing data
        clear_existing_data()
        
        # Step 2: Seed schools
        school_ids = seed_schools()
        
        # Step 3: Seed students (20 per school by default)
        seed_students(school_ids, students_per_school=20)
        
        # Step 4: Print summary
        print_summary()
        
        print("\n" + "=" * 70)
        print("✅ SEEDING COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\n💡 Note: Students have school_name but NO Region column.")
        print("   Region mapping is handled in the app.py logic layer.\n")
        
    except Exception as e:
        print(f"\n❌ SEEDING FAILED: {e}")
        exit(1)
