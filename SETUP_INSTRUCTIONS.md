# הוראות התקנה - Locker Faults System

## אופציה 1: שימוש במסד בענן (מומלץ לצוות)

כל חברי הצוות עובדים על אותו מסד נתונים בענן.

### שלבים:

1. **שכפל הפרויקט**:
```bash
git clone <repository-url>
cd loker-faults-system
```

2. **התקן תלויות**:
```bash
pip install -r requirements.txt
```

3. **צור קובץ `.env`**:
```env
DATABASE_URL=postgresql://team41:xBjwE7X6BjQjARSGTFcWOg7TJ0ZiQbyq@dpg-d615mm24d50c73eh9o0g-a.oregon-postgres.render.com/studentlocker
```

4. **הרץ**:
```bash
streamlit run app.py
```

✅ **זהו! כולם עובדים על אותו מסד**

---

## אופציה 2: פיתוח מקומי (למפתח ראשי)

אם אתה המפתח הראשי ויש לך PostgreSQL מקומי עם נתונים:

1. **השתמש בסקריפט ההעברה**:
```bash
python simple_migrate.py
```

הסקריפט יעתיק את כל הנתונים מהמקומי שלך לענן.

---

## פתרון בעיות

### "אין חיבור למסד"
- בדוק שיש לך חיבור לאינטרנט
- ודא שהעתקת את ה-URL המלא ל-`.env`

### "הטבלאות לא קיימות"
- המסד בענן צריך להכיל את הטבלאות והנתונים
- הרץ את `simple_migrate.py` מהמחשב שיש בו נתונים

### "התקנת psycopg2 נכשלה"
```bash
pip install psycopg2-binary
```

---

## מידע טכני

- **מסד בענן**: Render PostgreSQL (חינמי)
- **מיקום**: Oregon, USA
- **גרסה**: PostgreSQL 18.1
- **זמינות**: 24/7 (ייכנס לשינה אחרי 15 דקות חוסר פעילות)

⚠️ **אל תעלה את `.env` לגיט!** (כבר ב-`.gitignore`)
