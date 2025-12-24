@echo off
echo ========================================
echo Starting Fantasy Baseball Chatbot BACKEND
echo ========================================
echo.

cd /d "C:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot\backend"

echo Activating virtual environment...
call venv\Scripts\activate

echo.
echo Starting backend server on http://localhost:8000
echo Press Ctrl+C to stop
echo.

python -m uvicorn app.main:app --reload --port 8000

pause
