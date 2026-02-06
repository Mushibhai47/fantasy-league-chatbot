@echo off
echo ========================================
echo Restarting Fantasy Baseball Chatbot Backend
echo ========================================

echo.
echo [1/3] Stopping existing uvicorn processes...
taskkill /F /IM uvicorn.exe 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   Stopped existing backend
) else (
    echo   No existing backend found
)

echo.
echo [2/3] Waiting 2 seconds...
timeout /t 2 >nul

echo.
echo [3/3] Starting backend server...
echo   Backend will run on http://localhost:8000
echo   Press Ctrl+C to stop the server
echo.

cd /d "%~dp0"
python main.py

pause
