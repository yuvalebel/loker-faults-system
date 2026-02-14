"""
Migration Script: Add technician_notes column to Faults table
Run this script once to update the database schema
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

# SQLite Database
SQLITE_URL = 'sqlite:///faults_system.db'
engine = create_engine(SQLITE_URL, echo=True)

def add_technician_notes_column():
    """Add technician_notes column to faults table if it doesn't exist"""
    try:
        with engine.connect() as conn:
            # Check if column already exists
            result = conn.execute(text("PRAGMA table_info(faults)")).fetchall()
            columns = [row[1] for row in result]
            
            if 'technician_notes' not in columns:
                print("Adding technician_notes column...")
                conn.execute(text("ALTER TABLE faults ADD COLUMN technician_notes TEXT"))
                conn.commit()
                print("✅ Column added successfully!")
            else:
                print("✅ Column technician_notes already exists")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == '__main__':
    add_technician_notes_column()
