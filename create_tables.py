"""
Create missing tables in PostgreSQL database
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL = os.getenv('DATABASE_URL')
engine = create_engine(POSTGRES_URL, echo=True)

def create_tables():
    """Create School, Locker, Closet, and Complex tables if they don't exist"""
    
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Create School table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS "School" (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE
                )
            """))
            print("✅ School table created/verified")
            
            # Create Complex table (building complex)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS "Complex" (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL
                )
            """))
            print("✅ Complex table created/verified")
            
            # Create Closet table (cabinet/closet within a complex)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS "Closet" (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    "complexId" INTEGER REFERENCES "Complex"(id) ON DELETE CASCADE
                )
            """))
            print("✅ Closet table created/verified")
            
            # Create Locker table (studentId is TEXT to match Student.id)
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS "Locker" (
                    id SERIAL PRIMARY KEY,
                    "lockerNumber" VARCHAR(50) NOT NULL,
                    "closetId" INTEGER REFERENCES "Closet"(id) ON DELETE CASCADE,
                    "studentId" TEXT REFERENCES "Student"(id) ON DELETE SET NULL
                )
            """))
            print("✅ Locker table created/verified")
            
            # Add schoolId column to Student table if it doesn't exist (TEXT type to match schema)
            conn.execute(text("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='Student' AND column_name='schoolId'
                    ) THEN
                        ALTER TABLE "Student" ADD COLUMN "schoolId" TEXT REFERENCES "School"(id);
                    END IF;
                END $$;
            """))
            print("✅ Student.schoolId column added/verified")
            
            trans.commit()
            print("\n🎉 All tables created successfully!")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Error: {e}")
            raise

if __name__ == "__main__":
    print("=" * 70)
    print("📋 Creating Missing Database Tables")
    print("=" * 70)
    create_tables()
