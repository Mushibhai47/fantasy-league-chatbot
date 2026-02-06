@echo off
echo ========================================
echo   STOPPING ALL SERVERS
echo ========================================
echo.
echo Killing all Python processes...
taskkill /F /IM python.exe 2>nul
echo.
echo All servers stopped!
echo.
pause
