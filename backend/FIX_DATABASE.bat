@echo off
echo ============================================================
echo  FIXING DATABASE - ADDING MESSAGE LIMIT COLUMNS
echo ============================================================
echo.

echo Running database migration...
python migrations\apply_migration.py

if errorlevel 1 (
    echo.
    echo ERROR: Migration failed!
    echo.
    echo This might be because:
    echo 1. PostgreSQL is not running
    echo 2. Database doesn't exist
    echo 3. .env file has wrong credentials
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  DATABASE FIXED!
echo ============================================================
echo.
echo The users table now has the message limit columns.
echo You can now upload CSV files without errors!
echo.
pause