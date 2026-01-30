"""
Create demo faults data for testing
=====================================
This script creates sample fault reports in the SQLite database
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import from main app
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app import Fault, Base, get_students
from datetime import datetime, timedelta
import random

# SQLite Connection
SQLITE_URL = 'sqlite:///faults_system.db'
engine = create_engine(SQLITE_URL, echo=False)

# Create tables
Base.metadata.create_all(engine)

# Create session
Session = sessionmaker(bind=engine)
session = Session()

def create_demo_faults():
    """Create demo fault reports"""
    
    print("🔧 Creating demo faults...")
    
    # Get students from PostgreSQL
    try:
        students_df = get_students()
        
        if students_df.empty:
            print("❌ No students found in PostgreSQL database")
            return
        
        print(f"✅ Found {len(students_df)} students in database")
        
        # Fault types in Hebrew and English
        fault_types = [
            "תקלה במנעול",
            "נזק לדלת", 
            "הקוד לא עובד",
            "ספרים תקועים",
            "מפתח אבוד",
            "אחר"
        ]
        
        # Sample descriptions
        descriptions = [
            "המנעול לא נפתח אחרי הזנת הקוד הנכון",
            "הדלת לא נסגרת עד הסוף",
            "הקוד שקיבלתי לא עובד בכלל",
            "הספרים שלי תקועים בפנים ואני צריך אותם לשיעור",
            "איבדתי את המפתח של הלוקר",
            "ידית הדלת שבורה",
            "יש חריץ בדלת",
            "המנעול תקוע ולא זז",
            "שכחתי את הקוד ולא יכול לפתוח",
            "הלוקר לא נועל כמו שצריך"
        ]
        
        # Statuses
        statuses = ['Open', 'InProgress', 'Resolved', 'Closed']
        
        # Create 15 demo faults
        demo_faults = []
        
        for i in range(15):
            # Random student
            student_row = students_df.sample(1).iloc[0]
            student_id = student_row['id']
            
            # Random fault type
            fault_type = random.choice(fault_types)
            
            # Calculate severity based on fault type
            from app import get_severity
            severity = get_severity(fault_type)
            
            # Random books stuck (20% chance)
            books_stuck = random.random() < 0.2
            
            # Random urgency (30% chance of urgent)
            is_urgent = random.random() < 0.3
            
            # Random status (weighted: more Open and InProgress)
            status = random.choices(
                statuses, 
                weights=[40, 30, 20, 10]  # More open faults
            )[0]
            
            # Random description
            description = random.choice(descriptions)
            
            # Random created date (last 30 days)
            days_ago = random.randint(0, 30)
            created_at = datetime.now() - timedelta(days=days_ago)
            
            # Resolved date if status is Resolved or Closed
            resolved_at = None
            if status in ['Resolved', 'Closed']:
                resolved_days = random.randint(1, days_ago) if days_ago > 0 else 0
                resolved_at = created_at + timedelta(days=resolved_days)
            
            # Assigned technician if InProgress or Resolved
            technician = None
            if status in ['InProgress', 'Resolved', 'Closed']:
                technicians = ['דני', 'יוסי', 'משה', 'אבי', 'רון']
                technician = random.choice(technicians)
            
            # Create fault
            fault = Fault(
                student_id_ext=student_id,
                locker_id=None,  # Will be linked via student
                fault_type=fault_type,
                severity=severity,
                books_stuck=books_stuck,
                is_urgent=is_urgent,
                status=status,
                description=description,
                created_at=created_at,
                resolved_at=resolved_at,
                assigned_technician=technician
            )
            
            demo_faults.append(fault)
        
        # Add all faults to session
        session.add_all(demo_faults)
        session.commit()
        
        print(f"✅ Created {len(demo_faults)} demo faults!")
        
        # Print summary
        print("\n📊 Summary:")
        print(f"  - Open: {len([f for f in demo_faults if f.status == 'Open'])}")
        print(f"  - In Progress: {len([f for f in demo_faults if f.status == 'InProgress'])}")
        print(f"  - Resolved: {len([f for f in demo_faults if f.status == 'Resolved'])}")
        print(f"  - Closed: {len([f for f in demo_faults if f.status == 'Closed'])}")
        print(f"  - Urgent: {len([f for f in demo_faults if f.is_urgent])}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def clear_existing_faults():
    """Clear all existing faults"""
    try:
        deleted = session.query(Fault).delete()
        session.commit()
        print(f"🗑️  Deleted {deleted} existing faults")
    except Exception as e:
        print(f"❌ Error clearing faults: {e}")
        session.rollback()

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Demo Faults Data Generator")
    print("=" * 60)
    
    # Ask user
    response = input("\n⚠️  Clear existing faults first? (y/n): ").lower()
    
    if response == 'y':
        clear_existing_faults()
    
    create_demo_faults()
    
    print("\n✅ Done! Refresh your Streamlit app to see the demo faults.")
    print("=" * 60)
