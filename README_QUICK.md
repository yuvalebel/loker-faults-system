# 🔧 מערכת ניהול תקלות לוקרים

מערכת לדיווח וניהול תקלות בלוקרים של תלמידים.

---

## 🚀 התקנה מהירה (3 דקות)

```bash
# 1. שכפול
git clone <repository-url>
cd loker-faults-system

# 2. התקנה
pip install -r requirements.txt

# 3. הגדרת .env
# צור קובץ .env עם השורה הבאה:
DATABASE_URL=postgresql://team41:xBjwE7X6BjQjARSGTFcWOg7TJ0ZiQbyq@dpg-d615mm24d50c73eh9o0g-a.oregon-postgres.render.com/studentlocker

# 4. (אופציונלי) תקלות לדוגמה
python seed_demo_faults.py

# 5. הרצה
streamlit run app.py
```

👉 **האפליקציה תיפתח ב:** http://localhost:8501

---

## 📖 מדריכים

- **[מדריך מלא לשותפים](SETUP_FOR_TEAM.md)** ⭐ מומלץ
- **[העלאה לענן](CLOUD_SETUP.md)** - Render/Supabase

---

## 🏗️ ארכיטקטורה

| מסד נתונים | סוג | תוכן | גישה |
|-----------|-----|------|------|
| **PostgreSQL** (ענן) | Render | תלמידים (85) | קריאה בלבד ✅ |
| **SQLite** (מקומי) | קובץ | תקלות | קריאה + כתיבה ✅ |

**💡 הערה:** בעתיד גם התקלות יועברו לענן

---

## ✨ פיצ'רים

- ✅ דיווח תקלות חדשות
- ✅ צפייה וסינון תקלות
- ✅ עדכון סטטוס
- ✅ רשימת תלמידים
- ✅ סטטיסטיקות

---

## 🛠️ טכנולוגיות

**Frontend:** Streamlit  
**Backend:** Python, SQLAlchemy  
**DB:** PostgreSQL (ענן) + SQLite (מקומי)  
**Data:** Pandas

---

## 🆘 עזרה

**בעיות בהתקנה?** ראה [פתרון בעיות](SETUP_FOR_TEAM.md#-פתרון-בעיות-נפוצות)

**שאלות?** פנה למנהל הפרויקט
