@echo off
REM סקריפט להעברת נתונים מהמקומי לענן

echo ======================================
echo העתקת מסד נתונים לענן
echo ======================================
echo.

REM הגדרת משתני סביבה למניעת בקשת סיסמה
set PGPASSWORD=koren7

echo שלב 1: ייצוא נתונים מהמסד המקומי...
"C:\Program Files\PostgreSQL\13\bin\pg_dump.exe" -U postgres -h localhost -d loker_test -f backup.sql --no-owner --no-acl

if %ERRORLEVEL% NEQ 0 (
    echo שגיאה בייצוא!
    pause
    exit /b 1
)

echo ✓ הייצוא הושלם בהצלחה!
echo.

echo שלב 2: העלאת נתונים לענן Render...
"C:\Program Files\PostgreSQL\13\bin\psql.exe" "postgresql://team41:xBjwE7X6BjQjARSGTFcWOg7TJ0ZiQbyq@dpg-d615mm24d50c73eh9o0g-a.oregon-postgres.render.com/studentlocker" -f backup.sql

if %ERRORLEVEL% NEQ 0 (
    echo שגיאה בהעלאה!
    pause
    exit /b 1
)

echo.
echo ======================================
echo ✓ ההעברה הושלמה בהצלחה!
echo ======================================
echo.
echo כל הנתונים הועתקו לענן.
echo עכשיו כולם יכולים להשתמש באפליקציה!
echo.
pause
