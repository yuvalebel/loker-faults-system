"""
Database Migration Script
=========================
This script adds the 'is_recurring' column to existing faults_system.db

Run this if you get errors about missing 'is_recurring' column.
"""

import sqlite3
import os

DB_PATH = 'faults_system.db'

def migrate_database():
    """Add is_recurring column to existing database"""
    
    if not os.path.exists(DB_PATH):
        print(f"✅ No existing database found at {DB_PATH}")
        print("   A new database will be created when you run flask_app.py")
        return
    
    print(f"🔧 Migrating database: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(faults)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_recurring' in columns:
            print("✅ Column 'is_recurring' already exists - no migration needed")
            conn.close()
            return
        
        # Add the new column
        print("   Adding 'is_recurring' column...")
        cursor.execute("""
            ALTER TABLE faults 
            ADD COLUMN is_recurring BOOLEAN DEFAULT 0
        """)
        
        conn.commit()
        print("✅ Migration completed successfully!")
        print("   Column 'is_recurring' added with default value False")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Error during migration: {e}")
        print("\n💡 Alternative: Delete the old database and create a new one:")
        print(f"   1. Stop the Flask server")
        print(f"   2. Delete: {DB_PATH}")
        print(f"   3. Restart: python flask_app.py")
        return

if __name__ == '__main__':
    print("=" * 60)
    print("Database Migration Tool")
    print("=" * 60)
    migrate_database()
    print("=" * 60)
