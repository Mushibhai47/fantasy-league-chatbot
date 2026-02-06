"""Service for managing user message limits and tracking usage"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.user import User
import uuid


class MessageLimitService:
    """Service to handle message limit tracking and enforcement"""

    @staticmethod
    def check_and_reset_if_needed(user: User, db: Session) -> User:
        """
        Check if the user's limit period has expired and reset if needed

        Args:
            user: User object
            db: Database session

        Returns:
            Updated user object
        """
        now = datetime.utcnow()

        # Check if we need to reset the counter
        if now >= user.limit_reset_date:
            user.messages_used = 0
            user.limit_reset_date = now + timedelta(days=30)
            db.commit()
            db.refresh(user)

        return user

    @staticmethod
    def can_send_message(user: User, db: Session) -> tuple[bool, int, str]:
        """
        Check if user can send a message

        Args:
            user: User object
            db: Database session

        Returns:
            Tuple of (can_send: bool, remaining: int, message: str)
        """
        # First check if we need to reset
        user = MessageLimitService.check_and_reset_if_needed(user, db)

        remaining = user.monthly_limit - user.messages_used

        if user.messages_used >= user.monthly_limit:
            return False, 0, f"Monthly message limit reached. Resets on {user.limit_reset_date.strftime('%Y-%m-%d')}"

        return True, remaining, f"{remaining} messages remaining this month"

    @staticmethod
    def increment_usage(user: User, db: Session) -> User:
        """
        Increment the user's message usage counter

        Args:
            user: User object
            db: Database session

        Returns:
            Updated user object
        """
        user.messages_used += 1
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_usage_stats(user: User) -> dict:
        """
        Get user's current usage statistics

        Args:
            user: User object

        Returns:
            Dictionary with usage stats
        """
        remaining = user.monthly_limit - user.messages_used
        percentage_used = (user.messages_used / user.monthly_limit * 100) if user.monthly_limit > 0 else 0

        return {
            "messages_used": user.messages_used,
            "monthly_limit": user.monthly_limit,
            "messages_remaining": remaining,
            "percentage_used": round(percentage_used, 2),
            "reset_date": user.limit_reset_date.isoformat(),
            "days_until_reset": (user.limit_reset_date - datetime.utcnow()).days
        }

    @staticmethod
    def update_monthly_limit(user: User, new_limit: int, db: Session) -> User:
        """
        Update a user's monthly message limit

        Args:
            user: User object
            new_limit: New monthly limit
            db: Database session

        Returns:
            Updated user object
        """
        if new_limit < 0:
            raise ValueError("Monthly limit cannot be negative")

        user.monthly_limit = new_limit
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_or_create_user(user_id: str, db: Session) -> User:
        """
        Get existing user or create new one

        Args:
            user_id: User ID (UUID string)
            db: Database session

        Returns:
            User object
        """
        # Try to parse as UUID
        try:
            user_uuid = uuid.UUID(user_id)
        except (ValueError, AttributeError):
            # If invalid UUID, create a new one
            user_uuid = uuid.uuid4()

        # Try to get existing user
        user = db.query(User).filter(User.id == user_uuid).first()

        if not user:
            # Create new user with default limits
            user = User(
                id=user_uuid,
                messages_used=0,
                monthly_limit=100,
                limit_reset_date=datetime.utcnow() + timedelta(days=30)
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user
