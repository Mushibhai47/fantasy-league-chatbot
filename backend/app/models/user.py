"""User model"""
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.database import Base, GUID


class User(Base):
    """User model for session management"""

    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    leagues = relationship("League", back_populates="user", cascade="all, delete-orphan")
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
