"""ESPN Fantasy Sports Router"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, League, Roster
from app.services.player_matcher import PlayerMatcher
import requests
import uuid
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)

router = APIRouter()

ESPN_API_BASE = "https://fantasy.espn.com/apis/v3/games/flb"
ESPN_SEASON = "2026"

ESPN_POSITION_MAP = {
    1: "C", 2: "1B", 3: "2B", 4: "3B", 5: "SS",
    6: "OF", 7: "DH", 8: "SP", 9: "RP"
}

ESPN_TEAM_MAP = {
    1: "ATL", 2: "BOS", 3: "LAA", 4: "CWS", 5: "CLE", 6: "COL",
    7: "DET", 8: "HOU", 9: "KC", 10: "MIL", 11: "MIN", 12: "NYM",
    13: "NYY", 14: "OAK", 15: "PHI", 16: "PIT", 17: "STL", 18: "SD",
    19: "SF", 20: "SEA", 21: "TB", 22: "TEX", 23: "TOR", 24: "WSH",
    25: "ATH", 26: "CIN", 27: "LAD", 28: "ARI", 29: "CHC", 30: "MIA"
}

IL_SLOT_IDS = {17}


class ESPNImportRequest(BaseModel):
    league_id: str
    espn_s2: str
    swid: str
    existing_league_id: Optional[str] = None
    season: Optional[str] = None


def _fetch_espn_league(league_id: str, espn_s2: str, swid: str, season: str) -> dict:
    url = f"{ESPN_API_BASE}/seasons/{season}/segments/0/leagues/{league_id}"
    print(f"[ESPN] Fetching: {url}")
    try:
        resp = requests.get(
            url,
            params={"view": ["mRoster", "mTeam", "mSettings"]},
            cookies={"espn_s2": espn_s2, "SWID": swid},
            headers={
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
            timeout=30
        )
    except requests.exceptions.Timeout:
        print(f"[ESPN] Request timed out after 30s")
        raise HTTPException(status_code=504, detail="ESPN API timed out. The league may be private or ESPN is blocking this request.")
    except requests.exceptions.ConnectionError as e:
        print(f"[ESPN] Connection error: {e}")
        raise HTTPException(status_code=502, detail=f"Could not connect to ESPN API: {str(e)[:200]}")
    print(f"[ESPN] Response status: {resp.status_code}, content length: {len(resp.text)}")
    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="ESPN authentication failed. Check your espn_s2 and SWID cookies.")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="ESPN league not found. Check your league ID.")
    if not resp.ok:
        print(f"[ESPN] Error body: {resp.text[:500]}")
        raise HTTPException(status_code=400, detail=f"ESPN API error: {resp.status_code} - {resp.text[:300]}")
    return resp.json()


@router.post("/import-league")
async def import_espn_league(req: ESPNImportRequest, db: Session = Depends(get_db)):
    """Fetch ESPN Fantasy Baseball league roster and store in DB."""
    season = req.season or ESPN_SEASON
    print(f"[ESPN] Importing league {req.league_id} for season {season}")

    data = _fetch_espn_league(req.league_id, req.espn_s2, req.swid, season)

    league_name = data.get("settings", {}).get("name", f"ESPN League {req.league_id}")
    teams = data.get("teams", [])
    print(f"[ESPN] Found {len(teams)} teams in '{league_name}'")

    team_name_map = {}
    for t in teams:
        name = (t.get("name") or t.get("abbrev") or f"Team {t['id']}").strip()
        team_name_map[t["id"]] = name

    players_data = []
    for team in teams:
        owner_name = team_name_map[team["id"]]
        for entry in team.get("roster", {}).get("entries", []):
            lineup_slot = entry.get("lineupSlotId", 0)
            player = entry.get("playerPoolEntry", {}).get("player", {})
            player_name = player.get("fullName", "").strip()
            if not player_name:
                continue
            position = ESPN_POSITION_MAP.get(player.get("defaultPositionId", 0), "UTIL")
            mlb_team = ESPN_TEAM_MAP.get(player.get("proTeamId", 0), "")
            status = "IL" if lineup_slot in IL_SLOT_IDS else None
            players_data.append({
                "name": player_name,
                "team": mlb_team,
                "position": position,
                "owner": owner_name,
                "status": status,
            })

    print(f"[ESPN] Parsed {len(players_data)} players")

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
            pass

    if not user:
        user = User()
        db.add(user)
        db.flush()

    league = League(
        id=uuid.uuid4(),
        user_id=user.id,
        league_type="espn",
        csv_filename=f"espn_{req.league_id}"
    )
    db.add(league)
    db.flush()

    matcher = PlayerMatcher(db)
    roster_entries = []

    for pd in players_data:
        player = matcher.get_or_create_player(pd)
        roster_entries.append((player, pd))

    db.flush()

    for player, pd in roster_entries:
        db.add(Roster(
            league_id=league.id,
            player_id=player.id,
            team_owner=pd["owner"],
            status=pd.get("status")
        ))

    db.commit()

    team_owners = sorted(set(pd["owner"] for pd in players_data))
    print(f"[ESPN] Imported {len(players_data)} players across {len(team_owners)} teams")

    return {
        "id": str(league.id),
        "league_type": "espn",
        "total_players": len(players_data),
        "owned_players": len(players_data),
        "free_agents": 0,
        "teams": team_owners,
        "league_name": league_name
    }


class ESPNPlayerEntry(BaseModel):
    name: str
    team: str
    position: str
    owner: str
    status: Optional[str] = None


class ESPNParsedImportRequest(BaseModel):
    players: List[ESPNPlayerEntry]
    league_name: Optional[str] = None
    espn_league_id: Optional[str] = None
    existing_league_id: Optional[str] = None


def _save_espn_players(players_data: list, league_name: str, espn_league_id: str, existing_league_id: Optional[str], db: Session) -> dict:
    """Shared logic: given a list of player dicts, create/replace league in DB."""
    user = None
    if existing_league_id:
        try:
            old_uuid = uuid.UUID(existing_league_id)
            old_league = db.query(League).filter(League.id == old_uuid).first()
            if old_league:
                db.query(Roster).filter(Roster.league_id == old_uuid).delete()
                user = db.query(User).filter(User.id == old_league.user_id).first()
                db.delete(old_league)
                db.flush()
        except Exception:
            pass

    if not user:
        user = User()
        db.add(user)
        db.flush()

    league = League(
        id=uuid.uuid4(),
        user_id=user.id,
        league_type="espn",
        csv_filename=f"espn_{espn_league_id or 'unknown'}"
    )
    db.add(league)
    db.flush()

    matcher = PlayerMatcher(db)
    roster_entries = []
    for pd in players_data:
        player = matcher.get_or_create_player(pd)
        roster_entries.append((player, pd))
    db.flush()

    for player, pd in roster_entries:
        db.add(Roster(
            league_id=league.id,
            player_id=player.id,
            team_owner=pd["owner"],
            status=pd.get("status")
        ))

    db.commit()
    team_owners = sorted(set(pd["owner"] for pd in players_data))
    return {
        "id": str(league.id),
        "league_type": "espn",
        "total_players": len(players_data),
        "owned_players": len(players_data),
        "free_agents": 0,
        "teams": team_owners,
        "league_name": league_name or f"ESPN League {espn_league_id}"
    }


@router.post("/import-parsed")
async def import_espn_parsed(req: ESPNParsedImportRequest, db: Session = Depends(get_db)):
    """Accept pre-parsed ESPN roster data from the browser and store in DB.
    Used when the browser fetches ESPN directly (bypasses server IP blocks)."""
    players_data = [p.dict() for p in req.players]
    print(f"[ESPN] import-parsed: {len(players_data)} players, league='{req.league_name}'")
    if not players_data:
        raise HTTPException(status_code=400, detail="No player data received.")
    result = _save_espn_players(
        players_data,
        req.league_name or "",
        req.espn_league_id or "",
        req.existing_league_id,
        db
    )
    print(f"[ESPN] Saved parsed import: {result['total_players']} players, league_id={result['id']}")
    return result