# 🔧 מערכת ניהול תקלות לוקרים — Locker Faults System

מערכת לניהול ודיווח תקלות בלוקרים של תלמידים. **SPA** עם Flask + Bootstrap RTL.

## 🏗️ ארכיטקטורה

המערכת קוראת **בזמן אמת (read-only)** מה-DB של אתר אדון לוקר (Supabase Postgres) וכותבת תקלות ל-DB Postgres נפרד שלנו ב-Render.

```
┌──────────────────────────────────┐         ┌──────────────────────────┐
│  Adon Locker DB (Supabase)       │         │  Our DB (Render Postgres)│
│  Students, Lockers, Schools...   │         │  Faults                  │
│  ─── READ ONLY ───                │◄────────│                          │
└──────────────────────────────────┘         └──────────────────────────┘
        ▲                                              ▲
        │ live SELECT                                  │ INSERT/UPDATE
        │ (60s TTL cache)                              │
        │                                              │
        └─────────────────┬────────────────────────────┘
                          │
                  ┌───────────────┐
                  │  Flask app    │
                  │  + Google     │
                  │    OAuth      │
                  └───────────────┘
                          ▲
                          │ HTTPS
                  ┌───────────────┐
                  │  משתמשים      │
                  │  (allowlisted)│
                  └───────────────┘
```

**שני חיבורי DB נפרדים** מנוהלים ב-[db.py](db.py):
- `OUR_DATABASE_URL` — קריאה+כתיבה. טבלת `faults`.
- `ADON_LOCKER_DATABASE_URL` — קריאה בלבד. תלמידים, לוקרים, ארונות, בתי ספר, מנעולים.

מיפוי הסכמה המלא: [docs/schema_mapping.md](docs/schema_mapping.md).

## 🚀 הרצה לוקאלית

### 1. תלויות
```bash
pip install -r requirements.txt
```

### 2. הגדרת `.env`
```bash
cp .env.example .env
# מלא: ADON_LOCKER_DATABASE_URL, GOOGLE_CLIENT_ID/SECRET, ALLOWED_EMAILS, SECRET_KEY
```

לפרטי כל env var — ראי [.env.example](.env.example).

צור Postgres מקומי ל-`OUR_DATABASE_URL` (אפשר Docker `postgres:16`), או תשתמשי ב-Render free tier.

### 3. הרצה
```bash
FLASK_DEBUG=1 python flask_app.py
```
פותח על `http://localhost:5000` → מפנה ל-Google login.

## ☁️ פריסה ל-Render

[`render.yaml`](render.yaml) הוא Blueprint שמגדיר אוטומטית:
- Postgres מנוהל (ל-`faults`)
- Web service עם gunicorn
- Health check ב-`/api/health`
- Env vars (חלקם דורשים מילוי ידני בדשבורד)

**צעדים:**
1. ב-Render: **New → Blueprint** → לחבר את הריפו → Render יקרא את `render.yaml` ויציע משאבים.
2. בדשבורד למלא את ה-secrets שמסומנים `sync: false`:
   - `ADON_LOCKER_DATABASE_URL` — מנתנאל (`?sslmode=require` בסוף!)
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — מ-Google Cloud Console
   - `ALLOWED_EMAILS` — CSV של אימיילים מורשים
3. ב-Google Cloud Console להוסיף את ה-callback URL של Render (`https://<app>.onrender.com/auth/callback`) ל-OAuth credentials.
4. ב-Supabase של נתנאל לוודא שה-IPs של Render ב-allowlist (אם יש).

## 🔌 API

| Method | Endpoint | תיאור |
|---|---|---|
| GET | `/` | SPA |
| GET | `/api/students` | רשימת תלמידים live מ-Adon Locker |
| GET | `/api/student_locker/<id>` | לוקר התלמיד מ-Adon Locker |
| GET | `/api/locker/<id>` | פרטי לוקר לפי ID |
| GET | `/api/faults` | תקלות + נתוני תלמיד מועשרים |
| POST | `/api/faults` | יצירת תקלה (זיהוי אוטו' של תקלה חוזרת) |
| POST | `/api/faults/update` | עדכון סטטוס + הערות טכנאי |
| POST | `/api/update_status` | עדכון סטטוס בלבד |
| GET | `/api/technicians` | טכנאים + עומס נוכחי |
| POST | `/api/suggest_technician` | דירוג טכנאים לתקלה ספציפית |
| POST | `/api/assign_fault` | הקצאת טכנאי לתקלה |
| POST | `/api/schedule` | אלגוריתם תזמון לכלל הטכנאים |
| GET | `/api/health` | Liveness probe (ציבורי, ללא auth) |
| GET | `/auth/login` | Google OAuth flow |
| GET | `/auth/logout` | סיום סשן |

## 🧮 אלגוריתם תזמון

3 שלבים: Anchor → Region Exhaustion → Global Leftovers.

לכל בית ספר:
```
priority_score = 0.35×N + 0.25×U + 0.25×T + 0.15×R
```
- `N` = מספר תקלות (capped at 5)
- `U` = ממוצע חומרה (1-5)
- `T` = max age בימים (capped 1-5)
- `R` = 5 אם יש תקלה חוזרת אצל אותו תלמיד, אחרת 1
- **Override**: `books_stuck=True` → `priority_score = 10000`.

5 אזורים: Jerusalem, Center, North, South, Lowland. מיפוי `SCHOOL_MAPPING` ב-[flask_app.py](flask_app.py) — **דורש עדכון** מול שמות בתי הספר האמיתיים אצל נתנאל (ראי TODO ב-schema_mapping.md).

## 🧰 רשימת ציוד + סוג תיק (יוני 2026)

לכל טכנאי המערכת מציגה איזה תיק לקחת — **מכאני / דיגיטלי / שניהם** — לפי סוגי הלוקרים בתקלות שהוקצו לו.

**רשימת ציוד מקובעת ב-`templates/index.html`** (קבועים `EQUIPMENT_BASE` / `EQUIPMENT_MECHANICAL_EXTRA` / `EQUIPMENT_DIGITAL_EXTRA`):
- **ציוד בסיס** (תמיד): פטיש/מברגים/פליירים, אקדח ניטים+ניטים, מברגה+מקדחים, פטישון+מקדחים, ברגי ג׳מבו, לום, דלתות ספייר
- **תוספת מכאני:** מפתחות מאסטר
- **תוספת דיגיטלי:** סוללות, קודנים, ספקי כוח משני סוגים

איפה זה מוצג:
- **לשונית "תזמון טכנאים" ב-`/`** — כל כרטיס טכנאי כולל קופסה קופצת "ציוד לקחת" עם תווית סוג תיק. בתוך ה-accordion של כל בית ספר מופיעה גם שורת "סוגי לוקרים".
- **מסך `/technician`** — באנר זהוב עליון עם סוג התיק לפי כל התקלות המסוננות, ושורת "תיק" קטנה על כל כרטיס בית ספר וכל כרטיס ארון.

## 🔑 קודים בכרטיס תקלה (יוני 2026)

ב-`/technician`:
- **לוקר דיגיטלי** — שני בלוקי קוד נפרדים: `קוד תלמיד:` ו-`קוד מאסטר:` (כל אחד מוצג רק אם קיים).
- **לוקר מכאני** — קוד החוגה היחיד מ-`Lock.code` (`code2` כשיש מנעול דו-קודי).

## 🗂️ סוגי תקלות (יוני 2026)

מוגדרים ב-`templates/index.html` בקבוע `FAULT_TYPES`:
- **מכאני:** מנעול התקלקל · נזק לדלת · אין מנעול · לוקר לא נסגר · ציר דלת שבור · אחר
- **דיגיטלי:** הקודן לא עובד · נזק לדלת · לוקר לא נסגר · ציר דלת שבור · אחר

שמות ישנים (תקלה במנעול / מפתח אבוד / מסך לא מגיב / בעיה בסוללה / תקלה בלוח הקלדה / נעילת חירום) — עודכנו בדאטה דרך `legacy/migrate_fault_types.py`. הסקריפט תומך ב-`--apply` (אחרת dry-run).

## 📂 מבנה הפרויקט

```
loker-faults-system/
├── flask_app.py           # Routes + business logic
├── db.py                  # Two engines + raw SQL queries (Adon Locker)
├── auth.py                # Google OAuth + email allowlist
├── templates/
│   └── index.html         # SPA
├── docs/
│   └── schema_mapping.md  # מיפוי מודל מקומי → סכמת Adon Locker
├── legacy/                # סקריפטי seed ישנים (לא בשימוש, נשמרו לתיעוד)
├── requirements.txt
├── Procfile               # gunicorn entrypoint
├── render.yaml            # Render Blueprint
├── runtime.txt            # Python version pin
├── .env.example
└── .gitignore
```

## 🔒 אבטחה

- **Google OAuth + email allowlist** (`auth.py`) — חוסם כל route חוץ מ-`/auth/*`, `/static/*`, `/api/health`.
- **Read-only ל-Adon Locker** — ה-engine ב-`db.py` מוגדר עם `postgresql_readonly=True`. כל הקוד משתמש ב-`SELECT` בלבד.
- **Session cookies**: `HttpOnly`, `SameSite=Lax`, `Secure` ב-prod.
- **SECRET_KEY** ייצור Render אוטומטית.

## 🛠️ Stack

Backend: Flask 3, SQLAlchemy 2, gunicorn, Authlib  
Frontend: Bootstrap 5 RTL, vanilla JS, Chart.js  
DB: Postgres (שני חיבורים)  
Hosting: Render (web + Postgres) + Supabase (חיצוני, של נתנאל)

---

**מפתחים:** יובל לבל (owner), טליה Cup, Team 41
