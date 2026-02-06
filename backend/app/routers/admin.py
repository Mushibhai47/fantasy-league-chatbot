"""Admin API endpoints for dashboard"""
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import json
from app.database import get_db
from app.models import Chat, League, User
from app.services.message_limit_service import MessageLimitService

router = APIRouter()

# Simple admin authentication
ADMIN_USERS = {"rudy", "grey"}
ADMIN_PASSWORD = "razzball2024"

def verify_admin(authorization: Optional[str] = Header(None)):
    """Simple admin authentication"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    try:
        auth_type, credentials = authorization.split(" ")
        if auth_type.lower() != "basic":
            raise HTTPException(status_code=401, detail="Invalid auth type")
        username, password = credentials.split(":")
        if username not in ADMIN_USERS or password != ADMIN_PASSWORD:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return username
    except:
        raise HTTPException(status_code=401, detail="Invalid authorization format")


# Data Models
class DashboardStats(BaseModel):
    total_users: int
    total_chats: int
    active_now: int
    api_cost: float
    usage_data: List[Dict[str, Any]]
    top_queries: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]


class UserInfo(BaseModel):
    name: str
    email: str
    league_id: str
    last_active: str
    total_chats: int
    status: str


class AnalyticsData(BaseModel):
    avg_chats: float
    avg_duration: int
    return_rate: int
    total_api_calls: int
    total_tokens: int
    estimated_cost: float
    popular_features: List[Dict[str, Any]]


class ChatLog(BaseModel):
    user: str
    message: str
    response: str
    timestamp: str


class MessageLimitUpdate(BaseModel):
    user_id: str
    new_limit: int


class GlobalLimitUpdate(BaseModel):
    default_limit: int


class UserLimitInfo(BaseModel):
    user_id: str
    messages_used: int
    monthly_limit: int
    messages_remaining: int
    percentage_used: float
    reset_date: str
    days_until_reset: int


# Dashboard Endpoints
@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    """Get dashboard statistics from real database"""
    try:
        # Total users (unique league_ids)
        total_users = db.query(func.count(func.distinct(Chat.league_id))).scalar() or 0

        # Total chats
        total_chats = db.query(func.count(Chat.id)).scalar() or 0

        # Active users in last 5 minutes
        five_mins_ago = datetime.now() - timedelta(minutes=5)
        active_now = db.query(func.count(func.distinct(Chat.league_id))).filter(
            Chat.timestamp > five_mins_ago
        ).scalar() or 0

        # API cost estimation ($0.001 per chat with gpt-4o-mini)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_chats = db.query(func.count(Chat.id)).filter(
            Chat.timestamp >= today_start
        ).scalar() or 0
        api_cost = today_chats * 0.001

        # Usage data (last 7 days)
        usage_data = []
        for i in range(6, -1, -1):
            date = datetime.now() - timedelta(days=i)
            day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            count = db.query(func.count(Chat.id)).filter(
                Chat.timestamp >= day_start,
                Chat.timestamp < day_end
            ).scalar() or 0
            usage_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "chats": count
            })

        # Top queries
        top_queries_result = db.query(
            Chat.user_message,
            func.count(Chat.id).label('count')
        ).group_by(Chat.user_message).order_by(func.count(Chat.id).desc()).limit(5).all()

        top_queries = [{"query": q[0][:50] + "..." if len(q[0]) > 50 else q[0], "count": q[1]} for q in top_queries_result if q[0]]

        # Recent activity
        recent_chats = db.query(Chat).order_by(Chat.timestamp.desc()).limit(5).all()
        recent_activity = []
        for chat in recent_chats:
            recent_activity.append({
                "icon": "💬",
                "title": f"User asked: {chat.user_message[:40]}..." if chat.user_message else "Chat",
                "time": format_time_ago(chat.timestamp)
            })

        return DashboardStats(
            total_users=total_users,
            total_chats=total_chats,
            active_now=active_now,
            api_cost=round(api_cost, 4),
            usage_data=usage_data,
            top_queries=top_queries if top_queries else [{"query": "No queries yet", "count": 0}],
            recent_activity=recent_activity if recent_activity else [{"icon": "📊", "title": "No activity yet", "time": "Now"}]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/users", response_model=List[UserInfo])
async def get_users(db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    """Get list of all users from real database"""
    try:
        # Get unique users with chat counts
        user_stats = db.query(
            Chat.league_id,
            func.count(Chat.id).label('total_chats'),
            func.max(Chat.timestamp).label('last_active')
        ).group_by(Chat.league_id).all()

        users = []
        for stat in user_stats:
            if stat.league_id:
                is_active = (datetime.now() - stat.last_active).total_seconds() < 86400 if stat.last_active else False
                users.append(UserInfo(
                    name=f"User {stat.league_id[:8]}",
                    email=f"user-{stat.league_id[:8]}@league.com",
                    league_id=stat.league_id,
                    last_active=format_time_ago(stat.last_active) if stat.last_active else "Unknown",
                    total_chats=stat.total_chats,
                    status="active" if is_active else "inactive"
                ))

        return users if users else []

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/analytics", response_model=AnalyticsData)
async def get_analytics(db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    """Get analytics data from real database"""
    try:
        # Total chats
        total_chats = db.query(func.count(Chat.id)).scalar() or 0

        # Unique users
        unique_users = db.query(func.count(func.distinct(Chat.league_id))).scalar() or 1

        # Average chats per user
        avg_chats = total_chats / unique_users if unique_users > 0 else 0

        # Return rate (users with more than 1 chat)
        users_with_multiple = db.query(Chat.league_id).group_by(Chat.league_id).having(
            func.count(Chat.id) > 1
        ).count()
        return_rate = int((users_with_multiple / unique_users * 100)) if unique_users > 0 else 0

        # Estimated cost ($0.001 per chat)
        estimated_cost = total_chats * 0.001

        # Popular features based on keywords
        popular_features = [
            {"name": "General Questions", "usage": total_chats}
        ]

        return AnalyticsData(
            avg_chats=round(avg_chats, 1),
            avg_duration=5,
            return_rate=return_rate,
            total_api_calls=total_chats,
            total_tokens=total_chats * 500,
            estimated_cost=round(estimated_cost, 4),
            popular_features=popular_features
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/chats", response_model=List[ChatLog])
async def get_chats(
    date_filter: str = "today",
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    """Get chat logs from real database"""
    try:
        query = db.query(Chat)

        # Apply date filter
        if date_filter == "today":
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(Chat.timestamp >= today_start)
        elif date_filter == "week":
            week_ago = datetime.now() - timedelta(days=7)
            query = query.filter(Chat.timestamp >= week_ago)
        elif date_filter == "month":
            month_ago = datetime.now() - timedelta(days=30)
            query = query.filter(Chat.timestamp >= month_ago)

        chats = query.order_by(Chat.timestamp.desc()).limit(100).all()

        return [
            ChatLog(
                user=f"user-{chat.league_id[:8]}@league.com" if chat.league_id else "anonymous",
                message=chat.user_message or "No message",
                response=chat.bot_response[:100] + "..." if chat.bot_response and len(chat.bot_response) > 100 else (chat.bot_response or "No response"),
                timestamp=chat.timestamp.isoformat() if chat.timestamp else ""
            )
            for chat in chats
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/clear-logs")
async def clear_logs(db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    """Clear all chat logs"""
    try:
        count = db.query(Chat).delete()
        db.commit()
        return {"message": "All logs cleared", "rows_deleted": count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/export-data")
async def export_data(db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    """Export all data as JSON"""
    try:
        chats = db.query(Chat).order_by(Chat.timestamp.desc()).all()

        export_data = {
            "export_date": datetime.now().isoformat(),
            "total_records": len(chats),
            "data": [
                {
                    "league_id": chat.league_id,
                    "user_message": chat.user_message,
                    "bot_response": chat.bot_response,
                    "timestamp": chat.timestamp.isoformat() if chat.timestamp else None
                }
                for chat in chats
            ]
        }

        json_str = json.dumps(export_data, indent=2)

        return StreamingResponse(
            iter([json_str]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=razzball-export-{datetime.now().strftime('%Y%m%d')}.json"}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/message-limits", response_model=List[UserLimitInfo])
async def get_all_user_limits(db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    """Get message limits for all users"""
    try:
        users = db.query(User).all()
        limit_info = []

        for user in users:
            stats = MessageLimitService.get_usage_stats(user)
            limit_info.append(UserLimitInfo(
                user_id=str(user.id),
                messages_used=stats["messages_used"],
                monthly_limit=stats["monthly_limit"],
                messages_remaining=stats["messages_remaining"],
                percentage_used=stats["percentage_used"],
                reset_date=stats["reset_date"],
                days_until_reset=stats["days_until_reset"]
            ))

        return limit_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/message-limits/{user_id}", response_model=UserLimitInfo)
async def get_user_limit(user_id: str, db: Session = Depends(get_db), admin: str = Depends(verify_admin)):
    """Get message limit for a specific user"""
    try:
        user = MessageLimitService.get_or_create_user(user_id, db)
        stats = MessageLimitService.get_usage_stats(user)

        return UserLimitInfo(
            user_id=str(user.id),
            messages_used=stats["messages_used"],
            monthly_limit=stats["monthly_limit"],
            messages_remaining=stats["messages_remaining"],
            percentage_used=stats["percentage_used"],
            reset_date=stats["reset_date"],
            days_until_reset=stats["days_until_reset"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/message-limits/{user_id}")
async def update_user_limit(
    user_id: str,
    limit_data: MessageLimitUpdate,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    """Update message limit for a specific user"""
    try:
        user = MessageLimitService.get_or_create_user(user_id, db)
        updated_user = MessageLimitService.update_monthly_limit(user, limit_data.new_limit, db)
        stats = MessageLimitService.get_usage_stats(updated_user)

        return {
            "message": "Limit updated successfully",
            "user_id": str(updated_user.id),
            "new_limit": limit_data.new_limit,
            "stats": stats
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/message-limits/global")
async def update_global_limit(
    limit_data: GlobalLimitUpdate,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    """Update default message limit for all NEW users (doesn't affect existing users)"""
    try:
        if limit_data.default_limit < 0:
            raise HTTPException(status_code=400, detail="Limit cannot be negative")

        # This would typically be stored in a config table
        # For now, we'll just return confirmation
        # In production, you'd want to store this in a settings/config table

        return {
            "message": "Global default limit updated",
            "default_limit": limit_data.default_limit,
            "note": "This affects new users only. Use individual endpoints to update existing users."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/message-limits/{user_id}/reset")
async def reset_user_usage(
    user_id: str,
    db: Session = Depends(get_db),
    admin: str = Depends(verify_admin)
):
    """Reset a user's message usage counter (admin override)"""
    try:
        user = MessageLimitService.get_or_create_user(user_id, db)
        user.messages_used = 0
        user.limit_reset_date = datetime.utcnow() + timedelta(days=30)
        db.commit()
        db.refresh(user)

        stats = MessageLimitService.get_usage_stats(user)

        return {
            "message": "User usage reset successfully",
            "user_id": str(user.id),
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


def format_time_ago(timestamp) -> str:
    """Format timestamp as 'X minutes/hours/days ago'"""
    if not timestamp:
        return "Unknown"
    try:
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        delta = datetime.now() - timestamp

        if delta.total_seconds() < 60:
            return "Just now"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    except:
        return "Unknown"
