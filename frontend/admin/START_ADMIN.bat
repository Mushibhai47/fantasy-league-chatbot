@echo off
echo ============================================================
echo RAZZBALL CHATBOT - ADMIN DASHBOARD
echo ============================================================
echo.
echo Starting admin dashboard on port 3004...
echo.
echo Admin URL: http://localhost:3004
echo Login: rudy / razzball2024
echo.
echo Press CTRL+C to stop the server
echo ============================================================
echo.
python -m http.server 3004
pause
