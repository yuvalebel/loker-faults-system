"""
Check Student table structure
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

POSTGRES_URL = os.getenv('DATABASE_URL')
engine = create_engine(POSTGRES_URL)

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'Student'
        ORDER BY ordinal_position
    """))
    
    print("Student table columns:")
    print("=" * 50)
    for row in result:
        print(f"{row[0]:<30} {row[1]}")
