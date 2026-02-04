# Locker Faults System - Streamlit Sidecar App

## ארכיטקטורה היברידית
האפליקציה משתמשת בגישת Sidecar עם שני מסדי נתונים:

### PostgreSQL (קריאה בלבד)
- קריאת נתוני תלמידים מהמערכת הראשית
- חיבור אוטומטי לבסיס הנתונים הקיים: `loker_test`
- **אין כתיבה למסד נתונים זה!**

### SQLite (כתיבה)
- שמירת דיווחי תקלות במסד נתונים נפרד: `faults_system.db`
- טבלת `faults` עם:
  - `id` - מזהה ייחודי (auto-increment)
  - `student_id_ext` - FK לתלמיד במסד PostgreSQL
  - `locker_id` - מזהה לוקר
  - `fault_type` - סוג התקלה
  - `is_urgent` - דחוף/לא דחוף
  - `status` - סטטוס (Open/InProgress/Resolved/Closed)
  - `description` - תיאור התקלה
  - `created_at` - זמן יצירה

## התקנה

### עבור חברי צוות (המלצה)

1. **שכפל את הפרויקט**:
```bash
git clone <repository-url>
cd loker-faults-system
```

2. **התקן ספריות**:
```bash
pip install -r requirements.txt
```

3. **צור קובץ `.env`** (או העתק מ-`.env.example`):
```env
DATABASE_URL=postgresql://team41:xBjwE7X6BjQjARSGTFcWOg7TJ0ZiQbyq@dpg-d615mm24d50c73eh9o0g-a.oregon-postgres.render.com/studentlocker
```

4. **הרץ**:
```bash
streamlit run app.py
```

### עבור המפתח הראשי (פעם אחת)

אם אתה המפתח הראשי ויש לך נתונים במסד מקומי:

```bash
python init_cloud_db.py
```

הסקריפט יעתיק את טבלת התלמידים מהמקומי לענן.

## הרצת האפליקציה

```bash
streamlit run app.py
```

האפליקציה תיפתח בדפדפן בכתובת: http://localhost:8501

## פיצ'רים

### 📝 דיווח על תקלה חדשה
- בחירת תלמיד מהמאגר הקיים (PostgreSQL)
- הלוקר מתקבל אוטומטית לפי התלמיד
- בחירת סוג תקלה
- סימון דחיפות
- הוספת תיאור מפורט

### 📋 צפייה בתקלות
- טבלה עם כל התקלות
- סינון לפי סטטוס, דחיפות וסוג
- סטטיסטיקות מסכמות
- ייצוא לקובץ CSV

### 👥 רשימת תלמידים
- צפייה בכל התלמידים מהמאגר הראשי
- חיפוש לפי שם, תעודת זהות או אימייל
- קריאה בלבד (Read-Only)

## טכנולוגיות
- **Streamlit** - ממשק המשתמש
- **SQLAlchemy** - ORM לניהול מסדי נתונים
- **Pandas** - עיבוד נתונים והצגה
- **psycopg2** - מנהל התקן PostgreSQL
- **python-dotenv** - ניהול משתני סביבה
