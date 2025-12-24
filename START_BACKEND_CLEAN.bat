@echo off
echo ========================================
echo Starting Fantasy Baseball Chatbot BACKEND
echo Port: 8000
echo ========================================
echo.

cd /d "C:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot\backend"

echo Starting backend server...
python -m uvicorn app.main:app --reload --port 8000

pause
