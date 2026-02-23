"""Chat schemas"""
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List, Dict


class ChatRequest(BaseModel):
    """Chat request"""
    league_id: UUID
    message: str
    user_id: Optional[str] = None  # User ID for tracking message limits
    user_api_key: Optional[str] = None  # User's OpenAI/Claude API key (optional, uses .env if not provided)
    provider: str = "openai"  # 'openai' or 'claude'
    conversation_history: Optional[List[Dict[str, str]]] = None  # Previous messages for memory


class ChatResponse(BaseModel):
    """Chat response"""
    message: str
    response: str
    tokens_used: Optional[int] = None
    messages_remaining: Optional[int] = None  # Messages remaining this month
    limit_info: Optional[str] = None  # User-friendly limit message
