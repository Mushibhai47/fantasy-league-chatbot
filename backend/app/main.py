"""Main FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db
import asyncio
import logging

settings = get_settings()
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Fantasy League Chatbot API",
    description="AI-powered fantasy baseball roster assistant",
    version="1.0.0"
)

# CORS middleware - allow all origins for deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for Replit/deployment
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

async def _refresh_projections_loop():
    """Background task: proactively refresh all projection types every 5 minutes during active hours."""
    from app.services.projection_service import ProjectionService, _is_active_hours
    await asyncio.sleep(30)  # wait for startup to settle
    while True:
        try:
            if _is_active_hours():
                for proj_type in ["ros", "daily", "weekly"]:
                    try:
                        svc = ProjectionService(projection_type=proj_type)
                        svc.fetch_projections()
                        logger.info(f"Background refresh: {proj_type} projections updated")
                    except Exception as e:
                        logger.error(f"Background refresh failed for {proj_type}: {e}")
        except Exception as e:
            logger.error(f"Background refresh loop error: {e}")
        await asyncio.sleep(5 * 60)  # wait 5 minutes

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    init_db()
    asyncio.create_task(_refresh_projections_loop())
    logger.info("Background projection refresh task started")


# Root endpoint
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Fantasy League Chatbot API",
        "version": "1.0.0",
        "status": "running"
    }


# Health check
@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT
    }


# Include routers
from app.routers import csv, chat, admin

app.include_router(csv.router, prefix="/api/csv", tags=["CSV Upload"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chatbot"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin Dashboard"])
