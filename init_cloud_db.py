"""
סקריפט אתחול מסד נתונים בענן
יוצר את טבלת Student (הבסיסית) בענן
"""
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

LOCAL_DB = "postgresql://postgres:koren7@localhost:5432/loker_test"
CLOUD_DB = os.getenv('DATABASE_URL')

print("=" * 70)
print("🚀 אתחול מסד נתונים בענן")
print("=" * 70)

local_engine = create_engine(LOCAL_DB)
cloud_engine = create_engine(CLOUD_DB)

print("\n1️⃣  מתחבר למסדי נתונים...")
with local_engine.connect() as local_conn, cloud_engine.connect() as cloud_conn:
    
    print("✓ חיבור מוצלח\n")
    
    # 2. יצירת טבלת Student
    print("2️⃣  יוצר טבלת Student...")
    
    # מחק טבלה קיימת
    cloud_conn.execute(text('DROP TABLE IF EXISTS "Student" CASCADE'))
    cloud_conn.commit()
    
    create_student_table = text("""
        CREATE TABLE "Student" (
            id TEXT PRIMARY KEY,
            fname TEXT,
            lname TEXT,
            "class" TEXT,
            "classNumber" TEXT,
            "studentId" TEXT,
            "jwtForKeepTheLocker" TEXT,
            "schoolId" TEXT,
            comments TEXT,
            "parentPhone" TEXT,
            email TEXT,
            "parentFname" TEXT,
            "parentLname" TEXT,
            "createdAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            "updatedAt" TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cloud_conn.execute(create_student_table)
    cloud_conn.commit()
    print("✓ טבלת Student נוצרה\n")
    
    # 3. העתקת נתוני תלמידים
    print("3️⃣  מעתיק נתוני תלמידים...")
    
    students_query = text('''
        SELECT id, fname, lname, "class", "classNumber", "studentId", 
               "jwtForKeepTheLocker", "schoolId", comments, "parentPhone",
               email, "parentFname", "parentLname", "createdAt", "updatedAt"
        FROM "Student"
        LIMIT 200
    ''')
    
    students = local_conn.execute(students_query).fetchall()
    print(f"   נמצאו {len(students)} תלמידים")
    
    if students:
        # נקה נתונים קודמים
        cloud_conn.execute(text('DELETE FROM "Student"'))
        cloud_conn.commit()
        
        # הכנס תלמידים
        insert_query = text('''
            INSERT INTO "Student" 
            (id, fname, lname, "class", "classNumber", "studentId", 
             "jwtForKeepTheLocker", "schoolId", comments, "parentPhone",
             email, "parentFname", "parentLname", "createdAt", "updatedAt")
            VALUES 
            (:id, :fname, :lname, :class, :classNumber, :studentId,
             :jwtForKeepTheLocker, :schoolId, :comments, :parentPhone,
             :email, :parentFname, :parentLname, :createdAt, :updatedAt)
        ''')
        
        for student in students:
            data = {
                'id': student[0],
                'fname': student[1],
                'lname': student[2],
                'class': student[3],
                'classNumber': student[4],
                'studentId': student[5],
                'jwtForKeepTheLocker': student[6],
                'schoolId': student[7],
                'comments': student[8],
                'parentPhone': student[9],
                'email': student[10],
                'parentFname': student[11],
                'parentLname': student[12],
                'createdAt': student[13],
                'updatedAt': student[14]
            }
            cloud_conn.execute(insert_query, data)
        
        cloud_conn.commit()
        print(f"✓ {len(students)} תלמידים הועתקו\n")
    
    # 4. בדיקה
    print("4️⃣  בודק את המסד בענן...")
    result = cloud_conn.execute(text('SELECT COUNT(*) FROM "Student"'))
    count = result.fetchone()[0]
    print(f"✓ יש {count} תלמידים במסד הענן\n")

print("=" * 70)
print("🎉 האתחול הושלם בהצלחה!")
print("=" * 70)
print("\n✅ עכשיו כולם יכולים להריץ: streamlit run app.py")
print("✅ כל המפתחים יעבדו על אותו מסד נתונים")
