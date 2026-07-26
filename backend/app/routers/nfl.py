"""NFL Fantasy Router - Upload Fantrax NFL CSV, fetch projections, manage scoring profiles"""
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, League, Roster, Player, ScoringProfile
from app.services.csv_parser import CSVParser
from app.services.player_matcher import PlayerMatcher
from app.services import nfl_projection_service as nfl_svc
from app.services.nfl_scoring import (
    calc_points, score_player_list,
    DEFAULT_WEIGHTS, PRESET_PROFILES,
)
import uuid
import json
import tempfile
import os
from typing import Optional, List

router = APIRouter()


@router.post("/upload")
async def upload_nfl_csv(
    file: UploadFile = File(...),
    existing_league_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload a Fantrax NFL CSV.
    Auto-detects NFL Fantrax format (QB/RB/WR/TE positions + *XXXXX* IDs).
    """
    allowed = ('.csv', '.xls', '.xlsx')
    if not any(file.filename.lower().endswith(ext) for ext in allowed):
        raise HTTPException(status_code=400, detail="File must be CSV or Excel.")

    file_ext = os.path.splitext(file.filename.lower())[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        parser = CSVParser()
        players_data, league_type = parser.parse_csv(tmp_path)

        if league_type != 'fantrax_nfl':
            raise HTTPException(
                status_code=400,
                detail=f"Expected an NFL Fantrax CSV but detected: '{league_type}'. "
                       "Make sure you're uploading the full league player export from Fantrax with NFL positions."
            )

        # Replace existing league if re-uploading
        user = None
        if existing_league_id:
            try:
                old_uuid = uuid.UUID(existing_league_id)
                old_league = db.query(League).filter(League.id == old_uuid).first()
                if old_league:
                    db.query(Roster).filter(Roster.league_id == old_uuid).delete()
                    user = db.query(User).filter(User.id == old_league.user_id).first()
                    db.delete(old_league)
                    db.flush()
            except Exception:
                user = None

        if not user:
            user = User()
            db.add(user)
            db.flush()

        league = League(
            id=uuid.uuid4(),
            user_id=user.id,
            league_type='fantrax',
            sport='nfl',
            csv_filename=file.filename,
        )
        db.add(league)
        db.flush()

        matcher = PlayerMatcher(db)
        owned_count = 0
        fa_count = 0
        player_owner_pairs = []

        for pd_row in players_data:
            if pd_row['owner'] == 'Free Agent':
                fa_count += 1
                continue
            player = matcher.get_or_create_player(pd_row)
            player_owner_pairs.append((player, pd_row))
            owned_count += 1

        db.flush()

        for player, pd_row in player_owner_pairs:
            roster = Roster(
                league_id=league.id,
                player_id=player.id,
                team_owner=pd_row['owner'],
                status=pd_row.get('status'),
            )
            db.add(roster)

        db.commit()

        team_owners = sorted(set(
            r[1]['owner'] for r in player_owner_pairs
            if r[1]['owner'] and r[1]['owner'] != 'Free Agent'
        ))

        print(f"[NFL] Uploaded: {owned_count} owned, {fa_count} FAs, league={league.id}")
        return {
            "id": str(league.id),
            "sport": "nfl",
            "league_type": "fantrax",
            "total_players": len(players_data),
            "owned_players": owned_count,
            "free_agents": fa_count,
            "teams": team_owners,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing NFL CSV: {str(e)}")
    finally:
        os.unlink(tmp_path)


@router.get("/{league_id}/teams")
async def get_nfl_teams(league_id: uuid.UUID, db: Session = Depends(get_db)):
    """Get list of team owner names in an NFL league."""
    league = db.query(League).filter(League.id == league_id, League.sport == 'nfl').first()
    if not league:
        raise HTTPException(status_code=404, detail="NFL league not found")

    rosters = db.query(Roster.team_owner).filter(
        Roster.league_id == league_id,
        Roster.team_owner != 'Free Agent'
    ).distinct().all()

    teams = sorted(set(r.team_owner for r in rosters if r.team_owner))
    return {"league_id": str(league_id), "teams": teams, "sport": "nfl"}


@router.get("/{league_id}/projections/ros")
async def get_ros_projections(league_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Get ROS projections for all players in an NFL league.
    Returns owned players only, matched to their fantasy owner, with projection stats.
    """
    league = db.query(League).filter(League.id == league_id, League.sport == 'nfl').first()
    if not league:
        raise HTTPException(status_code=404, detail="NFL league not found")

    rosters = db.query(Roster).filter(
        Roster.league_id == league_id,
        Roster.team_owner != 'Free Agent'
    ).all()

    proj_list = nfl_svc.get_ros_projections()
    fantrax_lookup = nfl_svc.build_fantrax_lookup(proj_list)
    yahoo_lookup = nfl_svc.build_yahoo_lookup(proj_list)

    results = []
    for roster in rosters:
        player = db.query(Player).filter(Player.id == roster.player_id).first()
        if not player:
            continue

        proj = None
        if player.fantrax_id:
            proj = fantrax_lookup.get(player.fantrax_id.strip())
        if not proj and player.yahoo_id:
            proj = yahoo_lookup.get(str(player.yahoo_id).strip())

        results.append({
            "name": player.name,
            "position": player.position,
            "nfl_team": player.team,
            "owner": roster.team_owner,
            "fantrax_id": player.fantrax_id,
            "projection": proj,
        })

    return {
        "league_id": str(league_id),
        "sport": "nfl",
        "week": "ros",
        "players": results,
    }


@router.get("/{league_id}/projections/weekly")
async def get_weekly_projections(
    league_id: uuid.UUID,
    week: int = Query(default=1, ge=1, le=18),
    db: Session = Depends(get_db)
):
    """
    Get weekly projections for all players in an NFL league.
    Pass ?week=N (1-18) to select the NFL week.
    """
    league = db.query(League).filter(League.id == league_id, League.sport == 'nfl').first()
    if not league:
        raise HTTPException(status_code=404, detail="NFL league not found")

    rosters = db.query(Roster).filter(
        Roster.league_id == league_id,
        Roster.team_owner != 'Free Agent'
    ).all()

    proj_list = nfl_svc.get_weekly_projections(week)
    fantrax_lookup = nfl_svc.build_fantrax_lookup(proj_list)
    yahoo_lookup = nfl_svc.build_yahoo_lookup(proj_list)

    results = []
    for roster in rosters:
        player = db.query(Player).filter(Player.id == roster.player_id).first()
        if not player:
            continue

        proj = None
        if player.fantrax_id:
            proj = fantrax_lookup.get(player.fantrax_id.strip())
        if not proj and player.yahoo_id:
            proj = yahoo_lookup.get(str(player.yahoo_id).strip())

        results.append({
            "name": player.name,
            "position": player.position,
            "nfl_team": player.team,
            "owner": roster.team_owner,
            "fantrax_id": player.fantrax_id,
            "projection": proj,
        })

    return {
        "league_id": str(league_id),
        "sport": "nfl",
        "week": week,
        "players": results,
    }


# ── Scoring Profiles ────────────────────────────────────────────────────────

@router.get("/scoring/defaults")
async def get_scoring_defaults():
    """Return the default scoring weights and available presets."""
    return {
        "weights": DEFAULT_WEIGHTS,
        "presets": list(PRESET_PROFILES.keys()),
    }


@router.get("/scoring/presets/{preset_name}")
async def get_scoring_preset(preset_name: str):
    """Return weights for a named preset (standard, half_ppr, ppr, superflex_half_ppr)."""
    weights = PRESET_PROFILES.get(preset_name)
    if not weights:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_name}' not found. Available: {list(PRESET_PROFILES.keys())}")
    return {"name": preset_name, "weights": weights}


@router.get("/scoring/profiles")
async def list_scoring_profiles(user_id: str, db: Session = Depends(get_db)):
    """List all scoring profiles saved by a user."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    profiles = db.query(ScoringProfile).filter(
        ScoringProfile.user_id == uid,
        ScoringProfile.sport == 'nfl'
    ).order_by(ScoringProfile.created_at).all()

    return {
        "profiles": [
            {
                "id": p.id,
                "name": p.name,
                "is_default": p.is_default,
                "weights": p.weights,
                "created_at": p.created_at.isoformat(),
            }
            for p in profiles
        ]
    }


@router.post("/scoring/profiles")
async def save_scoring_profile(
    user_id: str = Form(...),
    name: str = Form(...),
    weights_json: str = Form(...),
    db: Session = Depends(get_db)
):
    """Save a named custom scoring profile for a user."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    try:
        weights = json.loads(weights_json)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        user = User(id=uid)
        db.add(user)
        db.flush()

    profile = ScoringProfile(
        user_id=uid,
        name=name.strip(),
        sport='nfl',
        is_default=False,
        weights_json=json.dumps(weights),
    )
    db.add(profile)
    db.commit()

    return {"id": profile.id, "name": profile.name, "message": "Scoring profile saved."}


@router.delete("/scoring/profiles/{profile_id}")
async def delete_scoring_profile(
    profile_id: int,
    user_id: str,
    db: Session = Depends(get_db)
):
    """Delete a user's saved scoring profile."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    profile = db.query(ScoringProfile).filter(
        ScoringProfile.id == profile_id,
        ScoringProfile.user_id == uid
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default profile")

    db.delete(profile)
    db.commit()
    return {"message": f"Profile '{profile.name}' deleted."}


@router.post("/scoring/calculate")
async def calculate_scored_projections(
    week: int = Form(default=99),
    weights_json: str = Form(default='{}'),
):
    """
    Calculate custom-scored projections for all NFL players.
    week=99 for ROS, 1-18 for a specific week.
    Returns top 200 players sorted by custom_pts desc.
    """
    try:
        weights = json.loads(weights_json) if weights_json and weights_json != '{}' else DEFAULT_WEIGHTS
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    players = nfl_svc.get_ros_projections() if week == 99 else nfl_svc.get_weekly_projections(week)
    scored = score_player_list([dict(p) for p in players], weights=weights)

    return {
        "week": "ros" if week == 99 else week,
        "total_players": len(scored),
        "players": scored[:200],
    }
