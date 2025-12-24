"""Roster model"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base, GUID


class Roster(Base):
    """Roster model - players in leagues"""

    __tablename__ = "rosters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    league_id = Column(GUID, ForeignKey("leagues.id"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    team_owner = Column(String(255), nullable=False)  # 'Free Agent' if unowned
    status = Column(String(50))  # 'AA', 'MG', 'Doc', etc. (from Fantrax)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    league = relationship("League", back_populates="rosters")
    player = relationship("Player", back_populates="rosters")
