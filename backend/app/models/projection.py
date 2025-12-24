"""Projection models"""
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, DECIMAL, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class ProjectionDaily(Base):
    """Daily projections"""

    __tablename__ = "projections_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    date = Column(Date, nullable=False)

    # Batting stats
    pa = Column(DECIMAL(5, 2))   # Plate appearances
    ab = Column(DECIMAL(5, 2))   # At bats
    h = Column(DECIMAL(5, 2))    # Hits
    r = Column(DECIMAL(5, 2))    # Runs
    hr = Column(DECIMAL(5, 2))   # Home runs
    rbi = Column(DECIMAL(5, 2))  # RBIs
    sb = Column(DECIMAL(5, 2))   # Stolen bases
    bb = Column(DECIMAL(5, 2))   # Walks
    so = Column(DECIMAL(5, 2))   # Strikeouts
    avg = Column(DECIMAL(5, 3))  # Batting average
    obp = Column(DECIMAL(5, 3))  # On-base percentage
    slg = Column(DECIMAL(5, 3))  # Slugging percentage

    # Pitching stats (for pitchers)
    ip = Column(DECIMAL(5, 2))   # Innings pitched
    k = Column(DECIMAL(5, 2))    # Strikeouts (pitching)
    w = Column(DECIMAL(5, 2))    # Wins
    l = Column(DECIMAL(5, 2))    # Losses
    sv = Column(DECIMAL(5, 2))   # Saves
    era = Column(DECIMAL(5, 2))  # ERA
    whip = Column(DECIMAL(5, 2)) # WHIP

    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    player = relationship("Player", back_populates="projections_daily")

    __table_args__ = (
        UniqueConstraint('player_id', 'date', name='unique_daily_projection'),
    )


class ProjectionWeekly(Base):
    """Weekly projections"""

    __tablename__ = "projections_weekly"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    week_start = Column(Date, nullable=False)

    # Same stats as daily
    pa = Column(DECIMAL(6, 2))
    ab = Column(DECIMAL(6, 2))
    h = Column(DECIMAL(6, 2))
    r = Column(DECIMAL(6, 2))
    hr = Column(DECIMAL(6, 2))
    rbi = Column(DECIMAL(6, 2))
    sb = Column(DECIMAL(6, 2))
    bb = Column(DECIMAL(6, 2))
    so = Column(DECIMAL(6, 2))
    avg = Column(DECIMAL(5, 3))
    obp = Column(DECIMAL(5, 3))
    slg = Column(DECIMAL(5, 3))

    # Pitching
    ip = Column(DECIMAL(6, 2))
    k = Column(DECIMAL(6, 2))
    w = Column(DECIMAL(5, 2))
    l = Column(DECIMAL(5, 2))
    sv = Column(DECIMAL(5, 2))
    era = Column(DECIMAL(5, 2))
    whip = Column(DECIMAL(5, 2))

    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    player = relationship("Player", back_populates="projections_weekly")

    __table_args__ = (
        UniqueConstraint('player_id', 'week_start', name='unique_weekly_projection'),
    )


class ProjectionROS(Base):
    """Rest-of-season projections"""

    __tablename__ = "projections_ros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    season = Column(Integer, nullable=False)

    # Same stats as daily/weekly
    pa = Column(DECIMAL(7, 2))
    ab = Column(DECIMAL(7, 2))
    h = Column(DECIMAL(7, 2))
    r = Column(DECIMAL(7, 2))
    hr = Column(DECIMAL(7, 2))
    rbi = Column(DECIMAL(7, 2))
    sb = Column(DECIMAL(7, 2))
    bb = Column(DECIMAL(7, 2))
    so = Column(DECIMAL(7, 2))
    avg = Column(DECIMAL(5, 3))
    obp = Column(DECIMAL(5, 3))
    slg = Column(DECIMAL(5, 3))

    # Pitching
    ip = Column(DECIMAL(7, 2))
    k = Column(DECIMAL(7, 2))
    w = Column(DECIMAL(5, 2))
    l = Column(DECIMAL(5, 2))
    sv = Column(DECIMAL(5, 2))
    era = Column(DECIMAL(5, 2))
    whip = Column(DECIMAL(5, 2))

    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    player = relationship("Player", back_populates="projections_ros")

    __table_args__ = (
        UniqueConstraint('player_id', 'season', name='unique_ros_projection'),
    )
