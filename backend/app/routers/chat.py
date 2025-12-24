"""Chat Router - GPT-4 Powered Fantasy Baseball Assistant"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import League, Roster
from app.services.openai_service import OpenAIService
from app.services.projection_service import ProjectionService
from app.schemas.chat import ChatRequest, ChatResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Chat with GPT-4 AI assistant about fantasy baseball roster

    Requires:
    - league_id: UUID of uploaded league
    - message: User's question
    """
    try:
        # Get league
        league = db.query(League).filter(League.id == request.league_id).first()
        if not league:
            raise HTTPException(status_code=404, detail="League not found")

        # Get user's roster and free agents from database
        all_rosters = db.query(Roster).filter(Roster.league_id == request.league_id).all()

        user_roster = []
        free_agents_db = []

        for roster in all_rosters:
            player = roster.player

            player_data = {
                'name': player.name,
                'mlb_team': player.team,
                'position': player.position,
                'owner': roster.team_owner,
            }

            if roster.team_owner == 'Free Agent':
                free_agents_db.append(player_data)
            else:
                user_roster.append(player_data)

        # Fetch latest projections from Razzball API
        projection_service = ProjectionService()
        try:
            projections_df = projection_service.fetch_projections()
            logger.info(f"Fetched {len(projections_df)} projections from Razzball API")

            # Enrich roster with projections (API uses $STAT$ format)
            for player in user_roster:
                proj = projection_service.get_player_projection(player['name'])
                if proj:
                    player['hr'] = proj.get('$HR$')
                    player['rbi'] = proj.get('$RBI$')
                    player['sb'] = proj.get('$SB$')
                    player['avg'] = proj.get('$AVG$')
                    player['r'] = proj.get('$R$')
                    player['era'] = proj.get('$ERA$')
                    player['whip'] = proj.get('$WHIP$')
                    player['w'] = proj.get('$W$')
                    player['sv'] = proj.get('$SV$')

            # Enrich free agents with projections (top 50 only for context)
            free_agents = []
            for player in free_agents_db[:50]:
                proj = projection_service.get_player_projection(player['name'])
                if proj:
                    # Add projection stats
                    player['hr'] = proj.get('$HR$')
                    player['rbi'] = proj.get('$RBI$')
                    player['sb'] = proj.get('$SB$')
                    player['avg'] = proj.get('$AVG$')
                    player['r'] = proj.get('$R$')
                    player['era'] = proj.get('$ERA$')
                    player['whip'] = proj.get('$WHIP$')
                    player['w'] = proj.get('$W$')
                    player['sv'] = proj.get('$SV$')
                    player['dollar_value'] = proj.get('$')  # Overall $ value
                    player['has_projections'] = True
                    logger.info(f"Matched projection for {player['name']}: ${proj.get('$')}")
                else:
                    player['has_projections'] = False
                    logger.warning(f"No projection match for {player['name']}")
                free_agents.append(player)

        except Exception as e:
            logger.warning(f"Could not fetch projections: {str(e)}. Proceeding without projections.")
            free_agents = free_agents_db[:50]

        # Build context for AI
        context_data = {
            'my_roster': user_roster,
            'free_agents': free_agents,
            'league_info': {
                'league_type': league.league_type,
                'total_players': len(all_rosters),
                'free_agents': len(free_agents_db)
            }
        }

        # Get AI response
        openai_service = OpenAIService()
        ai_response = openai_service.get_chat_completion(
            user_message=request.message,
            conversation_history=request.conversation_history if hasattr(request, 'conversation_history') else None,
            context_data=context_data
        )

        return ChatResponse(
            message=request.message,
            response=ai_response,
            tokens_used=0  # We can add token counting later if needed
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating response: {str(e)}")
