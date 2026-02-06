@echo off
echo ============================================================
echo  DATABASE VIEWER - View your SQLite database
echo ============================================================
echo.

python -c "import sqlite3; conn = sqlite3.connect('fantasy_chatbot.db'); cursor = conn.cursor(); cursor.execute('SELECT name FROM sqlite_master WHERE type=\"table\"'); tables = cursor.fetchall(); print('Tables in database:'); [print(f'  - {t[0]}') for t in tables]; print(); cursor.execute('SELECT * FROM users'); users = cursor.fetchall(); print(f'Total users: {len(users)}'); conn.close()"

echo.
echo.
echo To open in a GUI tool, download DB Browser for SQLite:
echo https://sqlitebrowser.org/dl/
echo.
echo Then open: fantasy_chatbot.db
echo.
pause
