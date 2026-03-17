"""OpenAI Chat Service - GPT-4 powered fantasy baseball recommendations"""
from openai import OpenAI
from typing import List, Dict, Optional
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class OpenAIService:
    """GPT-4 chat service for fantasy baseball recommendations"""

    def __init__(self):
        self.model = "gpt-4o-mini"  # Fast model for all queries
        self.mini_model = "gpt-4o-mini"  # Same fast model
        self.system_prompt = """You are an expert fantasy baseball advisor for Razzball.com.

You have access to LEAGUE ROSTER DATA enriched with Razzball projections from api.razzball.com.

INTRO FORMAT (ALWAYS use this when analyzing a team):
When analyzing a specific team, start with:
"Here's a breakdown of your team, [TeamName], using players projected $1+ in [FORMAT] league format. I can re-run this in ([list other formats]) if you like. The optimal team projected average should be $260 ($164 hitting/$96 pitching) though it's typically closer to $250 since, unlike the bot, people have free will."

UNDERSTANDING THE DATA FORMAT:
Each player is listed on its own line with pipe-separated fields:
  PLAYER: Name | Pos: SS | Team: NYY | $12.3 $R:2.1 $HR:3.4 $RBI:2.8 $SB:1.5 $AVG:2.5 $/G:0.8
  PLAYER: Name | Pos: SP | Team: LAD | $8.5 $W:2.1 $SV:0.0 $K:5.2 $ERA:1.3 $WHIP:-0.1 $/G:0.6

UNDERSTANDING DOLLAR VALUES ($):
- $ = Overall projected fantasy dollar value for the season (sum of category $)
- $/G = Dollar value per game (shows per-game impact)
- Category $ for HITTERS: $R (runs), $HR (home runs), $RBI (RBIs), $SB (stolen bases), $AVG (batting avg), $OBP (on-base %)
- Category $ for PITCHERS: $W (wins), $SV (saves), $K (strikeouts), $ERA, $WHIP, $QS (quality starts), $HLD (holds)
- $20+ = Elite player (star)
- $10-19 = Very good starter
- $5-9 = Solid contributor
- $1-4 = Replacement level
- Negative $ = Below replacement level

CRITICAL RULES - ACCURACY:
1. ONLY use player data from the context provided - these are REAL Razzball projections
2. Each player's values are on their OWN line starting with "PLAYER:". Read EACH line independently.
3. NEVER mix up values between players. If you see "PLAYER: Sandoval | ... | $2.3", that $2.3 belongs ONLY to Sandoval.
4. Before writing a player's value in your response, RE-READ their specific line from the context to verify.
5. If a player has "NO PROJECTION" on their line, say so - do NOT guess or use another player's values.
6. NEVER correct, rename, or substitute player names. Use the EXACT name from the roster data. If the roster says "Colby Thomas", write "Colby Thomas" — do NOT change it to a name you think is more familiar.
7. If a player has no projection data (listed under "NO PROJECTION DATA"), note them under the table as "Players not found in projection file: [names]"
8. Be concise but specific - always cite the numbers EXACTLY as they appear in the data.
9. NEVER invent, estimate, or use your training knowledge for player stats, $ values, teams, or positions. If a player is not in the context data, say "I don't have projection data for [player name]" — do NOT fabricate numbers from memory.

IMPORTANT - SEPARATE HITTERS AND PITCHERS:
Always show hitters and pitchers in SEPARATE tables. Pitchers are Pos = SP, RP, or P.
- HITTER table columns: Player | Pos | Team | $ | $R | $HR | $RBI | $SB | $AVG
- PITCHER table columns: Player | Pos | Team | $ | $W | $SV | $K | $ERA | $WHIP
Never show $HR/$RBI for pitchers or $W/$SV/$K for hitters.

PROJECTION FORMATS:
The data provided uses the format shown in "ACTIVE PROJECTION FORMAT" in the context.
Available formats: MLB12 (12-team mixed), MLB15 (15-team mixed), MLB10 (10-team mixed), AL12 (12-team AL-only), NL12 (12-team NL-only).
Always mention which format is active. If the user asks for a different format, the system will automatically switch.

IMPORTANT - TEAM $ TOTALS (PRE-CALCULATED):
The context includes "AUTHORITATIVE TOTALS" blocks and a "PRE-CALCULATED TEAM RANKINGS" table.
These numbers are calculated by the backend and are AUTHORITATIVE. They are the ONLY correct values.
- ALWAYS use these pre-calculated numbers. Do NOT try to add up player values yourself. NEVER recalculate.
- If the context says "TOTAL $: $288.3 | RANK: 3", then that team's total IS $288.3 and rank IS 3. Period.
- These totals only include players with $ >= $1 (negatives excluded).
- When analyzing a team, use the AUTHORITATIVE TOTALS block for that team.
- When comparing teams, use the pre-calculated ranking table directly.
- When asked for category totals, display ALL categories from the pre-calculated table.

FREE AGENTS / BEST AVAILABLE:
- "Best available", "free agents", "available players", "waiver wire" all mean the same thing: unrostered players.
- Free agents are listed under "TOP FREE AGENTS" in the context, sorted by $ descending.
- When showing free agents, show ALL available from the context, sorted by $ (highest first).
- Only show players that actually appear in the FREE AGENTS section - never show rostered players as available.

DISPLAYING TABLES:
| Player | Pos | Team | $ | $HR | $RBI | $R | $SB | $AVG |
|--------|-----|------|---|-----|------|----|----|------|

CRITICAL - ANALYSIS STYLE:
- Use the PRE-CALCULATED totals from the context. Never try to add up dollar values yourself.
- Be CONCISE and DATA-DRIVEN. Use numbers, not generic advice.
- Compare to the rest of the league using the pre-calculated ranks.

STRENGTHS/WEAKNESSES ANALYSIS:
When asked about strengths, weaknesses, or category analysis:
- Show EVERY category with its $ value and rank from the AUTHORITATIVE TOTALS
- Format as a table: Category | $ Value | Rank
- Strengths = categories where rank is in top 3
- Weaknesses = categories where rank is in bottom 3
- Name specific players driving the strength/weakness with their category $ values

BANNED PHRASES (NEVER use these):
- "Focus on making strategic moves..."
- "Monitor free agents..."
- "Make strategic trades..."
- "Consider improving..."
- "Could be beneficial..."
- "To enhance your team's competitiveness..."
- "Focusing on bolstering..."
- Any sentence that could apply to ANY team without data. If you could say it without seeing the data, don't say it.

GOOD examples:
- "Your $SB is $27.1 (1st), driven by Trea Turner ($8.2 $SB) and Bobby Witt ($6.1 $SB)."
- "$W is $15.7 (6th) - your weakest pitching category."
BAD examples:
- "Focus on improving your hitting lineup." (generic, useless)
- "Making strategic moves could improve your team." (empty advice)

When making recommendations:
1. Reference specific players with their actual $ values
2. Show category dollar breakdowns to explain WHY
3. Use markdown tables for comparisons
4. Always reference the pre-calculated league rankings
5. NEVER end with generic advice. End with specific data."""

    def _filter_roster_by_question(self, roster: List[Dict], user_message: str) -> List[Dict]:
        """
        Filter roster to only include relevant players based on user's question
        This prevents token limit issues
        """
        user_lower = user_message.lower()
        import re

        # First, check if a specific team is mentioned (higher priority than comparison detection)
        # Look for patterns like "Team RG", "RG team", "for RG", "on RG", "(RG)"
        # Team name must be 2-4 ALL-CAPS letters, keywords can be any case
        # Use inline (?i:...) for case-insensitive keywords while requiring caps for team names
        pattern1 = re.search(r'\b(?i:team)\s+([A-Z]{2,4})\b', user_message)
        pattern2 = re.search(r'\b(?i:for|on)\s+([A-Z]{2,4})\b', user_message)
        pattern3 = re.search(r'\(([A-Z]{2,4})\)', user_message)
        pattern4 = re.search(r'\b([A-Z]{2,4})\s+(?i:team)\b', user_message)
        team_match = pattern1 or pattern2 or pattern3 or pattern4

        # Check if this is a comparison/analysis question requiring multi-team data
        comparison_keywords = [
            'compare to', 'compared to', 'comparison',
            'versus', 'vs', 'vs.',
            'other teams', 'all teams', 'each team',
            'league average', 'league-wide', 'standings',
            'rank teams', 'team rankings', 'best team', 'worst team',
            'how does my team', 'how does team'
        ]
        is_comparison = any(keyword in user_lower for keyword in comparison_keywords)

        # If a specific team is mentioned WITHOUT multi-team comparison keywords, filter to that team
        if team_match and not is_comparison:
            # Extract team name from the matched pattern (all patterns capture in group 1)
            team_name = team_match.group(1).upper()
            # Filter to only this team's players
            filtered = [p for p in roster if p.get('owner', '').upper() == team_name]
            if filtered:
                logger.info(f"Single team query detected - sending {len(filtered)} players from Team {team_name}")
                return filtered

        # If this is a comparison question, send top players from ALL teams
        if is_comparison:
            # For comparison questions, send top players from each team (to stay under token limit)
            # Group players by owner
            from collections import defaultdict
            teams = defaultdict(list)

            for player in roster:
                owner = player.get('owner', 'Unknown')
                if owner != 'Free Agent':  # Skip free agents for team comparisons
                    teams[owner].append(player)

            # Determine how many players per team based on league size
            num_teams = len(teams)
            if num_teams <= 6:
                players_per_team = 15  # Small league - send more players
            elif num_teams <= 12:
                players_per_team = 8   # Medium league - 8 players/team = ~96 total
            else:
                players_per_team = 5   # Large league - 5 players/team = ~75 total

            # For each team, take top N players by dollar value ($1+)
            filtered_roster = []
            for owner, players in teams.items():
                # Filter to $1+ players first
                valuable_players = [p for p in players if float(p.get('dollar_value', 0) or 0) >= 1.0]
                # Sort by dollar value descending
                sorted_players = sorted(
                    valuable_players,
                    key=lambda x: float(x.get('dollar_value', 0) or 0),
                    reverse=True
                )
                # Take top N from this team
                filtered_roster.extend(sorted_players[:players_per_team])

            logger.info(f"Comparison query detected - sending top {players_per_team} players ($1+) from {len(teams)} teams ({len(filtered_roster)} total players)")
            return filtered_roster

        # If no team specified, return top players by dollar value (limit to 150 players)
        # Sort by dollar value descending
        sorted_roster = sorted(roster, key=lambda x: float(x.get('dollar_value', 0) or 0), reverse=True)
        logger.info(f"General query - sending top 150 players by dollar value")
        return sorted_roster[:150]

    def get_chat_completion(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        context_data: Optional[Dict] = None
    ) -> str:
        """
        Get GPT-4 chat completion with fantasy baseball context

        Args:
            user_message: User's question/request
            conversation_history: Previous messages in conversation
            context_data: Additional context (roster, projections, etc.)

        Returns:
            AI response string
        """
        try:
            # Build messages array
            messages = [{"role": "system", "content": self.system_prompt}]

            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)

            # Add context data if provided (filter roster based on question)
            if context_data:
                # Filter roster to only relevant players
                if context_data.get('my_roster'):
                    context_data['my_roster'] = self._filter_roster_by_question(
                        context_data['my_roster'],
                        user_message
                    )

                context_message = self._build_context_message(context_data)
                # Log context size for debugging
                context_chars = len(context_message)
                est_context_tokens = context_chars // 4  # Rough estimate: 4 chars = 1 token
                logger.info(f"Context message: {context_chars} chars (~{est_context_tokens} tokens)")
                messages.append({"role": "system", "content": context_message})

            # Add user message
            messages.append({"role": "user", "content": user_message})

            # Detect if this is a comparison query - use faster/cheaper model
            comparison_keywords = ['compare', 'comparison', 'versus', 'vs', 'other teams', 'all teams', 'standings', 'rank teams']
            is_comparison = any(kw in user_message.lower() for kw in comparison_keywords)
            model_to_use = self.mini_model if is_comparison else self.model

            logger.info(f"Using model: {model_to_use} (comparison={is_comparison})")

            # Get completion from GPT-4o-mini (FAST)
            response = client.chat.completions.create(
                model=model_to_use,
                messages=messages,
                temperature=0.3,
                max_tokens=2500,  # Large enough for full roster tables + analysis
            )

            # Extract response
            ai_message = response.choices[0].message.content
            logger.info(f"GPT-4 response generated ({len(ai_message)} chars)")

            return ai_message

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error getting GPT-4 completion: {error_msg}")

            # Check if it's a token limit error
            if "context_length_exceeded" in error_msg or "maximum context length" in error_msg:
                logger.warning("Token limit exceeded - retrying with truncated context")
                # Truncate the context message to fit
                try:
                    truncated_messages = []
                    for msg in messages:
                        if msg["role"] == "system" and len(msg["content"]) > 8000:
                            # Keep first 8000 chars of context (enough for rankings + a few teams)
                            truncated_messages.append({"role": msg["role"], "content": msg["content"][:8000] + "\n\n[Context truncated due to size. Use the PRE-CALCULATED TEAM RANKINGS above for totals.]"})
                        else:
                            truncated_messages.append(msg)
                    response = client.chat.completions.create(
                        model=self.mini_model,
                        messages=truncated_messages,
                        temperature=0.3,
                        max_tokens=2000,
                    )
                    ai_message = response.choices[0].message.content
                    logger.info(f"Response generated with truncated context ({len(ai_message)} chars)")
                    return ai_message
                except Exception as retry_error:
                    logger.error(f"Retry failed: {str(retry_error)}")
                    return "Your request involves too much data. Please try a shorter question or ask about a specific team."

            # Generic error - could be rate limit, timeout, etc.
            logger.error(f"Unhandled OpenAI error: {error_msg}")
            return "I'm having trouble processing your request right now. Please try a simpler question or try again in a moment."

    def _build_context_message(self, context_data: Dict) -> str:
        """Build context message from roster/projection data"""
        context_parts = []

        # New format: direct league context text
        if context_data.get('league_context'):
            context_parts.append(context_data['league_context'])

        # Legacy format: user's roster if provided
        elif context_data.get('my_roster'):
            roster = context_data['my_roster']

            # Check if this is multi-team data (for comparisons)
            owners = set(p.get('owner') for p in roster if p.get('owner') != 'Free Agent')
            is_multi_team = len(owners) > 1

            if is_multi_team:
                # For comparisons, use ULTRA COMPACT format - just Name | Team | $
                # This saves massive tokens and GPT-4 can aggregate the data
                roster_text = "LEAGUE ROSTER DATA (Top $1+ players from each team):\n"
                roster_text += "Format: Name | Team | Total$\n"
                for player in roster:
                    name = player.get('name', 'Unknown')
                    owner = player.get('owner', '?')
                    dollar = player.get('dollar_value', '?')
                    roster_text += f"{name}|{owner}|${dollar}\n"
            else:
                # Single team - compact format to save tokens
                roster_text = "USER'S CURRENT ROSTER:\n"
                for player in roster:
                    roster_text += f"{player.get('name')} | {player.get('owner')} | ${player.get('dollar_value', '?')}\n"

            context_parts.append(roster_text)

        # Add free agents if provided
        if context_data.get('free_agents'):
            fa_text = "TOP FREE AGENTS AVAILABLE:\n"
            for player in context_data['free_agents'][:20]:  # Limit to 20 players
                fa_text += f"- {player.get('name')} ({player.get('position')}, {player.get('mlb_team')})"

                # Include dollar value if available (MOST IMPORTANT)
                if player.get('dollar_value') is not None:
                    fa_text += f" | $: {player.get('dollar_value')}"

                # Include category dollars if available
                cat_dollars = []
                if player.get('$HR') is not None: cat_dollars.append(f"$HR:{player.get('$HR')}")
                if player.get('$RBI') is not None: cat_dollars.append(f"$RBI:{player.get('$RBI')}")
                if player.get('$R') is not None: cat_dollars.append(f"$R:{player.get('$R')}")
                if player.get('$SB') is not None: cat_dollars.append(f"$SB:{player.get('$SB')}")
                if player.get('$AVG') is not None: cat_dollars.append(f"$AVG:{player.get('$AVG')}")
                if player.get('$W') is not None: cat_dollars.append(f"$W:{player.get('$W')}")
                if player.get('$SV') is not None: cat_dollars.append(f"$SV:{player.get('$SV')}")
                if player.get('$K') is not None: cat_dollars.append(f"$K:{player.get('$K')}")
                if player.get('$ERA') is not None: cat_dollars.append(f"$ERA:{player.get('$ERA')}")
                if player.get('$WHIP') is not None: cat_dollars.append(f"$WHIP:{player.get('$WHIP')}")
                if cat_dollars:
                    fa_text += f" | {', '.join(cat_dollars)}"

                fa_text += "\n"
            context_parts.append(fa_text)

        # Add specific player projection if provided
        if context_data.get('player_projection'):
            proj = context_data['player_projection']
            proj_text = f"PLAYER PROJECTION for {proj.get('Name')}:\n"
            proj_text += f"Team: {proj.get('Team')} | Pos: {proj.get('Pos')}\n"
            proj_text += f"Projected Stats: {proj.get('HR')} HR, {proj.get('RBI')} RBI, "
            proj_text += f"{proj.get('SB')} SB, {proj.get('AVG')} AVG\n"
            context_parts.append(proj_text)

        # Add league info if provided
        if context_data.get('league_info'):
            league = context_data['league_info']
            league_text = f"LEAGUE INFO: {league.get('league_type')} | "
            league_text += f"{league.get('total_players')} total players, "
            league_text += f"{league.get('free_agents')} free agents\n"
            context_parts.append(league_text)

        return "\n".join(context_parts)

    def get_pickup_recommendations(
        self,
        my_roster: List[Dict],
        free_agents: List[Dict],
        position: Optional[str] = None,
        stat_category: Optional[str] = None
    ) -> str:
        """
        Get AI recommendations for which free agents to pick up

        Args:
            my_roster: User's current roster
            free_agents: Available free agents with projections
            position: Position to focus on (optional)
            stat_category: Stat category to target (optional)

        Returns:
            AI recommendation string
        """
        # Build specific prompt
        user_message = "Based on my roster and available free agents, who should I pick up?"

        if position:
            user_message += f" I'm looking for a {position}."

        if stat_category:
            user_message += f" I need help with {stat_category}."

        # Build context
        context_data = {
            'my_roster': my_roster,
            'free_agents': free_agents
        }

        return self.get_chat_completion(user_message, context_data=context_data)

    def get_trade_advice(
        self,
        my_players: List[str],
        their_players: List[str],
        my_roster: List[Dict]
    ) -> str:
        """
        Get AI advice on a potential trade

        Args:
            my_players: Players I would give up
            their_players: Players I would receive
            my_roster: My full roster for context

        Returns:
            AI trade analysis
        """
        user_message = f"Should I accept this trade?\n"
        user_message += f"I give: {', '.join(my_players)}\n"
        user_message += f"I get: {', '.join(their_players)}"

        context_data = {'my_roster': my_roster}

        return self.get_chat_completion(user_message, context_data=context_data)


# Test the service
if __name__ == "__main__":
    service = OpenAIService()

    print("\n" + "="*60)
    print("Testing OpenAI Chat Service")
    print("="*60)

    # Test basic chat
    test_message = "Who should I target for home runs?"
    print(f"\nUser: {test_message}")

    response = service.get_chat_completion(test_message)
    print(f"\nAI: {response}")

    print("\n[OK] OpenAI service test complete")
