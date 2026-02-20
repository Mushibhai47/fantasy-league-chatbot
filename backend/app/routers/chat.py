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

        # Get FREE AGENTS separately (limit to 30)
        fa_rosters = db.query(Roster).options(
            joinedload(Roster.player)
        ).filter(
            Roster.league_id == request.league_id,
            Roster.team_owner == 'Free Agent'
        ).limit(30).all()

        # Fallback for free agents too
        if not fa_rosters:
            fa_rosters = db.query(Roster).options(
                joinedload(Roster.player)
            ).filter(
                Roster.league_id == str(request.league_id),
                Roster.team_owner == 'Free Agent'
            ).limit(30).all()

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
        HITTER_CATS = ['R', 'HR', 'RBI', 'SB', 'AVG']
        PITCHER_CATS = ['W', 'SV', 'K', 'ERA', 'WHIP']
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

            player_str = f"{player.name} ({player.position}, {player.team}){dollar_val}"

            if owner == 'Free Agent':
                if len(free_agents) < 20:
                    free_agents.append(player_str)
            else:
                # Parse all dollar categories
                parsed = parse_dollar_categories(dollar_val)
                numeric_dollar = parsed['$']

                # Initialize team tracking if needed
                if owner not in teams_cat_dollars:
                    teams_cat_dollars[owner] = {'h_$': [], 'p_$': []}
                    for cat in ALL_CATS:
                        teams_cat_dollars[owner][cat] = []

                if is_pitcher:
                    if owner not in teams_pitchers:
                        teams_pitchers[owner] = []
                    teams_pitchers[owner].append(player_str)
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
        context_text += "Team | Total $ | Hitting $ | Pitching $ | $R | $HR | $RBI | $SB | $AVG | $W | $SV | $ERA | $WHIP | $K | Rank\n"
        for team_name in ranked_teams:
            t = team_totals[team_name]
            context_text += (
                f"{team_name} | ${t['total']} | ${t['hitting']} | ${t['pitching']} | "
                f"${t['R']} | ${t['HR']} | ${t['RBI']} | ${t['SB']} | ${t['AVG']} | "
                f"${t['W']} | ${t['SV']} | ${t['ERA']} | ${t['WHIP']} | ${t['K']} | {t['rank']}\n"
            )
        context_text += "\n"

        # List each team's roster with hitters and pitchers separated
        for team_name in all_team_names:
            hitters = teams_hitters.get(team_name, [])
            pitchers = teams_pitchers.get(team_name, [])
            no_proj = teams_no_projection.get(team_name, [])
            total = len(hitters) + len(pitchers)
            t = team_totals[team_name]
            context_text += f"TEAM '{team_name}' ROSTER ({total} players) [Hitting: ${t['hitting']} | Pitching: ${t['pitching']} | Total: ${t['total']} | Rank: {t['rank']}]:\n"

            if hitters:
                context_text += f"  HITTERS ({len(hitters)}):\n"
                for p in hitters[:50]:
                    context_text += f"    - {p}\n"

            if pitchers:
                context_text += f"  PITCHERS ({len(pitchers)}):\n"
                for p in pitchers[:50]:
                    context_text += f"    - {p}\n"

            if no_proj:
                context_text += f"  NO PROJECTION DATA: {', '.join(no_proj)}\n"

            context_text += "\n"

        # List free agents or note if none
        if free_agents:
            context_text += "TOP FREE AGENTS:\n"
            for fa in free_agents:
                context_text += f"  - {fa}\n"
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

        # Get AI response using FAST gpt-4o-mini
        openai_service = OpenAIService()
        ai_response = openai_service.get_chat_completion(
            user_message=request.message,
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
