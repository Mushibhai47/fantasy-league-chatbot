@echo off
echo ============================================================
echo  RAZZBALL CHATBOT - BACKEND STARTUP
echo ============================================================
echo.

echo [1/4] Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo      Dependencies installed successfully!

echo.
echo [2/4] Running database migration...
python migrations\apply_migration.py
if errorlevel 1 (
    echo WARNING: Migration had issues, but continuing...
)

echo.
echo [3/4] Checking database connection...
python -c "from app.database import engine; print('Database OK')" 2>nul
if errorlevel 1 (
    echo WARNING: Could not verify database connection
    echo Make sure PostgreSQL is running and .env is configured
)

echo.
echo [4/4] Starting backend server...
echo.
echo ============================================================
echo  BACKEND STARTED SUCCESSFULLY!
echo ============================================================
echo.
echo  Backend API: http://localhost:8000
echo  API Docs:    http://localhost:8000/docs
echo  Health:      http://localhost:8000/
echo.
echo  Press CTRL+C to stop the server
echo ============================================================
echo.

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause