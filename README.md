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

1. התקן את הספריות הנדרשות:
```bash
pip install -r requirements.txt
```

## הרצת האפליקציה

```bash
cd AdonLocker_Project
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
