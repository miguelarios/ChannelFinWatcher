"""Utility functions for the application."""
import os
import logging
from pathlib import Path
from app.config import get_settings

logger = logging.getLogger(__name__)


def ensure_directories():
    """Ensure all required directories exist and are writable."""
    settings = get_settings()
    
    directories = [
        Path(settings.media_dir),
        Path(settings.temp_dir),
        Path(settings.config_file).parent,
        Path(settings.database_url.replace("sqlite:///", "")).parent,
    ]
    
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Directory ensured: {directory}")
            
            # Test write permissions
            test_file = directory / ".write_test"
            test_file.touch()
            test_file.unlink()
            
        except Exception as e:
            logger.error(f"Failed to create or access directory {directory}: {e}")
            raise


def get_directory_info():
    """Get information about configured directories."""
    settings = get_settings()
    
    directories = {
        "media": settings.media_dir,
        "temp": settings.temp_dir,
        "config": str(Path(settings.config_file).parent),
        "data": str(Path(settings.database_url.replace("sqlite:///", "")).parent),
    }
    
    info = {}
    for name, path in directories.items():
        path_obj = Path(path)
        info[name] = {
            "path": path,
            "exists": path_obj.exists(),
            "is_dir": path_obj.is_dir() if path_obj.exists() else False,
            "writable": os.access(path, os.W_OK) if path_obj.exists() else False,
        }
    
    return info