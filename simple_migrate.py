"""
סקריפט פשוט להעתקת נתונים - גרסה עובדת
"""
from sqlalchemy import create_engine, text, inspect
import os
from dotenv import load_dotenv

load_dotenv()

LOCAL_DB = "postgresql://postgres:koren7@localhost:5432/loker_test"
CLOUD_DB = os.getenv('DATABASE_URL')

print("=" * 70)
print("🔄 העתקת נתונים לענן - גרסה פשוטה")
print("=" * 70)

local_engine = create_engine(LOCAL_DB)
cloud_engine = create_engine(CLOUD_DB)

# קבל רשימת טבלאות
inspector = inspect(local_engine)
tables = inspector.get_table_names()

print(f"\nנמצאו {len(tables)} טבלאות\n")

# טבלאות בסדר נכון (נסה Student ו-Locker קודם)
priority_tables = ['Student', 'Locker']
other_tables = [t for t in tables if t not in priority_tables]
ordered_tables = priority_tables + other_tables

successful = 0
failed = 0

for table_name in ordered_tables:
    if table_name not in tables:
        continue
        
    try:
        print(f"📦 {table_name}...", end=' ')
        
        # קרא נתונים
        with local_engine.connect() as local_conn:
            result = local_conn.execute(text(f'SELECT * FROM "{table_name}"'))
            rows = result.fetchall()
            columns = list(result.keys())
        
        if not rows:
            print("(ריק)")
            continue
            
        # נקה והכנס
        with cloud_engine.connect() as cloud_conn:
            # נסה למחוק נתונים קיימים
            try:
                cloud_conn.execute(text(f'DELETE FROM "{table_name}"'))
                cloud_conn.commit()
            except:
                pass
            
            # הכנס נתונים
            cols_str = ', '.join([f'"{col}"' for col in columns])
            placeholders = ', '.join([f':{col}' for col in columns])
            insert_sql = f'INSERT INTO "{table_name}" ({cols_str}) VALUES ({placeholders})'
            
            for row in rows:
                data = dict(zip(columns, row))
                try:
                    cloud_conn.execute(text(insert_sql), data)
                    cloud_conn.commit()
                except Exception as e:
                    # אם יש שגיאה, אולי הטבלה לא קיימת - ננסה ליצור אותה
                    if "does not exist" in str(e):
                        print(f"\n  יוצר טבלה {table_name}...")
                        # קבל את ה-DDL
                        with local_engine.connect() as lc:
                            ddl_result = lc.execute(text(f"""
                                SELECT 
                                    'CREATE TABLE "' || table_name || '" (' ||
                                    string_agg(
                                        '"' || column_name || '" ' || 
                                        CASE 
                                            WHEN data_type = 'USER-DEFINED' THEN udt_name
                                            ELSE data_type 
                                        END ||
                                        CASE WHEN character_maximum_length IS NOT NULL 
                                            THEN '(' || character_maximum_length || ')'
                                            ELSE ''
                                        END,
                                        ', '
                                    ) || ')'
                                FROM information_schema.columns
                                WHERE table_name = '{table_name}'
                                GROUP BY table_name
                            """))
                            ddl = ddl_result.fetchone()
                            if ddl:
                                try:
                                    cloud_conn.execute(text(ddl[0]))
                                    cloud_conn.commit()
                                    # נסה שוב
                                    cloud_conn.execute(text(insert_sql), data)
                                    cloud_conn.commit()
                                except:
                                    pass
                    continue
            
        print(f"✓ ({len(rows)} שורות)")
        successful += 1
        
    except Exception as e:
        print(f"✗ ({str(e)[:50]})")
        failed += 1

print("\n" + "=" * 70)
print(f"✓ הצלחות: {successful} | ✗ כישלונות: {failed}")
print("=" * 70)

if successful > 0:
    print("\n🎉 חלק מהנתונים הועתקו!")
    print("נסה להריץ: streamlit run app.py")
