"""
Quick script to view database contents
"""
import sqlite3
from datetime import datetime

# Connect to database
conn = sqlite3.connect('fantasy_chatbot.db')
cursor = conn.cursor()

print("=" * 70)
print("  DATABASE CONTENTS")
print("=" * 70)
print()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("📊 TABLES:")
for table in tables:
    table_name = table[0]
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cursor.fetchone()[0]
    print(f"  ├─ {table_name}: {count} rows")
print()

# Show users table with new columns
print("=" * 70)
print("👥 USERS TABLE:")
print("=" * 70)

cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print("\nColumns:")
for col in columns:
    col_name = col[1]
    col_type = col[2]
    default = col[4] if col[4] else "None"
    print(f"  ├─ {col_name} ({col_type}) - default: {default}")

cursor.execute("SELECT * FROM users LIMIT 5")
users = cursor.fetchall()
print(f"\nFirst 5 users: (Total: {len(users)})")
if users:
    for user in users:
        print(f"  ├─ User ID: {user[0]}")
        print(f"     Created: {user[1]}")
        if len(user) > 2:
            print(f"     Messages Used: {user[2]}")
            print(f"     Monthly Limit: {user[3]}")
            print(f"     Reset Date: {user[4]}")
        print()
else:
    print("  No users yet!")

# Show leagues table
print("=" * 70)
print("🏀 LEAGUES TABLE:")
print("=" * 70)

cursor.execute("SELECT COUNT(*) FROM leagues")
league_count = cursor.fetchone()[0]
print(f"\nTotal leagues: {league_count}")

if league_count > 0:
    cursor.execute("SELECT id, league_type, uploaded_at FROM leagues LIMIT 5")
    leagues = cursor.fetchall()
    print("\nRecent leagues:")
    for league in leagues:
        print(f"  ├─ League: {league[0]}")
        print(f"     Type: {league[1]}")
        print(f"     Uploaded: {league[2]}")
        print()

# Show chats table
print("=" * 70)
print("💬 CHATS TABLE:")
print("=" * 70)

cursor.execute("SELECT COUNT(*) FROM chats")
chat_count = cursor.fetchone()[0]
print(f"\nTotal chats: {chat_count}")

if chat_count > 0:
    cursor.execute("SELECT league_id, user_message, timestamp FROM chats ORDER BY timestamp DESC LIMIT 3")
    chats = cursor.fetchall()
    print("\nRecent chats:")
    for chat in chats:
        print(f"  ├─ League: {chat[0][:8]}...")
        print(f"     Message: {chat[1][:50]}..." if len(chat[1]) > 50 else f"     Message: {chat[1]}")
        print(f"     Time: {chat[2]}")
        print()

conn.close()

print("=" * 70)
print("\n💡 TIP: Install DB Browser for SQLite to view/edit database visually")
print("   Download: https://sqlitebrowser.org/dl/")
print()
