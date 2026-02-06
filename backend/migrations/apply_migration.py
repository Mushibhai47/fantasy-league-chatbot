"""
Migration script to add message limit columns to users table
Run this script if you have an existing database that needs to be updated
"""
import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine
from sqlalchemy import text


def apply_migration():
    """Apply the message limits migration"""
    print("🔄 Applying migration: Add message limit tracking columns...")

    with engine.connect() as connection:
        try:
            # Detect database type
            db_url = str(engine.url)
            is_sqlite = 'sqlite' in db_url

            print(f"📝 Database type: {'SQLite' if is_sqlite else 'PostgreSQL'}")

            # Check if columns already exist (SQLite compatible)
            if is_sqlite:
                # SQLite: Use PRAGMA table_info
                result = connection.execute(text("PRAGMA table_info(users)"))
                existing_columns = [row[1] for row in result]
            else:
                # PostgreSQL: Use information_schema
                check_query = text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'users'
                """)
                result = connection.execute(check_query)
                existing_columns = [row[0] for row in result]

            print(f"📋 Existing columns: {len(existing_columns)}")

            # Check which columns we need to add
            needed_columns = ['messages_used', 'monthly_limit', 'limit_reset_date']
            missing_columns = [col for col in needed_columns if col not in existing_columns]

            if not missing_columns:
                print("✅ Migration already applied - all columns exist")
                return

            print(f"📝 Need to add {len(missing_columns)} columns: {missing_columns}")

            # Add missing columns (SQLite compatible)
            if 'messages_used' in missing_columns:
                connection.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN messages_used INTEGER DEFAULT 0 NOT NULL
                """))
                print("  ✓ Added messages_used column")
                connection.commit()

            if 'monthly_limit' in missing_columns:
                connection.execute(text("""
                    ALTER TABLE users
                    ADD COLUMN monthly_limit INTEGER DEFAULT 100 NOT NULL
                """))
                print("  ✓ Added monthly_limit column")
                connection.commit()

            if 'limit_reset_date' in missing_columns:
                if is_sqlite:
                    # SQLite: Use datetime() function
                    connection.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN limit_reset_date TIMESTAMP DEFAULT (datetime('now', '+30 days'))
                    """))
                else:
                    # PostgreSQL: Use NOW() + INTERVAL
                    connection.execute(text("""
                        ALTER TABLE users
                        ADD COLUMN limit_reset_date TIMESTAMP DEFAULT (NOW() + INTERVAL '30 days') NOT NULL
                    """))
                print("  ✓ Added limit_reset_date column")
                connection.commit()

            # Update existing users (if any)
            if is_sqlite:
                connection.execute(text("""
                    UPDATE users
                    SET limit_reset_date = datetime('now', '+30 days')
                    WHERE limit_reset_date IS NULL
                """))
            else:
                connection.execute(text("""
                    UPDATE users
                    SET
                        messages_used = COALESCE(messages_used, 0),
                        monthly_limit = COALESCE(monthly_limit, 100),
                        limit_reset_date = COALESCE(limit_reset_date, NOW() + INTERVAL '30 days')
                """))
            print("  ✓ Updated existing user records")
            connection.commit()

            # Create index
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_users_limit_reset_date ON users(limit_reset_date)
            """))
            print("  ✓ Created index on limit_reset_date")
            connection.commit()

            # Display summary
            result = connection.execute(text("""
                SELECT
                    COUNT(*) as total_users,
                    AVG(CAST(messages_used AS FLOAT)) as avg_messages_used,
                    AVG(CAST(monthly_limit AS FLOAT)) as avg_monthly_limit
                FROM users
            """))
            stats = result.fetchone()

            print("\n📊 Migration Summary:")
            print(f"  Total users: {stats[0]}")
            print(f"  Avg messages used: {stats[1] or 0:.2f}")
            print(f"  Avg monthly limit: {stats[2] or 0:.0f}")

            print("\n✅ Migration completed successfully!")

        except Exception as e:
            print(f"\n❌ Migration failed: {str(e)}")
            connection.rollback()
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("  MESSAGE LIMITS MIGRATION")
    print("=" * 60)
    print()

    try:
        apply_migration()
    except Exception as e:
        print(f"\n💥 Error: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
