"""Sleeper Fantasy Router — no OAuth, users connect by username."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
import uuid
import logging

from app.database import get_db
from app.models import User, League, Roster
from app.services.player_matcher import PlayerMatcher
from app.services import sleeper_service

logger = logging.getLogger(__name__)
router = APIRouter()


class SleeperImportRequest(BaseModel):
    league_id: str
    existing_league_id: Optional[str] = None


@router.get("/user/{username}")
async def get_sleeper_user_leagues(username: str):
    """
    Look up a Sleeper username and return their NFL leagues.
    Tries the current season first, then the prior season as a fallback.
    """
    try:
        user = sleeper_service.lookup_user(username)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Sleeper user '{username}' not found")

    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=404, detail="Invalid Sleeper user")

    leagues = sleeper_service.get_user_leagues_multi_season(user_id, sport="nfl")

    return {
        "user_id": user_id,
        "username": user.get("username"),
        "display_name": user.get("display_name"),
        "leagues": [
            {
                "league_id": lg.get("league_id"),
                "name": lg.get("name"),
                "total_rosters": lg.get("total_rosters"),
                "roster_positions": lg.get("roster_positions", []),
                "status": lg.get("status"),
                "scoring_settings": lg.get("scoring_settings", {}),
            }
            for lg in leagues
        ],
    }


@router.post("/import")
async def import_sleeper_league(req: SleeperImportRequest, db: Session = Depends(get_db)):
    """
    Fetch a Sleeper league's full roster and store in the DB.
    Returns the same shape as the CSV/Yahoo upload endpoints so the frontend
    flow works unchanged from that point on.
    """
    try:
        league_data = sleeper_service.build_league_data(req.league_id)
    except Exception as exc:
        logger.exception("Sleeper import failed")
        raise HTTPException(status_code=400, detail=f"Failed to fetch Sleeper league: {exc}")

    players_data = league_data["players_data"]
    if not players_data:
        raise HTTPException(status_code=404, detail="No players found in this Sleeper league")

    # Handle re-import: delete old league, reuse old user row
    user = None
    if req.existing_league_id:
        try:
            old_uuid = uuid.UUID(req.existing_league_id)
            old_league = db.query(League).filter(League.id == old_uuid).first()
            if old_league:
                db.query(Roster).filter(Roster.league_id == old_uuid).delete()
                user = db.query(User).filter(User.id == old_league.user_id).first()
                db.delete(old_league)
                db.flush()
        except Exception:
            user = None

    if not user:
        user = User()
        db.add(user)
        db.flush()

    league = League(
        id=uuid.uuid4(),
        user_id=user.id,
        league_type="sleeper",
        sport=league_data["sport"],
        csv_filename=f"sleeper_{req.league_id}",
    )
    db.add(league)
    db.flush()

    matcher = PlayerMatcher(db)
    player_owner_pairs = []

    for pd_row in players_data:
        player = matcher.get_or_create_player(pd_row)
        player_owner_pairs.append((player, pd_row))

    db.flush()

    for player, pd_row in player_owner_pairs:
        roster = Roster(
            league_id=league.id,
            player_id=player.id,
            team_owner=pd_row["owner"],
            status=None,
        )
        db.add(roster)

    db.commit()

    logger.info(f"[Sleeper] Imported {len(player_owner_pairs)} players, league={league.id}")

    return {
        "id": str(league.id),
        "sport": league_data["sport"],
        "league_type": "sleeper",
        "league_name": league_data["league_name"],
        "total_players": len(player_owner_pairs),
        "teams": league_data["teams"],
        "weights": league_data["weights"],
        "preset": league_data["preset"],
    }
