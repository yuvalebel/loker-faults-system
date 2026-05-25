# Schema Mapping — מודל מקומי ↔ Adon Locker (Netanel's Prisma)

מסמך מקור-אמת לתרגום בין הסכמה הישנה (SQLite מקומי, נתונים פיקטיביים) לסכמה האמיתית של אתר אדון לוקר (Postgres על Supabase, נתנאל).

המקור: `C:/tmp/adon-locker-docs/schema.prisma`

---

## חוקי יסוד

1. **קריאה בלבד.** כל שאילתה מול `ADON_LOCKER_DATABASE_URL` היא `SELECT`. `INSERT/UPDATE/DELETE/CREATE/ALTER/DROP` אסורים.
2. **שמות טבלאות עם אות גדולה.** Prisma ↔ Postgres → ברירת המחדל היא `"Student"`, `"Locker"`, `"Closet"` — חייבים מירכאות כפולות ב-SQL.
3. **שמות עמודות עם אות גדולה / camelCase.** למשל `"studentId"`, `"lockerNumber"`, `"closetId"`.
4. **enums הם אובייקטי Postgres נפרדים.** הערכים הם strings PascalCase (למשל `'Faulty'`, `'Mechanical'`).
5. **כל ה-PKs הם cuid.** מחרוזות בסגנון `clxyz123abc...`. לא integer.

---

## היררכיית הישויות ב-DB של נתנאל

```
Year (שנת לימודים)
 └─ School (בית ספר)
     └─ Complex (אגף/מתחם בבית ספר)
         └─ Closet (ארון לוקרים — קובע אם דיגיטלי או מכני)
             └─ Locker (תא בודד)
                 ├─ Lock? (מנעול מכני, טבלה נפרדת — רק אם מכני)
                 └─ Student? (תלמיד מוקצה כרגע)
```

---

## מיפוי `students` (טבלה מקומית) → `Student` (DB אמיתי)

| שדה במודל המקומי | מקור בסכמה האמיתית | הערה |
|---|---|---|
| `id` (String, UUID/numeric) | `Student.id` (cuid) | פורמט שונה אבל String בשני הצדדים. ה-API מחזיר את זה כפי שהוא. |
| `fname` | `Student.fname` | זהה |
| `lname` | `Student.lname` | זהה |
| `studentId` | `Student.studentId` | תעודת זהות — זהה |
| `student_class` (alias `class`) | `Student.class` | בקוד הנוכחי המודל ב-Python נקרא `student_class` עם `Column('class', ...)` כי `class` שמורה ב-Python. ב-SQL הגולמי ה-column הוא `"class"`. |
| `classNumber` | `Student.classNumber` | במקומי זה Integer, ב-Prisma זה String. **נצטרך להמיר ל-String/Int באחידות לתצוגה.** |
| `parentPhone` | `Student.parentPhone` | זהה |
| `email` | `Student.email` | זהה |
| `school_name` | `School.name` via JOIN על `Student.schoolId = School.id` | במקומי זה String free, אצל נתנאל זה FK. **JOIN חובה.** |

**שדות חדשים שזמינים אצל נתנאל ולא היו אצלנו (אופציונלי לעתיד):**
- `Student.parentFname`, `Student.parentLname` — שם מלא של ההורה
- `Student.comments` — הערות חופשיות
- `Student.schoolId` — לחיבור ישיר לבית ספר ולא דרך שם

**שאילתת SELECT מוצעת:**
```sql
SELECT
  s.id,
  s.fname,
  s.lname,
  s."studentId",
  s.class                AS class,
  s."classNumber"        AS "classNumber",
  s."parentPhone",
  s.email,
  sch.name               AS school_name
FROM "Student" s
LEFT JOIN "School" sch ON sch.id = s."schoolId"
ORDER BY s.fname, s.lname;
```

---

## מיפוי `lockers` (טבלה מקומית) → `Locker` + `Closet` + `Complex` + `School` + `Lock`

זה המיפוי המסובך. במקומי הכל בטבלה אחת שטוחה. אצל נתנאל זה היררכיה של 4 טבלאות + Lock.

| שדה במודל המקומי | מקור בסכמה האמיתית | הערה |
|---|---|---|
| `locker_id` | `Locker.id` (cuid) | לא יותר `'L-0001'`, זה cuid. ה-API נשמר במחרוזת. |
| `school_name` | `School.name` via `Locker.schoolId` | JOIN |
| `cabinet_name` | `Closet.name` via `Locker.closetId` | JOIN. ה-frontend מציג את זה תחת "ארון". |
| `cell_number` | `Locker.lockerNumber` (Int) → cast to String | לתצוגה. אין `'101', '102'` — סתם 1, 2, 3 בתוך כל ארון. |
| `lock_type` ('digital'/'mechanical') | `Closet.type` ('Electronic'/'Mechanical') → תרגום | **`'Electronic'` → `'digital'`** ו-**`'Mechanical'` → `'mechanical'`**. ה-frontend בודק `locker.lock_type === 'digital'` ב-[index.html:2296,2298](C:/tmp/loker-faults-system/templates/index.html#L2296). |
| `student_code` | `Locker.userCode` | מנעול דיגיטלי — קוד התלמיד |
| `master_code` | `Locker.masterCode` | מנעול דיגיטלי — קוד מאסטר |
| `lock_number` | `Lock.lockNumber` via `Locker.lockId` | מנעול מכני — מספר על המנעול הפיזי. **NULL אם אין `lockId`.** |
| `current_student_id` | `Locker.studentId` | FK ל-Student. במקומי זה היה String חופשי, עכשיו cuid. |
| `status` ('available'/'in_use'/'faulty') | **`Locker.status` + `Locker.orderStatus` משולבים** | ראה הערה למטה. |
| `academic_year` | `School.year.years` (3 רמות JOIN) | אופציונלי לתצוגה. |
| `assigned_at` | אין מקבילה ישירה | אצל נתנאל יש `Locker.updatedAt`. אם רוצים זמן הקצאה צריך לבדוק transactions. **לא קריטי לתקלות.** |
| `notes` | `Locker.notes` | זהה |

### 🚨 הערה קריטית: סטטוס לוקר

במקומי יש שדה אחד `status` עם 3 ערכים. אצל נתנאל יש **שני** שדות:

| `LockerStatus` | משמעות |
|---|---|
| `Available` | תקין |
| `Faulty` | תקלה |
| `Off` | מושבת |

| `OrderStatus` | משמעות |
|---|---|
| `Available` | פנוי להשכרה |
| `Busy` | מושכר כרגע (יש תלמיד) |
| `InTheRentalProcess` | בתהליך השכרה |

**הצעת תרגום למודל המקומי:**
- אם `Locker.status = 'Faulty'` → `'faulty'`
- אחרת אם `Locker.orderStatus = 'Busy'` → `'in_use'`
- אחרת → `'available'`

**שאילתת SELECT מוצעת ל-locker by ID:**
```sql
SELECT
  l.id                        AS locker_id,
  sch.name                    AS school_name,
  c.name                      AS cabinet_name,
  l."lockerNumber"::text      AS cell_number,
  CASE c.type
    WHEN 'Electronic' THEN 'digital'
    WHEN 'Mechanical' THEN 'mechanical'
  END                         AS lock_type,
  l."userCode"                AS student_code,
  l."masterCode"              AS master_code,
  lk."lockNumber"             AS lock_number,
  l."studentId"               AS current_student_id,
  CASE
    WHEN l.status = 'Faulty' THEN 'faulty'
    WHEN l."orderStatus" = 'Busy' THEN 'in_use'
    ELSE 'available'
  END                         AS status,
  l.notes                     AS notes
FROM "Locker" l
JOIN "School" sch ON sch.id = l."schoolId"
JOIN "Closet" c   ON c.id   = l."closetId"
LEFT JOIN "Lock" lk ON lk.id = l."lockId"
WHERE l.id = :locker_id;
```

**שאילתת SELECT ל-locker by student_id:**
זהה לעיל, רק `WHERE l."studentId" = :student_id LIMIT 1`. (תיאורטית תלמיד יכול להיות עם כמה לוקרים — `Student.locker` הוא מערך — אבל בפועל נחזיר את הראשון. אם זה הופך לבעיה נחזיר את כל המערך.)

---

## טבלת `faults` — הדאטה שלנו (לא נוגעים בנתנאל)

נשארת כפי שהיא ב-[flask_app.py:222-238](C:/tmp/loker-faults-system/flask_app.py#L222-L238), עם שינוי אחד:
- `student_id_ext` ו-`locker_id` עכשיו מחזיקים cuid strings (במקום `'L-0001'` או UUIDs פיקטיביים).

הטבלה תרוץ על **`OUR_DATABASE_URL`** (Postgres ב-Render), לא ב-Supabase של נתנאל.

---

## רשימת בתי הספר (`SCHOOL_MAPPING`)

ב-[flask_app.py:101-149](C:/tmp/loker-faults-system/flask_app.py#L101-L149) יש 47 בתי ספר ממופים לאזורים. **כשנתחבר ל-DB אמיתי, ייתכן ששמות בתי הספר שונים** (אולי בלי גרשיים, עם ניקוד שונה, וכו').

**TODO אחרי חיבור:** להריץ `SELECT DISTINCT name FROM "School" ORDER BY name;` ולעדכן את `SCHOOL_MAPPING` כך שיכיל בדיוק את השמות שמופיעים ב-DB. כל בית ספר שלא ימופה יסומן `'Unknown'` ולא יופנה לטכנאי בצורה אופטימלית.

---

## טבלאות שלא נוגע בהן (לעת עתה)

זמינות אצל נתנאל אבל לא רלוונטיות למערכת תקלות:
- `Account`, `Session`, `User`, `PasswordResetToken` — auth של אתר אדון לוקר
- `Transaction`, `LockerProductOrder`, `LockerProducts`, `LockerVipImage` — מערכת תשלומים
- `WaitingList`, `EarlyRegistration` — רישום מוקדם
- `OTP` — קודי אימות
- `City` — אם נרצה לעשות חיתוך גיאוגרפי טוב יותר בעתיד

---

## ToggleS אחרי חיבור (לעדכן את המסמך)

- [ ] לוודא ששמות בתי הספר ב-`SCHOOL_MAPPING` תואמים ל-`School.name` ב-DB
- [ ] לוודא שתלמידים יש להם תמיד `schoolId` (אם NULL — איך נתפוס?)
- [ ] לוודא שלוקרים מכניים יש להם תמיד `lockId` (אם NULL — `lock_number` יהיה NULL ו-frontend יציג "—")
- [ ] לבדוק האם תלמיד אחד יכול להיות עם כמה לוקרים בפועל (אם כן — להחזיר רשימה)
- [ ] לוודא שאין כפילויות `(closetId, lockerNumber)` — Prisma מבטיח unique אבל כדאי לאמת
