@echo off
cls
echo ========================================
echo   RAZZBALL CHATBOT - EASY STARTUP
echo ========================================
echo.
echo Starting all servers...
echo This will open 3 command windows.
echo.
echo Wait 10 seconds after they open, then:
echo.
echo   1. Open: http://localhost:3003
echo      (Embed Widget - Enter API key and upload CSV)
echo.
echo   2. Open: http://localhost:3004
echo      (Admin Dashboard - Login: rudy / razzball2024)
echo.
echo ========================================
echo.

REM Start Backend API
echo [1/3] Starting Backend API on port 8000...
start "Backend API" cmd /k "cd backend && python -m uvicorn app.main:app --reload --port 8000"
timeout /t 5 /nobreak >nul

REM Start Embed Widget
echo [2/3] Starting Embed Widget on port 3003...
start "Embed Widget" cmd /k "cd frontend\embed && python -m http.server 3003"
timeout /t 2 /nobreak >nul

REM Start Admin Dashboard
echo [3/3] Starting Admin Dashboard on port 3004...
start "Admin Dashboard" cmd /k "cd frontend\admin && python -m http.server 3004"

echo.
echo ========================================
echo   ALL SERVERS STARTED!
echo ========================================
echo.
echo Wait 10 seconds, then open:
echo.
echo   Embed Widget:      http://localhost:3003
echo   Admin Dashboard:   http://localhost:3004
echo.
echo API Key: Users provide their own OR use free tier (100 msgs/month)
echo.
echo Admin Login:
echo   Username: rudy
echo   Password: razzball2024
echo.
echo Press any key to close this window...
pause >nul