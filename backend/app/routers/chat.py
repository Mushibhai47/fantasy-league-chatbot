"""Chat Router - GPT-4o-mini Powered Fantasy Baseball Assistant with Razzball Projections"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import League, Roster, Chat, Player, User
from app.services.openai_service import OpenAIService
from app.services.projection_service import ProjectionService
from app.services.message_limit_service import MessageLimitService
from app.schemas.chat import ChatRequest, ChatResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Global projection cache (fetched once, reused for all chats)
_projections_df = None


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
                        "error": "Monthly message limit reached",
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
        # Detect requested league type from user message, default MLB12
        AVAILABLE_LEAGUE_TYPES = ["MLB12", "MLB15", "MLB10", "AL12", "NL12"]
        DEFAULT_LEAGUE_TYPE = "MLB12"

        # Check if user requested a specific league type
        import re
        requested_type = DEFAULT_LEAGUE_TYPE
        msg_upper = request.message.upper()
        for lt in AVAILABLE_LEAGUE_TYPES:
            if lt in msg_upper:
                requested_type = lt
                break

        nfbc_lookup = {}  # NFBCID -> full projection data string
        fantrax_lookup = {}  # FantraxID -> full projection data string
        name_lookup = {}  # name -> full projection data string

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

                    if dollar_str:
                        # Store by NFBCID (most reliable for NFBC CSVs)
                        nfbc_id = row.get('NFBCID', '')
                        if nfbc_id and str(nfbc_id) not in ('nan', 'None', ''):
                            nfbc_lookup[str(nfbc_id)] = dollar_str

                        # Store by FantraxID
                        fantrax_id = row.get('FantraxID', '')
                        if fantrax_id and str(fantrax_id) not in ('nan', 'None', ''):
                            fantrax_lookup[str(fantrax_id)] = dollar_str

                        # Store by name (fallback)
                        proj_name = str(row.get('Name', '')).lower()
                        proj_name = re.sub(r'\[player id=\d+\]|\[/player\]', '', proj_name).strip()
                        if proj_name:
                            name_lookup[proj_name] = dollar_str

                logger.info(f"💰 Lookups ready ({requested_type}): {len(nfbc_lookup)} NFBC, {len(fantrax_lookup)} Fantrax, {len(name_lookup)} by name")
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

            # Fallback to name matching
            name_lower = player_name.lower().strip()
            if name_lower in name_lookup:
                return f" [{name_lookup[name_lower]}]"

            # Partial name match
            for proj_name, dollar in name_lookup.items():
                if name_lower in proj_name or proj_name in name_lower:
                    return f" [{dollar}]"
            return ""

        # Group players by team owner, separating hitters and pitchers
        # Also track dollar values and category $ for pre-calculated totals
        teams_hitters = {}  # owner -> list of player strings
        teams_pitchers = {}  # owner -> list of player strings
        teams_no_projection = {}  # owner -> list of player names with no projection
        # Per-team category tracking: owner -> {category -> list of values}
        HITTER_CATS = ['R', 'HR', 'RBI', 'SB', 'AVG', 'OBP']
        PITCHER_CATS = ['W', 'SV', 'K', 'ERA', 'WHIP', 'HLD']
        ALL_CATS = HITTER_CATS + PITCHER_CATS
        teams_cat_dollars = {}  # owner -> {'$': [], 'R': [], 'HR': [], ...}
        free_agents = []
        PITCHER_POSITIONS = ('SP', 'RP', 'P')

        import re as _re

        def parse_dollar_categories(dollar_val_str):
            """Parse dollar value string to extract overall $ and category $"""
            result = {'$': None}
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
            is_pitcher = pos in PITCHER_POSITIONS

            # Build clear, standalone player string to prevent GPT from mixing up values
            # Format: "Name | Pos: SP | Team: NYY | $: 12.3 | $W: 2.1 | $K: 5.2 | ..."
            if dollar_val:
                # dollar_val is like " [$12.3 $R:1.2 $HR:3.4 ...]" - reformat to pipe-separated
                clean_dollar = dollar_val.strip().strip('[]')
                player_str = f"{player.name} | Pos: {player.position} | Team: {player.team} | {clean_dollar}"
            else:
                player_str = f"{player.name} | Pos: {player.position} | Team: {player.team} | NO PROJECTION"

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
                    teams_cat_dollars[owner] = {'h_$': [], 'p_$': []}
                    for cat in ALL_CATS:
                        teams_cat_dollars[owner][cat] = []

                # Track H/SP/RP counts
                if 'h_count' not in teams_cat_dollars[owner]:
                    teams_cat_dollars[owner]['h_count'] = 0
                    teams_cat_dollars[owner]['sp_count'] = 0
                    teams_cat_dollars[owner]['rp_count'] = 0

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
            totals = {
                'hitting': round(h_sum, 1),
                'pitching': round(p_sum, 1),
                'total': round(h_sum + p_sum, 1),
                'count': len(h_dollars) + len(p_dollars),
                'h_count': cd.get('h_count', 0),
                'sp_count': cd.get('sp_count', 0),
                'rp_count': cd.get('rp_count', 0),
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

        # Build clear context text for AI with hitter/pitcher separation
        format_names = {"MLB12": "12-team mixed", "MLB15": "15-team mixed", "MLB10": "10-team mixed", "AL12": "12-team AL-only", "NL12": "12-team NL-only"}
        all_formats_str = ", ".join(AVAILABLE_LEAGUE_TYPES)
        context_text = f"FANTASY LEAGUE DATA ({league.league_type}):\n"
        context_text += f"ACTIVE PROJECTION FORMAT: {requested_type} ({format_names.get(requested_type, 'mixed')}).\n"
        context_text += f"AVAILABLE FORMATS: {all_formats_str}. User can request any format.\n"
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

        # ============================================================
        # HARD-CODED REPORT GENERATORS (bypass GPT for accuracy)
        # ============================================================

        def generate_league_overview_dollars() -> str:
            """Generate League Overview $ table - matches Rudy's SQL LEAGUEREVIEW"""
            num_teams = len(ranked_teams)
            lines = []
            lines.append(f"**League Overview $ ({requested_type}) - {num_teams} Teams**\n")
            lines.append("| Owner | $ | H | SP | RP | $R | $HR | $RBI | $SB | $AVG | $OBP | $W | $SV | $ERA | $WHIP | $K | $HLD |")
            lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            for team_name in ranked_teams:
                t = team_totals[team_name]
                lines.append(
                    f"| {team_name} | {t['total']} | {t['h_count']} | {t['sp_count']} | {t['rp_count']} | "
                    f"{t['R']} | {t['HR']} | {t['RBI']} | {t['SB']} | {t['AVG']} | {t['OBP']} | "
                    f"{t['W']} | {t['SV']} | {t['ERA']} | {t['WHIP']} | {t['K']} | {t['HLD']} |"
                )
            return "\n".join(lines)

        def generate_league_overview_ranks() -> str:
            """Generate League Overview Ranks table - roto scoring (num_teams=best, 1=worst)"""
            num_teams = len(ranked_teams)
            lines = []
            lines.append(f"\n**League Overview Ranks (Roto: {num_teams}=Best, 1=Worst)**\n")
            lines.append("| Owner | $Rank | $R | $HR | $RBI | $SB | $AVG | $OBP | $W | $SV | $ERA | $WHIP | $K | $HLD | Total Pts |")
            lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")

            # Calculate roto ranks for each category
            # Higher $ = better rank for ALL categories (since $ already accounts for direction)
            roto_cats = ['R', 'HR', 'RBI', 'SB', 'AVG', 'OBP', 'W', 'SV', 'ERA', 'WHIP', 'K', 'HLD']
            team_ranks = {team: {} for team in ranked_teams}

            for cat in roto_cats:
                # Sort teams by category $ (higher = better for roto)
                sorted_by_cat = sorted(ranked_teams, key=lambda t: team_totals[t][cat])
                # Assign ranks: position 0 gets rank 1 (worst), position N-1 gets rank N (best)
                for rank_idx, team_name in enumerate(sorted_by_cat):
                    team_ranks[team_name][cat] = rank_idx + 1

            # Also rank by total $
            sorted_by_total = sorted(ranked_teams, key=lambda t: team_totals[t]['total'])
            for rank_idx, team_name in enumerate(sorted_by_total):
                team_ranks[team_name]['total_rank'] = rank_idx + 1

            # Calculate total roto points
            for team_name in ranked_teams:
                team_ranks[team_name]['roto_total'] = sum(
                    team_ranks[team_name][cat] for cat in roto_cats
                )

            # Sort by roto total descending (most points = best)
            roto_sorted = sorted(ranked_teams, key=lambda t: team_ranks[t]['roto_total'], reverse=True)

            for team_name in roto_sorted:
                r = team_ranks[team_name]
                lines.append(
                    f"| {team_name} | {r['total_rank']} | {r['R']} | {r['HR']} | {r['RBI']} | {r['SB']} | "
                    f"{r['AVG']} | {r['OBP']} | {r['W']} | {r['SV']} | {r['ERA']} | {r['WHIP']} | "
                    f"{r['K']} | {r['HLD']} | {r['roto_total']} |"
                )
            return "\n".join(lines)

        def generate_league_report() -> str:
            """Generate full league report ($ table + ranks table)"""
            report = generate_league_overview_dollars()
            report += "\n\n"
            report += generate_league_overview_ranks()
            return report

        # ============================================================
        # TRIGGER PHRASE DETECTION - bypass GPT for hard-coded reports
        # ============================================================
        msg_lower = request.message.lower()

        report_triggers = [
            'league overview', 'league review', 'leaguereview', 'league report',
            'show me the league', 'team rankings', 'rank all teams',
            'roto standings', 'roto ranks', 'category rankings',
            'how does the league look', 'league standings',
            'show all teams', 'show rankings'
        ]

        is_report_trigger = any(trigger in msg_lower for trigger in report_triggers)

        if is_report_trigger:
            # BYPASS GPT - return hard-coded report directly
            logger.info(f"Report trigger detected: '{request.message}' - bypassing GPT")
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

            # Increment message usage
            if not request.user_api_key:
                try:
                    user_id = request.user_id or str(request.league_id)
                    user = MessageLimitService.get_or_create_user(user_id, db)
                    MessageLimitService.increment_usage(user, db)
                    messages_remaining = user.monthly_limit - user.messages_used
                except Exception as e:
                    logger.warning(f"Could not increment usage: {e}")

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
                context_text += f"  $R: ${t['R']} | $HR: ${t['HR']} | $RBI: ${t['RBI']} | $SB: ${t['SB']} | $AVG: ${t['AVG']} | $OBP: ${t['OBP']}\n"
                context_text += f"  $W: ${t['W']} | $SV: ${t['SV']} | $K: ${t['K']} | $ERA: ${t['ERA']} | $WHIP: ${t['WHIP']} | $HLD: ${t['HLD']}\n"
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
