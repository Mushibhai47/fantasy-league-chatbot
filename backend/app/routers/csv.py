"""CSV Upload Router"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, League, Roster
from app.services.csv_parser import CSVParser
from app.services.player_matcher import PlayerMatcher
from app.schemas.league import LeagueResponse, RosterResponse, PlayerInRoster
from typing import Optional
import uuid
import tempfile
import os

router = APIRouter()


@router.post("/upload", response_model=LeagueResponse)
async def upload_csv(
    file: UploadFile = File(...),
    existing_league_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload league CSV file

    Accepts CSV from Fantrax, CBS Sports, or NFBC
    Auto-detects format and parses roster
    """
    # Validate file type
    allowed_extensions = ('.csv', '.xls', '.xlsx')
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(status_code=400, detail="File must be a CSV or Excel file (.csv, .xls, .xlsx)")

    # Save uploaded file temporarily
    file_ext = os.path.splitext(file.filename.lower())[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name

    try:
        # Parse CSV
        parser = CSVParser()
        players_data, league_type = parser.parse_csv(tmp_file_path)

        # If re-uploading, delete old rosters and league to prevent accumulation
        user = None
        if existing_league_id:
            try:
                old_league_uuid = uuid.UUID(existing_league_id)
                old_league = db.query(League).filter(League.id == old_league_uuid).first()
                if old_league:
                    db.query(Roster).filter(Roster.league_id == old_league_uuid).delete()
                    user = db.query(User).filter(User.id == old_league.user_id).first()
                    db.delete(old_league)
                    db.flush()
            except Exception:
                user = None
        else:
            user = None

        # Create user if needed
        if not user:
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

        # Match and store players — all in memory, one flush at the end
        matcher = PlayerMatcher(db)
        owned_count = 0
        free_agent_count = 0
        player_owner_pairs = []  # (Player, player_data) — IDs populated after single flush

        for player_data in players_data:
            if player_data['owner'] == 'Free Agent':
                free_agent_count += 1
                continue  # Don't store free agents — saves 97% of DB space
            player = matcher.get_or_create_player(player_data)
            player_owner_pairs.append((player, player_data))
            owned_count += 1

        # Single flush: assigns auto-generated IDs to all newly created players at once
        db.flush()

        # Now build roster entries (player.id is available after the flush)
        roster_entries = []
        for player, player_data in player_owner_pairs:
            roster = Roster(
                league_id=league.id,
                player_id=player.id,
                team_owner=player_data['owner'],
                status=player_data.get('status')
            )
            roster_entries.append(roster)

        for roster in roster_entries:
            db.add(roster)
        db.commit()

        # Build team list directly from roster entries (no extra DB query needed)
        team_owners = sorted(set(
            r.team_owner for r in roster_entries
            if r.team_owner and r.team_owner != 'Free Agent'
        ))

        # Return response
        return LeagueResponse(
            id=league.id,
            league_type=league_type,
            total_players=len(players_data),
            owned_players=owned_count,
            free_agents=free_agent_count,
            uploaded_at=league.uploaded_at,
            teams=team_owners
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


@router.get("/{league_id}/teams")
async def get_teams(
    league_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get list of team owner names in a league (excludes Free Agent)"""
    league = db.query(League).filter(League.id == league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    rosters = db.query(Roster.team_owner).filter(
        Roster.league_id == league_id,
        Roster.team_owner != 'Free Agent'
    ).distinct().all()

    teams = sorted(set(r.team_owner for r in rosters if r.team_owner))
    return {"league_id": str(league_id), "teams": teams}


@router.get("/league-types")
async def get_league_types():
    """Return the available Razzball projection league types"""
    return {
        "league_types": ["MLB12", "MLB12_5X5OBP", "MLB12_6X6OBP", "MLB12_6X6HLD", "MLB12_6X6QS", "MLB15", "MLB15_5X5OBP", "MLB10", "AL12", "NL12"],
        "default": "MLB12"
    }


@router.get("/{league_id}/free-agents", response_model=RosterResponse)
async def get_free_agents(
    league_id: uuid.UUID,
    db: Session = Depends(get_db)
):
    """Get all free agents in a league"""
    return await get_roster(league_id, owner="Free Agent", db=db)
