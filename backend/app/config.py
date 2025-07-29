"""Application configuration management."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    database_url: str = "sqlite:///data/app.db"
    
    # Application Paths
    media_dir: str = "/app/media"
    temp_dir: str = "/app/temp"
    config_file: str = "/app/config/config.yaml"
    
    # FastAPI Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # Optional Cookie File
    cookies_file: str = "/app/cookies.txt"
    
    # Application Metadata
    app_name: str = "ChannelFinWatcher"
    app_version: str = "0.1.0"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()