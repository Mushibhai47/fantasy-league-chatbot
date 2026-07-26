"""NFL Custom Scoring Engine — all scoring is flat: api_field_value * weight"""
from typing import Dict, Optional

# ── Default weights (from Rudy's Custom Points spreadsheet) ───────────────
# Values are points-per-unit of the raw API stat field.
# Bonus fields (yards_passing_300 etc.) return a probability from the API,
# so the same formula applies: probability * user's bonus points value.
DEFAULT_WEIGHTS: Dict[str, float] = {
    # Passing
    "pass_yds":         0.04,
    "pass_td":          4.0,
    "int":             -2.0,
    "pass_tpc":         2.0,   # 2-pt conversion pass
    "cmp":              0.0,   # completions (0 by default)
    # Passing bonuses (API returns probability of hitting threshold)
    "yards_passing_300": 0.0,
    "yards_passing_400": 0.0,
    # Rushing
    "rush_yds":         0.1,
    "run_td":           6.0,
    "rush_tpc":         2.0,   # 2-pt conversion rush
    "fum_lost":        -2.0,
    # Rushing bonuses
    "yards_rushing_100": 0.0,
    "yards_rushing_150": 0.0,
    # Receiving
    "rec":              0.0,   # 0=standard, 0.5=half-PPR, 1.0=PPR
    "rec_yds":          0.1,
    "rec_td":           6.0,
    "rec_tpc":          2.0,   # 2-pt conversion reception
    # Receiving bonuses
    "yards_receiving_100": 0.0,
    "yards_receiving_150": 0.0,
    # Kicking
    "xp":               1.0,
    "fg":               3.0,
    "10-19_fg_made":    0.0,
    "20-29_fg_made":    0.0,
    "30-39_fg_made":    0.0,
    "40-49_fg_made":    0.0,
    "50+_fg_made":      0.0,
    "xp_missed":        0.0,   # computed as xpa - xp
    "fg_missed":        0.0,   # computed as fga - fg
}

# ── Named presets ──────────────────────────────────────────────────────────
def _preset(rec: float) -> Dict[str, float]:
    return {**DEFAULT_WEIGHTS, "rec": rec}

PRESET_PROFILES = {
    "standard":            _preset(0.0),
    "half_ppr":            _preset(0.5),
    "ppr":                 _preset(1.0),
    "superflex_half_ppr":  _preset(0.5),
}


def calc_points(player_row: dict, weights: Optional[Dict[str, float]] = None) -> float:
    """
    Calculate fantasy points for one NFL API player row.
    Every stat is: api_field_value * weight  (including probability-based bonus fields).
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    total = 0.0

    for field, pts_per in weights.items():
        if pts_per == 0.0:
            continue

        # Special computed fields
        if field == "xp_missed":
            try:
                val = max(float(player_row.get("xpa", 0) or 0) - float(player_row.get("xp", 0) or 0), 0)
            except (TypeError, ValueError):
                val = 0.0
        elif field == "fg_missed":
            try:
                val = max(float(player_row.get("fga", 0) or 0) - float(player_row.get("fg", 0) or 0), 0)
            except (TypeError, ValueError):
                val = 0.0
        else:
            raw = player_row.get(field)
            if raw is None:
                continue
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue

        total += val * pts_per

    return round(total, 2)


def score_player_list(players: list, weights: Optional[Dict[str, float]] = None) -> list:
    """Add 'custom_pts' to each player dict and return sorted by custom_pts desc."""
    if weights is None:
        weights = DEFAULT_WEIGHTS
    for p in players:
        p["custom_pts"] = calc_points(p, weights)
    return sorted(players, key=lambda x: x["custom_pts"], reverse=True)
