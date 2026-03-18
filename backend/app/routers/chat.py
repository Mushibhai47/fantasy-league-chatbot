"""Chat Router - GPT-4o-mini Powered Fantasy Baseball Assistant with Razzball Projections"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import League, Roster, Chat, Player, User
from app.services.openai_service import OpenAIService
from app.services.projection_service import ProjectionService
from app.services.message_limit_service import MessageLimitService
from app.schemas.chat import ChatRequest, ChatResponse
import pandas as pd
import logging
import re as _re

logger = logging.getLogger(__name__)
router = APIRouter()

# Global projection caches (fetched once, reused for all chats)
_projections_df = None
_weekly_projections_df = None
_daily_projections_df = None
_daily_cache_date = None  # EST date when daily cache was last populated

# CBS team code differences between CBS Sports CSV exports and the Razzball projection API
_CBS_TEAM_MAP = {'CHW': 'CWS', 'WAS': 'WSN'}


def _normalize_cbs_name(cbs_str: str) -> str:
    """Normalize a CBS Sports player name for flexible matching.

    Handles team code differences (CHW→CWS), Jr./Sr. suffixes, and
    multi-position formats (2B,3B vs 2B) so that names from the CBS CSV
    and from the Razzball projection API can be compared reliably.

    Examples:
        'Jazz Chisholm 2B,3B | NYY'  →  'jazz chisholm|NYY'
        'Jazz Chisholm Jr. 2B | NYY' →  'jazz chisholm|NYY'
        'Cameron Schlittler P | CHW' →  'cameron schlittler|CWS'
    """
    if not cbs_str:
        return ''
    parts = str(cbs_str).split('|')
    team = parts[1].strip().upper() if len(parts) > 1 else ''
    team = _CBS_TEAM_MAP.get(team, team)
    # Remove trailing position token(s) — e.g. "OF", "2B,3B", "SP", "P", "1B/DH"
    name_tokens = parts[0].strip().split()
    while name_tokens and _re.match(r'^[A-Z0-9,/]+$', name_tokens[-1]):
        name_tokens.pop()
    name = ' '.join(name_tokens)
    # Lowercase, strip Jr./Sr./II/III, strip periods
    name = name.lower()
    name = _re.sub(r'\b(jr\.?|sr\.?|ii+|iii+)\b', '', name)
    name = name.replace('.', '').replace('  ', ' ').strip()
    return f"{name}|{team}"


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    FAST Chat with GPT-4o-mini AI assistant about fantasy baseball roster
    No external API calls - uses only database data for speed
    """
    try:
        # Get league
        league = db.query(League).filter(League.id == request.league_id).first()
        if not league:
            raise HTTPException(status_code=404, detail="League not found")

        # Check message limits (unless user provides their own API key)
        messages_remaining = None
        limit_message = None

        if not request.user_api_key:
            # User is using backend API key, so enforce limits
            user_id = request.user_id or str(request.league_id)  # Use league_id as fallback
            user = MessageLimitService.get_or_create_user(user_id, db)

            # Check if user can send message
            can_send, remaining, message = MessageLimitService.can_send_message(user, db)

            if not can_send:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Daily message limit reached",
                        "message": message,
                        "messages_remaining": 0,
                        "reset_date": user.limit_reset_date.isoformat()
                    }
                )

            messages_remaining = remaining
            limit_message = message
            logger.info(f"User {user_id}: {remaining} messages remaining")

        # Get ALL owned players (no limit - need full rosters for accurate analysis)
        owned_rosters = db.query(Roster).options(
            joinedload(Roster.player)
        ).filter(
            Roster.league_id == request.league_id,
            Roster.team_owner != 'Free Agent'
        ).all()

        # Fallback: try string comparison if no results
        if not owned_rosters:
            logger.info(f"Trying string league_id: {str(request.league_id)}")
            owned_rosters = db.query(Roster).options(
                joinedload(Roster.player)
            ).filter(
                Roster.league_id == str(request.league_id),
                Roster.team_owner != 'Free Agent'
            ).all()

        # Get FREE AGENTS separately (no limit - we sort by $ later)
        fa_rosters = db.query(Roster).options(
            joinedload(Roster.player)
        ).filter(
            Roster.league_id == request.league_id,
            Roster.team_owner == 'Free Agent'
        ).all()

        # Fallback for free agents too
        if not fa_rosters:
            fa_rosters = db.query(Roster).options(
                joinedload(Roster.player)
            ).filter(
                Roster.league_id == str(request.league_id),
                Roster.team_owner == 'Free Agent'
            ).all()

        # Combine
        all_rosters = owned_rosters + fa_rosters
        logger.info(f"Found {len(owned_rosters)} owned players, {len(fa_rosters)} free agents")

        # Debug: log unique owners to see what's in the database
        if owned_rosters:
            unique_owners = set(r.team_owner for r in owned_rosters[:20])
            logger.info(f"Sample owners in DB: {unique_owners}")

        # Get projections (cached globally - only slow on first request)
        global _projections_df
        dollar_lookup = {}

        # PERFORMANCE FIX: Only fetch if cache is empty
        if _projections_df is None or len(_projections_df) == 0:
            logger.info("⏳ Fetching projections (first time only)...")
            projection_service = ProjectionService(projection_type="ros")
            try:
                _projections_df = projection_service.fetch_projections()
                logger.info(f"✅ Projections cached: {len(_projections_df)} players")
            except Exception as e:
                logger.warning(f"⚠️ Could not fetch projections: {e}")
                _projections_df = None
        else:
            logger.info(f"✅ Using cached projections: {len(_projections_df)} players")

        # Build fast lookup dictionaries from cache (by NFBCID, FantraxID, and name)
        # Detect requested league type — frontend selection takes priority, then message keyword
        AVAILABLE_LEAGUE_TYPES = ["MLB12", "MLB12_5X5OBP", "MLB12_6X6OBP", "MLB12_6X6HLD", "MLB12_6X6QS", "MLB15", "MLB15_5X5OBP", "MLB10", "AL12", "NL12"]
        DEFAULT_LEAGUE_TYPE = "MLB12"

        import re
        requested_type = DEFAULT_LEAGUE_TYPE
        # 1. Use frontend-selected league type if provided
        if request.league_type and request.league_type.upper() in AVAILABLE_LEAGUE_TYPES:
            requested_type = request.league_type.upper()
        else:
            # 2. Detect from message text as fallback
            msg_upper = request.message.upper()
            for lt in AVAILABLE_LEAGUE_TYPES:
                if lt in msg_upper:
                    requested_type = lt
                    break

        nfbc_lookup = {}  # NFBCID -> full projection data string
        fantrax_lookup = {}  # FantraxID -> full projection data string
        cbs_name_lookup = {}  # normalized CBSSportsName -> full projection data string
        name_lookup = {}  # name -> full projection data string
        proj_pos_lookup = {}  # NFBCID/FantraxID -> Pos from projection data (for display)

        if _projections_df is not None:
            try:
                # Filter to requested league type
                filtered_df = _projections_df
                if 'LeagueType' in _projections_df.columns:
                    type_df = _projections_df[_projections_df['LeagueType'] == requested_type]
                    if len(type_df) > 0:
                        filtered_df = type_df
                        logger.info(f"📊 Filtered to {requested_type}: {len(filtered_df)} players")
                    else:
                        # Fallback to default if requested type not found
                        mlb12_df = _projections_df[_projections_df['LeagueType'] == DEFAULT_LEAGUE_TYPE]
                        if len(mlb12_df) > 0:
                            filtered_df = mlb12_df
                            requested_type = DEFAULT_LEAGUE_TYPE
                            logger.info(f"⚠️ Requested type not found, fell back to {DEFAULT_LEAGUE_TYPE}: {len(filtered_df)} players")
                        else:
                            logger.info(f"⚠️ No league type data found, using all")

                for _, row in filtered_df.iterrows():
                    # Determine if pitcher based on Pos
                    pos = str(row.get('Pos', '')).upper()
                    is_pitcher = pos in ('SP', 'RP', 'P')

                    # Build a rich dollar value string with category breakdowns
                    dollar_parts = []

                    # Overall dollar value
                    overall = row.get('$', row.get('dollar_value', ''))
                    if overall and str(overall) not in ('nan', 'None', ''):
                        dollar_parts.append(f"${overall}")

                    # Points value (for points leagues)
                    pts = row.get('PTS', '')
                    if pts and str(pts) not in ('nan', 'None', ''):
                        dollar_parts.append(f"PTS:{pts}")

                    # Per-game value
                    per_game = row.get('$/G$', '')
                    if per_game and str(per_game) not in ('nan', 'None', ''):
                        dollar_parts.append(f"$/G:{per_game}")

                    if is_pitcher:
                        # Pitcher categories ONLY
                        for cat in ['$W$', '$SV$', '$K$', '$ERA$', '$WHIP$', '$QS$', '$HLD$']:
                            val = row.get(cat, '')
                            if val and str(val) not in ('nan', 'None', ''):
                                cat_name = cat.replace('$', '')
                                dollar_parts.append(f"${cat_name}:{val}")
                    else:
                        # Hitter categories ONLY
                        for cat in ['$R$', '$HR$', '$RBI$', '$SB$', '$AVG$', '$OBP$']:
                            val = row.get(cat, '')
                            if val and str(val) not in ('nan', 'None', ''):
                                cat_name = cat.replace('$', '')
                                dollar_parts.append(f"${cat_name}:{val}")

                    dollar_str = ' '.join(dollar_parts) if dollar_parts else ''

                    # Always store position (even if no dollar value)
                    nfbc_id = row.get('NFBCID', '')
                    fantrax_id = row.get('FantraxID', '')
                    row_pos = str(row.get('Pos', '')).strip()
                    if row_pos and row_pos not in ('nan', 'None', ''):
                        if nfbc_id and str(nfbc_id) not in ('nan', 'None', ''):
                            proj_pos_lookup[str(nfbc_id)] = row_pos
                        if fantrax_id and str(fantrax_id) not in ('nan', 'None', ''):
                            proj_pos_lookup[str(fantrax_id)] = row_pos
                        # Also store by CBS name key for CBS leagues
                        cbs_sn_pos = str(row.get('CBSSportsName', ''))
                        if cbs_sn_pos and cbs_sn_pos not in ('nan', 'None', ''):
                            cbs_pos_key = _normalize_cbs_name(cbs_sn_pos)
                            if cbs_pos_key:
                                proj_pos_lookup[cbs_pos_key] = row_pos

                    if dollar_str:
                        # Store by NFBCID (most reliable for NFBC CSVs)
                        if nfbc_id and str(nfbc_id) not in ('nan', 'None', ''):
                            nfbc_lookup[str(nfbc_id)] = dollar_str

                        # Store by FantraxID
                        if fantrax_id and str(fantrax_id) not in ('nan', 'None', ''):
                            fantrax_lookup[str(fantrax_id)] = dollar_str

                        # Store by normalized CBSSportsName (most reliable for CBS leagues)
                        cbs_sn = str(row.get('CBSSportsName', ''))
                        if cbs_sn and cbs_sn not in ('nan', 'None', ''):
                            cbs_key = _normalize_cbs_name(cbs_sn)
                            if cbs_key:
                                cbs_name_lookup[cbs_key] = dollar_str

                        # Store by name (fallback)
                        proj_name = str(row.get('Name', '')).lower()
                        proj_name = re.sub(r'\[player id=\d+\]|\[/player\]', '', proj_name).strip()
                        if proj_name:
                            name_lookup[proj_name] = dollar_str

                # Second pass: fill CBS entries that LeagueType filtering may have excluded
                # (e.g. a player only in MLB12 data when requested_type filtered to AL12/NL12)
                if filtered_df is not _projections_df and 'CBSSportsName' in _projections_df.columns:
                    for _, row2 in _projections_df.iterrows():
                        cbs_sn2 = str(row2.get('CBSSportsName', ''))
                        if not cbs_sn2 or cbs_sn2 in ('nan', 'None', ''):
                            continue
                        cbs_key2 = _normalize_cbs_name(cbs_sn2)
                        if not cbs_key2 or cbs_key2 in cbs_name_lookup:
                            continue  # Already captured from filtered data — don't override
                        pos2 = str(row2.get('Pos', '')).upper()
                        is_p2 = pos2 in ('SP', 'RP', 'P')
                        dp2 = []
                        overall2 = row2.get('$', row2.get('dollar_value', ''))
                        if overall2 and str(overall2) not in ('nan', 'None', ''):
                            dp2.append(f"${overall2}")
                        pts2 = row2.get('PTS', '')
                        if pts2 and str(pts2) not in ('nan', 'None', ''):
                            dp2.append(f"PTS:{pts2}")
                        pg2 = row2.get('$/G$', '')
                        if pg2 and str(pg2) not in ('nan', 'None', ''):
                            dp2.append(f"$/G:{pg2}")
                        for cat2 in (['$W$', '$SV$', '$K$', '$ERA$', '$WHIP$', '$QS$', '$HLD$'] if is_p2 else ['$R$', '$HR$', '$RBI$', '$SB$', '$AVG$', '$OBP$']):
                            v2 = row2.get(cat2, '')
                            if v2 and str(v2) not in ('nan', 'None', ''):
                                dp2.append(f"${cat2.replace('$', '')}:{v2}")
                        ds2 = ' '.join(dp2) if dp2 else ''
                        if ds2:
                            cbs_name_lookup[cbs_key2] = ds2
                        if cbs_key2 not in proj_pos_lookup and pos2 and pos2 not in ('nan', 'None', ''):
                            proj_pos_lookup[cbs_key2] = pos2

                logger.info(f"💰 Lookups ready ({requested_type}): {len(nfbc_lookup)} NFBC, {len(fantrax_lookup)} Fantrax, {len(cbs_name_lookup)} CBS, {len(name_lookup)} by name")
            except Exception as e:
                logger.warning(f"⚠️ Could not build dollar lookup: {e}")

        def get_player_dollar_value(player_name: str, player_obj=None) -> str:
            """Get dollar value using NFBCID/FantraxID first, then name fallback"""
            # Try NFBCID first (most reliable for NFBC CSVs)
            if player_obj and player_obj.nfbc_id:
                val = nfbc_lookup.get(str(player_obj.nfbc_id), '')
                if val:
                    return f" [{val}]"

            # Try FantraxID
            if player_obj and player_obj.fantrax_id:
                val = fantrax_lookup.get(str(player_obj.fantrax_id), '')
                if val:
                    return f" [{val}]"

            # Try CBSSportsName (most reliable for CBS leagues — handles name mismatches like Colby/Cody)
            if player_obj and player_obj.cbs_player_name:
                cbs_key = _normalize_cbs_name(str(player_obj.cbs_player_name))
                if cbs_key:
                    val = cbs_name_lookup.get(cbs_key, '')
                    if val:
                        return f" [{val}]"
                    # CBS player with no exact CBS key match — stop here, no name guessing
                    logger.debug(f"CBS miss: key='{cbs_key}' not in cbs_name_lookup ({len(cbs_name_lookup)} entries)")
                    return ""

            # Fallback to exact name matching only (no partial/fuzzy — avoids wrong-player matches)
            name_lower = player_name.lower().strip()
            if name_lower in name_lookup:
                return f" [{name_lookup[name_lower]}]"
            return ""

        # ============================================================
        # PLATFORM-AWARE MATCHING HELPERS
        # ============================================================
        def get_player_id_for_col(player_obj, id_col: str) -> str:
            """Return the player's ID value for the given id_col (NFBCID / FantraxID / CBSSportsName)."""
            if id_col == 'FantraxID':
                return str(player_obj.fantrax_id) if player_obj.fantrax_id else ''
            elif id_col == 'CBSSportsName':
                # Normalize so CHW→CWS, Jr. stripped, position removed — matches API format
                raw = str(player_obj.cbs_player_name) if player_obj.cbs_player_name else ''
                return _normalize_cbs_name(raw) if raw else ''
            else:  # NFBCID (default)
                return str(player_obj.nfbc_id) if player_obj.nfbc_id else ''

        def resolve_id_col(df) -> str:
            """Choose the best ID column that actually exists in df for this league type.
            IMPORTANT: must be called first so roster lookups use the same column."""
            if league.league_type == 'fantrax' and 'FantraxID' in df.columns:
                return 'FantraxID'
            elif league.league_type == 'cbs' and 'CBSSportsName' in df.columns:
                return 'CBSSportsName'
            elif 'NFBCID' in df.columns:
                return 'NFBCID'
            return 'NFBCID'

        def get_player_match_id(player_obj):
            """Get the best available ID for matching based on league type (legacy helper)."""
            if league.league_type == 'fantrax' and player_obj.fantrax_id:
                return ('FantraxID', str(player_obj.fantrax_id))
            elif league.league_type == 'cbs' and player_obj.cbs_player_name:
                return ('CBSSportsName', str(player_obj.cbs_player_name))
            elif player_obj.nfbc_id:
                return ('NFBCID', str(player_obj.nfbc_id))
            elif player_obj.fantrax_id:
                return ('FantraxID', str(player_obj.fantrax_id))
            return (None, None)

        def build_projection_lookup(df):
            """Build {id_val: row} lookup. Returns (lookup, id_col_used) so callers
            can build roster ID sets with the SAME column — preventing false matches
            (e.g. FantraxID accidentally colliding with a different NFBCID).
            For CBS leagues the key is the normalized CBS name so CHW/CWS and Jr.
            differences don't break the match."""
            id_col = resolve_id_col(df)
            lookup = {}
            if id_col in df.columns:
                for _, row in df.iterrows():
                    id_val = str(row.get(id_col, ''))
                    if id_val and id_val not in ('nan', 'None', ''):
                        key = _normalize_cbs_name(id_val) if id_col == 'CBSSportsName' else id_val
                        if key:
                            lookup[key] = row
            return lookup, id_col

        def get_team_player_ids(team_name, id_col: str = None):
            """Get {match_id: roster_entry} for a team, keyed by id_col.
            Pass id_col from build_projection_lookup to guarantee the keys match."""
            result = {}
            for roster_entry in owned_rosters:
                owner = roster_entry.team_owner
                if owner and owner.startswith('@'):
                    owner = owner[1:]
                if owner == team_name and roster_entry.player:
                    if id_col:
                        id_val = get_player_id_for_col(roster_entry.player, id_col)
                    else:
                        _, id_val = get_player_match_id(roster_entry.player)
                    if id_val and id_val not in ('nan', 'None', ''):
                        result[id_val] = roster_entry
            return result

        def get_owned_ids(id_col: str = None):
            """Get set of IDs for all owned players keyed by id_col."""
            ids = set()
            for roster_entry in owned_rosters:
                if roster_entry.player:
                    if id_col:
                        id_val = get_player_id_for_col(roster_entry.player, id_col)
                    else:
                        _, id_val = get_player_match_id(roster_entry.player)
                    if id_val and id_val not in ('nan', 'None', ''):
                        ids.add(id_val)
            return ids

        def find_team_name(target_team):
            """Fuzzy match a team name from user input"""
            target_lower = target_team.lower().strip().lstrip('@')
            for t in all_team_names:
                t_clean = t.lower().strip().lstrip('@')
                if target_lower in t_clean or t_clean in target_lower:
                    return t
            for t in all_team_names:
                t_clean = t.lower().strip().lstrip('@')
                if any(word in t_clean for word in target_lower.split() if len(word) > 2):
                    return t
            return None

        def fmt_stat(v, decimals=2):
            """Format a stat value for display"""
            if str(v) in ('nan', 'None', ''):
                return '0'
            try:
                fv = float(v)
                if decimals == 3:
                    return str(round(fv, 3))
                return str(int(fv)) if fv == int(fv) else str(round(fv, decimals))
            except (ValueError, TypeError):
                return str(v)

        def fetch_ros_lookup(id_col: str = None):
            """Fetch ROS projections and build a lookup by platform ID.
            Pass id_col to force a specific column (e.g. same as weekly lookup)."""
            global _projections_df
            if _projections_df is None:
                try:
                    svc = ProjectionService(projection_type="ros")
                    _projections_df = svc.fetch_projections()
                except Exception as e:
                    logger.error(f"Failed to fetch ROS projections: {e}")
                    return {}, 'NFBCID'
            ros_df = _projections_df
            if 'LeagueType' in ros_df.columns:
                type_df = ros_df[ros_df['LeagueType'] == requested_type]
                if len(type_df) > 0:
                    ros_df = type_df
            if id_col:
                # Force specific column (must exist in ros_df or we fall back)
                if id_col in ros_df.columns:
                    lookup = {}
                    for _, row in ros_df.iterrows():
                        v = str(row.get(id_col, ''))
                        if v and v not in ('nan', 'None', ''):
                            lookup[v] = row
                    return lookup, id_col
            return build_projection_lookup(ros_df)

        # Group players by team owner, separating hitters and pitchers
        # Also track dollar values and category $ for pre-calculated totals
        teams_hitters = {}  # owner -> list of player strings
        teams_pitchers = {}  # owner -> list of player strings
        teams_no_projection = {}  # owner -> list of player names with no projection
        # Per-team category tracking: owner -> {category -> list of values}
        HITTER_CATS = ['R', 'HR', 'RBI', 'SB', 'AVG', 'OBP']
        PITCHER_CATS = ['W', 'SV', 'K', 'ERA', 'WHIP', 'HLD', 'QS']
        ALL_CATS = HITTER_CATS + PITCHER_CATS
        teams_cat_dollars = {}  # owner -> {'$': [], 'R': [], 'HR': [], ...}
        free_agents = []
        PITCHER_POSITIONS = ('SP', 'RP', 'P')

        import re as _re

        def parse_dollar_categories(dollar_val_str):
            """Parse dollar value string to extract overall $ and category $"""
            result = {'$': None, 'PTS': None}
            for cat in ALL_CATS:
                result[cat] = None
            if not dollar_val_str:
                return result
            # Extract overall $ value: "[$12.3 ..."
            overall_match = _re.search(r'\[\$(-?[\d.]+)', dollar_val_str)
            if overall_match:
                try:
                    result['$'] = float(overall_match.group(1))
                except ValueError:
                    pass
            # Extract PTS value: "PTS:7.5"
            pts_match = _re.search(r'PTS:(-?[\d.]+)', dollar_val_str)
            if pts_match:
                try:
                    result['PTS'] = float(pts_match.group(1))
                except ValueError:
                    pass
            # Extract category values: "$R:1.2", "$HR:-0.5", etc.
            for cat in ALL_CATS:
                cat_match = _re.search(rf'\${cat}:(-?[\d.]+)', dollar_val_str)
                if cat_match:
                    try:
                        result[cat] = float(cat_match.group(1))
                    except ValueError:
                        pass
            return result

        for roster in all_rosters:
            player = roster.player
            owner = roster.team_owner
            # Clean team owner name (remove @ prefix from NFBC format)
            if owner and owner.startswith('@'):
                owner = owner[1:]
            dollar_val = get_player_dollar_value(player.name, player)
            pos = (player.position or '').upper()
            # For CBS players, prefer API position over DB position (DB comes from source CSV which may be wrong)
            if player.cbs_player_name:
                _cbs_pk = _normalize_cbs_name(str(player.cbs_player_name))
                _api_pos = proj_pos_lookup.get(_cbs_pk, '')
                if _api_pos:
                    pos = _api_pos.upper()
            is_pitcher = pos in PITCHER_POSITIONS

            # Clean player name: strip trailing position codes (e.g. "Noelvi Marte 3B,OF" -> "Noelvi Marte")
            display_name = _re.sub(
                r'\s+(?:(?:1B|2B|3B|SS|OF|DH|SP|RP|P|C)(?:[/,](?:1B|2B|3B|SS|OF|DH|SP|RP|P|C))*)\s*$',
                '', player.name or ''
            ).strip() or player.name or '?'

            # Resolve best display position: prefer API projection data over DB (source CSV)
            display_pos = player.position or ''
            if player.cbs_player_name:
                # CBS players: always use API position (DB pos can be wrong/outdated)
                _cbs_pk2 = _normalize_cbs_name(str(player.cbs_player_name))
                _api_pos2 = proj_pos_lookup.get(_cbs_pk2, '')
                if _api_pos2:
                    display_pos = _api_pos2
            elif not display_pos or display_pos.upper() == 'P':
                pid_key = str(player.nfbc_id) if player.nfbc_id else ''
                if not pid_key and player.fantrax_id:
                    pid_key = str(player.fantrax_id)
                if pid_key:
                    display_pos = proj_pos_lookup.get(pid_key, display_pos)
            display_pos = display_pos or '?'

            # Build clear, standalone player string to prevent GPT from mixing up values
            # Format: "Name | Pos: SP | Team: NYY | $: 12.3 | $W: 2.1 | $K: 5.2 | ..."
            if dollar_val:
                # dollar_val is like " [$12.3 $R:1.2 $HR:3.4 ...]" - reformat to pipe-separated
                clean_dollar = dollar_val.strip().strip('[]')
                player_str = f"{display_name} | Pos: {display_pos} | Team: {player.team} | {clean_dollar}"
            else:
                player_str = f"{display_name} | Pos: {display_pos} | Team: {player.team} | NO PROJECTION"

            if owner == 'Free Agent':
                # Store tuple (dollar_value, player_str) for sorting later
                parsed_fa = parse_dollar_categories(dollar_val)
                fa_dollar = parsed_fa['$'] if parsed_fa['$'] is not None else -999
                free_agents.append((fa_dollar, player_str))
            else:
                # Parse all dollar categories
                parsed = parse_dollar_categories(dollar_val)
                numeric_dollar = parsed['$']

                # Initialize team tracking if needed
                if owner not in teams_cat_dollars:
                    teams_cat_dollars[owner] = {'h_$': [], 'p_$': [], 'pts_vals': []}
                    for cat in ALL_CATS:
                        teams_cat_dollars[owner][cat] = []

                # Track H/SP/RP counts
                if 'h_count' not in teams_cat_dollars[owner]:
                    teams_cat_dollars[owner]['h_count'] = 0
                    teams_cat_dollars[owner]['sp_count'] = 0
                    teams_cat_dollars[owner]['rp_count'] = 0

                numeric_pts = parsed.get('PTS')
                if numeric_pts is not None:
                    teams_cat_dollars[owner]['pts_vals'].append(numeric_pts)

                if is_pitcher:
                    if owner not in teams_pitchers:
                        teams_pitchers[owner] = []
                    teams_pitchers[owner].append(player_str)
                    # Count SP vs RP
                    if pos == 'SP':
                        teams_cat_dollars[owner]['sp_count'] += 1
                    elif pos == 'RP':
                        teams_cat_dollars[owner]['rp_count'] += 1
                    else:
                        # Generic 'P' - count as SP by default
                        teams_cat_dollars[owner]['sp_count'] += 1
                    if numeric_dollar is not None:
                        teams_cat_dollars[owner]['p_$'].append(numeric_dollar)
                        # Only sum categories for $1+ players
                        if numeric_dollar >= 1.0:
                            for cat in PITCHER_CATS:
                                if parsed[cat] is not None:
                                    teams_cat_dollars[owner][cat].append(parsed[cat])
                    else:
                        if owner not in teams_no_projection:
                            teams_no_projection[owner] = []
                        teams_no_projection[owner].append(f"{player.name} ({player.position})")
                else:
                    if owner not in teams_hitters:
                        teams_hitters[owner] = []
                    teams_hitters[owner].append(player_str)
                    # Count hitters
                    teams_cat_dollars[owner]['h_count'] += 1
                    if numeric_dollar is not None:
                        teams_cat_dollars[owner]['h_$'].append(numeric_dollar)
                        # Only sum categories for $1+ players
                        if numeric_dollar >= 1.0:
                            for cat in HITTER_CATS:
                                if parsed[cat] is not None:
                                    teams_cat_dollars[owner][cat].append(parsed[cat])
                    else:
                        if owner not in teams_no_projection:
                            teams_no_projection[owner] = []
                        teams_no_projection[owner].append(f"{player.name} ({player.position})")

        # All team names
        all_team_names = sorted(set(list(teams_hitters.keys()) + list(teams_pitchers.keys())))

        # Pre-calculate team totals ($1+ only) with category breakdowns
        team_totals = {}
        for team_name in all_team_names:
            cd = teams_cat_dollars.get(team_name, {})
            h_dollars = cd.get('h_$', [])
            p_dollars = cd.get('p_$', [])
            h_sum = sum(d for d in h_dollars if d >= 1.0)
            p_sum = sum(d for d in p_dollars if d >= 1.0)
            pts_vals = cd.get('pts_vals', [])
            totals = {
                'hitting': round(h_sum, 1),
                'pitching': round(p_sum, 1),
                'total': round(h_sum + p_sum, 1),
                'count': len(h_dollars) + len(p_dollars),
                'h_count': cd.get('h_count', 0),
                'sp_count': cd.get('sp_count', 0),
                'rp_count': cd.get('rp_count', 0),
                'PTS': round(sum(pts_vals), 1),
            }
            # Sum each category ($1+ players only - already filtered during collection)
            for cat in ALL_CATS:
                cat_vals = cd.get(cat, [])
                totals[cat] = round(sum(cat_vals), 1)
            team_totals[team_name] = totals

        # Sort teams by total $ for ranking
        ranked_teams = sorted(all_team_names, key=lambda t: team_totals[t]['total'], reverse=True)
        for rank, team_name in enumerate(ranked_teams, 1):
            team_totals[team_name]['rank'] = rank

        # ============================================================
        # HARD-CODED REPORT GENERATORS (bypass GPT for accuracy)
        # ============================================================

        # Determine active categories by checking top 30 players in projection data.
        # If a category is all-zero for the top 30, it's not scored in this format.
        all_possible_cats = ['R', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'W', 'SV', 'ERA', 'WHIP', 'K', 'HLD', 'QS']
        active_cats = []
        try:
            # Use NYY + NYM (one AL, one NL) as representative sample —
            # any category scored in this format will be non-zero for those players
            _sample = filtered_df[filtered_df['Team'].isin(['NYY', 'NYM'])] if 'Team' in filtered_df.columns else filtered_df.head(30)
            if len(_sample) < 5:  # fallback if neither team has data in this slice
                _sample = filtered_df.nlargest(30, '$') if '$' in filtered_df.columns else filtered_df.head(30)
            for cat in all_possible_cats:
                df_col = f'${cat}$'
                if df_col in filtered_df.columns:
                    col_vals = _sample[df_col].fillna(0)
                    if (col_vals.astype(float) != 0).any():
                        active_cats.append(cat)
                else:
                    # Column not in projection data — fall back to team totals
                    if any(team_totals[t].get(cat, 0.0) != 0.0 for t in ranked_teams):
                        active_cats.append(cat)
        except Exception as _e:
            logger.warning(f"active_cats NYY/NYM check failed: {_e}, using team totals")
            for cat in all_possible_cats:
                if any(team_totals[t].get(cat, 0.0) != 0.0 for t in ranked_teams):
                    active_cats.append(cat)

        # Build clear context text for AI with hitter/pitcher separation
        format_names = {"MLB12": "12-team mixed", "MLB15": "15-team mixed", "MLB10": "10-team mixed", "AL12": "12-team AL-only", "NL12": "12-team NL-only"}
        all_formats_str = ", ".join(AVAILABLE_LEAGUE_TYPES)
        context_text = f"FANTASY LEAGUE DATA ({league.league_type}):\n"
        context_text += f"ACTIVE PROJECTION FORMAT: {requested_type} ({format_names.get(requested_type, 'mixed')}).\n"
        context_text += f"AVAILABLE FORMATS: {all_formats_str}. User can request any format.\n"
        # Dynamic column instruction so GPT uses the right batting stat for this format
        _h_avg_col = '$OBP' if 'OBP' in active_cats else '$AVG'
        _p_extra_col = ' | $HLD' if 'HLD' in active_cats else (' | $QS' if 'QS' in active_cats else '')
        context_text += f"TABLE COLUMNS FOR THIS FORMAT - HITTERS: Player | Pos | Team | $ | $R | $HR | $RBI | $SB | {_h_avg_col} — PITCHERS: Player | Pos | Team | $ | $W | $SV | $K | $ERA | $WHIP{_p_extra_col}\n"
        context_text += f"TEAMS IN LEAGUE: {', '.join(all_team_names)}\n\n"

        # Pre-calculated team rankings table with category breakdowns
        context_text += "PRE-CALCULATED TEAM RANKINGS ($1+ players only):\n"
        context_text += "Team | Total $ | H | SP | RP | $R | $HR | $RBI | $SB | $AVG | $OBP | $W | $SV | $ERA | $WHIP | $K | $HLD | Rank\n"
        for team_name in ranked_teams:
            t = team_totals[team_name]
            context_text += (
                f"{team_name} | ${t['total']} | {t['h_count']} | {t['sp_count']} | {t['rp_count']} | "
                f"${t['R']} | ${t['HR']} | ${t['RBI']} | ${t['SB']} | ${t['AVG']} | ${t['OBP']} | "
                f"${t['W']} | ${t['SV']} | ${t['ERA']} | ${t['WHIP']} | ${t['K']} | ${t['HLD']} | {t['rank']}\n"
            )
        context_text += "\n"

        def generate_league_overview_dollars() -> str:
            """Generate League Overview $ table - matches Rudy's SQL LEAGUEREVIEW"""
            num_teams = len(ranked_teams)
            lines = []
            lines.append(f"**League Overview $ ({requested_type}) - {num_teams} Teams**\n")
            # Build header dynamically - only include non-zero columns
            has_pts = any(team_totals[t].get('PTS', 0) != 0 for t in ranked_teams)
            header_parts = ['Owner', '$']
            if has_pts:
                header_parts.append('PTS')
            header_parts += ['H', 'SP', 'RP']
            for cat in active_cats:
                header_parts.append(f'${cat}')
            lines.append('| ' + ' | '.join(header_parts) + ' |')
            lines.append('|' + '---|' * len(header_parts))
            for team_name in ranked_teams:
                t = team_totals[team_name]
                row_parts = [team_name, str(t['total'])]
                if has_pts:
                    row_parts.append(str(t.get('PTS', 0)))
                row_parts += [str(t['h_count']), str(t['sp_count']), str(t['rp_count'])]
                for cat in active_cats:
                    row_parts.append(str(t[cat]))
                lines.append('| ' + ' | '.join(row_parts) + ' |')
            return "\n".join(lines)

        def generate_league_overview_ranks() -> str:
            """Generate League Overview Ranks table - roto scoring (num_teams=best, 1=worst)"""
            num_teams = len(ranked_teams)
            lines = []
            lines.append(f"\n**League Overview Ranks (Roto: {num_teams}=Best, 1=Worst)**\n")
            # Build header dynamically
            header_parts = ['Owner', '$Rank']
            for cat in active_cats:
                header_parts.append(f'${cat}')
            header_parts.append('Total Pts')
            lines.append('| ' + ' | '.join(header_parts) + ' |')
            lines.append('|' + '---|' * len(header_parts))

            # Calculate roto ranks for each active category only
            team_ranks = {team: {} for team in ranked_teams}

            for cat in active_cats:
                sorted_by_cat = sorted(ranked_teams, key=lambda t: team_totals[t][cat])
                for rank_idx, team_name in enumerate(sorted_by_cat):
                    team_ranks[team_name][cat] = rank_idx + 1

            # Rank by total $
            sorted_by_total = sorted(ranked_teams, key=lambda t: team_totals[t]['total'])
            for rank_idx, team_name in enumerate(sorted_by_total):
                team_ranks[team_name]['total_rank'] = rank_idx + 1

            # Calculate total roto points
            for team_name in ranked_teams:
                team_ranks[team_name]['roto_total'] = sum(
                    team_ranks[team_name][cat] for cat in active_cats
                )

            # Sort by roto total descending (most points = best)
            roto_sorted = sorted(ranked_teams, key=lambda t: team_ranks[t]['roto_total'], reverse=True)

            for team_name in roto_sorted:
                r = team_ranks[team_name]
                row_parts = [team_name, str(r['total_rank'])]
                for cat in active_cats:
                    row_parts.append(str(r[cat]))
                row_parts.append(str(r['roto_total']))
                lines.append('| ' + ' | '.join(row_parts) + ' |')
            return "\n".join(lines)

        def generate_league_report() -> str:
            """Generate full league report ($ table + ranks table)"""
            report = generate_league_overview_dollars()
            report += "\n\n"
            report += generate_league_overview_ranks()
            return report

        def generate_team_overview(target_team: str) -> str:
            """Generate Team Overview - hitters table + pitchers table for a specific team"""
            # Find matching team name (fuzzy match)
            matched_team = None
            target_lower = target_team.lower().strip().lstrip('@')
            for t in all_team_names:
                t_clean = t.lower().strip().lstrip('@')
                if target_lower in t_clean or t_clean in target_lower:
                    matched_team = t
                    break

            if not matched_team:
                # Try partial word match
                for t in all_team_names:
                    t_clean = t.lower().strip().lstrip('@')
                    if any(word in t_clean for word in target_lower.split() if len(word) > 2):
                        matched_team = t
                        break

            if not matched_team:
                return f"Could not find team matching '{target_team}'. Available teams: {', '.join(all_team_names)}"

            t = team_totals[matched_team]
            lines = []
            lines.append(f"**Team Overview: {matched_team}**")
            lines.append(f"Total: ${t['total']} | Rank: {t['rank']}/{len(ranked_teams)}\n")

            # HITTERS TABLE
            hitters = teams_hitters.get(matched_team, [])
            if hitters:
                # Determine active hitter cats
                h_cats = [c for c in active_cats if c in HITTER_CATS]
                lines.append(f"**Hitters ({len(hitters)})**\n")
                h_header = ['Name', 'Pos', 'Team', '$', 'PTS', '$/G']
                for cat in h_cats:
                    h_header.append(f'${cat}')
                lines.append('| ' + ' | '.join(h_header) + ' |')
                lines.append('|' + '---|' * len(h_header))

                # Parse each hitter's data from the player string
                hitter_rows = []
                for p_str in hitters:
                    # Format: "Name | Pos: SP | Team: NYY | $12.3 PTS:7.5 $/G:5.2 $R:1.2 $HR:3.4 ..."
                    parts = p_str.split(' | ')
                    name = parts[0] if len(parts) > 0 else '?'
                    pos = parts[1].replace('Pos: ', '') if len(parts) > 1 else '?'
                    team = parts[2].replace('Team: ', '') if len(parts) > 2 else '?'
                    dollar_part = parts[3] if len(parts) > 3 else ''

                    # Extract overall $
                    overall_match = _re.search(r'^\$(-?[\d.]+)', dollar_part)
                    overall = float(overall_match.group(1)) if overall_match else 0.0

                    # Extract PTS
                    pts_match = _re.search(r'PTS:(-?[\d.]+)', dollar_part)
                    pts_val = pts_match.group(1) if pts_match else ''

                    # Extract $/G
                    pg_match = _re.search(r'\$/G:(-?[\d.]+)', dollar_part)
                    per_game = pg_match.group(1) if pg_match else ''

                    # Extract category values
                    cat_vals = {}
                    for cat in h_cats:
                        cat_match = _re.search(rf'\${cat}:(-?[\d.]+)', dollar_part)
                        cat_vals[cat] = cat_match.group(1) if cat_match else '0'

                    row = [name, pos, team, str(overall), pts_val, per_game]
                    for cat in h_cats:
                        row.append(cat_vals[cat])
                    hitter_rows.append((overall, '| ' + ' | '.join(row) + ' |'))

                # Sort by $ descending
                hitter_rows.sort(key=lambda x: x[0], reverse=True)
                for _, row_str in hitter_rows:
                    lines.append(row_str)

            # PITCHERS TABLE
            pitchers = teams_pitchers.get(matched_team, [])
            if pitchers:
                p_cats = [c for c in active_cats if c in PITCHER_CATS]
                lines.append(f"\n**Pitchers ({len(pitchers)})**\n")
                p_header = ['Name', 'Pos', 'Team', '$', 'PTS', '$/G']
                for cat in p_cats:
                    p_header.append(f'${cat}')
                lines.append('| ' + ' | '.join(p_header) + ' |')
                lines.append('|' + '---|' * len(p_header))

                pitcher_rows = []
                for p_str in pitchers:
                    parts = p_str.split(' | ')
                    name = parts[0] if len(parts) > 0 else '?'
                    pos = parts[1].replace('Pos: ', '') if len(parts) > 1 else '?'
                    team = parts[2].replace('Team: ', '') if len(parts) > 2 else '?'
                    dollar_part = parts[3] if len(parts) > 3 else ''

                    overall_match = _re.search(r'^\$(-?[\d.]+)', dollar_part)
                    overall = float(overall_match.group(1)) if overall_match else 0.0

                    # Extract PTS
                    pts_match = _re.search(r'PTS:(-?[\d.]+)', dollar_part)
                    pts_val = pts_match.group(1) if pts_match else ''

                    # Extract $/G
                    pg_match = _re.search(r'\$/G:(-?[\d.]+)', dollar_part)
                    per_game = pg_match.group(1) if pg_match else ''

                    cat_vals = {}
                    for cat in p_cats:
                        cat_match = _re.search(rf'\${cat}:(-?[\d.]+)', dollar_part)
                        cat_vals[cat] = cat_match.group(1) if cat_match else '0'

                    row = [name, pos, team, str(overall), pts_val, per_game]
                    for cat in p_cats:
                        row.append(cat_vals[cat])
                    pitcher_rows.append((overall, '| ' + ' | '.join(row) + ' |'))

                pitcher_rows.sort(key=lambda x: x[0], reverse=True)
                for _, row_str in pitcher_rows:
                    lines.append(row_str)

            return "\n".join(lines)

        def _clean_str(v) -> str:
            """Return string value or empty string for nan/None"""
            s = str(v)
            return '' if s in ('nan', 'None') else s

        def _fmt_ts(v) -> str:
            """Format API timestamp (Excel serial or ISO string) to readable date"""
            s = str(v)
            if s in ('nan', 'None', ''):
                return ''
            try:
                f = float(s)
                # Excel serial date (days since 1899-12-30)
                from datetime import datetime, timedelta
                dt = datetime(1899, 12, 30) + timedelta(days=f)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                return s  # Already a string

        def _get_ha(row) -> str:
            h = row.get('Team_HomeGames', '')
            a = row.get('Team_AwayGames', '')
            if _clean_str(h) and _clean_str(a):
                return f"{fmt_stat(h)}/{fmt_stat(a)}"
            return _clean_str(row.get('H/A', ''))

        def _get_rl_weekly(row) -> str:
            r = row.get('Team_vR_Games', '')
            l = row.get('Team_vL_Games', '')
            if _clean_str(r) and _clean_str(l):
                return f"{fmt_stat(r)}/{fmt_stat(l)}"
            return ''

        def _get_wof(row) -> str:
            v = row.get('Week of', '')
            if str(v) in ('nan', 'None', ''):
                return ''
            try:
                f = float(str(v))
                from datetime import datetime, timedelta
                dt = datetime(1899, 12, 30) + timedelta(days=f)
                return dt.strftime('%m/%d/%Y')
            except (ValueError, TypeError):
                return str(v)

        def _get_target_date(use_tomorrow: bool = False):
            """Return target date in EST, falling back to offset from UTC-5"""
            from datetime import datetime, timedelta, timezone
            est = timezone(timedelta(hours=-5))  # EST (UTC-5); close enough year-round
            base = datetime.now(est).date()
            return base + timedelta(days=1 if use_tomorrow else 0)

        def _filter_daily_df_by_date(df, use_tomorrow: bool = False):
            """Filter daily projection DataFrame to the target date (EST).
            If no rows match, falls back to the most recent date in the data
            so the report always shows something useful (e.g. test/off-season data)."""
            if 'Date' not in df.columns:
                return df
            target_date = _get_target_date(use_tomorrow)
            try:
                tmp = df.copy()
                tmp['_parsed_date'] = pd.to_datetime(tmp['Date'], errors='coerce').dt.date
                filtered = tmp[tmp['_parsed_date'] == target_date]
                if len(filtered) > 0:
                    logger.info(f"Daily filter: {len(filtered)} rows for {target_date}")
                    return filtered
                # Fallback: use most recent available date
                dates = sorted(tmp['_parsed_date'].dropna().unique())
                if dates:
                    fallback = dates[-1]
                    fallback_rows = tmp[tmp['_parsed_date'] == fallback]
                    logger.info(f"No data for {target_date}, using fallback date {fallback} ({len(fallback_rows)} rows)")
                    return fallback_rows
            except Exception as e:
                logger.warning(f"Could not filter by date: {e}")
            return df

        def _get_date_str(row) -> str:
            v = row.get('Date', '')
            if str(v) in ('nan', 'None', ''):
                return ''
            try:
                d = pd.to_datetime(v, errors='coerce')
                return d.strftime('%Y-%m-%d') if not pd.isnull(d) else str(v)
            except Exception:
                return str(v)

        def _weekly_ros12(row) -> str:
            for k in ('$ROS12$', 'ROS12'):
                v = row.get(k, '')
                if _clean_str(v):
                    return fmt_stat(v)
            return ''

        def _weekly_ros_pg(row) -> str:
            for k in ('ROS12 $/G', '$/G'):
                v = row.get(k, '')
                if _clean_str(v):
                    return fmt_stat(v)
            return ''

        def _weekly_ros15(row) -> str:
            for k in ('$ROS15$', 'ROS15'):
                v = row.get(k, '')
                if _clean_str(v):
                    return fmt_stat(v)
            return ''

        def _daily_ros12(row) -> str:
            for k in ('$ROS12$', 'ROS12'):
                v = row.get(k, '')
                if _clean_str(v):
                    return fmt_stat(v)
            return ''

        def _daily_ros_pg(row) -> str:
            for k in ('ROS12 $/G', '$/G'):
                v = row.get(k, '')
                if _clean_str(v):
                    return fmt_stat(v)
            return ''

        def _daily_ros15(row) -> str:
            for k in ('$ROS15$', 'ROS15'):
                v = row.get(k, '')
                if _clean_str(v):
                    return fmt_stat(v)
            return ''

        def generate_pickups_report(projection_type: str, use_tomorrow: bool = False) -> str:
            """Generate Weekly/Daily Pickups - best available FAs by position"""
            global _weekly_projections_df, _daily_projections_df, _daily_cache_date

            if projection_type == "weekly":
                label = "Weekly"
            elif use_tomorrow:
                label = "Tomorrow"
            else:
                label = "Today"

            # Fetch the appropriate projections
            if projection_type == "weekly":
                if _weekly_projections_df is None:
                    try:
                        svc = ProjectionService(projection_type="weekly")
                        _weekly_projections_df = svc.fetch_projections()
                        logger.info(f"Fetched {len(_weekly_projections_df)} weekly projections")
                    except Exception as e:
                        logger.error(f"Failed to fetch weekly projections: {e}")
                        return f"Could not fetch {label.lower()} projections. Please try again later."
                pickup_df = _weekly_projections_df
            else:
                # Invalidate daily cache if the EST date has changed
                today_est = _get_target_date(False)
                if _daily_cache_date != today_est:
                    _daily_projections_df = None
                    _daily_cache_date = today_est
                    logger.info(f"Daily cache invalidated for new date: {today_est}")
                if _daily_projections_df is None:
                    try:
                        svc = ProjectionService(projection_type="daily")
                        _daily_projections_df = svc.fetch_projections()
                        logger.info(f"Fetched {len(_daily_projections_df)} daily projections")
                    except Exception as e:
                        logger.error(f"Failed to fetch daily projections: {e}")
                        return f"Could not fetch {label.lower()} projections. Please try again later."
                pickup_df = _daily_projections_df

            # Filter to requested league type
            if 'LeagueType' in pickup_df.columns:
                type_df = pickup_df[pickup_df['LeagueType'] == requested_type]
                if len(type_df) > 0:
                    pickup_df = type_df

            # Filter by AL/NL for AL12/NL12 league types
            if requested_type == 'AL12' and 'League' in pickup_df.columns:
                pickup_df = pickup_df[pickup_df['League'] == 'AL']
            elif requested_type == 'NL12' and 'League' in pickup_df.columns:
                pickup_df = pickup_df[pickup_df['League'] == 'NL']

            # Filter by date for daily pickups (EST, with fallback to most recent date)
            if projection_type == "daily":
                pickup_df = _filter_daily_df_by_date(pickup_df, use_tomorrow=use_tomorrow)

            # Determine which ID column the projection data actually contains
            id_col = resolve_id_col(pickup_df)

            # Platform-aware: build set of owned player IDs using the same id_col
            owned_ids = get_owned_ids(id_col)

            # For CBS leagues: also build name-based owned set as fallback.
            # CBS players have no NFBC/Fantrax IDs, so if CBSSportsName isn't in the API
            # projection data, owned_ids will be empty and all players appear as free agents.
            owned_names = set()
            if league.league_type == 'cbs' and id_col != 'CBSSportsName':
                for roster_entry in owned_rosters:
                    if roster_entry.player and roster_entry.player.name:
                        owned_names.add(roster_entry.player.name.lower().strip())

            # Filter projections to only free agents (not owned)
            fa_rows = []
            if id_col in pickup_df.columns:
                for _, row in pickup_df.iterrows():
                    pid = str(row.get(id_col, ''))
                    # For CBS, normalize the API's CBSSportsName to match our owned_ids keys
                    if id_col == 'CBSSportsName' and pid:
                        pid = _normalize_cbs_name(pid)
                    if pid and pid not in ('nan', 'None', '') and pid not in owned_ids:
                        # CBS name fallback: skip players whose name matches an owned player
                        if owned_names:
                            api_name = _re.sub(r'\[player id=\d+\]|\[/player\]', '', str(row.get('Name', ''))).strip().lower()
                            if api_name in owned_names:
                                continue
                        dollar_val = row.get('$', 0)
                        try:
                            dollar_val = float(dollar_val) if str(dollar_val) not in ('nan', 'None', '') else 0.0
                        except (ValueError, TypeError):
                            dollar_val = 0.0

                        # RP special case: include if SV > 0.2 even below threshold
                        pos = str(row.get('Pos', '?'))
                        sv_val = 0.0
                        try:
                            sv_val = float(row.get('SV', 0)) if str(row.get('SV', '')).replace('.','').replace('-','').isdigit() else 0.0
                        except (ValueError, TypeError):
                            sv_val = 0.0

                        if dollar_val >= -5 or (pos.upper() == 'RP' and sv_val > 0.2):
                            name = str(row.get('Name', '?'))
                            name = _re.sub(r'\[player id=\d+\]|\[/player\]', '', name).strip()
                            team = str(row.get('Team', '?'))
                            fa_rows.append({
                                'name': name, 'pos': pos, 'team': team,
                                'dollar': dollar_val, 'row': row
                            })

            if not fa_rows:
                return f"No {label.lower()} pickup data available. Make sure projections are loaded."

            # Group by position
            position_groups = {
                'C': [], '1B/3B': [], '2B/SS': [], 'OF/DH': [],
                'SP': [], 'RP': []
            }

            for fa in fa_rows:
                pos = fa['pos'].upper()
                placed = False
                if 'C' == pos:
                    position_groups['C'].append(fa)
                    placed = True
                if '1B' in pos or '3B' in pos:
                    position_groups['1B/3B'].append(fa)
                    placed = True
                if '2B' in pos or 'SS' in pos:
                    position_groups['2B/SS'].append(fa)
                    placed = True
                if 'OF' in pos or 'DH' in pos or 'LF' in pos or 'RF' in pos or 'CF' in pos:
                    position_groups['OF/DH'].append(fa)
                    placed = True
                if pos == 'SP' or (pos == 'P' and 'RP' not in pos):
                    position_groups['SP'].append(fa)
                    placed = True
                if 'RP' in pos:
                    position_groups['RP'].append(fa)
                    placed = True
                if not placed:
                    if pos in ('P',):
                        position_groups['SP'].append(fa)
                    else:
                        position_groups['OF/DH'].append(fa)

            lines = []
            lines.append(f"**{label} Pickups ({requested_type})**\n")

            for group_name, players in position_groups.items():
                if not players:
                    continue
                players.sort(key=lambda x: x['dollar'], reverse=True)
                top = players[:10]
                is_pitcher_group = group_name in ('SP', 'RP')

                # Detect available columns from sample row
                sample_row = top[0]['row'] if top else None
                sample_keys = set(dict(sample_row).keys()) if sample_row is not None else set()

                lines.append(f"\n**{group_name} ({len(players)} available, showing top {len(top)})**\n")

                if projection_type == "weekly":
                    # ── WEEKLY: match Rudy's mockup exactly ──────────────────
                    if not is_pitcher_group:
                        # Hitter header
                        header = ['Name', 'Team', 'H', 'Pos', 'Y! Pos', 'W/o', 'Opp',
                                  '$', 'PTS', '$OBP$', '$MT', '$FS',
                                  'G', 'PA', 'R', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'SLG',
                                  'R%', 'ROS12', '$/G', 'ROS15', 'RFS12', 'RFS15',
                                  'Games', 'H/A', 'R/L', 'Timestamp']
                        lines.append('| ' + ' | '.join(header) + ' |')
                        lines.append('|' + '---|' * len(header))
                        for fa in top:
                            r = fa['row']
                            lines.append('| ' + ' | '.join([
                                fa['name'], fa['team'],
                                _clean_str(r.get('Handedness', '')),
                                fa['pos'],
                                _clean_str(r.get('Y! Pos', '')),
                                _get_wof(r),
                                _clean_str(r.get('Opp', '')),
                                str(round(fa['dollar'], 1)),
                                fmt_stat(r.get('PTS', '')),
                                fmt_stat(r.get('$/G$', '')),
                                fmt_stat(r.get('$ MT$', '')),
                                fmt_stat(r.get('$ FS$', '')),
                                fmt_stat(r.get('G', '')),
                                fmt_stat(r.get('PA', '')),
                                fmt_stat(r.get('R', '')),
                                fmt_stat(r.get('HR', '')),
                                fmt_stat(r.get('RBI', '')),
                                fmt_stat(r.get('SB', '')),
                                fmt_stat(r.get('AVG', ''), 3),
                                fmt_stat(r.get('OBP', ''), 3),
                                fmt_stat(r.get('SLG', ''), 3),
                                fmt_stat(r.get('R%', '')),
                                _weekly_ros12(r),
                                _weekly_ros_pg(r),
                                _weekly_ros15(r),
                                fmt_stat(r.get('RFS12', '')),
                                fmt_stat(r.get('RFS15', '')),
                                fmt_stat(r.get('Team_Games', r.get('Games', ''))),
                                _get_ha(r),
                                _get_rl_weekly(r),
                                _fmt_ts(r.get('Timestamp', '')),
                            ]) + ' |')
                    else:
                        # Pitcher header
                        header = ['Name', 'Team', 'H', 'Pos', 'Y! Pos', 'W/o', 'Opp',
                                  '$', 'PTS', '$OBP$', '$MT', '$FS',
                                  'GS', 'QS', 'W', 'L', 'IP', 'H', 'ER', 'K', 'BB', 'HR_P',
                                  'ERA', 'WHIP',
                                  'R%', 'ROS12', '$/G', 'ROS15', 'RFS12', 'RFS15',
                                  'Games', 'H/A', 'R/L', 'Timestamp']
                        lines.append('| ' + ' | '.join(header) + ' |')
                        lines.append('|' + '---|' * len(header))
                        for fa in top:
                            r = fa['row']
                            lines.append('| ' + ' | '.join([
                                fa['name'], fa['team'],
                                _clean_str(r.get('Handedness', '')),
                                fa['pos'],
                                _clean_str(r.get('Y! Pos', '')),
                                _get_wof(r),
                                _clean_str(r.get('Opp', '')),
                                str(round(fa['dollar'], 1)),
                                fmt_stat(r.get('PTS', '')),
                                fmt_stat(r.get('$/G$', '')),
                                fmt_stat(r.get('$ MT$', '')),
                                fmt_stat(r.get('$ FS$', '')),
                                fmt_stat(r.get('GS', '')),
                                fmt_stat(r.get('QS', '')),
                                fmt_stat(r.get('W', '')),
                                fmt_stat(r.get('L', '')),
                                fmt_stat(r.get('IP', '')),
                                fmt_stat(r.get('H_Pitch', r.get('H_pitch', ''))),
                                fmt_stat(r.get('ER', '')),
                                fmt_stat(r.get('SO_Pitch', r.get('K', ''))),
                                fmt_stat(r.get('BB_Pitch', '')),
                                fmt_stat(r.get('HR_Pitch', '')),
                                fmt_stat(r.get('ERA', ''), 3),
                                fmt_stat(r.get('WHIP', ''), 3),
                                fmt_stat(r.get('R%', '')),
                                _weekly_ros12(r),
                                _weekly_ros_pg(r),
                                _weekly_ros15(r),
                                fmt_stat(r.get('RFS12', '')),
                                fmt_stat(r.get('RFS15', '')),
                                fmt_stat(r.get('Team_Games', r.get('Games', ''))),
                                _get_ha(r),
                                _get_rl_weekly(r),
                                _fmt_ts(r.get('Timestamp', '')),
                            ]) + ' |')

                else:
                    # ── DAILY: match Rudy's SQL queries ──────────────────────
                    has_pitcher_col = 'PitcherName' in sample_keys
                    has_throws_col = 'Throws' in sample_keys

                    if not is_pitcher_group:
                        # Hitter header: Name, Team, H, Pos, Y! Pos, Date, Opp, [Pitcher, R/L,] $, G, PA, R, HR, RBI, SB, AVG, OBP, SLG, R%, ROS12, $/G, ROS15, Timestamp
                        header = ['Name', 'Team', 'H', 'Pos', 'Y! Pos', 'Date', 'Opp']
                        if has_pitcher_col:
                            header.append('Pitcher')
                        if has_throws_col:
                            header.append('R/L')
                        header += ['$', 'PTS', 'G', 'PA', 'R', 'HR', 'RBI', 'SB',
                                   'AVG', 'OBP', 'SLG',
                                   'R%', 'ROS12', '$/G', 'ROS15', 'Timestamp']
                        lines.append('| ' + ' | '.join(header) + ' |')
                        lines.append('|' + '---|' * len(header))
                        for fa in top:
                            r = fa['row']
                            row_parts = [
                                fa['name'], fa['team'],
                                _clean_str(r.get('Handedness', '')),
                                fa['pos'],
                                _clean_str(r.get('Y! Pos', '')),
                                _get_date_str(r),
                                _clean_str(r.get('Opp', '')),
                            ]
                            if has_pitcher_col:
                                row_parts.append(_clean_str(r.get('PitcherName', '')))
                            if has_throws_col:
                                row_parts.append(_clean_str(r.get('Throws', '')))
                            row_parts += [
                                str(round(fa['dollar'], 1)),
                                fmt_stat(r.get('PTS', '')),
                                fmt_stat(r.get('G', '')),
                                fmt_stat(r.get('PA', '')),
                                fmt_stat(r.get('R', '')),
                                fmt_stat(r.get('HR', '')),
                                fmt_stat(r.get('RBI', '')),
                                fmt_stat(r.get('SB', '')),
                                fmt_stat(r.get('AVG', ''), 3),
                                fmt_stat(r.get('OBP', ''), 3),
                                fmt_stat(r.get('SLG', ''), 3),
                                fmt_stat(r.get('R%', '')),
                                _daily_ros12(r),
                                _daily_ros_pg(r),
                                _daily_ros15(r),
                                _fmt_ts(r.get('Timestamp', '')),
                            ]
                            lines.append('| ' + ' | '.join(row_parts) + ' |')
                    else:
                        # Pitcher header: Name, Team, H, Pos, Y! Pos, Date, Opp, $, PTS, GS, QS, W, L, IP, H, ER, K, BB, HR, ERA, WHIP, R%, ROS12, $/G, ROS15, Timestamp
                        header = ['Name', 'Team', 'H', 'Pos', 'Y! Pos', 'Date', 'Opp', '$', 'PTS',
                                  'GS', 'QS', 'W', 'L', 'IP', 'H', 'ER', 'K', 'BB', 'HR',
                                  'ERA', 'WHIP',
                                  'R%', 'ROS12', '$/G', 'ROS15', 'Timestamp']
                        lines.append('| ' + ' | '.join(header) + ' |')
                        lines.append('|' + '---|' * len(header))
                        for fa in top:
                            r = fa['row']
                            lines.append('| ' + ' | '.join([
                                fa['name'], fa['team'],
                                _clean_str(r.get('Handedness', '')),
                                fa['pos'],
                                _clean_str(r.get('Y! Pos', '')),
                                _get_date_str(r),
                                _clean_str(r.get('Opp', '')),
                                str(round(fa['dollar'], 1)),
                                fmt_stat(r.get('PTS', '')),
                                fmt_stat(r.get('GS', '')),
                                fmt_stat(r.get('QS', '')),
                                fmt_stat(r.get('W', '')),
                                fmt_stat(r.get('L', '')),
                                fmt_stat(r.get('IP', '')),
                                fmt_stat(r.get('H_Pitch', r.get('H_pitch', ''))),
                                fmt_stat(r.get('ER', '')),
                                fmt_stat(r.get('SO_Pitch', r.get('K', ''))),
                                fmt_stat(r.get('BB_Pitch', '')),
                                fmt_stat(r.get('HR_Pitch', '')),
                                fmt_stat(r.get('ERA', ''), 3),
                                fmt_stat(r.get('WHIP', ''), 3),
                                fmt_stat(r.get('R%', '')),
                                _daily_ros12(r),
                                _daily_ros_pg(r),
                                _daily_ros15(r),
                                _fmt_ts(r.get('Timestamp', '')),
                            ]) + ' |')

            return "\n".join(lines)

        def generate_weekly_start_sit(target_team: str) -> str:
            """Generate Weekly Start/Sit - shows user's team with weekly projections (Opp, G, stats)"""
            global _weekly_projections_df

            # Fetch weekly projections if not cached
            if _weekly_projections_df is None:
                try:
                    svc = ProjectionService(projection_type="weekly")
                    _weekly_projections_df = svc.fetch_projections()
                    logger.info(f"Fetched {len(_weekly_projections_df)} weekly projections")
                except Exception as e:
                    logger.error(f"Failed to fetch weekly projections: {e}")
                    return "Could not fetch weekly projections. Please try again later."

            weekly_df = _weekly_projections_df

            # Filter to requested league type
            if 'LeagueType' in weekly_df.columns:
                type_df = weekly_df[weekly_df['LeagueType'] == requested_type]
                if len(type_df) > 0:
                    weekly_df = type_df

            # Filter by AL/NL for AL12/NL12
            if requested_type == 'AL12' and 'League' in weekly_df.columns:
                weekly_df = weekly_df[weekly_df['League'] == 'AL']
            elif requested_type == 'NL12' and 'League' in weekly_df.columns:
                weekly_df = weekly_df[weekly_df['League'] == 'NL']

            matched_team = find_team_name(target_team)
            if not matched_team:
                return f"Could not find team matching '{target_team}'. Available teams: {', '.join(all_team_names)}"

            # Platform-aware: build projection lookup first to determine id_col
            weekly_lookup, id_col = build_projection_lookup(weekly_df)
            team_ids = get_team_player_ids(matched_team, id_col)

            # Match team players to weekly projections
            hitter_rows = []
            pitcher_rows = []
            inactive_hitters = []
            inactive_pitchers = []

            # Get ROS lookup for inactive player values (same id_col for consistent matching)
            ros_lookup, _ = fetch_ros_lookup(id_col)

            for match_id, roster_entry in team_ids.items():
                player = roster_entry.player
                weekly_row = weekly_lookup.get(match_id)

                if weekly_row is not None:
                    name = str(weekly_row.get('Name', player.name))
                    name = _re.sub(r'\[player id=\d+\]|\[/player\]', '', name).strip()
                    pos = str(weekly_row.get('Pos', player.position or '?'))
                    team = str(weekly_row.get('Team', player.team or '?'))
                    opp = str(weekly_row.get('Opp', ''))
                    if opp in ('nan', 'None'):
                        opp = ''
                    dollar = weekly_row.get('$', 0)
                    try:
                        dollar = float(dollar) if str(dollar) not in ('nan', 'None', '') else 0.0
                    except (ValueError, TypeError):
                        dollar = 0.0

                    games = weekly_row.get('G', '')
                    try:
                        games = int(float(games)) if str(games) not in ('nan', 'None', '') else ''
                    except (ValueError, TypeError):
                        games = ''

                    # Get weekly-specific fields
                    week_of = weekly_row.get('Week of', '')
                    team_games = weekly_row.get('Team_Games', '')
                    home_away = ''
                    t_home = weekly_row.get('Team_HomeGames', '')
                    t_away = weekly_row.get('Team_AwayGames', '')
                    if str(t_home) not in ('nan', 'None', '') and str(t_away) not in ('nan', 'None', ''):
                        home_away = f"{fmt_stat(t_home)}/{fmt_stat(t_away)}"

                    is_pitcher = pos.upper() in ('SP', 'RP', 'P')

                    # ROS context columns
                    ros_row_w = ros_lookup.get(match_id)
                    ros12 = ''
                    ros_pg = ''
                    ros15 = ''
                    if ros_row_w is not None:
                        rd = ros_row_w.get('$', '')
                        if str(rd) not in ('nan', 'None', ''):
                            ros12 = fmt_stat(rd)
                        rpg = ros_row_w.get('$/G$', '')
                        if str(rpg) not in ('nan', 'None', ''):
                            ros_pg = fmt_stat(rpg)
                        r15 = ros_row_w.get('$ROS15$', '')
                        if str(r15) not in ('nan', 'None', ''):
                            ros15 = fmt_stat(r15)
                    # Also check weekly row directly for ROS columns ($ROS12$, ROS12 $/G, $ROS15$)
                    if not ros12:
                        for k in ('$ROS12$', 'ROS12'):
                            r12_w = weekly_row.get(k, '')
                            if str(r12_w) not in ('nan', 'None', ''):
                                ros12 = fmt_stat(r12_w)
                                break
                    if not ros_pg:
                        for k in ('ROS12 $/G', '$/G'):
                            rpg_w = weekly_row.get(k, '')
                            if str(rpg_w) not in ('nan', 'None', ''):
                                ros_pg = fmt_stat(rpg_w)
                                break
                    if not ros15:
                        for k in ('$ROS15$', 'ROS15'):
                            r15_w = weekly_row.get(k, '')
                            if str(r15_w) not in ('nan', 'None', ''):
                                ros15 = fmt_stat(r15_w)
                                break

                    handedness = _clean_str(weekly_row.get('Handedness', ''))
                    y_pos = _clean_str(weekly_row.get('Y! Pos', ''))
                    wof_str = _get_wof(weekly_row)
                    obp_dollar = fmt_stat(weekly_row.get('$/G$', ''))
                    mt_dollar = fmt_stat(weekly_row.get('$ MT$', ''))
                    fs_dollar = fmt_stat(weekly_row.get('$ FS$', ''))
                    r_pct = fmt_stat(weekly_row.get('R%', ''))
                    rfs12 = fmt_stat(weekly_row.get('RFS12', ''))
                    rfs15 = fmt_stat(weekly_row.get('RFS15', ''))
                    rl_weekly = _get_rl_weekly(weekly_row)
                    ts_weekly = _fmt_ts(weekly_row.get('Timestamp', ''))

                    pts_weekly = fmt_stat(weekly_row.get('PTS', ''))

                    if is_pitcher:
                        pitcher_rows.append((dollar, [
                            name, team, handedness, pos, y_pos, wof_str, opp,
                            str(round(dollar, 1)), pts_weekly,
                            obp_dollar, mt_dollar, fs_dollar,
                            fmt_stat(weekly_row.get('GS', '')), fmt_stat(weekly_row.get('QS', '')),
                            fmt_stat(weekly_row.get('W', '')), fmt_stat(weekly_row.get('L', '')),
                            fmt_stat(weekly_row.get('IP', '')),
                            fmt_stat(weekly_row.get('H_Pitch', weekly_row.get('H_pitch', ''))),
                            fmt_stat(weekly_row.get('ER', '')),
                            fmt_stat(weekly_row.get('SO_Pitch', weekly_row.get('K', ''))),
                            fmt_stat(weekly_row.get('BB_Pitch', '')),
                            fmt_stat(weekly_row.get('HR_Pitch', '')),
                            fmt_stat(weekly_row.get('ERA', ''), 2), fmt_stat(weekly_row.get('WHIP', ''), 2),
                            r_pct, ros12, ros_pg, ros15, rfs12, rfs15,
                            fmt_stat(team_games), home_away, rl_weekly, ts_weekly
                        ]))
                    else:
                        hitter_rows.append((dollar, [
                            name, team, handedness, pos, y_pos, wof_str, opp,
                            str(round(dollar, 1)), pts_weekly,
                            obp_dollar, mt_dollar, fs_dollar,
                            str(games),
                            fmt_stat(weekly_row.get('PA', '')),
                            fmt_stat(weekly_row.get('R', '')), fmt_stat(weekly_row.get('HR', '')),
                            fmt_stat(weekly_row.get('RBI', '')), fmt_stat(weekly_row.get('SB', '')),
                            fmt_stat(weekly_row.get('AVG', ''), 3), fmt_stat(weekly_row.get('OBP', ''), 3),
                            fmt_stat(weekly_row.get('SLG', ''), 3),
                            r_pct, ros12, ros_pg, ros15, rfs12, rfs15,
                            fmt_stat(team_games), home_away, rl_weekly, ts_weekly
                        ]))
                else:
                    # No weekly projection = inactive player. Cross-ref with ROS
                    ros_row = ros_lookup.get(match_id)
                    pos = player.position or '?'
                    is_pitcher = pos.upper() in ('SP', 'RP', 'P')
                    ros_dollar = ''
                    ros_per_game = ''
                    if ros_row is not None:
                        rd = ros_row.get('$', '')
                        if str(rd) not in ('nan', 'None', ''):
                            ros_dollar = fmt_stat(rd)
                        rpg = ros_row.get('$/G$', '')
                        if str(rpg) not in ('nan', 'None', ''):
                            ros_per_game = fmt_stat(rpg)

                    inactive_entry = [player.name, player.team or '?', ros_dollar, ros_per_game]
                    sort_val = float(ros_dollar) if ros_dollar else -999
                    if is_pitcher:
                        inactive_pitchers.append((sort_val, inactive_entry))
                    else:
                        inactive_hitters.append((sort_val, inactive_entry))

            # Sort by $ descending
            hitter_rows.sort(key=lambda x: x[0], reverse=True)
            pitcher_rows.sort(key=lambda x: x[0], reverse=True)
            inactive_hitters.sort(key=lambda x: x[0], reverse=True)
            inactive_pitchers.sort(key=lambda x: x[0], reverse=True)

            lines = []
            lines.append(f"**Weekly Start/Sit: {matched_team} ({requested_type})**\n")

            # Hitters table
            if hitter_rows:
                lines.append(f"**Hitters ({len(hitter_rows)})**\n")
                h_header = ['Name', 'Team', 'H', 'Pos', 'Y! Pos', 'W/o', 'Opp',
                            '$', 'PTS', '$OBP$', '$MT', '$FS',
                            'G', 'PA', 'R', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'SLG',
                            'R%', 'ROS12', '$/G', 'ROS15', 'RFS12', 'RFS15',
                            'Games', 'H/A', 'R/L', 'Timestamp']
                lines.append('| ' + ' | '.join(h_header) + ' |')
                lines.append('|' + '---|' * len(h_header))
                for _, row_data in hitter_rows:
                    lines.append('| ' + ' | '.join(row_data) + ' |')

            # Pitchers table
            if pitcher_rows:
                lines.append(f"\n**Pitchers ({len(pitcher_rows)})**\n")
                p_header = ['Name', 'Team', 'H', 'Pos', 'Y! Pos', 'W/o', 'Opp',
                            '$', 'PTS', '$OBP$', '$MT', '$FS',
                            'GS', 'QS', 'W', 'L', 'IP', 'H', 'ER', 'K', 'BB', 'HR_P',
                            'ERA', 'WHIP',
                            'R%', 'ROS12', '$/G', 'ROS15', 'RFS12', 'RFS15',
                            'Games', 'H/A', 'R/L', 'Timestamp']
                lines.append('| ' + ' | '.join(p_header) + ' |')
                lines.append('|' + '---|' * len(p_header))
                for _, row_data in pitcher_rows:
                    lines.append('| ' + ' | '.join(row_data) + ' |')

            # Inactive hitters
            if inactive_hitters:
                lines.append(f"\n**Inactive Hitters ({len(inactive_hitters)})** - No weekly projection\n")
                lines.append('| Name | Team | ROS $ | $/G |')
                lines.append('|---|---|---|---|')
                for _, row_data in inactive_hitters:
                    lines.append('| ' + ' | '.join(row_data) + ' |')

            # Inactive pitchers
            if inactive_pitchers:
                lines.append(f"\n**Inactive Pitchers ({len(inactive_pitchers)})** - No weekly projection\n")
                lines.append('| Name | Team | ROS $ | $/G |')
                lines.append('|---|---|---|---|')
                for _, row_data in inactive_pitchers:
                    lines.append('| ' + ' | '.join(row_data) + ' |')

            if not hitter_rows and not pitcher_rows and not inactive_hitters and not inactive_pitchers:
                lines.append("No weekly projection data found for this team's players.")

            return "\n".join(lines)

        def generate_daily_start_sit(target_team: str, use_tomorrow: bool = False) -> str:
            """Generate Daily Start/Sit - shows user's team with today's/tomorrow's projections"""
            global _daily_projections_df, _daily_cache_date

            day_label = "Tomorrow" if use_tomorrow else "Today"

            # Invalidate daily cache if EST date has changed
            today_est = _get_target_date(False)
            if _daily_cache_date != today_est:
                _daily_projections_df = None
                _daily_cache_date = today_est
                logger.info(f"Daily cache invalidated for new date: {today_est}")

            # Fetch daily projections if not cached
            if _daily_projections_df is None:
                try:
                    svc = ProjectionService(projection_type="daily")
                    _daily_projections_df = svc.fetch_projections()
                    logger.info(f"Fetched {len(_daily_projections_df)} daily projections")
                except Exception as e:
                    logger.error(f"Failed to fetch daily projections: {e}")
                    return f"Could not fetch daily projections. Please try again later."

            daily_df = _daily_projections_df

            # Filter to requested league type
            if 'LeagueType' in daily_df.columns:
                type_df = daily_df[daily_df['LeagueType'] == requested_type]
                if len(type_df) > 0:
                    daily_df = type_df

            # Filter by AL/NL for AL12/NL12
            if requested_type == 'AL12' and 'League' in daily_df.columns:
                daily_df = daily_df[daily_df['League'] == 'AL']
            elif requested_type == 'NL12' and 'League' in daily_df.columns:
                daily_df = daily_df[daily_df['League'] == 'NL']

            # Filter by date (EST, with fallback to most recent date in data)
            daily_df = _filter_daily_df_by_date(daily_df, use_tomorrow=use_tomorrow)

            matched_team = find_team_name(target_team)
            if not matched_team:
                return f"Could not find team matching '{target_team}'. Available teams: {', '.join(all_team_names)}"

            # Platform-aware: build projection lookup first to determine id_col
            daily_lookup, id_col = build_projection_lookup(daily_df)
            team_ids = get_team_player_ids(matched_team, id_col)

            hitter_rows = []
            pitcher_rows = []
            inactive_hitters = []
            inactive_pitchers = []

            # ROS lookup for inactive player values (same id_col for consistent matching)
            ros_lookup, _ = fetch_ros_lookup(id_col)

            for match_id, roster_entry in team_ids.items():
                player = roster_entry.player
                daily_row = daily_lookup.get(match_id)

                if daily_row is not None:
                    name = str(daily_row.get('Name', player.name))
                    name = _re.sub(r'\[player id=\d+\]|\[/player\]', '', name).strip()
                    pos = str(daily_row.get('Pos', player.position or '?'))
                    team = str(daily_row.get('Team', player.team or '?'))
                    opp = str(daily_row.get('Opp', ''))
                    if opp in ('nan', 'None'):
                        opp = ''
                    dollar = daily_row.get('$', 0)
                    try:
                        dollar = float(dollar) if str(dollar) not in ('nan', 'None', '') else 0.0
                    except (ValueError, TypeError):
                        dollar = 0.0

                    # Get ROS context - try daily row first (has $ROS12$ and ROS12 $/G), then ROS lookup
                    ros12 = _daily_ros12(daily_row)
                    ros_pg = _daily_ros_pg(daily_row)
                    if not ros12 or not ros_pg:
                        ros_row = ros_lookup.get(match_id)
                        if ros_row is not None:
                            if not ros12:
                                rd = ros_row.get('$', '')
                                if str(rd) not in ('nan', 'None', ''):
                                    ros12 = fmt_stat(rd)
                            if not ros_pg:
                                rpg = ros_row.get('$/G$', '')
                                if str(rpg) not in ('nan', 'None', ''):
                                    ros_pg = fmt_stat(rpg)

                    is_pitcher = pos.upper() in ('SP', 'RP', 'P')
                    ros15 = _daily_ros15(daily_row)
                    r_pct = fmt_stat(daily_row.get('R%', ''))
                    ts_daily = _fmt_ts(daily_row.get('Timestamp', ''))
                    handedness_d = _clean_str(daily_row.get('Handedness', ''))
                    y_pos_d = _clean_str(daily_row.get('Y! Pos', ''))
                    date_d = _get_date_str(daily_row)

                    pts_daily = fmt_stat(daily_row.get('PTS', ''))

                    if is_pitcher:
                        pitcher_rows.append((dollar, [
                            name, team, handedness_d, pos, y_pos_d, date_d, opp,
                            str(round(dollar, 1)), pts_daily,
                            fmt_stat(daily_row.get('GS', '')), fmt_stat(daily_row.get('QS', '')),
                            fmt_stat(daily_row.get('W', '')), fmt_stat(daily_row.get('L', '')),
                            fmt_stat(daily_row.get('IP', '')),
                            fmt_stat(daily_row.get('H_Pitch', daily_row.get('H_pitch', ''))),
                            fmt_stat(daily_row.get('ER', '')),
                            fmt_stat(daily_row.get('SO_Pitch', daily_row.get('K', ''))),
                            fmt_stat(daily_row.get('BB_Pitch', '')),
                            fmt_stat(daily_row.get('HR_Pitch', '')),
                            fmt_stat(daily_row.get('ERA', ''), 3), fmt_stat(daily_row.get('WHIP', ''), 3),
                            r_pct, ros12, ros_pg, ros15, ts_daily
                        ]))
                    else:
                        pitcher_name_d = _clean_str(daily_row.get('PitcherName', ''))
                        throws_d = _clean_str(daily_row.get('Throws', ''))
                        hitter_rows.append((dollar, [
                            name, team, handedness_d, pos, y_pos_d, date_d, opp,
                            pitcher_name_d, throws_d,
                            str(round(dollar, 1)), pts_daily,
                            fmt_stat(daily_row.get('G', '')),
                            fmt_stat(daily_row.get('PA', '')),
                            fmt_stat(daily_row.get('R', '')), fmt_stat(daily_row.get('HR', '')),
                            fmt_stat(daily_row.get('RBI', '')), fmt_stat(daily_row.get('SB', '')),
                            fmt_stat(daily_row.get('AVG', ''), 3), fmt_stat(daily_row.get('OBP', ''), 3),
                            fmt_stat(daily_row.get('SLG', ''), 3),
                            r_pct, ros12, ros_pg, ros15, ts_daily
                        ]))
                else:
                    # No daily projection = inactive/no game. Cross-ref with ROS
                    ros_row = ros_lookup.get(match_id)
                    pos = player.position or '?'
                    is_pitcher = pos.upper() in ('SP', 'RP', 'P')
                    ros_dollar = ''
                    ros_per_game = ''
                    if ros_row is not None:
                        rd = ros_row.get('$', '')
                        if str(rd) not in ('nan', 'None', ''):
                            ros_dollar = fmt_stat(rd)
                        rpg = ros_row.get('$/G$', '')
                        if str(rpg) not in ('nan', 'None', ''):
                            ros_per_game = fmt_stat(rpg)

                    inactive_entry = [player.name, player.team or '?', ros_dollar, ros_per_game]
                    sort_val = float(ros_dollar) if ros_dollar else -999
                    if is_pitcher:
                        inactive_pitchers.append((sort_val, inactive_entry))
                    else:
                        inactive_hitters.append((sort_val, inactive_entry))

            # Sort all by $ descending
            hitter_rows.sort(key=lambda x: x[0], reverse=True)
            pitcher_rows.sort(key=lambda x: x[0], reverse=True)
            inactive_hitters.sort(key=lambda x: x[0], reverse=True)
            inactive_pitchers.sort(key=lambda x: x[0], reverse=True)

            lines = []
            lines.append(f"**{day_label} Start/Sit: {matched_team} ({requested_type})**\n")

            # Hitters table
            if hitter_rows:
                lines.append(f"**Hitters ({len(hitter_rows)})**\n")
                h_header = ['Name', 'Team', 'H', 'Pos', 'Y! Pos', 'Date', 'Opp',
                            'Pitcher', 'R/L', '$', 'PTS',
                            'G', 'PA', 'R', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'SLG',
                            'R%', 'ROS12', '$/G', 'ROS15', 'Timestamp']
                lines.append('| ' + ' | '.join(h_header) + ' |')
                lines.append('|' + '---|' * len(h_header))
                for _, row_data in hitter_rows:
                    lines.append('| ' + ' | '.join(row_data) + ' |')

            # Pitchers table
            if pitcher_rows:
                lines.append(f"\n**Pitchers ({len(pitcher_rows)})**\n")
                p_header = ['Name', 'Team', 'H', 'Pos', 'Y! Pos', 'Date', 'Opp', '$', 'PTS',
                            'GS', 'QS', 'W', 'L', 'IP', 'H', 'ER', 'K', 'BB', 'HR',
                            'ERA', 'WHIP',
                            'R%', 'ROS12', '$/G', 'ROS15', 'Timestamp']
                lines.append('| ' + ' | '.join(p_header) + ' |')
                lines.append('|' + '---|' * len(p_header))
                for _, row_data in pitcher_rows:
                    lines.append('| ' + ' | '.join(row_data) + ' |')

            # Inactive hitters (no game today / not on active roster)
            if inactive_hitters:
                lines.append(f"\n**Inactive Hitters ({len(inactive_hitters)})** - No game {day_label.lower()}\n")
                lines.append('| Name | Team | ROS $ | $/G |')
                lines.append('|---|---|---|---|')
                for _, row_data in inactive_hitters:
                    lines.append('| ' + ' | '.join(row_data) + ' |')

            # Inactive pitchers
            if inactive_pitchers:
                lines.append(f"\n**Inactive Pitchers ({len(inactive_pitchers)})** - No game {day_label.lower()}\n")
                lines.append('| Name | Team | ROS $ | $/G |')
                lines.append('|---|---|---|---|')
                for _, row_data in inactive_pitchers:
                    lines.append('| ' + ' | '.join(row_data) + ' |')

            if not hitter_rows and not pitcher_rows and not inactive_hitters and not inactive_pitchers:
                lines.append(f"No daily projection data found for {day_label.lower()}.")

            return "\n".join(lines)

        # ============================================================
        # TRIGGER PHRASE DETECTION - bypass GPT for hard-coded reports
        # ============================================================
        msg_lower = request.message.lower()

        league_report_triggers = [
            'league overview', 'league review', 'leaguereview', 'league report',
            'show me the league', 'team rankings', 'rank all teams',
            'roto standings', 'roto ranks', 'category rankings',
            'how does the league look', 'league standings',
            'show all teams', 'show rankings'
        ]

        team_overview_triggers = ['team overview', 'team report', 'show my team', 'my team overview']

        weekly_pickup_triggers = ['weekly pickups', 'weekly pickup', 'weekly picks', 'week pickups',
                                  'weekly best available', 'weekly fa']
        daily_pickup_triggers = ['daily pickups', 'daily pickup', 'daily picks', 'today pickups',
                                 'today\'s pickups', 'daily best available', 'daily fa',
                                 'today best available']
        tomorrow_pickup_triggers = ['tomorrow pickups', 'tomorrow pickup', 'tomorrow picks',
                                    'tomorrow\'s pickups', 'tomorrow best available', 'tomorrow fa']
        weekly_start_sit_triggers = ['weekly start/sit', 'weekly start sit',
                                     'weekly roster', 'weekly team', 'this week team',
                                     'my week', 'week overview', 'week start']
        daily_start_sit_triggers = ['today start/sit', 'today start sit', 'daily start/sit',
                                    'daily start sit', 'today roster', 'today team',
                                    'today overview', 'today\'s start', 'my today']
        tomorrow_start_sit_triggers = ['tomorrow start/sit', 'tomorrow start sit',
                                       'tomorrow roster', 'tomorrow team',
                                       'tomorrow overview', 'tomorrow\'s start', 'my tomorrow']

        # Order matters: check more specific triggers first (tomorrow before today, daily before weekly)
        is_league_report = any(trigger in msg_lower for trigger in league_report_triggers)
        is_team_overview = any(trigger in msg_lower for trigger in team_overview_triggers)
        is_tomorrow_pickups = any(trigger in msg_lower for trigger in tomorrow_pickup_triggers)
        is_tomorrow_start_sit = any(trigger in msg_lower for trigger in tomorrow_start_sit_triggers)
        is_daily_start_sit = any(trigger in msg_lower for trigger in daily_start_sit_triggers)
        is_weekly_pickups = any(trigger in msg_lower for trigger in weekly_pickup_triggers)
        is_daily_pickups = any(trigger in msg_lower for trigger in daily_pickup_triggers)
        is_weekly_start_sit = any(trigger in msg_lower for trigger in weekly_start_sit_triggers)

        if is_league_report:
            # BYPASS GPT - return hard-coded league report directly
            logger.info(f"League report trigger detected: '{request.message}' - bypassing GPT")
            report_response = generate_league_report()

            # Save to chat history
            try:
                chat_record = Chat(
                    league_id=str(request.league_id),
                    user_message=request.message,
                    bot_response=report_response
                )
                db.add(chat_record)
                db.commit()
            except Exception as e:
                logger.warning(f"Could not save chat: {e}")
                db.rollback()

            # Hard-coded reports do NOT count against message limits

            return ChatResponse(
                message=request.message,
                response=report_response,
                tokens_used=0,
                messages_remaining=messages_remaining,
                limit_info=limit_message
            )

        if is_team_overview:
            # BYPASS GPT - return hard-coded team overview
            # Extract team name from message (remove trigger phrase and league type to find team name)
            team_search = msg_lower
            for trigger in team_overview_triggers:
                team_search = team_search.replace(trigger, '')
            # Strip league type identifiers
            for lt in AVAILABLE_LEAGUE_TYPES:
                team_search = team_search.replace(lt.lower(), '')
            target_team = team_search.strip().strip(':').strip()

            # If no team name found in remaining text, check for team names in full message
            if not target_team or len(target_team) < 2:
                for t in all_team_names:
                    t_clean = t.lower().strip().lstrip('@')
                    if t_clean in msg_lower:
                        target_team = t
                        break

            if not target_team or len(target_team) < 2:
                report_response = f"Please specify a team name. Example: 'team overview rudygamble'\n\nAvailable teams: {', '.join(all_team_names)}"
            else:
                logger.info(f"Team overview trigger detected for '{target_team}' - bypassing GPT")
                report_response = generate_team_overview(target_team)

            # Save to chat history
            try:
                chat_record = Chat(
                    league_id=str(request.league_id),
                    user_message=request.message,
                    bot_response=report_response
                )
                db.add(chat_record)
                db.commit()
            except Exception as e:
                logger.warning(f"Could not save chat: {e}")
                db.rollback()

            # Hard-coded reports do NOT count against message limits

            return ChatResponse(
                message=request.message,
                response=report_response,
                tokens_used=0,
                messages_remaining=messages_remaining,
                limit_info=limit_message
            )

        if is_weekly_start_sit:
            # BYPASS GPT - return weekly start/sit for user's team
            # Extract team name (same logic as team overview)
            team_search = msg_lower
            for trigger in weekly_start_sit_triggers:
                team_search = team_search.replace(trigger, '')
            for lt in AVAILABLE_LEAGUE_TYPES:
                team_search = team_search.replace(lt.lower(), '')
            target_team = team_search.strip().strip(':').strip()

            if not target_team or len(target_team) < 2:
                for t in all_team_names:
                    t_clean = t.lower().strip().lstrip('@')
                    if t_clean in msg_lower:
                        target_team = t
                        break

            if not target_team or len(target_team) < 2:
                report_response = f"Please specify a team name. Example: 'weekly start/sit rudygamble'\n\nAvailable teams: {', '.join(all_team_names)}"
            else:
                logger.info(f"Weekly start/sit trigger detected for '{target_team}' - bypassing GPT")
                report_response = generate_weekly_start_sit(target_team)

            try:
                chat_record = Chat(
                    league_id=str(request.league_id),
                    user_message=request.message,
                    bot_response=report_response
                )
                db.add(chat_record)
                db.commit()
            except Exception as e:
                logger.warning(f"Could not save chat: {e}")
                db.rollback()

            # Hard-coded reports do NOT count against message limits

            return ChatResponse(
                message=request.message,
                response=report_response,
                tokens_used=0,
                messages_remaining=messages_remaining,
                limit_info=limit_message
            )

        if is_daily_start_sit or is_tomorrow_start_sit:
            # BYPASS GPT - return daily start/sit for user's team
            use_tomorrow = is_tomorrow_start_sit
            day_label = "Tomorrow" if use_tomorrow else "Today"
            team_search = msg_lower
            all_daily_ss_triggers = daily_start_sit_triggers + tomorrow_start_sit_triggers
            for trigger in all_daily_ss_triggers:
                team_search = team_search.replace(trigger, '')
            for lt in AVAILABLE_LEAGUE_TYPES:
                team_search = team_search.replace(lt.lower(), '')
            target_team = team_search.strip().strip(':').strip()

            if not target_team or len(target_team) < 2:
                for t in all_team_names:
                    t_clean = t.lower().strip().lstrip('@')
                    if t_clean in msg_lower:
                        target_team = t
                        break

            if not target_team or len(target_team) < 2:
                report_response = f"Please specify a team name. Example: '{day_label.lower()} start/sit rudygamble'\n\nAvailable teams: {', '.join(all_team_names)}"
            else:
                logger.info(f"{day_label} start/sit trigger detected for '{target_team}' - bypassing GPT")
                report_response = generate_daily_start_sit(target_team, use_tomorrow=use_tomorrow)

            try:
                chat_record = Chat(
                    league_id=str(request.league_id),
                    user_message=request.message,
                    bot_response=report_response
                )
                db.add(chat_record)
                db.commit()
            except Exception as e:
                logger.warning(f"Could not save chat: {e}")
                db.rollback()

            # Hard-coded reports do NOT count against message limits

            return ChatResponse(
                message=request.message,
                response=report_response,
                tokens_used=0,
                messages_remaining=messages_remaining,
                limit_info=limit_message
            )

        if is_tomorrow_pickups or is_weekly_pickups or is_daily_pickups:
            # BYPASS GPT - return hard-coded pickup report
            if is_weekly_pickups:
                pickup_type = "weekly"
                use_tomorrow = False
            elif is_tomorrow_pickups:
                pickup_type = "daily"
                use_tomorrow = True
            else:
                pickup_type = "daily"
                use_tomorrow = False
            label = "Tomorrow" if use_tomorrow else ("Weekly" if pickup_type == "weekly" else "Today")
            logger.info(f"{label} pickups trigger detected - bypassing GPT")
            report_response = generate_pickups_report(pickup_type, use_tomorrow=use_tomorrow)

            try:
                chat_record = Chat(
                    league_id=str(request.league_id),
                    user_message=request.message,
                    bot_response=report_response
                )
                db.add(chat_record)
                db.commit()
            except Exception as e:
                logger.warning(f"Could not save chat: {e}")
                db.rollback()

            # Hard-coded reports do NOT count against message limits

            return ChatResponse(
                message=request.message,
                response=report_response,
                tokens_used=0,
                messages_remaining=messages_remaining,
                limit_info=limit_message
            )

        # ============================================================
        # NORMAL GPT FLOW (for non-report queries)
        # ============================================================

        # Smart context filtering: detect which team(s) the user is asking about
        # Only send relevant team rosters to prevent GPT confusion
        msg_clean = request.message  # preserve original case for matching

        # Check for team mentions in user message
        mentioned_teams = []
        for team_name in all_team_names:
            # Check various patterns: exact name, @name, partial match
            team_lower = team_name.lower()
            team_no_at = team_lower.lstrip('@')
            if (team_lower in msg_lower or
                team_no_at in msg_lower or
                f"@{team_no_at}" in msg_lower):
                mentioned_teams.append(team_name)

        # Determine which teams' rosters to include
        comparison_keywords = ['compare', 'comparison', 'all teams', 'each team', 'every team',
                              'category totals', 'team rankings', 'rank teams', 'standings',
                              'best team', 'worst team', 'league summary',
                              'vs the other', 'vs other', 'other teams', 'against other',
                              'against the other', 'how did', 'how does', 'versus',
                              'show me all', 'all 15', 'all 12', 'all 10']
        is_comparison = any(kw in msg_lower for kw in comparison_keywords)

        # Detect free agent / best available queries
        fa_keywords = ['free agent', 'free agents', 'best available', 'available players',
                       'waiver', 'waivers', 'pickup', 'pick up', 'not on a team',
                       'not rostered', 'unrostered', 'fa list']
        is_fa_query = any(kw in msg_lower for kw in fa_keywords)

        if is_fa_query:
            # Free agent query - don't send team rosters, focus on FAs
            teams_to_show = mentioned_teams if mentioned_teams else []
            logger.info(f"Free agent query detected, teams_to_show={teams_to_show}")
        elif mentioned_teams and is_comparison:
            # User mentioned specific team(s) AND wants comparison - show rankings + those teams
            teams_to_show = mentioned_teams
            logger.info(f"Comparison query with specific teams: {mentioned_teams}")
        elif mentioned_teams and not is_comparison:
            # User asked about specific team(s) only
            teams_to_show = mentioned_teams
            logger.info(f"Single-team query detected: {mentioned_teams}")
        elif is_comparison:
            # Pure comparison query - just the rankings table
            teams_to_show = []
            logger.info("Comparison query - using rankings table only")
        else:
            # General query - send top 3 teams by $ to keep context manageable
            teams_to_show = ranked_teams[:3]
            logger.info(f"General query - sending top 3 teams: {teams_to_show}")

        # List selected team rosters with hitters and pitchers separated
        # USE STANDALONE FORMAT: each player on its own clearly labeled line to prevent GPT mixing up values
        if teams_to_show:
            for team_name in teams_to_show:
                hitters = teams_hitters.get(team_name, [])
                pitchers = teams_pitchers.get(team_name, [])
                no_proj = teams_no_projection.get(team_name, [])
                total = len(hitters) + len(pitchers)
                t = team_totals[team_name]

                # Put AUTHORITATIVE totals in a very prominent block BEFORE the roster
                context_text += f"===== TEAM '{team_name}' AUTHORITATIVE TOTALS (from PRE-CALCULATED rankings) =====\n"
                context_text += f"  TOTAL $: ${t['total']} | RANK: {t['rank']} out of {len(ranked_teams)}\n"
                context_text += f"  HITTING $: ${t['hitting']} | PITCHING $: ${t['pitching']}\n"
                _avg_obp_label = '$OBP' if 'OBP' in active_cats else '$AVG'
                _avg_obp_val = t['OBP'] if 'OBP' in active_cats else t['AVG']
                context_text += f"  $R: ${t['R']} | $HR: ${t['HR']} | $RBI: ${t['RBI']} | $SB: ${t['SB']} | {_avg_obp_label}: ${_avg_obp_val}\n"
                _p_extra = f" | $HLD: ${t['HLD']}" if 'HLD' in active_cats else (f" | $QS: ${t.get('QS', 0.0)}" if 'QS' in active_cats else "")
                context_text += f"  $W: ${t['W']} | $SV: ${t['SV']} | $K: ${t['K']} | $ERA: ${t['ERA']} | $WHIP: ${t['WHIP']}{_p_extra}\n"
                context_text += f"  USE THESE NUMBERS. DO NOT RECALCULATE.\n"
                context_text += f"===== ROSTER ({total} players) =====\n"

                if hitters:
                    context_text += f"  HITTERS ({len(hitters)}):\n"
                    for p in hitters[:50]:
                        context_text += f"    PLAYER: {p}\n"

                if pitchers:
                    context_text += f"  PITCHERS ({len(pitchers)}):\n"
                    for p in pitchers[:50]:
                        context_text += f"    PLAYER: {p}\n"

                if no_proj:
                    context_text += f"  NO PROJECTION DATA: {', '.join(no_proj)}\n"

                context_text += "\n"
        else:
            context_text += "NOTE: Full rosters available. Ask about a specific team to see player details.\n\n"

        # Check if user pasted NFBC IDs in their message - resolve them to player data
        nfbc_ids_in_msg = _re.findall(r'\b(\d{4,6})\b', request.message)
        if len(nfbc_ids_in_msg) >= 3:  # Likely a list of IDs (not just random numbers)
            logger.info(f"Detected {len(nfbc_ids_in_msg)} potential NFBC IDs in message")
            resolved_players = []
            unresolved_ids = []
            for nid in nfbc_ids_in_msg:
                # Look up in projections by NFBCID
                if _projections_df is not None and 'NFBCID' in _projections_df.columns:
                    player_rows = filtered_df[filtered_df['NFBCID'].astype(str) == nid]
                    if len(player_rows) > 0:
                        row = player_rows.iloc[0]
                        name = str(row.get('Name', 'Unknown'))
                        name = _re.sub(r'\[player id=\d+\]|\[/player\]', '', name).strip()
                        team = str(row.get('Team', '?'))
                        pos = str(row.get('Pos', '?'))
                        dollar_str = nfbc_lookup.get(nid, '')
                        resolved_players.append(f"{name} (NFBCID:{nid}, {pos}, {team}) [{dollar_str}]")
                    else:
                        unresolved_ids.append(nid)
                else:
                    unresolved_ids.append(nid)

            if resolved_players:
                context_text += f"\nPLAYER LOOKUP BY NFBC ID ({len(resolved_players)} found):\n"
                for p in resolved_players:
                    context_text += f"  - {p}\n"
            if unresolved_ids:
                context_text += f"  UNRESOLVED IDs: {', '.join(unresolved_ids)}\n"
            context_text += "\n"

        # Sort free agents by $ descending and show them
        if free_agents:
            # free_agents is list of (dollar_value, player_str) tuples
            free_agents.sort(key=lambda x: x[0], reverse=True)
            # Show more FAs if user is asking about free agents/best available
            fa_limit = 50 if is_fa_query else 20
            context_text += f"TOP FREE AGENTS (sorted by $ descending, showing top {min(fa_limit, len(free_agents))}):\n"
            for i, (fa_dollar, fa_str) in enumerate(free_agents[:fa_limit]):
                context_text += f"  PLAYER: {fa_str}\n"
        else:
            context_text += "NOTE: No free agents in this data (CSV only contains owned players)\n"

        # Named player lookup: if the user mentions players not in any roster,
        # search the full projection data so GPT doesn't have to hallucinate
        if _projections_df is not None:
            msg_lower = request.message.lower()
            # Build a lookup of all names already in context (roster + FA) to avoid dupes
            names_in_context = set()
            for _, p_str in free_agents:
                first_part = p_str.split('|')[0].strip().lower()
                names_in_context.add(first_part)
            for owner_players in list(teams_hitters.values()) + list(teams_pitchers.values()):
                for p_str in owner_players:
                    first_part = p_str.split('|')[0].strip().lower()
                    names_in_context.add(first_part)

            extra_players = []
            seen_keys = set()
            for _, row in filtered_df.iterrows():
                raw_name = str(row.get('Name', ''))
                clean = re.sub(r'\[player id=\d+\]|\[/player\]', '', raw_name).strip()
                if not clean:
                    continue
                clean_lower = clean.lower()
                if clean_lower in names_in_context or clean_lower in seen_keys:
                    continue
                # Check if any word combo from this name appears in the message
                words = clean_lower.split()
                if len(words) >= 2:
                    # Need at least first + last name match to avoid false positives
                    if words[-1] in msg_lower and words[0] in msg_lower:
                        seen_keys.add(clean_lower)
                        val = get_player_dollar_value(clean, None)
                        # Build projection string from row
                        p_pos = str(row.get('Pos', '?')).strip()
                        p_team = str(row.get('Team', '?')).strip()
                        if val:
                            extra_players.append(f"{clean} | Pos: {p_pos} | Team: {p_team} | {val.strip().strip('[]')}")
                        else:
                            # Build from row directly
                            row_parts = []
                            overall = row.get('$', '')
                            if overall and str(overall) not in ('nan', 'None', ''):
                                row_parts.append(f"${overall}")
                            for cat in ['PTS', '$R$', '$HR$', '$RBI$', '$SB$', '$AVG$', '$W$', '$SV$', '$K$', '$ERA$', '$WHIP$']:
                                v = row.get(cat, '')
                                if v and str(v) not in ('nan', 'None', ''):
                                    row_parts.append(f"{cat.replace('$','')}:{v}")
                            if row_parts:
                                extra_players.append(f"{clean} | Pos: {p_pos} | Team: {p_team} | {' '.join(row_parts)}")

            if extra_players:
                context_text += f"\nPLAYER LOOKUP (from projection data, not on any roster):\n"
                for ep in extra_players:
                    context_text += f"  PLAYER: {ep}\n"
                context_text += "\n"
                logger.info(f"Named player lookup: added {len(extra_players)} players to context")

        # Time-period detection: if message mentions week/today/tomorrow,
        # also look up named players in the weekly/daily projection data
        _time_label = None
        _time_df = None
        if 'week' in msg_lower:
            _time_label = 'WEEKLY'
            if _weekly_projections_df is None:
                try:
                    from app.services.projection_service import ProjectionService
                    svc = ProjectionService(projection_type="weekly")
                    _weekly_projections_df = svc.fetch_projections()
                except Exception as _te:
                    logger.warning(f"Could not load weekly data for time lookup: {_te}")
            _time_df = _weekly_projections_df
        elif 'tomorrow' in msg_lower:
            _time_label = 'TOMORROW'
            _time_df = _daily_projections_df
        elif 'today' in msg_lower:
            _time_label = 'TODAY'
            _time_df = _daily_projections_df

        if _time_label and _time_df is not None:
            try:
                # Filter to requested league type
                if 'LeagueType' in _time_df.columns:
                    _tdf = _time_df[_time_df['LeagueType'] == requested_type]
                    if len(_tdf) == 0:
                        _tdf = _time_df
                else:
                    _tdf = _time_df
                _time_players = []
                _seen_time = set()
                for _, row in _tdf.iterrows():
                    raw_name = str(row.get('Name', ''))
                    clean = re.sub(r'\[player id=\d+\]|\[/player\]', '', raw_name).strip()
                    if not clean:
                        continue
                    clean_lower = clean.lower()
                    if clean_lower in _seen_time:
                        continue
                    words = clean_lower.split()
                    if len(words) >= 2 and words[-1] in msg_lower and words[0] in msg_lower:
                        _seen_time.add(clean_lower)
                        p_pos = str(row.get('Pos', '?')).strip()
                        p_team = str(row.get('Team', '?')).strip()
                        row_parts = []
                        overall = row.get('$', '')
                        if overall and str(overall) not in ('nan', 'None', ''):
                            row_parts.append(f"${overall}")
                        for cat in ['GS', 'QS', 'W', 'SV', 'K', 'ERA', 'WHIP', 'G', 'PA', 'R', 'HR', 'RBI', 'SB', 'AVG', 'OBP']:
                            v = row.get(cat, '')
                            if v and str(v) not in ('nan', 'None', ''):
                                row_parts.append(f"{cat}:{v}")
                        if row_parts:
                            _time_players.append(f"{clean} | Pos: {p_pos} | Team: {p_team} | {' '.join(row_parts)}")
                if _time_players:
                    context_text += f"\n{_time_label} PLAYER DATA (use this for time-specific questions):\n"
                    for tp in _time_players:
                        context_text += f"  PLAYER: {tp}\n"
                    context_text += "\n"
                    logger.info(f"{_time_label} player lookup: added {len(_time_players)} players")
            except Exception as _te:
                logger.warning(f"Time-scoped player lookup failed: {_te}")

        context_chars = len(context_text)
        est_tokens = context_chars // 4
        logger.info(f"Context built: {len(all_team_names)} teams, {len(free_agents)} free agents, ~{est_tokens} tokens ({context_chars} chars)")

        # Build context for OpenAI (use simple format it can understand)
        context_data = {
            'league_context': context_text,
            'league_info': {
                'league_type': league.league_type,
                'total_teams': len(all_team_names),
                'team_names': all_team_names
            }
        }

        # Build conversation history (last 6 messages max to save tokens)
        conversation_history = None
        if request.conversation_history:
            # Only keep last 6 messages (3 exchanges) to stay within token limits
            conversation_history = request.conversation_history[-6:]
            logger.info(f"Conversation history: {len(conversation_history)} messages")

        # Get AI response using FAST gpt-4o-mini
        openai_service = OpenAIService()
        ai_response = openai_service.get_chat_completion(
            user_message=request.message,
            conversation_history=conversation_history,
            context_data=context_data
        )

        # Save chat to database for admin dashboard
        try:
            chat_record = Chat(
                league_id=str(request.league_id),
                user_message=request.message,
                bot_response=ai_response
            )
            db.add(chat_record)
            db.commit()
        except Exception as e:
            logger.warning(f"Could not save chat: {e}")
            db.rollback()

        # Increment message usage counter (only if using backend API key)
        if not request.user_api_key:
            try:
                user_id = request.user_id or str(request.league_id)
                user = MessageLimitService.get_or_create_user(user_id, db)
                MessageLimitService.increment_usage(user, db)
                # Update remaining count
                messages_remaining = user.monthly_limit - user.messages_used
                logger.info(f"User {user_id} used 1 message, {messages_remaining} remaining")
            except Exception as e:
                logger.warning(f"Could not increment usage: {e}")

        return ChatResponse(
            message=request.message,
            response=ai_response,
            tokens_used=0,
            messages_remaining=messages_remaining,
            limit_info=limit_message
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
