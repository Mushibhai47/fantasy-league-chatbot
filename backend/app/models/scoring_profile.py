"""NFL Scoring Profile model"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import json

from app.database import Base, GUID


class ScoringProfile(Base):
    """Named custom scoring profile saved by a user."""

    __tablename__ = "scoring_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(GUID, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)       # e.g. "Superflex Half-PPR"
    sport = Column(String(10), nullable=False, default='nfl')
    is_default = Column(Boolean, default=False)
    weights_json = Column(Text, nullable=False)      # JSON: {"pass_yds": 0.04, "rec": 0.5, ...}
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="scoring_profiles")

    @property
    def weights(self) -> dict:
        return json.loads(self.weights_json)

    @weights.setter
    def weights(self, value: dict):
        self.weights_json = json.dumps(value)
