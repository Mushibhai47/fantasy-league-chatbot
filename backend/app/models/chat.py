"""Chat model for storing chat history"""
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class Chat(Base):
    """Chat history model"""
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    league_id = Column(String(36), index=True)
    user_message = Column(Text)
    bot_response = Column(Text)
    timestamp = Column(DateTime, server_default=func.now(), index=True)
