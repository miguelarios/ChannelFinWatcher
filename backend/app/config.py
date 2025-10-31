"""Application configuration management."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    database_url: str = "sqlite:////app/data/app.db"
    
    # Application Paths
    media_dir: str = "/app/media"
    temp_dir: str = "/app/temp"
    config_file: str = "/app/data/config.yaml"  # Consolidated into data directory

    # FastAPI Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # Optional Cookie File (for age-restricted content)
    cookies_file: str = "/app/data/cookies.txt"  # Consolidated into data directory
    
    # Application Metadata
    app_name: str = "ChannelFinWatcher"
    app_version: str = "0.1.0"

    # Scheduler Configuration (Story 007)
    scheduler_timezone: str = "UTC"  # Override with TZ environment variable
    scheduler_database_url: str = "sqlite:////app/data/scheduler_jobs.db"

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Use system TZ environment variable if available
        import os
        if 'TZ' in os.environ:
            self.scheduler_timezone = os.environ['TZ']


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()