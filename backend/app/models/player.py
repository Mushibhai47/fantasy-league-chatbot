"""Player model"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Player(Base):
    """Player model - master reference"""

    __tablename__ = "players"

    id = Column(Integer, primary_key=True, autoincrement=True)
    razzball_id = Column(Integer, unique=True, index=True)  # From RazzID
    name = Column(String(255), nullable=False, index=True)
    team = Column(String(10))  # MLB team (NYY, BOS, etc.)
    position = Column(String(20))  # OF, SP, RP, etc.

    # Platform-specific IDs
    fantrax_id = Column(String(50), index=True)  # *05ajh*
    nfbc_id = Column(Integer, index=True)  # 11802

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    rosters = relationship("Roster", back_populates="player")
    projections_daily = relationship("ProjectionDaily", back_populates="player")
    projections_weekly = relationship("ProjectionWeekly", back_populates="player")
    projections_ros = relationship("ProjectionROS", back_populates="player")
