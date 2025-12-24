"""CSV Upload Router"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, League, Roster
from app.services.csv_parser import CSVParser
from app.services.player_matcher import PlayerMatcher
from app.schemas.league import LeagueResponse, RosterResponse, PlayerInRoster
import uuid
import tempfile
import os

router = APIRouter()


@router.post("/upload", response_model=LeagueResponse)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload league CSV file

    Accepts CSV from Fantrax, CBS Sports, or NFBC
    Auto-detects format and parses roster
    """
    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name

    try:
        # Parse CSV
        parser = CSVParser()
        players_data, league_type = parser.parse_csv(tmp_file_path)

        # Create or get user (for now, create a new one each time)
        user = User()
        db.add(user)
        db.flush()

        # Create league record
        league = League(
            id=uuid.uuid4(),
            user_id=user.id,
            league_type=league_type,
            csv_filename=file.filename
        )
        db.add(league)
        db.flush()

        # Match and store players (optimized with bulk inserts)
        matcher = PlayerMatcher(db)
        owned_count = 0
        free_agent_count = 0
        roster_entries = []

        for player_data in players_data:
            # Get or create player
            player = matcher.get_or_create_player(player_data)

            # Create roster entry object (don't add to session yet)
            roster = Roster(
                league_id=league.id,
                player_id=player.id,
                team_owner=player_data['owner'],
                status=player_data.get('status')
            )
            roster_entries.append(roster)

            if player_data['owner'] == 'Free Agent':
                free_agent_count += 1
            else:
                owned_count += 1

        # Bulk insert all roster entries at once (much faster)
        db.bulk_save_objects(roster_entries)
        db.commit()

        # Return response
        return LeagueResponse(
            id=league.id,
            league_type=league_type,
            total_players=len(players_data),
            owned_players=owned_count,
            free_agents=free_agent_count,
            uploaded_at=league.uploaded_at
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")

    finally:
        # Clean up temp file
        os.unlink(tmp_file_path)


@router.get("/{league_id}/roster", response_model=RosterResponse)
async def get_roster(
    league_id: uuid.UUID,
    owner: str = None,
    db: Session = Depends(get_db)
):
    """
    Get roster for a league

    Query params:
    - owner: Filter by team owner (optional)
    """
    # Get league
    league = db.query(League).filter(League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    # Get rosters
    query = db.query(Roster).filter(Roster.league_id == league_id)

    if owner:
        query = query.filter(Roster.team_owner == owner)

    rosters = query.all()

    # Build response
    players = []
    for roster in rosters:
        player = roster.player

        # Get latest projection (if available)
        latest_projection = None
        if player.projections_daily:
            latest_projection = sorted(
                player.projections_daily,
                key=lambda p: p.date,
                reverse=True
            )[0]

        player_data = PlayerInRoster(
            id=player.id,
            name=player.name,
            mlb_team=player.team,
            position=player.position,
            owner=roster.team_owner,
            hr=latest_projection.hr if latest_projection else None,
            rbi=latest_projection.rbi if latest_projection else None,
            sb=latest_projection.sb if latest_projection else None,
            avg=latest_projection.avg if latest_projection else None,
        )
        players.append(player_data)

    return RosterResponse(
        league_id=league.id,
        league_type=league.league_type,
        players=players
    )


@router.get("/{league_id}/free-agents", response_model=RosterResponse)
async def get_free_agents(
    league_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get all free agents in a league"""
    return await get_roster(league_id, owner="Free Agent", db=db)
