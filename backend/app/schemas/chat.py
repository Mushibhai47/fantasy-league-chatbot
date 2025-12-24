"""Chat schemas"""
from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class ChatRequest(BaseModel):
    """Chat request"""
    league_id: UUID
    message: str
    user_api_key: Optional[str] = None  # User's OpenAI/Claude API key (optional, uses .env if not provided)
    provider: str = "openai"  # 'openai' or 'claude'


class ChatResponse(BaseModel):
    """Chat response"""
    message: str
    response: str
    tokens_used: Optional[int] = None
