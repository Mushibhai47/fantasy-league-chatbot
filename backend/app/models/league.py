"""League model"""
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base, GUID


class League(Base):
    """League model for uploaded CSVs"""

    __tablename__ = "leagues"

    id = Column(GUID, primary_key=True)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    league_type = Column(String(20), nullable=False)  # 'fantrax', 'cbs', 'nfbc', 'yahoo'
    sport = Column(String(10), nullable=False, server_default='mlb')  # 'mlb' or 'nfl'
    csv_filename = Column(String(255))
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="leagues")
    rosters = relationship("Roster", back_populates="league", cascade="all, delete-orphan")
