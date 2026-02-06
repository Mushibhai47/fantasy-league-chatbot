@echo off
echo ========================================
echo Starting ALL Razzball Chatbot Servers
echo ========================================
echo.
echo This will open 3 command windows:
echo 1. Backend API (port 8000)
echo 2. Embed Widget (port 3003)
echo 3. Admin Dashboard (port 3004)
echo.
echo Press any key to start...
pause >nul

echo.
echo Starting Backend API...
start cmd /k "cd backend && START_BACKEND_CLEAN.bat"

timeout /t 3 >nul

echo Starting Embed Widget...
start cmd /k "cd frontend\embed && START_EMBED.bat"

timeout /t 2 >nul

echo Starting Admin Dashboard...
start cmd /k "cd frontend\admin && START_ADMIN.bat"

echo.
echo ========================================
echo All servers started!
echo ========================================
echo.
echo Backend API:       http://localhost:8000
echo Embed Widget:      http://localhost:3003
echo Admin Dashboard:   http://localhost:3004
echo.
echo Admin Login:
echo   Username: rudy or grey
echo   Password: razzball2024
echo.
echo Close this window when done.
echo ========================================
echo.

pause
