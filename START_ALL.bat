@echo off
echo ============================================================
echo  RAZZBALL CHATBOT - STARTING ALL SERVICES
echo ============================================================
echo.

echo [1/3] Starting Backend Server (Port 8000)...
start "Razzball Backend" cmd /k "cd backend && START.bat"

timeout /t 3 > nul

echo [2/3] Starting Widget Server (Port 3003)...
start "Razzball Widget" cmd /k "cd frontend\embed && START_WIDGET.bat"

timeout /t 2 > nul

echo [3/3] Starting Admin Dashboard (Port 3004)...
start "Razzball Admin" cmd /k "cd frontend\admin && START_ADMIN.bat"

timeout /t 2 > nul

echo.
echo ============================================================
echo  ALL SERVICES STARTED!
echo ============================================================
echo.
echo  Backend:  http://localhost:8000
echo  Widget:   http://localhost:3003
echo  Admin:    http://localhost:3004
echo.
echo  Opening in browser in 3 seconds...
echo ============================================================

timeout /t 3 > nul

start http://localhost:3003
start http://localhost:3004
start http://localhost:8000/docs

echo.
echo All windows opened! Close this window when done.
pause
