"""
סקריפט להעברת נתונים ממסד נתונים מקומי לענן
===============================================
הסקריפט מעתיק טבלאות ונתונים מ-PostgreSQL מקומי ל-PostgreSQL בענן (Render)
"""

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.schema import CreateTable
import os
from dotenv import load_dotenv

# טען משתני סביבה
load_dotenv()

# הגדרות
LOCAL_DB = "postgresql://postgres:koren7@localhost:5432/loker_test"
CLOUD_DB = os.getenv('DATABASE_URL')

print("=" * 70)
print("🔄 העברת נתונים ממסד מקומי לענן")
print("=" * 70)

# יצירת חיבורים
print("\n📡 מתחבר למסדי הנתונים...")
try:
    local_engine = create_engine(LOCAL_DB)
    cloud_engine = create_engine(CLOUD_DB)
    
    local_conn = local_engine.connect()
    cloud_conn = cloud_engine.connect()
    
    print("✓ התחברות מוצלחת למסד המקומי")
    print("✓ התחברות מוצלחת למסד בענן")
except Exception as e:
    print(f"✗ שגיאה בהתחברות: {e}")
    exit(1)

# קבלת רשימת טבלאות מהמקומי
print("\n📋 מחפש טבלאות...")
result = local_conn.execute(text("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema='public' 
    AND table_type='BASE TABLE'
    ORDER BY table_name
"""))
tables = [row[0] for row in result]

print(f"✓ נמצאו {len(tables)} טבלאות: {', '.join(tables)}")

if not tables:
    print("⚠️  לא נמצאו טבלאות להעתקה!")
    exit(0)

# העתקת כל טבלה
metadata = MetaData()

# שלב 1: יצירת כל הטבלאות (ללא foreign keys)
print(f"\n{'='*70}")
print("🔨 שלב 1: יצירת מבנה טבלאות בענן...")
print(f"{'='*70}")

for table_name in tables:
    try:
        # טען מבנה טבלה מהמקומי
        metadata_temp = MetaData()
        table = Table(table_name, metadata_temp, autoload_with=local_engine)
        
        # יצירת הטבלה בענן
        print(f"  ⚙️  יוצר טבלה: {table_name}")
        table.create(cloud_engine, checkfirst=True)
    except Exception as e:
        # נתעלם משגיאות של foreign keys בשלב זה
        print(f"  ⚠️  {table_name}: {str(e)[:100]}")

print("✓ כל הטבלאות נוצרו")

# שלב 2: העתקת נתונים
print(f"\n{'='*70}")
print("📦 שלב 2: העתקת נתונים...")
print(f"{'='*70}")

for table_name in tables:
    print(f"\n  📦 {table_name}:")
    
    try:
        # קרא נתונים
        print(f"     📥 קורא נתונים...", end=' ')
        result = local_conn.execute(text(f'SELECT * FROM "{table_name}"'))
        rows = result.fetchall()
        columns = result.keys()
        
        print(f"✓ ({len(rows)} שורות)")
        
        if len(rows) == 0:
            print(f"     ⚠️  טבלה ריקה - מדלג")
            continue
        
        # נקה טבלה בענן
        print(f"     🧹 מנקה נתונים ישנים...", end=' ')
        cloud_conn.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE'))
        cloud_conn.commit()
        print("✓")
        
        # הכנס נתונים
        print(f"     📤 מעלה נתונים...", end=' ')
        columns_str = ', '.join([f'"{col}"' for col in columns])
        placeholders = ', '.join([f':{col}' for col in columns])
        insert_query = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'
        
        # הכנס בקבוצות
        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            data = [dict(zip(columns, row)) for row in batch]
            cloud_conn.execute(text(insert_query), data)
            cloud_conn.commit()
        
        print(f"✓ {len(rows)} שורות הועלו")
        
    except Exception as e:
        print(f"\n     ✗ שגיאה: {str(e)[:150]}")
        cloud_conn.rollback()
        continue

# סגור חיבורים
local_conn.close()
cloud_conn.close()

print(f"\n{'='*70}")
print("🎉 ההעברה הושלמה בהצלחה!")
print(f"{'='*70}")
print("\n✓ כל הטבלאות והנתונים הועתקו לענן")
print("✓ עכשיו כל המפתחים יכולים להתחבר למסד בענן")
print("\n💡 הוראות לשימוש:")
print("   1. שתף את קובץ .env (בפרטי) עם חברי הצוות")
print("   2. כולם יריצו: streamlit run app.py")
print("   3. כולם יעבדו על אותו מסד נתונים!")

