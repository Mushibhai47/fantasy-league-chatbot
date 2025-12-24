"""League schemas"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class PlayerInRoster(BaseModel):
    """Player in roster"""
    id: int
    name: str
    mlb_team: Optional[str]
    position: Optional[str]
    owner: str

    # Projections (optional)
    hr: Optional[float] = None
    rbi: Optional[float] = None
    sb: Optional[float] = None
    avg: Optional[float] = None

    class Config:
        from_attributes = True


class LeagueResponse(BaseModel):
    """League upload response"""
    id: UUID
    league_type: str
    total_players: int
    owned_players: int
    free_agents: int
    uploaded_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str
        }


class RosterResponse(BaseModel):
    """Roster display"""
    league_id: UUID
    league_type: str
    players: List[PlayerInRoster]

    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str
        }
