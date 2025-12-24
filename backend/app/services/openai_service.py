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
        self.model = "gpt-4"
        self.system_prompt = """You are an expert fantasy baseball advisor for Razzball.com.

IMPORTANT GUIDELINES:
1. Primarily use player data provided in the context below (roster, free agents, positions, teams)
2. When Razzball projections are provided, ALWAYS reference them in your recommendations
3. The most important projection is the "dollar_value" ($) - this converts all categories to one scale
4. Dollar values ($): $1 = replacement level, $20+ = elite player. Use this to compare hitters vs pitchers!
5. When projections are NOT available, you may use general baseball knowledge to provide helpful advice

UNDERSTANDING DOLLAR VALUES ($):
- Dollar values make different stats comparable (e.g., 50 HR is amazing, but 50 R is bad)
- All categories (HR, RBI, R, SB, AVG for hitters; W, SV, ERA, WHIP, K for pitchers) are converted to $
- A $20 hitter and $20 pitcher have equal fantasy value
- Focus on $ when comparing players or recommending pickups

Your job is to help users make smart fantasy baseball decisions by analyzing:
- Current roster composition and team needs
- Available free agents and their $ values
- Player projections (especially dollar values)
- Roster strategy and category balance
- Position eligibility and scarcity

When making recommendations:
1. Reference player name, position, MLB team, and $ VALUE (when available)
2. Sort free agents by $ value to find the most valuable pickups
3. When comparing players, use $ value as the primary metric
4. Consider roster needs and position scarcity
5. Be specific about projected stats (HR, RBI, ERA, etc.) when available

Keep responses concise and actionable. Help users win their leagues!"""

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

            # Add context data if provided
            if context_data:
                context_message = self._build_context_message(context_data)
                messages.append({"role": "system", "content": context_message})

            # Add user message
            messages.append({"role": "user", "content": user_message})

            # Get completion from GPT-4
            response = client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=800,
            )

            # Extract response
            ai_message = response.choices[0].message.content
            logger.info(f"GPT-4 response generated ({len(ai_message)} chars)")

            return ai_message

        except Exception as e:
            logger.error(f"Error getting GPT-4 completion: {str(e)}")
            return "I'm having trouble processing your request right now. Please try again."

    def _build_context_message(self, context_data: Dict) -> str:
        """Build context message from roster/projection data"""
        context_parts = []

        # Add user's roster if provided
        if context_data.get('my_roster'):
            roster_text = "USER'S CURRENT ROSTER:\n"
            for player in context_data['my_roster'][:20]:  # Limit to 20 players
                roster_text += f"- {player.get('name')} ({player.get('position')}, {player.get('mlb_team')})"

                # Include dollar value if available (MOST IMPORTANT)
                if player.get('dollar_value') is not None:
                    roster_text += f" | $VALUE: ${player.get('dollar_value')}"

                # Include stats if available
                if player.get('hr') or player.get('rbi'):
                    roster_text += f" | Proj: "
                    if player.get('hr'):
                        roster_text += f"{player.get('hr')} HR"
                    if player.get('rbi'):
                        roster_text += f", {player.get('rbi')} RBI"

                roster_text += "\n"
            context_parts.append(roster_text)

        # Add free agents if provided
        if context_data.get('free_agents'):
            fa_text = "TOP FREE AGENTS AVAILABLE:\n"
            for player in context_data['free_agents'][:15]:  # Limit to 15 players
                fa_text += f"- {player.get('name')} ({player.get('position')}, {player.get('mlb_team')})"

                # Include dollar value if available (MOST IMPORTANT)
                if player.get('dollar_value') is not None:
                    fa_text += f" | $VALUE: ${player.get('dollar_value')}"

                # Include stats if available
                if player.get('hr') or player.get('rbi'):
                    fa_text += f" | Proj: "
                    if player.get('hr'):
                        fa_text += f"{player.get('hr')} HR"
                    if player.get('rbi'):
                        fa_text += f", {player.get('rbi')} RBI"

                # Include pitcher stats if available
                if player.get('era') or player.get('whip'):
                    fa_text += f" | Proj: "
                    if player.get('era'):
                        fa_text += f"{player.get('era')} ERA"
                    if player.get('whip'):
                        fa_text += f", {player.get('whip')} WHIP"

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
