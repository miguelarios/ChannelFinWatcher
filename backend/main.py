"""Main FastAPI application."""
import logging
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, create_tables
from app.utils import ensure_directories, get_directory_info
from app.api import router as api_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="YouTube channel monitoring and video downloading application"
)

# Include API routes
app.include_router(api_router, prefix="/api/v1", tags=["channels"])


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    try:
        # Ensure directories exist
        ensure_directories()
        logger.info("Directory structure verified")
        
        # Create database tables
        create_tables()
        logger.info("Database tables initialized")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": f"{settings.app_name} API",
        "version": settings.app_version,
        "docs": "/docs"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint with database connectivity test."""
    try:
        # Test database connection
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = f"error: {str(e)}"
    
    # Get directory information
    directories = get_directory_info()
    
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "database": db_status,
        "directories": directories
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=settings.api_host, 
        port=settings.api_port,
        log_level="info"
    )