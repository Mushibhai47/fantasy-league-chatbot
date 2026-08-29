"""NFL Custom Scoring Engine — all scoring is flat: api_field_value * weight"""
from typing import Dict, Optional

# ── Default weights (from Rudy's Custom Points spreadsheet) ───────────────
# Values are points-per-unit of the raw API stat field.
# Bonus fields (yards_passing_300 etc.) return a probability from the API,
# so the same formula applies: probability * user's bonus points value.
DEFAULT_WEIGHTS: Dict[str, float] = {
    # Passing
    "pass_yds":           0.04,
    "pass_td":            4.0,
    "int":               -2.0,
    "pass_tpc":           2.0,
    "cmp":                0.0,
    "yards_passing_300":  0.0,
    "yards_passing_400":  0.0,
    # Rushing
    "rush_yds":           0.1,
    "run_td":             6.0,
    "rush_tpc":           2.0,
    "fum_lost":          -2.0,
    "yards_rushing_100":  0.0,
    "yards_rushing_150":  0.0,
    # Receiving
    "rec":                0.0,   # 0=STD, 0.5=half-PPR, 1.0=PPR
    "rec_yds":            0.1,
    "rec_td":             6.0,
    "rec_tpc":            2.0,
    "yards_receiving_100": 0.0,
    "yards_receiving_150": 0.0,
    # Kicking
    "xp":                 1.0,
    "fg":                 3.0,
    "10-19_fg_made":      0.0,
    "20-29_fg_made":      0.0,
    "30-39_fg_made":      0.0,
    "40-49_fg_made":      0.0,
    "50+_fg_made":        0.0,
    "xp_missed":          0.0,
    "fg_missed":          0.0,
    # Defense / Special Teams
    "sacks_def":          1.0,
    "int_def":            2.0,
    "fum_def_recovered":  2.0,
    "saf":                2.0,
    "td_def_return":      6.0,
    "Points_Zero":        5.0,
    "Points_1to6":        4.0,
    "Points_7to13":       3.0,
    "Points_14to20":      1.0,
    "Points_21to27":      0.0,
    "Points_28to34":     -1.0,
    "Points_35+":        -3.0,
    # IDP
    "tackles_solo":       1.0,
    "tackles_ast":        0.5,
    "fum_def":            2.0,
    "pass_def":           1.0,
}

# ── Named presets ──────────────────────────────────────────────────────────
def _preset(rec: float) -> Dict[str, float]:
    return {**DEFAULT_WEIGHTS, "rec": rec}

PRESET_PROFILES = {
    "standard":   _preset(0.0),
    "half_ppr":   _preset(0.5),
    "ppr":        _preset(1.0),
    "custom":     _preset(0.0),   # custom starts from STD; frontend sends overrides via scoring_weights
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


_API_PRESET_FIELD = {
    "standard":  "std_pts",
    "half_ppr":  "halfppr_pts",
    "ppr":       "ppr_pts",
}


def get_pts(player_row: dict, weights: Optional[Dict[str, float]] = None, preset: Optional[str] = None) -> float:
    """Use API pre-calculated pts for standard presets; fall back to calc_points for custom."""
    if preset in _API_PRESET_FIELD:
        api_val = player_row.get(_API_PRESET_FIELD[preset])
        if api_val is not None:
            try:
                return round(float(api_val), 2)
            except (TypeError, ValueError):
                pass
    return calc_points(player_row, weights)


def score_player_list(players: list, weights: Optional[Dict[str, float]] = None) -> list:
    """Add 'custom_pts' to each player dict and return sorted by custom_pts desc."""
    if weights is None:
        weights = DEFAULT_WEIGHTS
    for p in players:
        p["custom_pts"] = calc_points(p, weights)
    return sorted(players, key=lambda x: x["custom_pts"], reverse=True)
