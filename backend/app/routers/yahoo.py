"""Yahoo Fantasy Sports OAuth Router"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, League, Roster
from app.models.player import Player
from app.services.player_matcher import PlayerMatcher
from app.config import get_settings
import requests
import base64
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

router = APIRouter()
settings = get_settings()

YAHOO_AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
YAHOO_TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
YAHOO_API_BASE = "https://fantasysports.yahooapis.com/fantasy/v2"
YAHOO_MLB_GAME_ID = "422"  # 2026 MLB season game ID


def _get_credentials():
    client_id = getattr(settings, 'YAHOO_CLIENT_ID', None)
    client_secret = getattr(settings, 'YAHOO_CLIENT_SECRET', None)
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Yahoo API not configured")
    return client_id, client_secret


def _get_redirect_uri():
    base = getattr(settings, 'APP_BASE_URL', 'https://valiant-healing-production-ce05.up.railway.app')
    return f"{base}/api/yahoo/callback"


def _exchange_code_for_token(code: str, client_id: str, client_secret: str) -> dict:
    """Exchange authorization code for access + refresh tokens."""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        YAHOO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _get_redirect_uri(),
        },
        timeout=15
    )
    if not resp.ok:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {resp.text}")
    return resp.json()


def _refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict:
    """Refresh an expired access token."""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        YAHOO_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=15
    )
    if not resp.ok:
        raise HTTPException(status_code=400, detail=f"Token refresh failed: {resp.text}")
    return resp.json()


def _yahoo_api_get(url: str, access_token: str) -> ET.Element:
    """Make a Yahoo Fantasy API GET request, returns parsed XML root."""
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20
    )
    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=f"Yahoo API error: {resp.text}")
    root = ET.fromstring(resp.text)
    return root


def _parse_yahoo_roster(xml_root: ET.Element) -> list:
    """Parse Yahoo Fantasy roster XML into list of player dicts."""
    ns = {'y': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}
    players = []

    for player_el in xml_root.iter('{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}player'):
        name_el = player_el.find('.//{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}full')
        team_el = player_el.find('.//{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}editorial_team_abbr')
        pos_el = player_el.find('.//{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}display_position')
        yahoo_id_el = player_el.find('{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}player_id')
        ownership_el = player_el.find('.//{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}ownership_type')

        name = name_el.text if name_el is not None else ''
        team = team_el.text.upper() if team_el is not None else ''
        position = pos_el.text if pos_el is not None else ''
        yahoo_id = yahoo_id_el.text if yahoo_id_el is not None else ''
        ownership = ownership_el.text if ownership_el is not None else 'freeagent'

        owner = 'Free Agent' if ownership in ('freeagent', 'waivers') else ownership

        players.append({
            'yahoo_id': yahoo_id,
            'name': name,
            'mlb_team': team,
            'position': position,
            'owner': owner,
            'league_type': 'yahoo',
        })

    return players


@router.get("/auth")
async def yahoo_auth():
    """Redirect user to Yahoo OAuth authorization page."""
    client_id, _ = _get_credentials()
    redirect_uri = _get_redirect_uri()
    auth_url = (
        f"{YAHOO_AUTH_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&language=en-us"
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def yahoo_callback(
    code: str = Query(...),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Handle Yahoo OAuth callback, exchange code for tokens, fetch roster."""
    client_id, client_secret = _get_credentials()

    # Exchange code for tokens
    token_data = _exchange_code_for_token(code, client_id, client_secret)
    access_token = token_data['access_token']
    refresh_token = token_data.get('refresh_token', '')

    # Get user's leagues
    leagues_url = f"{YAHOO_API_BASE}/users;use_login=1/games;game_keys={YAHOO_MLB_GAME_ID}/leagues"
    try:
        xml_root = _yahoo_api_get(leagues_url, access_token)
        league_keys = []
        for league_el in xml_root.iter('{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}league_key'):
            league_keys.append(league_el.text)
    except Exception:
        league_keys = []

    # Redirect back to site with tokens and league keys in URL fragment
    # (frontend picks these up and stores them)
    frontend_url = getattr(settings, 'FRONTEND_URL', 'https://razzball.com')
    token_param = base64.b64encode(f"{access_token}:{refresh_token}".encode()).decode()
    leagues_param = ','.join(league_keys)

    redirect_url = f"{frontend_url}?yahoo_token={token_param}&yahoo_leagues={leagues_param}"
    return RedirectResponse(url=redirect_url)


@router.post("/import-league")
async def import_yahoo_league(
    league_key: str,
    access_token: str,
    refresh_token: str,
    existing_league_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Fetch roster from Yahoo Fantasy API and store in DB."""
    client_id, client_secret = _get_credentials()

    # Try fetching roster, refresh token if expired
    roster_url = f"{YAHOO_API_BASE}/league/{league_key}/players;status=T"
    try:
        xml_root = _yahoo_api_get(roster_url, access_token)
    except HTTPException as e:
        if e.status_code == 401:
            # Token expired, refresh it
            token_data = _refresh_access_token(refresh_token, client_id, client_secret)
            access_token = token_data['access_token']
            refresh_token = token_data.get('refresh_token', refresh_token)
            xml_root = _yahoo_api_get(roster_url, access_token)
        else:
            raise

    players_data = _parse_yahoo_roster(xml_root)
    if not players_data:
        raise HTTPException(status_code=404, detail="No players found in Yahoo league")

    # Delete old league data if re-importing
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
            user = None
    else:
        user = None

    if not user:
        user = User()
        db.add(user)
        db.flush()

    league = League(
        id=uuid.uuid4(),
        user_id=user.id,
        league_type='yahoo',
        csv_filename=f"yahoo_{league_key}"
    )
    db.add(league)
    db.flush()

    # Match and store players
    matcher = PlayerMatcher(db)
    owned_count = 0
    free_agent_count = 0
    player_owner_pairs = []

    for player_data in players_data:
        if player_data['owner'] == 'Free Agent':
            free_agent_count += 1
            continue  # Don't store free agents — saves 97% of DB space
        player = matcher.get_or_create_player(player_data)
        player_owner_pairs.append((player, player_data))
        owned_count += 1

    db.flush()

    roster_entries = []
    for player, player_data in player_owner_pairs:
        roster = Roster(
            league_id=league.id,
            player_id=player.id,
            team_owner=player_data['owner'],
            status=None
        )
        roster_entries.append(roster)

    for r in roster_entries:
        db.add(r)
    db.commit()

    team_owners = sorted(set(
        r.team_owner for r in roster_entries
        if r.team_owner and r.team_owner != 'Free Agent'
    ))

    return {
        "id": str(league.id),
        "league_type": "yahoo",
        "league_key": league_key,
        "total_players": len(players_data),
        "owned_players": owned_count,
        "free_agents": free_agent_count,
        "teams": team_owners,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


@router.get("/game-id")
async def get_mlb_game_id(access_token: str):
    """Helper: find the current MLB game ID for the logged-in user."""
    url = f"{YAHOO_API_BASE}/games;is_available=1;game_types=full;game_codes=mlb"
    xml_root = _yahoo_api_get(url, access_token)
    games = []
    for game_el in xml_root.iter('{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}game'):
        gk = game_el.find('{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}game_key')
        gn = game_el.find('{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}name')
        sy = game_el.find('{http://fantasysports.yahooapis.com/fantasy/v2/base.rng}season')
        if gk is not None:
            games.append({"key": gk.text, "name": gn.text if gn is not None else '', "season": sy.text if sy is not None else ''})
    return {"games": games}
