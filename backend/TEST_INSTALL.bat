@echo off
echo ============================================================
echo  CHECKING INSTALLATION
echo ============================================================
echo.

echo Testing Python...
python --version
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed!
    echo Download from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH"
    pause
    exit /b 1
)

echo.
echo Testing pip...
python -m pip --version
if errorlevel 1 (
    echo.
    echo ERROR: pip is not working!
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  ALL GOOD! Now installing project dependencies...
echo ============================================================
echo.

echo Installing dependencies (this may take 2-3 minutes)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies
    echo Check the error messages above
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SUCCESS! Everything is installed!
echo ============================================================
echo.
echo Now you can run: START.bat
echo.
pause
