@echo off
echo ========================================
echo Starting Fantasy Baseball Chatbot FRONTEND
echo Port: 3002
echo ========================================
echo.

cd /d "C:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot\frontend"

echo Starting frontend server on port 3002...
npm run dev -- -p 3002

pause
