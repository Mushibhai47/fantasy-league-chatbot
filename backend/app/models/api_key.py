"""API Key model for storing user's LLM keys"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base, GUID


class APIKey(Base):
    """User's OpenAI/Claude API keys (encrypted)"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    provider = Column(String(20), nullable=False)  # 'openai' or 'claude'
    encrypted_key = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="api_keys")
