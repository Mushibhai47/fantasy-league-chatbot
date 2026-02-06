@echo off
echo ======================================
echo Starting Razzball Chatbot Embed Widget
echo ======================================
echo.
echo The embed widget will be available at:
echo http://localhost:3003
echo.
echo Press Ctrl+C to stop the server
echo ======================================
echo.

python -m http.server 3003

pause
