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

    # Message limit tracking
    messages_used = Column(Integer, default=0, nullable=False)
    monthly_limit = Column(Integer, default=100, nullable=False)
    limit_reset_date = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=30), nullable=False)

    # Relationships
    leagues = relationship("League", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
