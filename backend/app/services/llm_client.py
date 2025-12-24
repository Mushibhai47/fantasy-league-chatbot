"""LLM Client - OpenAI and Claude integration"""
from typing import List, Dict, Optional
from openai import OpenAI
from anthropic import Anthropic


class LLMClient:
    """Client for LLM providers (OpenAI, Claude)"""

    def __init__(self, api_key: str, provider: str = "openai"):
        """
        Initialize LLM client

        Args:
            api_key: User's API key
            provider: 'openai' or 'claude'
        """
        self.provider = provider
        self.api_key = api_key

        if provider == "openai":
            self.client = OpenAI(api_key=api_key)
            self.model = "gpt-4-turbo-preview"
        elif provider == "claude":
            self.client = Anthropic(api_key=api_key)
            self.model = "claude-3-sonnet-20240229"
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def build_fantasy_context(
        self,
        user_roster: List[Dict],
        free_agents: List[Dict],
        projections_summary: str
    ) -> str:
        """
        Build context string for fantasy advice

        Args:
            user_roster: List of user's players with projections
            free_agents: List of available free agents
            projections_summary: Summary of projection data

        Returns:
            Context string
        """
        context = "# Fantasy Baseball Roster Assistant\n\n"

        # User's roster
        context += "## Your Current Roster:\n\n"
        if user_roster:
            for player in user_roster[:20]:  # Limit to avoid token limits
                context += f"- {player['name']} ({player['position']}, {player['mlb_team']})"
                if player.get('hr') or player.get('rbi') or player.get('sb'):
                    context += f" - Projected: {player.get('hr', 0):.2f} HR, {player.get('rbi', 0):.2f} RBI, {player.get('sb', 0):.2f} SB"
                context += "\n"
        else:
            context += "No players on your roster.\n"

        # Free agents
        context += "\n## Top Available Free Agents:\n\n"
        if free_agents:
            # Sort by HR projection (or other stat)
            sorted_fa = sorted(
                [p for p in free_agents if p.get('hr')],
                key=lambda x: x.get('hr', 0),
                reverse=True
            )[:30]  # Top 30

            for player in sorted_fa:
                context += f"- {player['name']} ({player['position']}, {player['mlb_team']})"
                if player.get('hr') or player.get('rbi') or player.get('sb'):
                    context += f" - Projected: {player.get('hr', 0):.2f} HR, {player.get('rbi', 0):.2f} RBI, {player.get('sb', 0):.2f} SB"
                context += "\n"
        else:
            context += "No free agents available.\n"

        # Projections info
        context += f"\n## Projection Data:\n{projections_summary}\n"

        return context

    def chat(
        self,
        message: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> tuple[str, int]:
        """
        Send chat message and get response

        Args:
            message: User's question
            context: Fantasy context (roster, free agents, projections)
            system_prompt: Optional system prompt override

        Returns:
            (response_text, tokens_used)
        """
        if not system_prompt:
            system_prompt = """You are a fantasy baseball expert assistant.
You help users make informed roster decisions based on their league data and player projections.

When answering:
- Be specific and data-driven
- Reference actual player projections when available
- Consider user's roster needs
- Suggest actionable moves (pickups, drops, trades if applicable)
- Keep responses concise but informative
- Use baseball statistics appropriately (HR, RBI, SB, AVG, etc.)

If you don't have enough information, say so clearly."""

        if self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{context}\n\n---\n\nUser Question: {message}"}
                ],
                temperature=0.7,
                max_tokens=500
            )

            answer = response.choices[0].message.content
            tokens = response.usage.total_tokens

            return answer, tokens

        elif self.provider == "claude":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"{context}\n\n---\n\nUser Question: {message}"}
                ]
            )

            answer = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens

            return answer, tokens


# Test the LLM client
if __name__ == "__main__":
    import os

    # Test with OpenAI (need to set OPENAI_API_KEY env var)
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("⚠️  Set OPENAI_API_KEY environment variable to test")
        exit()

    client = LLMClient(api_key=api_key, provider="openai")

    # Mock data
    user_roster = [
        {"name": "Aaron Judge", "position": "OF", "mlb_team": "NYY", "hr": 0.29, "rbi": 0.58, "sb": 0.09},
        {"name": "Shohei Ohtani", "position": "DH", "mlb_team": "LAD", "hr": 0.35, "rbi": 0.65, "sb": 0.12},
    ]

    free_agents = [
        {"name": "Jorge Soler", "position": "OF", "mlb_team": "SFG", "hr": 0.25, "rbi": 0.45, "sb": 0.02},
        {"name": "Kyle Schwarber", "position": "OF", "mlb_team": "PHI", "hr": 0.28, "rbi": 0.52, "sb": 0.01},
    ]

    context = client.build_fantasy_context(user_roster, free_agents, "Daily projections for today's games")

    print("\n🧪 Testing LLM Client\n")
    print(f"📋 Context:\n{context}\n")

    question = "Who should I pick up for power?"

    print(f"❓ Question: {question}\n")

    try:
        answer, tokens = client.chat(question, context)
        print(f"💬 Answer:\n{answer}\n")
        print(f"🔢 Tokens used: {tokens}")
    except Exception as e:
        print(f"❌ Error: {str(e)}")
