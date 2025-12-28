"""Main FastAPI application"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db

settings = get_settings()

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

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database tables on startup"""
    init_db()


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
from app.routers import csv, chat

app.include_router(csv.router, prefix="/api/csv", tags=["CSV Upload"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chatbot"])
