"""Application configuration"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings"""

    # Database
    DATABASE_URL: str

    # Razzball API
    RAZZBALL_API_KEY: str
    RAZZBALL_API_BASE_URL: str = "https://api.razzball.com/mlb"

    # Player Reference
    PLAYER_REFERENCE_URL: str = "https://razzball.com/mlbamidsshhh/"

    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    # CORS
    FRONTEND_URL: str = "http://localhost:3000"

    # Environment
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
