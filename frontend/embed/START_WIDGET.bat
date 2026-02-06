@echo off
echo ============================================================
echo  RAZZBALL CHATBOT - WIDGET SERVER
echo ============================================================
echo.
echo Starting widget server on port 3003...
echo.
echo Widget URL: http://localhost:3003
echo.
echo Press CTRL+C to stop the server
echo ============================================================
echo.

python -m http.server 3003

pause
