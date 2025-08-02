"""Utility functions for the application."""
import os
import logging
import yaml
import threading
from pathlib import Path
from typing import Dict, Any, List
from app.config import get_settings

logger = logging.getLogger(__name__)

# Thread lock for YAML file operations
yaml_lock = threading.Lock()


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


def load_yaml_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    settings = get_settings()
    config_path = Path(settings.config_file)
    
    if not config_path.exists():
        # Create empty config structure if file doesn't exist
        default_config = {
            "channels": [],
            "settings": {
                "default_video_limit": 10,
                "default_quality": "best",
                "default_schedule": "0 */6 * * *"  # Every 6 hours
            }
        }
        save_yaml_config(default_config)
        return default_config
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
            
        # Ensure required sections exist
        if 'channels' not in config:
            config['channels'] = []
        if 'settings' not in config:
            config['settings'] = {
                "default_video_limit": 10,
                "default_quality": "best",  
                "default_schedule": "0 */6 * * *"
            }
            
        return config
        
    except Exception as e:
        logger.error(f"Failed to load YAML config: {e}")
        return {"channels": [], "settings": {}}


def save_yaml_config(config: Dict[str, Any]) -> bool:
    """Save configuration to YAML file with thread safety."""
    settings = get_settings()
    config_path = Path(settings.config_file)
    
    # === THREAD-SAFE YAML OPERATIONS ===
    # Use global lock to prevent concurrent modifications that could corrupt the file
    with yaml_lock:
        try:
            # Ensure directory exists before writing
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write config with nice formatting for human readability
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(
                    config,
                    f,
                    default_flow_style=False,    # Use block style (more readable)
                    sort_keys=False,             # Preserve key order
                    indent=2,                    # Consistent indentation
                    allow_unicode=True           # Support Unicode channel names
                )
            
            logger.info(f"YAML config saved to {config_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save YAML config: {e}")
            return False


def sync_channels_to_yaml(channels: List[Dict[str, Any]]) -> bool:
    """Sync channel data from database to YAML configuration."""
    try:
        # Load current config
        config = load_yaml_config()
        
        # Convert database channels to YAML format
        yaml_channels = []
        for channel in channels:
            yaml_channel = {
                "url": channel.get("url"),
                "name": channel.get("name"),
                "limit": channel.get("limit", 10),
                "enabled": channel.get("enabled", True),
                "quality_preset": channel.get("quality_preset", "best"),
                "schedule_override": channel.get("schedule_override")
            }
            # Remove None values
            yaml_channel = {k: v for k, v in yaml_channel.items() if v is not None}
            yaml_channels.append(yaml_channel)
        
        # Update channels in config
        config["channels"] = yaml_channels
        
        # Save updated config
        return save_yaml_config(config)
        
    except Exception as e:
        logger.error(f"Failed to sync channels to YAML: {e}")
        return False


def update_channel_in_yaml(channel_data: Dict[str, Any]) -> bool:
    """
    Update a specific channel in YAML configuration file.
    
    This function supports User Story 2: Configure Channel Video Limit
    by ensuring changes made via the web UI are persisted to the YAML
    configuration file for consistency.
    
    Features:
    - Thread-safe file operations using yaml_lock
    - Upsert behavior (update existing or add new channel)
    - Preserves YAML structure and comments
    - Handles concurrent access safely
    - Removes None values to keep config clean
    
    Args:
        channel_data: Dictionary containing channel fields:
            - url (required): Channel URL for matching
            - name: Channel display name
            - limit: Video limit (1-100)
            - enabled: Monitoring enabled/disabled
            - quality_preset: Video quality setting
            - schedule_override: Custom cron schedule
            
    Returns:
        bool: True if update successful, False on error
        
    Thread Safety:
        Uses yaml_lock to prevent concurrent file modifications
        
    Example:
        update_channel_in_yaml({
            "url": "https://youtube.com/@example",
            "name": "Example Channel", 
            "limit": 25,
            "enabled": True
        })
    """
    try:
        # Load current config
        config = load_yaml_config()
        
        # Find and update the channel
        channel_updated = False
        for i, yaml_channel in enumerate(config["channels"]):
            if yaml_channel.get("url") == channel_data.get("url"):
                # Update existing channel
                config["channels"][i] = {
                    "url": channel_data.get("url"),
                    "name": channel_data.get("name"),
                    "limit": channel_data.get("limit", 10),
                    "enabled": channel_data.get("enabled", True),
                    "quality_preset": channel_data.get("quality_preset", "best"),
                    "schedule_override": channel_data.get("schedule_override")
                }
                # Remove None values
                config["channels"][i] = {k: v for k, v in config["channels"][i].items() if v is not None}
                channel_updated = True
                break
        
        if not channel_updated:
            # Add new channel if not found
            new_channel = {
                "url": channel_data.get("url"),
                "name": channel_data.get("name"),
                "limit": channel_data.get("limit", 10),
                "enabled": channel_data.get("enabled", True),
                "quality_preset": channel_data.get("quality_preset", "best"),
                "schedule_override": channel_data.get("schedule_override")
            }
            # Remove None values
            new_channel = {k: v for k, v in new_channel.items() if v is not None}
            config["channels"].append(new_channel)
        
        # Save updated config
        return save_yaml_config(config)
        
    except Exception as e:
        logger.error(f"Failed to update channel in YAML: {e}")
        return False


def remove_channel_from_yaml(channel_url: str) -> bool:
    """Remove a channel from YAML configuration."""
    try:
        # Load current config
        config = load_yaml_config()
        
        # Remove channel with matching URL
        original_count = len(config["channels"])
        config["channels"] = [
            ch for ch in config["channels"] 
            if ch.get("url") != channel_url
        ]
        
        # Check if channel was removed
        if len(config["channels"]) < original_count:
            return save_yaml_config(config)
        else:
            logger.warning(f"Channel with URL {channel_url} not found in YAML config")
            return True  # Not an error if channel wasn't there
            
    except Exception as e:
        logger.error(f"Failed to remove channel from YAML: {e}")
        return False