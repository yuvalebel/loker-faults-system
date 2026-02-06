"""Clear students"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    trans = conn.begin()
    conn.execute(text('DELETE FROM "Student"'))
    trans.commit()
    print('✅ Cleared all students')
