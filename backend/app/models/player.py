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
    team = Column(String(50))  # MLB team (NYY, BOS, etc.) — may be multi-team e.g. BAL/DET/ATL
    position = Column(String(50))  # OF, SP, RP, etc. — may be multi-pos e.g. 1B,2B,3B,SS,OF

    # Platform-specific IDs
    fantrax_id = Column(String(50), index=True)  # *05ajh*
    nfbc_id = Column(Integer, index=True)  # 11802
    cbs_player_name = Column(String(255), index=True)  # "Aaron Judge OF | NYY"
    yahoo_id = Column(String(50), index=True)  # Yahoo player ID
    sleeper_id = Column(String(50), index=True)  # Sleeper player ID

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    rosters = relationship("Roster", back_populates="player")
    projections_daily = relationship("ProjectionDaily", back_populates="player")
    projections_weekly = relationship("ProjectionWeekly", back_populates="player")
    projections_ros = relationship("ProjectionROS", back_populates="player")
