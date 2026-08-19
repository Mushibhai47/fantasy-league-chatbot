"""NFL Projection Service - Fetch player projections from Razzball NFL API"""
import requests
import logging
import os
import time
from typing import Dict, List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

_NFL_CACHE: Dict[str, dict] = {}       # key -> list of player dicts
_NFL_CACHE_TIME: Dict[str, float] = {}
_CACHE_TTL = 5 * 60  # 5 minutes

NFL_SEASON = "2026"
NFL_ROS_WEEK = "99"


def _api_headers() -> dict:
    api_key = os.getenv("RAZZBALL_API_KEY", "")
    return {
        "User-Agent": "PostmanRuntime/7.49.1",
        "Accept": "application/vnd.razzball-v1+json",
        "Razzball-Api-Key": api_key,
    }


def _api_base() -> str:
    base = os.getenv("RAZZBALL_API_BASE_URL", "https://api.razzball.com/mlb")
    return base.replace("/mlb", "")


def _fetch_nfl(week: str) -> List[dict]:
    """Fetch NFL projections for a given week (or '99' for ROS). Cached 5 min."""
    cache_key = f"nfl_{NFL_SEASON}_{week}"
    now = time.time()

    if cache_key in _NFL_CACHE:
        age = now - _NFL_CACHE_TIME.get(cache_key, 0)
        if age < _CACHE_TTL:
            logger.info(f"[NFL] Cache hit: week={week} ({len(_NFL_CACHE[cache_key])} players, age {int(age)}s)")
            return _NFL_CACHE[cache_key]

    url = f"{_api_base()}/nfl/projections/weekly/{NFL_SEASON}/{week}"
    logger.info(f"[NFL] Fetching projections: {url}")
    try:
        resp = requests.get(url, headers=_api_headers(), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        players = data.get("projections", data if isinstance(data, list) else [])

        # Strip stray \n from id_fantrax values
        for p in players:
            if p.get("id_fantrax"):
                p["id_fantrax"] = str(p["id_fantrax"]).strip()

        _NFL_CACHE[cache_key] = players
        _NFL_CACHE_TIME[cache_key] = now
        logger.info(f"[NFL] Fetched {len(players)} players for week={week}")
        return players
    except Exception as e:
        logger.error(f"[NFL] Fetch failed for week={week}: {e}")
        return _NFL_CACHE.get(cache_key, [])


def get_ros_projections() -> List[dict]:
    """Rest-of-season projections (week 99)."""
    return _fetch_nfl(NFL_ROS_WEEK)


def get_weekly_projections(week: int) -> List[dict]:
    """Weekly projections for a specific NFL week (1-18)."""
    return _fetch_nfl(str(week))


def _has_meaningful_data(players: List[dict]) -> bool:
    """Return True if any of the first 20 players has non-zero projected stats."""
    key_stats = ['pass_yds', 'rush_yds', 'rec_yds', 'pass_td', 'run_td', 'rec_td']
    for p in players[:20]:
        if any(float(p.get(s) or 0) > 0 for s in key_stats):
            return True
    return False


def get_best_weekly_projections(week: int = None) -> tuple:
    """
    Return (projections, label).
    Falls back to ROS when weekly data is empty (preseason / off-season).
    """
    if week:
        proj = get_weekly_projections(week)
        label = f"Week {week}"
    else:
        proj = get_weekly_projections(1)
        label = "This Week"

    if not _has_meaningful_data(proj):
        proj = get_ros_projections()
        label = "ROS (preseason — weekly projections not yet available)"

    return proj, label


def build_fantrax_lookup(players: List[dict]) -> Dict[str, dict]:
    """Return {fantrax_id -> player_row} for fast roster matching."""
    lookup = {}
    for p in players:
        fid = p.get("id_fantrax", "")
        if fid and fid not in ("None", ""):
            lookup[fid] = p
    return lookup


def build_yahoo_lookup(players: List[dict]) -> Dict[str, dict]:
    """Return {yahoo_id -> player_row} for Yahoo league matching."""
    lookup = {}
    for p in players:
        yid = str(p.get("id_yahoo", "")).strip()
        if yid and yid not in ("None", "0", ""):
            lookup[yid] = p
    return lookup


def build_nfbc_lookup(players: List[dict]) -> Dict[str, dict]:
    """Return {id_nffc -> player_row} for NFBC/NFFC league matching."""
    lookup = {}
    for p in players:
        nid = str(p.get("id_nffc", "")).strip()
        if nid and nid not in ("None", "0", ""):
            lookup[nid] = p
    return lookup


def calc_custom_points(player_row: dict, scoring: dict) -> float:
    """
    Calculate fantasy points from raw stat projections using a custom scoring dict.

    scoring keys match API stat field names, values are points-per-unit.
    Example:
        {"pass_yds": 0.04, "pass_td": 4, "int": -2, "rush_yds": 0.1,
         "run_td": 6, "rec": 0.5, "rec_yds": 0.1, "rec_td": 6, "fum_lost": -2}
    """
    total = 0.0
    for stat, pts_per in scoring.items():
        try:
            val = float(player_row.get(stat, 0) or 0)
            total += val * pts_per
        except (TypeError, ValueError):
            pass
    return round(total, 2)


# Standard scoring presets (used as defaults until user saves a custom profile)
SCORING_PRESETS = {
    "standard": {
        "pass_yds": 0.04, "pass_td": 4, "int": -2,
        "rush_yds": 0.1, "run_td": 6,
        "rec": 0, "rec_yds": 0.1, "rec_td": 6,
        "fum_lost": -2,
    },
    "half_ppr": {
        "pass_yds": 0.04, "pass_td": 4, "int": -2,
        "rush_yds": 0.1, "run_td": 6,
        "rec": 0.5, "rec_yds": 0.1, "rec_td": 6,
        "fum_lost": -2,
    },
    "ppr": {
        "pass_yds": 0.04, "pass_td": 4, "int": -2,
        "rush_yds": 0.1, "run_td": 6,
        "rec": 1.0, "rec_yds": 0.1, "rec_td": 6,
        "fum_lost": -2,
    },
    "superflex_half_ppr": {
        "pass_yds": 0.04, "pass_td": 4, "int": -2,
        "rush_yds": 0.1, "run_td": 6,
        "rec": 0.5, "rec_yds": 0.1, "rec_td": 6,
        "fum_lost": -2,
    },
}
