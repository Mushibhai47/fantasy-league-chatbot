"""Sleeper Fantasy API Service — no auth required, all public GET endpoints."""
import requests
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SLEEPER_API = "https://api.sleeper.app/v1"

# In-memory cache for the 10 MB+ players file — refreshed every 24 h per process
_PLAYERS_CACHE: Dict[str, dict] = {}
_PLAYERS_CACHE_TS: float = 0.0
_CACHE_TTL = 86_400  # 24 hours

# Sleeper scoring field names → our nfl_scoring.py weight keys
SCORING_MAP = {
    "pass_yd":           "pass_yds",
    "pass_td":           "pass_td",
    "pass_int":          "int",
    "int":               "int",
    "rush_yd":           "rush_yds",
    "rush_td":           "run_td",
    "rec_yd":            "rec_yds",
    "rec_td":            "rec_td",
    "rec":               "rec",
    "fum_lost":          "fum_lost",
    "bonus_pass_yd_300": "yards_passing_300",
    "bonus_pass_yd_400": "yards_passing_400",
    "bonus_rush_yd_100": "yards_rushing_100",
    "bonus_rush_yd_150": "yards_rushing_150",
    "bonus_rec_yd_100":  "yards_receiving_100",
    "bonus_rec_yd_150":  "yards_receiving_150",
    "xpm":               "xp",
    "fgm":               "fg",
    "xpmiss":            "xp_missed",
    "fgmiss":            "fg_missed",
    "sack":              "sacks_def",
    "safe":              "saf",
    "def_td":            "td_def_return",
    "pts_allow_0":       "Points_Zero",
    "pts_allow_1_6":     "Points_1to6",
    "pts_allow_7_13":    "Points_7to13",
    "pts_allow_14_20":   "Points_14to20",
    "pts_allow_21_27":   "Points_21to27",
    "pts_allow_28_34":   "Points_28to34",
    "pts_allow_35p":     "Points_35+",
}


def _get(url: str) -> any:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


# ── User / league lookup ─────────────────────────────────────────────────────

def lookup_user(username_or_id: str) -> dict:
    """Accepts a Sleeper username or numeric user_id. Returns the user object."""
    return _get(f"{SLEEPER_API}/user/{username_or_id}")


def get_user_leagues(user_id: str, sport: str = "nfl", season: str = "2026") -> List[dict]:
    """All leagues for a user in a given sport/season."""
    return _get(f"{SLEEPER_API}/user/{user_id}/leagues/{sport}/{season}") or []


def get_user_leagues_multi_season(user_id: str, sport: str = "nfl") -> List[dict]:
    """Try the current season, fall back to the previous one if empty."""
    from app.services.nfl_projection_service import NFL_SEASON
    seasons = [NFL_SEASON, str(int(NFL_SEASON) - 1)]
    for s in seasons:
        leagues = get_user_leagues(user_id, sport, s)
        if leagues:
            return leagues
    return []


def get_league_info(league_id: str) -> dict:
    return _get(f"{SLEEPER_API}/league/{league_id}")


def get_league_rosters(league_id: str) -> List[dict]:
    return _get(f"{SLEEPER_API}/league/{league_id}/rosters") or []


def get_league_users(league_id: str) -> List[dict]:
    return _get(f"{SLEEPER_API}/league/{league_id}/users") or []


# ── Player cache ─────────────────────────────────────────────────────────────

def get_players_cache(sport: str = "nfl") -> Dict[str, dict]:
    """Fetch the master player map (player_id → info). Cached 24 h in memory."""
    global _PLAYERS_CACHE, _PLAYERS_CACHE_TS
    now = time.time()
    if not _PLAYERS_CACHE or (now - _PLAYERS_CACHE_TS) > _CACHE_TTL:
        logger.info("[Sleeper] Fetching players cache from API...")
        _PLAYERS_CACHE = _get(f"{SLEEPER_API}/players/{sport}")
        _PLAYERS_CACHE_TS = now
        logger.info(f"[Sleeper] Players cache loaded: {len(_PLAYERS_CACHE)} entries")
    return _PLAYERS_CACHE


# ── Scoring helpers ───────────────────────────────────────────────────────────

def map_scoring_settings(sleeper_settings: dict) -> dict:
    """Convert a Sleeper scoring_settings dict to our nfl_scoring weight keys."""
    from app.services.nfl_scoring import DEFAULT_WEIGHTS
    weights = dict(DEFAULT_WEIGHTS)
    for sleeper_key, our_key in SCORING_MAP.items():
        if sleeper_key in sleeper_settings:
            try:
                weights[our_key] = float(sleeper_settings[sleeper_key])
            except (TypeError, ValueError):
                pass
    return weights


def detect_preset(weights: dict) -> Optional[str]:
    """Detect if a weight dict matches standard / half_ppr / ppr."""
    rec = weights.get("rec", 0.0)
    if rec == 0.0:
        return "standard"
    elif rec == 0.5:
        return "half_ppr"
    elif rec == 1.0:
        return "ppr"
    return None


# ── Main data builder ─────────────────────────────────────────────────────────

def build_league_data(league_id: str) -> dict:
    """
    Fetch everything for a Sleeper league and return it in our standard format.
    Returns:
        league_name, sport, players_data (list of dicts), weights, preset, teams
    """
    league_info = get_league_info(league_id)
    sport = league_info.get("sport", "nfl")

    # owner_id → display name / team name
    users_list = get_league_users(league_id)
    user_map: Dict[str, str] = {}
    for u in users_list:
        team_name = (u.get("metadata") or {}).get("team_name") or u.get("display_name", "Unknown")
        user_map[u["user_id"]] = team_name

    # Rosters
    rosters_list = get_league_rosters(league_id)

    # Player lookup (cached)
    players_cache = get_players_cache(sport)

    players_data: List[dict] = []
    for roster in rosters_list:
        owner_id = roster.get("owner_id")
        team_name = user_map.get(owner_id, f"Team {roster.get('roster_id', '?')}")
        all_ids = roster.get("players") or []

        for player_id in all_ids:
            info = players_cache.get(str(player_id), {})
            name = info.get("full_name") or ""
            if not name:
                continue
            positions = info.get("fantasy_positions") or []
            position = positions[0] if positions else info.get("position", "")
            nfl_team = info.get("team") or ""

            players_data.append({
                "name": name,
                "position": position,
                "team": nfl_team,
                "mlb_team": nfl_team,  # PlayerMatcher uses mlb_team key
                "owner": team_name,
                "sleeper_id": str(player_id),
                "league_type": "sleeper",
            })

    # Scoring
    scoring_settings = league_info.get("scoring_settings") or {}
    weights = map_scoring_settings(scoring_settings)
    preset = detect_preset(weights)

    teams = sorted(set(p["owner"] for p in players_data))

    return {
        "league_name": league_info.get("name", "Sleeper League"),
        "sport": sport,
        "players_data": players_data,
        "weights": weights,
        "preset": preset,
        "teams": teams,
        "total_rosters": league_info.get("total_rosters", 0),
    }
