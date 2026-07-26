"""User model"""
from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import uuid

from app.database import Base, GUID


class User(Base):
    """User model for session management"""

    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Message limit tracking (daily limit — resets every 24 hours)
    messages_used = Column(Integer, default=0, nullable=False)
    monthly_limit = Column(Integer, default=7, nullable=False)  # "monthly_limit" column kept for DB compat; now a daily limit
    limit_reset_date = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=1), nullable=False)

    # Relationships
    leagues = relationship("League", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    scoring_profiles = relationship("ScoringProfile", back_populates="user", cascade="all, delete-orphan")
