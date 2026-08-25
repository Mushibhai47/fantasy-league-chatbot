"""NFL Chat Router — GPT-4o-mini powered fantasy football assistant"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from typing import List, Dict, Optional
from uuid import UUID
import logging

from openai import OpenAI as _OpenAI
import os

from app.database import get_db
from app.models import League, Roster, Player
from app.services.message_limit_service import MessageLimitService
from app.services import nfl_projection_service as nfl_svc
from app.services.nfl_scoring import calc_points, DEFAULT_WEIGHTS, PRESET_PROFILES
from app.schemas.chat import ChatResponse

logger = logging.getLogger(__name__)
router = APIRouter()


class NFLChatRequest(BaseModel):
    message: str
    league_id: UUID
    user_id: Optional[str] = None
    user_api_key: Optional[str] = None
    selected_team: Optional[str] = None
    scoring_preset: Optional[str] = "half_ppr"
    scoring_weights: Optional[Dict[str, float]] = None
    week: Optional[int] = None
    conversation_history: Optional[List[Dict[str, str]]] = []


def _f(v, dec=1) -> str:
    """Format a numeric stat for display."""
    if v is None:
        return ""
    try:
        fv = float(v)
        if dec == 0:
            return str(int(round(fv)))
        return f"{fv:.{dec}f}"
    except (TypeError, ValueError):
        return str(v)


def _resolve_weights(req: NFLChatRequest) -> Dict[str, float]:
    """Pick scoring weights: custom > preset > half_ppr default."""
    if req.scoring_weights:
        return {**DEFAULT_WEIGHTS, **req.scoring_weights}
    if req.scoring_preset and req.scoring_preset in PRESET_PROFILES:
        return PRESET_PROFILES[req.scoring_preset]
    return PRESET_PROFILES["half_ppr"]


def _match_player(player: Player, fantrax_lkp: dict, yahoo_lkp: dict, nfbc_lkp: dict = None) -> Optional[dict]:
    """Find a player's projection row by fantrax_id, yahoo_id, or nfbc_id."""
    if player.fantrax_id:
        proj = fantrax_lkp.get(player.fantrax_id.strip())
        if proj:
            return proj
    if player.yahoo_id:
        proj = yahoo_lkp.get(str(player.yahoo_id).strip())
        if proj:
            return proj
    if nfbc_lkp and player.nfbc_id:
        proj = nfbc_lkp.get(str(player.nfbc_id).strip())
        if proj:
            return proj
    return None


def _find_team(name: str, all_teams: List[str]) -> Optional[str]:
    """Fuzzy-match a team name."""
    q = name.lower().strip().lstrip("@")
    for t in all_teams:
        if q in t.lower().strip().lstrip("@"):
            return t
    for t in all_teams:
        words = [w for w in q.split() if len(w) > 2]
        if any(w in t.lower() for w in words):
            return t
    return None


# ── Position groups ──────────────────────────────────────────────────────────
_SKILL = {"QB", "RB", "WR", "TE"}
_KICKER = {"K"}
_DEF = {"DEF", "DST"}
_IDP = {"DB", "DL", "LB", "DT", "DE", "S", "CB"}


def _pos_group(pos: str) -> str:
    p = (pos or "").upper()
    if p in _SKILL:
        return p
    if p in _KICKER:
        return "K"
    if p in _DEF:
        return "DEF"
    if p in _IDP:
        return "IDP"
    return "OTHER"


# ── Report generators ────────────────────────────────────────────────────────

def _qb_table(players_with_proj: list, label: str = "") -> str:
    header = ["Name", "Team", "Opp", "PTS", "Att", "Cmp", "Cmp%", "Pass Yds", "Pass TD", "Int", "Rush Yds", "Run TD", "Fum Lst"]
    rows = [header]
    for p, proj in players_with_proj:
        pts = _f(p.get("custom_pts", 0))
        r = proj or {}
        att = _f(r.get("att"), 0)
        cmp = _f(r.get("cmp"), 0)
        cpct = _f(r.get("comp_pct"), 1)
        pyds = _f(r.get("pass_yds"), 1)
        ptd = _f(r.get("pass_td"), 1)
        ints = _f(r.get("int"), 1)
        ryds = _f(r.get("rush_yds"), 1)
        rtd = _f(r.get("run_td"), 1)
        fum = _f(r.get("fum_lost"), 1)
        opp = r.get("opp") or ""
        rows.append([p["name"], p["nfl_team"], opp, pts, att, cmp, cpct, pyds, ptd, ints, ryds, rtd, fum])
    return _md_table(rows, label)


def _rb_wr_te_table(players_with_proj: list, label: str = "") -> str:
    header = ["Name", "Team", "Opp", "PTS", "Snaps", "Rush", "Rush Yds", "Yds/Car", "Run TD",
              "Tgt", "Rec", "Rec Yds", "Yds/Rec", "Rec TD", "Fum Lst"]
    rows = [header]
    for p, proj in players_with_proj:
        pts = _f(p.get("custom_pts", 0))
        r = proj or {}
        rows.append([
            p["name"], p["nfl_team"], r.get("opp") or "",
            pts,
            _f(r.get("snaps"), 0),
            _f(r.get("rush"), 0),
            _f(r.get("rush_yds"), 1),
            _f(r.get("rush_avg"), 2),
            _f(r.get("run_td"), 1),
            _f(r.get("targets"), 0),
            _f(r.get("rec"), 0),
            _f(r.get("rec_yds"), 1),
            _f(r.get("rec_ypc"), 2),
            _f(r.get("rec_td"), 1),
            _f(r.get("fum_lost"), 1),
        ])
    return _md_table(rows, label)


def _k_table(players_with_proj: list, label: str = "") -> str:
    header = ["Name", "Team", "Opp", "PTS", "XP", "FG", "XP Miss", "FG Miss"]
    rows = [header]
    for p, proj in players_with_proj:
        pts = _f(p.get("custom_pts", 0))
        r = proj or {}
        xp = float(r.get("xp") or 0)
        xpa = float(r.get("xpa") or 0)
        fg = float(r.get("fg") or 0)
        fga = float(r.get("fga") or 0)
        rows.append([
            p["name"], p["nfl_team"], r.get("opp") or "",
            pts, _f(xp, 1), _f(fg, 1),
            _f(max(xpa - xp, 0), 1), _f(max(fga - fg, 0), 1),
        ])
    return _md_table(rows, label)


def _def_table(players_with_proj: list, label: str = "") -> str:
    header = ["Name", "Team", "Opp", "PTS"]
    rows = [header]
    for p, proj in players_with_proj:
        pts = _f(p.get("custom_pts", 0))
        r = proj or {}
        rows.append([p["name"], p["nfl_team"], r.get("opp") or "", pts])
    return _md_table(rows, label)


def _md_table(rows: list, label: str = "") -> str:
    """Render a list of rows (first row = header) as a markdown table."""
    if len(rows) < 2:
        return f"_{label}: no data_"
    header = rows[0]
    sep = "|" + "|".join("---|" for _ in header)
    lines = []
    if label:
        lines.append(f"\n**{label}**\n")
    lines.append("| " + " | ".join(header) + " |")
    lines.append(sep)
    for row in rows[1:]:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def _position_table(pos_group: str, players_with_proj: list, label: str = "") -> str:
    if not players_with_proj:
        return ""
    lbl = label or pos_group
    if pos_group == "QB":
        return _qb_table(players_with_proj, lbl)
    elif pos_group in ("RB", "WR", "TE"):
        return _rb_wr_te_table(players_with_proj, lbl)
    elif pos_group == "K":
        return _k_table(players_with_proj, lbl)
    elif pos_group in ("DEF", "IDP"):
        return _def_table(players_with_proj, lbl)
    return ""


# ── Hard-coded report generators ─────────────────────────────────────────────

def generate_league_overview(
    owned_rosters, ros_fantrax, ros_yahoo, weights: dict, all_teams: List[str], ros_nfbc: dict = None
) -> str:
    """Rank all teams by total ROS custom_pts."""
    team_pts: Dict[str, float] = {}
    team_pos_pts: Dict[str, Dict[str, float]] = {}

    for roster in owned_rosters:
        player = roster.player
        if not player:
            continue
        owner = roster.team_owner
        proj = _match_player(player, ros_fantrax, ros_yahoo, ros_nfbc)
        pts = calc_points(proj, weights) if proj else 0.0
        pos_grp = _pos_group(player.position or "")

        team_pts[owner] = team_pts.get(owner, 0.0) + pts
        if owner not in team_pos_pts:
            team_pos_pts[owner] = {}
        team_pos_pts[owner][pos_grp] = team_pos_pts[owner].get(pos_grp, 0.0) + pts

    if not team_pts:
        return "No projection data available. Try again in a moment."

    ranked = sorted(team_pts.items(), key=lambda x: x[1], reverse=True)
    header = ["Rank", "Owner", "Total PTS", "QB", "RB", "WR", "TE", "K", "DEF"]
    rows = [header]
    for rank, (owner, total) in enumerate(ranked, 1):
        pp = team_pos_pts.get(owner, {})
        rows.append([
            str(rank), owner, _f(total),
            _f(pp.get("QB", 0)), _f(pp.get("RB", 0)), _f(pp.get("WR", 0)),
            _f(pp.get("TE", 0)), _f(pp.get("K", 0)), _f(pp.get("DEF", 0)),
        ])
    return f"**League Overview (ROS Custom Points)**\n\n{_md_table(rows)}"


def generate_team_overview(
    target_team: str, owned_rosters, ros_fantrax, ros_yahoo,
    weights: dict, all_teams: List[str], ros_nfbc: dict = None
) -> str:
    """Show one team's full roster, grouped by position."""
    matched = _find_team(target_team, all_teams)
    if not matched:
        return f"Team '{target_team}' not found. Available: {', '.join(all_teams)}"

    # Group players by position
    pos_buckets: Dict[str, list] = {}
    for roster in owned_rosters:
        if roster.team_owner != matched:
            continue
        player = roster.player
        if not player:
            continue
        proj = _match_player(player, ros_fantrax, ros_yahoo, ros_nfbc)
        pts = calc_points(proj, weights) if proj else 0.0
        pg = _pos_group(player.position or "")
        p_dict = {
            "name": player.name,
            "nfl_team": player.team or "",
            "custom_pts": pts,
        }
        pos_buckets.setdefault(pg, []).append((p_dict, proj))

    if not pos_buckets:
        return f"No players found for team '{matched}'."

    total = sum(pts for grp in pos_buckets.values() for p, _ in grp for pts in [p["custom_pts"]])
    lines = [f"**Team Overview: {matched}** | Total ROS PTS: {_f(total)}\n"]
    for pos_order in ["QB", "RB", "WR", "TE", "K", "DEF", "IDP", "OTHER"]:
        grp = pos_buckets.get(pos_order, [])
        if not grp:
            continue
        grp.sort(key=lambda x: x[0]["custom_pts"], reverse=True)
        lines.append(_position_table(pos_order, grp, pos_order))
    return "\n".join(lines)


def generate_pickups_report(
    projection_type: str, owned_rosters, weights: dict,
    week: Optional[int] = None
) -> str:
    """Best available FAs by position group (weekly or ROS)."""
    if projection_type == "weekly":
        all_proj, label = nfl_svc.get_best_weekly_projections(week)
    else:
        all_proj = nfl_svc.get_ros_projections()
        label = "ROS"

    if not all_proj:
        return f"Could not fetch {label} projections. Try again shortly."

    # Debug: log what keys the API actually returns (once per call)
    if all_proj:
        sample = all_proj[0]
        print(f"[Pickups] API sample keys={list(sample.keys())[:20]}", flush=True)
        print(f"[Pickups] sample pos fields: position={sample.get('position')!r} pos={sample.get('pos')!r}", flush=True)

    # Build owned-player ID + name sets for filtering
    owned_fantrax = set()
    owned_yahoo = set()
    owned_nfbc = set()
    owned_names = set()
    for roster in owned_rosters:
        p = roster.player
        if not p:
            continue
        if p.fantrax_id:
            owned_fantrax.add(str(p.fantrax_id).strip())
        if p.yahoo_id:
            owned_yahoo.add(str(p.yahoo_id).strip())
        if p.nfbc_id:
            owned_nfbc.add(str(p.nfbc_id).strip())
        if p.name:
            owned_names.add(p.name.lower().strip())

    print(f"[Pickups] owned: fantrax={len(owned_fantrax)} yahoo={len(owned_yahoo)} nfbc={len(owned_nfbc)} names={len(owned_names)}", flush=True)

    # Score and filter FAs
    fa_by_pos: Dict[str, list] = {}
    for proj in all_proj:
        # Filter out owned players — try IDs first, then name as fallback
        fid = str(proj.get("id_fantrax") or "").strip()
        yid = str(proj.get("id_yahoo") or "").strip()
        nid = str(proj.get("id_nffc") or "").strip()
        pname = str(proj.get("name") or "").lower().strip()
        if (
            (fid and fid in owned_fantrax)
            or (yid and yid in owned_yahoo)
            or (nid and nid in owned_nfbc)
            or (pname and pname in owned_names)
        ):
            continue
        # API may use "pos" or "position" — check both
        pos = proj.get("position") or proj.get("pos") or ""
        pg = _pos_group(str(pos).upper())
        if pg == "OTHER":
            continue
        pts = calc_points(proj, weights)
        p_dict = {
            "name": proj.get("name", "?"),
            "nfl_team": proj.get("team", ""),
            "custom_pts": pts,
        }
        fa_by_pos.setdefault(pg, []).append((p_dict, proj))

    print(f"[Pickups] owned_fantrax={len(owned_fantrax)} fa_by_pos keys={list(fa_by_pos.keys())}", flush=True)

    if not fa_by_pos:
        return f"No FA projection data available for {label}."

    lines = [f"**{label} Pickups (Custom Scoring)**\n"]
    for pos in ["QB", "RB", "WR", "TE", "K", "DEF", "IDP"]:
        grp = fa_by_pos.get(pos, [])
        if not grp:
            continue
        grp.sort(key=lambda x: x[0]["custom_pts"], reverse=True)
        top = grp[:10]
        lines.append(_position_table(pos, top, f"{pos} — Top {len(top)} of {len(grp)} available"))

    return "\n".join(lines)


def generate_start_sit(
    target_team: str, owned_rosters, weekly_fantrax, weekly_yahoo,
    weights: dict, all_teams: List[str], week_label: str = "This Week", weekly_nfbc: dict = None
) -> str:
    """Show user's team weekly projections sorted by custom_pts."""
    matched = _find_team(target_team, all_teams)
    if not matched:
        return f"Team '{target_team}' not found. Available: {', '.join(all_teams)}"

    pos_buckets: Dict[str, list] = {}
    for roster in owned_rosters:
        if roster.team_owner != matched:
            continue
        player = roster.player
        if not player:
            continue
        proj = _match_player(player, weekly_fantrax, weekly_yahoo, weekly_nfbc)
        pts = calc_points(proj, weights) if proj else 0.0
        pg = _pos_group(player.position or "")
        p_dict = {
            "name": player.name,
            "nfl_team": player.team or "",
            "custom_pts": pts,
        }
        pos_buckets.setdefault(pg, []).append((p_dict, proj))

    if not pos_buckets:
        return f"No players or projections found for team '{matched}'."

    lines = [f"**Start/Sit: {matched} — {week_label}**\n"]
    for pos in ["QB", "RB", "WR", "TE", "K", "DEF", "IDP"]:
        grp = pos_buckets.get(pos, [])
        if not grp:
            continue
        grp.sort(key=lambda x: x[0]["custom_pts"], reverse=True)
        lines.append(_position_table(pos, grp, f"{pos} (start order)"))
    return "\n".join(lines)


# ── Chat endpoint ────────────────────────────────────────────────────────────

@router.post("/", response_model=ChatResponse)
async def nfl_chat(
    request: NFLChatRequest,
    db: Session = Depends(get_db)
):
    """GPT-4o-mini fantasy football assistant for NFL leagues."""
    # Load league
    league = db.query(League).filter(League.id == request.league_id).first()
    if not league:
        raise HTTPException(status_code=404, detail="League not found")
    if getattr(league, "sport", "mlb") != "nfl":
        raise HTTPException(status_code=400, detail="This league is not an NFL league.")

    # Message limits (same as MLB)
    messages_remaining = None
    if not request.user_api_key:
        user_id = request.user_id or str(request.league_id)
        user = MessageLimitService.get_or_create_user(user_id, db)
        can_send, remaining, limit_msg = MessageLimitService.can_send_message(user, db)
        if not can_send:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Daily message limit reached",
                    "message": limit_msg,
                    "messages_remaining": 0,
                    "reset_date": user.limit_reset_date.isoformat(),
                }
            )
        messages_remaining = remaining

    # Load rosters
    owned_rosters = db.query(Roster).options(joinedload(Roster.player)).filter(
        Roster.league_id == request.league_id,
        Roster.team_owner != "Free Agent",
    ).all()

    all_teams = sorted(set(r.team_owner for r in owned_rosters if r.team_owner))

    # Resolve scoring
    weights = _resolve_weights(request)
    preset_label = request.scoring_preset or "half_ppr"

    # Fetch projections
    ros_proj = nfl_svc.get_ros_projections()
    ros_fantrax = nfl_svc.build_fantrax_lookup(ros_proj)
    ros_yahoo = nfl_svc.build_yahoo_lookup(ros_proj)
    ros_nfbc = nfl_svc.build_nfbc_lookup(ros_proj)

    week = request.week
    weekly_proj, weekly_label = nfl_svc.get_best_weekly_projections(week)
    weekly_fantrax = nfl_svc.build_fantrax_lookup(weekly_proj)
    weekly_yahoo = nfl_svc.build_yahoo_lookup(weekly_proj)
    weekly_nfbc = nfl_svc.build_nfbc_lookup(weekly_proj)

    # ── Detect intent and generate hard-coded reports ─────────────────────
    msg_lower = request.message.lower()
    hard_coded = None

    selected_team = request.selected_team or ""

    if any(k in msg_lower for k in ("league overview", "league rank", "standings")):
        hard_coded = generate_league_overview(
            owned_rosters, ros_fantrax, ros_yahoo, weights, all_teams, ros_nfbc=ros_nfbc
        )

    elif any(k in msg_lower for k in ("team overview",)):
        team_name = selected_team or all_teams[0] if all_teams else ""
        for t in all_teams:
            if t.lower().lstrip("@") in msg_lower or t.lower() in msg_lower:
                team_name = t
                break
        hard_coded = generate_team_overview(
            team_name, owned_rosters, ros_fantrax, ros_yahoo, weights, all_teams, ros_nfbc=ros_nfbc
        )

    elif any(k in msg_lower for k in ("ros pickup", "ros pickups", "ros waiver", "best available ros")):
        hard_coded = generate_pickups_report(
            "ros", owned_rosters, weights, week=week
        )

    elif any(k in msg_lower for k in ("weekly pickup", "pickups", "waiver wire", "waiver", "add", "best available")):
        hard_coded = generate_pickups_report(
            "weekly", owned_rosters, weights, week=week
        )

    elif any(k in msg_lower for k in ("start sit", "start/sit", "who to start", "weekly start")):
        team_name = selected_team or all_teams[0] if all_teams else ""
        for t in all_teams:
            if t.lower().lstrip("@") in msg_lower or t.lower() in msg_lower:
                team_name = t
                break
        hard_coded = generate_start_sit(
            team_name, owned_rosters, weekly_fantrax, weekly_yahoo,
            weights, all_teams, week_label=weekly_label, weekly_nfbc=weekly_nfbc
        )

    # ── Build context for GPT ─────────────────────────────────────────────
    context_lines = [
        f"FANTASY FOOTBALL LEAGUE DATA (NFL, Fantrax, scoring={preset_label})",
        f"Teams in league: {', '.join(all_teams)}",
        f"Selected team: {selected_team or '(not set)'}",
        "",
        "ROSTER + ROS PROJECTIONS:",
    ]

    # Build per-team summaries with custom_pts
    team_summaries: Dict[str, Dict[str, list]] = {}
    for roster in owned_rosters:
        player = roster.player
        if not player:
            continue
        owner = roster.team_owner
        proj = _match_player(player, ros_fantrax, ros_yahoo, ros_nfbc)
        pts = calc_points(proj, weights) if proj else 0.0
        pg = _pos_group(player.position or "")
        entry = f"{player.name} ({pg}) {_f(pts)} pts"
        if proj and proj.get("opp"):
            entry += f" vs {proj['opp']}"
        team_summaries.setdefault(owner, {}).setdefault(pg, []).append((pts, entry))

    for owner in sorted(team_summaries.keys()):
        total = sum(pts for grp in team_summaries[owner].values() for pts, _ in grp)
        context_lines.append(f"\n{owner} (Total ROS: {_f(total)} pts):")
        for pos in ["QB", "RB", "WR", "TE", "K", "DEF", "IDP"]:
            grp = team_summaries[owner].get(pos, [])
            if not grp:
                continue
            grp.sort(reverse=True)
            context_lines.append(f"  {pos}: " + " | ".join(e for _, e in grp[:6]))

    context_lines.append(
        "\nSCORING: Use above custom_pts for all ranking and comparison questions."
    )
    context_text = "\n".join(context_lines)

    # ── System prompt ─────────────────────────────────────────────────────
    system_prompt = f"""You are Razzbot, an expert NFL fantasy football analyst.
You have access to the league's full roster data with ROS custom-scored projections.
Scoring preset: {preset_label}.
Always use the provided custom_pts figures when ranking players or teams.
For specific reports (league overview, team overview, pickups, start/sit), they are
pre-generated accurately — just present them clearly and add brief analysis.
Keep responses concise and actionable. Format tables with markdown.

CONTEXT:
{context_text}"""

    # ── Build messages for GPT ────────────────────────────────────────────
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    history = request.conversation_history or []
    for msg in history[-12:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Prepend hard-coded report to the user message if generated
    user_content = request.message
    if hard_coded:
        user_content = f"{request.message}\n\n[PRE-CALCULATED REPORT]\n{hard_coded}"

    messages.append({"role": "user", "content": user_content})

    # ── Call GPT ──────────────────────────────────────────────────────────
    try:
        api_key = request.user_api_key or os.getenv("OPENAI_API_KEY", "")
        _client = _OpenAI(api_key=api_key)
        completion = _client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=1500,
        )
        response_text = completion.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI error in NFL chat: {e}")
        if hard_coded:
            response_text = hard_coded
        else:
            raise HTTPException(status_code=500, detail="AI service unavailable. Please try again.")

    # Record message usage
    if not request.user_api_key and messages_remaining is not None:
        try:
            uid = request.user_id or str(request.league_id)
            u = MessageLimitService.get_or_create_user(uid, db)
            MessageLimitService.increment_usage(u, db)
        except Exception:
            pass

    return ChatResponse(
        message=response_text,
        response=response_text,
        messages_remaining=messages_remaining,
    )
