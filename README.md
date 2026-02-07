# 🔧 מערכת ניהול תקלות לוקרים - Locker Faults System

מערכת מקצועית לניהול ודיווח תקלות בלוקרים של תלמידים, בנויה כ-**Single Page Application (SPA)** עם Flask Backend ו-HTML/Bootstrap Frontend.

## 🎯 תכונות מרכזיות

### ⚡ ביצועים גבוהים
- **Global Caching**: כל נתוני התלמידים נטענים ל-RAM בהפעלת השרת
- **אין Latency**: אפס שאילתות למסד נתונים מרוחק בזמן עבודה
- **מהיר פי 10-100** מהגרסה הקודמת

### 📊 ניהול תקלות חכם
- **דיווח תקלות** - טופס פשוט עם בחירת תלמיד מרשימה נשלפת
- **ניהול מלא** - צפייה, סינון ועדכון סטטוס תקלות
- **סיווג אוטומטי** - חומרה (1-5), דחיפות, ספרים תקועים
- **Modal לפרטים** - צפייה ועריכה מלאה של כל תקלה

### 🧮 אלגוריתם תזמון חכם לטכנאים
חלוקת תקלות מאוזנת לפי **ציון עדיפות לכל בית ספר**:

```
Priority Score = 0.35×N + 0.25×U + 0.25×T + 0.15×R

N = מספר תקלות פתוחות בבית ספר
U = תקלות דחופות (ספרים תקועים)
T = סך חומרת התקלות
R = תקלות שדווחו ב-24 שעות האחרונות

תקלות דחופות → ציון 1000 (עדיפות מקסימלית)
```

**Load Balancing**: כל בית ספר מוקצה לטכנאי עם העומס הנמוך ביותר - אין טכנאים פנויים בזמן שאחרים עמוסים!

### 🎨 ממשק משתמש מודרני
- **Bootstrap 5** עם תמיכה מלאה ב-RTL (עברית)
- **עיצוב מקצועי** - כרטיסים, גרדיאנטים, אנימציות
- **ללא רענונים** - עדכונים דינמיים באמצעות JavaScript
- **3 טאבים**: דיווח תקלה | ניהול תקלות | תזמון טכנאים

## 🗄️ ארכיטקטורה - Hybrid Database

### PostgreSQL (Remote - Read Only)
- נתוני תלמידים קיימים
- **נטען ל-RAM בהפעלה** - אפס שאילתות בזמן ריצה

### SQLite (Local - Read/Write)
- כל נתוני התקלות
- מהיר וללא תלות ברשת

## 🚀 התקנה והפעלה

### דרישות מקדימות
```bash
Python 3.7+
```

### שלב 1: התקנת תלויות
```bash
pip install -r requirements.txt
```

הקובץ `requirements.txt` כולל:
- Flask
- SQLAlchemy
- pandas
- psycopg2-binary
- python-dotenv

### שלב 2: הגדרת משתני סביבה
צור קובץ `.env` (או שנה את `.env.example`):
```env
DATABASE_URL=postgresql://user:password@host/database
```

### שלב 3: הפעלת השרת
```bash
python flask_app.py
```

השרת יתחיל על `http://localhost:5000`

**פלט צפוי:**
```
🔄 Loading students from PostgreSQL into RAM cache...
✅ Loaded 60 students into RAM cache
✅ Flask server ready with cached students data
 * Running on http://127.0.0.1:5000
```

### שלב 4: גישה לממשק
פתח דפדפן: **http://localhost:5000**

## 📁 מבנה הפרויקט

```
loker-faults-system/
├── flask_app.py              # שרת Flask עם API endpoints
├── templates/
│   └── index.html            # SPA Frontend (HTML/Bootstrap/JS)
├── faults_system.db          # SQLite Database (נוצר אוטומטית)
├── requirements.txt          # תלויות Python
├── .env                      # משתני סביבה (לא ב-Git)
├── .env.example              # דוגמה להגדרות
├── .gitignore               # קבצים להתעלמות
└── README.md                # התיעוד הזה
```

## 🔌 API Endpoints

### Backend Routes (Flask)

| Method | Endpoint | תיאור |
|--------|----------|-------|
| `GET` | `/` | מגיש את הדף הראשי (SPA) |
| `GET` | `/api/students` | מחזיר רשימת תלמידים מה-Cache |
| `GET` | `/api/faults` | מחזיר את כל התקלות עם מידע תלמידים |
| `POST` | `/api/faults` | יצירת תקלה חדשה |
| `POST` | `/api/update_status` | עדכון סטטוס תקלה |
| `POST` | `/api/schedule` | הרצת אלגוריתם תזמון טכנאים |

### דוגמה - יצירת תקלה
```javascript
fetch('/api/faults', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        student_id_ext: 'student-uuid',
        fault_type: 'תקלה במנעול',
        books_stuck: true,
        description: 'המנעול לא נפתח'
    })
})
```

### דוגמה - תזמון טכנאים
```javascript
fetch('/api/schedule', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
        num_technicians: 3
    })
})
```

## 📊 מודל נתונים

### טבלת Faults (SQLite)
```python
- id: מזהה ייחודי
- student_id_ext: מפתח זר לתלמיד (PostgreSQL)
- locker_id: מזהה לוקר
- fault_type: סוג תקלה (תקלה במנעול, ספרים תקועים, וכו')
- severity: חומרה (1-5)
- books_stuck: ספרים תקועים? (Boolean)
- is_urgent: דחוף? (Boolean)
- status: סטטוס (Open/Resolved/Closed)
- description: תיאור חופשי
- created_at: תאריך יצירה
- resolved_at: תאריך פתרון
- assigned_technician: טכנאי מוקצה
```

### מיפוי בתי ספר לאזורים
המפתח `SCHOOL_MAPPING` ב-`flask_app.py` קובע לאיזה אזור שייך כל בית ספר:
- **Jerusalem** (ירושלים)
- **Center** (מרכז)
- **North** (צפון)
- **South** (דרום)
- **Lowland** (שפלה)

## 🎯 תרחישי שימוש

### 1️⃣ דיווח תקלה חדשה
1. בחר תלמיד מהרשימה הנשלפת (חיפוש אפשרי)
2. בחר סוג תקלה
3. סמן אם יש ספרים תקועים (= דחוף אוטומטית)
4. הוסף תיאור (אופציונלי)
5. שלח

### 2️⃣ ניהול תקלות
- **סינון**: לפי סטטוס, דחיפות, טקסט חופשי
- **צפייה בפרטים**: לחץ על כפתור העין 👁️
- **עדכון סטטוס**: פתוחה → נפתרה → סגורה
- **הקצאת טכנאי**: בעת עדכון פרטים

### 3️⃣ תזמון טכנאים
1. הזן מספר טכנאים זמינים (1-10)
2. הרץ אלגוריתם
3. קבל חלוקה מאוזנת:
   - בתי ספר לכל טכנאי
   - רשימת תקלות מפורטת
   - ציוני עדיפות

## 🛠️ פיתוח והתאמה אישית

### שינוי מיפוי בתי ספר
ערוך את `SCHOOL_MAPPING` ב-`flask_app.py`:
```python
SCHOOL_MAPPING = {
    'שם בית ספר': 'אזור',
    # ...
}
```

### שינוי נוסחת העדיפות
במתודה `schedule_technicians()` שנה את המקדמים:
```python
school_scores['priority_score'] = (
    0.35 * school_scores['N'] +  # משקל מספר תקלות
    0.25 * school_scores['U'] +  # משקל דחיפות
    0.25 * school_scores['T'] +  # משקל חומרה
    0.15 * school_scores['R']    # משקל תקלות אחרונות
)
```

### הוספת סוג תקלה חדש
1. הוסף ל-`SEVERITY_MAP` ב-`flask_app.py`:
```python
SEVERITY_MAP = {
    "סוג תקלה חדש": 4,  # חומרה 1-5
    # ...
}
```

2. הוסף אופציה ב-`templates/index.html`:
```html
<option value="סוג תקלה חדש">סוג תקלה חדש</option>
```

## 🔒 אבטחה

- **SQL Injection**: SQLAlchemy ORM מונע injection
- **XSS**: תוכן משתמש מנוקה אוטומטית
- **Environment Variables**: סיסמאות ב-.env (לא ב-Git)
- **Production**: השתמש ב-Gunicorn/uWSGI ולא בשרת הפיתוח

### הפעלה ב-Production
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 flask_app:app
```

## 📝 רישוי

פרויקט פרטי - כל הזכויות שמורות

## 🆘 תמיכה ופתרון בעיות

### השרת לא עולה
- ודא ש-Flask מותקן: `pip install flask`
- בדוק את משתני הסביבה ב-`.env`
- בדוק חיבור ל-PostgreSQL

### לא נטענים תלמידים
- ודא ש-`DATABASE_URL` נכון
- בדוק גישה למסד הנתונים המרוחק
- בדוק לוגים של השרת

### תקלות לא נשמרות
- בדוק שקובץ `faults_system.db` קיים
- בדוק הרשאות כתיבה בתיקייה
- בדוק JavaScript console בדפדפן

## 🎓 טכנולוגיות

- **Backend**: Flask (Python)
- **Frontend**: HTML5, Bootstrap 5, Vanilla JavaScript
- **Database**: PostgreSQL (Remote) + SQLite (Local)
- **ORM**: SQLAlchemy
- **Data Processing**: pandas

---

**גרסה**: 2.0 (Flask SPA)  
**תאריך עדכון**: פברואר 2026  
**מפתחים**: Team 41

🚀 **ביצועים מהירים | 🎨 ממשק מודרני | 🧮 אלגוריתם חכם**
