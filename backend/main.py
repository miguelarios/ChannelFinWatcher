"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, SessionLocal
from app.utils import (
    ensure_directories,
    get_directory_info,
    initialize_default_settings,
    sync_all_settings_to_yaml
)
from app.api import router as api_router
from app.scheduler_service import scheduler_service

# Configure logging
# force=True is required because uvicorn configures logging before this module loads
# Without force=True, basicConfig silently does nothing and logs are suppressed
logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

# Get settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for application startup and shutdown.

    This handles:
    - Application initialization (directories, database, settings)
    - Scheduler startup and job recovery
    - Graceful shutdown of scheduler

    The lifespan context manager is the modern FastAPI pattern for managing
    startup and shutdown events, replacing the deprecated @app.on_event decorators.
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    try:
        # Ensure directories exist
        ensure_directories()
        logger.info("Directory structure verified")

        # Run pending database migrations automatically
        # This ensures schema changes from Alembic migrations are applied
        # NOTE: We do NOT call create_tables() - migrations handle schema
        from alembic.config import Config
        from alembic import command
        import traceback

        try:
            logger.info("Creating Alembic config...")
            alembic_cfg = Config("alembic.ini")
            logger.info("Running database migrations...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Alembic upgrade command completed")
            logger.info("Database migrations applied successfully")
        except SystemExit as sys_exit:
            logger.error(f"Alembic called sys.exit({sys_exit.code})")
            logger.error(
                f"Migration SystemExit: {traceback.format_exc()}"
            )
            # Re-raise - migrations are critical
            raise
        except Exception as migration_error:
            logger.error(
                f"Failed to apply database migrations: {migration_error}"
            )
            logger.error(f"Migration traceback: {traceback.format_exc()}")
            # Re-raise - migrations are critical for proper database schema
            raise

        # Initialize default application settings
        db = SessionLocal()
        try:
            logger.info("Initializing default settings...")
            initialize_default_settings(db)
            logger.info("Default application settings initialized")

            # Sync all settings from database to YAML configuration
            logger.info("Syncing settings to YAML...")
            sync_all_settings_to_yaml(db)
            logger.info("Application settings synced to YAML configuration")
        except Exception as settings_error:
            logger.error(f"Settings initialization failed: {settings_error}")
            import traceback
            logger.error(f"Settings traceback: {traceback.format_exc()}")
            raise
        finally:
            db.close()

        # Start scheduler service (Story 007)
        logger.info("Starting scheduler service...")
        await scheduler_service.start()
        logger.info("Scheduler service started successfully")

    except Exception as e:
        logger.error(f"Startup failed: {e}")
        import traceback
        logger.error(f"Startup traceback: {traceback.format_exc()}")
        raise

    # Application is ready, yield control
    yield

    # Shutdown
    logger.info("Shutting down application")
    try:
        await scheduler_service.shutdown()
        logger.info("Scheduler service stopped successfully")
    except Exception as e:
        logger.error(f"Error during scheduler shutdown: {e}")


# Create FastAPI app with lifespan management and comprehensive OpenAPI documentation
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
    **ChannelFinWatcher** is a YouTube channel monitoring system that automatically downloads
    the latest videos from configured channels for offline viewing.

    ## Features

    * **Channel Management**: Add, configure, and monitor YouTube channels
    * **Automated Downloads**: Scheduled downloads with configurable limits
    * **Real-time Status**: Monitor download progress and system health
    * **File Organization**: Jellyfin-compatible media organization

    ## API Documentation

    This API provides endpoints for:
    - Channel CRUD operations
    - Download status and history
    - System configuration and health monitoring

    ## Getting Started

    1. Use the `/health` endpoint to verify system status
    2. Add channels via the channels API
    3. Monitor downloads through the status endpoints
    """,
    lifespan=lifespan,  # Register lifespan context manager
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    contact={
        "name": "ChannelFinWatcher",
        "url": "https://github.com/yourusername/channelfinwatcher",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Include API routes
app.include_router(api_router, prefix="/api/v1", tags=["channels", "settings"])


@app.get("/", tags=["System"])
async def root():
    """
    Welcome endpoint providing basic API information.
    
    Returns system information and links to documentation.
    """
    return {
        "message": f"{settings.app_name} API",
        "version": settings.app_version,
        "description": "YouTube channel monitoring and video downloading system",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/api/v1/openapi.json"
        },
        "health_check": "/health"
    }


@app.get("/health", tags=["System"])
async def health_check(db: Session = Depends(get_db)):
    """
    System health check endpoint.
    
    Verifies database connectivity and directory structure.
    Returns comprehensive system status information.
    """
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