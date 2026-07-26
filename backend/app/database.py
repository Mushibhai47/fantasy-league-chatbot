"""Database configuration and session management"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import get_settings

settings = get_settings()

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.ENVIRONMENT == "development"
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables"""
    import app.models  # noqa
    Base.metadata.create_all(bind=engine)
    # Add columns that were added after initial deployment (safe to run repeatedly)
    _run_migrations()


def _run_migrations():
    """Apply incremental schema changes that create_all() won't handle."""
    from sqlalchemy import text
    with engine.connect() as conn:
        dialect = engine.dialect.name
        if dialect == 'postgresql':
            conn.execute(text(
                "ALTER TABLE leagues ADD COLUMN IF NOT EXISTS sport VARCHAR(10) DEFAULT 'mlb'"
            ))
            conn.commit()
        else:
            # SQLite: check if column exists before adding
            result = conn.execute(text("PRAGMA table_info(leagues)"))
            cols = [row[1] for row in result.fetchall()]
            if 'sport' not in cols:
                conn.execute(text("ALTER TABLE leagues ADD COLUMN sport VARCHAR(10) DEFAULT 'mlb'"))
                conn.commit()
    # scoring_profiles table is created by create_all() above (new table, no ALTER needed)


# UUID type that works with both PostgreSQL and SQLite
from sqlalchemy import TypeDecorator, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
import uuid


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses String(36).
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)
