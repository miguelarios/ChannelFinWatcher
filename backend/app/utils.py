"""Utility functions for the application."""
import os
import logging
import yaml
import threading
import re
from pathlib import Path
from typing import Dict, Any, List
from app.config import get_settings

logger = logging.getLogger(__name__)

# Thread lock for YAML file operations
yaml_lock = threading.Lock()


def channel_dir_name(channel) -> str:
    """
    Generate directory name for channel using original name.
    Only removes filesystem-unsafe characters, preserves emojis and special chars.
    
    Args:
        channel: Channel database model
    
    Returns:
        Directory name in format "OriginalChannelName [channel_id]"
        
    Raises:
        ValueError: If channel has no channel_id
    """
    # Ensure channel_id is present and valid
    if not channel.channel_id:
        raise ValueError(f"Channel {channel.id} has no channel_id")
    
    # Only remove characters that are truly unsafe for filesystems
    # Keep emojis, accented characters, hyphens, etc.
    safe_name = channel.name
    # Only remove: < > : " / \ | ? *
    safe_name = re.sub(r'[<>:"/\\|?*]', '', safe_name)
    safe_name = re.sub(r'\.+$', '', safe_name)  # Remove trailing dots
    safe_name = safe_name.strip()
    
    return f"{safe_name} [{channel.channel_id}]"


def ensure_directories():
    """Ensure all required directories exist and are writable."""
    settings = get_settings()
    
    # Extract database path from SQLite URL
    # sqlite:////app/data/app.db -> /app/data/app.db (keep single leading /)
    db_path = settings.database_url.replace("sqlite:///", "", 1)
    if db_path.startswith("/"):
        db_path = "/" + db_path.lstrip("/")

    directories = [
        Path(settings.media_dir),
        Path(settings.temp_dir),
        Path(settings.config_file).parent,
        Path(db_path).parent,
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

    # Extract database path from SQLite URL (same as ensure_directories)
    db_path = settings.database_url.replace("sqlite:///", "", 1)
    if db_path.startswith("/"):
        db_path = "/" + db_path.lstrip("/")

    directories = {
        "media": settings.media_dir,
        "temp": settings.temp_dir,
        "config": str(Path(settings.config_file).parent),
        "data": str(Path(db_path).parent),
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
    """
    Load configuration from YAML file with settings synchronization.
    
    For User Story 3, this function ensures the YAML configuration includes
    the current application settings and provides fallback values.
    """
    settings = get_settings()
    config_path = Path(settings.config_file)
    
    if not config_path.exists():
        # Create empty config structure if file doesn't exist
        default_config = {
            "channels": [],
            "settings": {
                "default_video_limit": 10,
                "default_quality_preset": "best",
                "default_schedule": "0 0 * * *"  # Daily at midnight UTC
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
                "default_quality_preset": "best",
                "default_schedule": "0 0 * * *"
            }
        else:
            # Ensure all required settings exist with fallbacks
            if 'default_video_limit' not in config['settings']:
                config['settings']['default_video_limit'] = 10
            if 'default_quality_preset' not in config['settings']:
                config['settings']['default_quality_preset'] = "best"
            if 'default_schedule' not in config['settings']:
                config['settings']['default_schedule'] = "0 0 * * *"
            
        return config
        
    except Exception as e:
        logger.error(f"Failed to load YAML config: {e}")
        return {"channels": [], "settings": {"default_video_limit": 10}}


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


def get_default_video_limit(db_session=None) -> int:
    """
    Get the default video limit setting from database or fallback to YAML.
    
    This function supports User Story 3: Set Global Default Video Limit
    by providing a centralized way to retrieve the default limit for new channels.
    
    Priority order:
    1. Database application_settings table
    2. YAML configuration file
    3. Hardcoded fallback (10)
    
    Args:
        db_session: Optional database session for direct queries
        
    Returns:
        int: Default video limit (1-100)
        
    Example:
        limit = get_default_video_limit()  # Returns 10 or configured value
    """
    try:
        # Try database first if session provided
        if db_session:
            from app.models import ApplicationSettings
            setting = db_session.query(ApplicationSettings).filter(
                ApplicationSettings.key == 'default_video_limit'
            ).first()
            if setting and setting.value:
                return int(setting.value)
        
        # Fallback to YAML configuration
        config = load_yaml_config()
        if 'settings' in config and 'default_video_limit' in config['settings']:
            return int(config['settings']['default_video_limit'])
        
        # Final fallback
        logger.warning("No default video limit found in database or YAML, using fallback value 10")
        return 10
        
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid default video limit value, using fallback: {e}")
        return 10
    except Exception as e:
        logger.error(f"Failed to get default video limit: {e}")
        return 10


def sync_setting_to_yaml(key: str, value: str) -> bool:
    """
    Sync a specific application setting from database to YAML configuration.
    
    This function supports User Story 3 by ensuring changes made via the API
    are reflected in the YAML configuration file for transparency and backup.
    
    Args:
        key: Setting key (e.g., 'default_video_limit')
        value: Setting value to sync
        
    Returns:
        bool: True if sync successful, False on error
        
    Thread Safety:
        Uses yaml_lock to prevent concurrent file modifications
    """
    try:
        # Load current config
        config = load_yaml_config()
        
        # Ensure settings section exists
        if 'settings' not in config:
            config['settings'] = {}
        
        # Update the specific setting
        config['settings'][key] = value
        
        # Save updated config
        return save_yaml_config(config)
        
    except Exception as e:
        logger.error(f"Failed to sync setting {key} to YAML: {e}")
        return False


def initialize_default_settings(db_session) -> bool:
    """
    Initialize default application settings in database if they don't exist.
    
    This function supports User Story 3 by ensuring default settings are
    available on first run or after database reset.
    
    Args:
        db_session: Database session for queries and inserts
        
    Returns:
        bool: True if initialization successful, False on error
    """
    try:
        from app.models import ApplicationSettings
        from datetime import datetime
        
        # Define default settings
        default_settings = [
            {
                'key': 'default_video_limit',
                'value': '10',
                'description': 'Default number of videos to keep per channel (1-100). Applied to new channels automatically.'
            },
            {
                'key': 'default_quality_preset',
                'value': 'best',
                'description': 'Default video quality preset for new channels (best, 1080p, 720p, 480p).'
            },
            {
                'key': 'default_schedule',
                'value': '0 0 * * *',
                'description': 'Default cron schedule for channel monitoring (daily at midnight UTC).'
            },
            {
                'key': 'nfo_enabled',
                'value': 'true',
                'description': 'Enable/disable NFO file generation for new video downloads. NFO files provide Jellyfin-compatible metadata.'
            },
            {
                'key': 'nfo_overwrite_existing',
                'value': 'false',
                'description': 'Overwrite existing NFO files during regeneration. Set to true to force update all NFO files.'
            }
        ]
        
        # Check and insert missing settings
        for setting_data in default_settings:
            existing = db_session.query(ApplicationSettings).filter(
                ApplicationSettings.key == setting_data['key']
            ).first()
            
            if not existing:
                setting = ApplicationSettings(
                    key=setting_data['key'],
                    value=setting_data['value'],
                    description=setting_data['description'],
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db_session.add(setting)
                logger.info(f"Initialized default setting: {setting_data['key']} = {setting_data['value']}")
        
        db_session.commit()
        
        # Sync new defaults to YAML
        for setting_data in default_settings:
            sync_setting_to_yaml(setting_data['key'], setting_data['value'])
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize default settings: {e}")
        db_session.rollback()
        return False


def validate_cookies_file_format(cookies_path: str) -> tuple[bool, str]:
    """
    Validate that a cookies file is in the Netscape format expected by yt-dlp.

    The Netscape cookie format is a tab-separated file with either:
    - A header line starting with "# Netscape HTTP Cookie File" or "# HTTP Cookie File"
    - Or data lines with 7 tab-separated fields: domain, tailmatch, path, secure, expires, name, value

    This validation helps users identify misconfigured cookie files early,
    before downloads fail with cryptic yt-dlp errors.

    Args:
        cookies_path: Path to the cookies file to validate

    Returns:
        Tuple of (is_valid, message):
        - (True, "success message") if file is valid Netscape format
        - (False, "error message") if file doesn't exist, is empty, or wrong format

    Example:
        is_valid, msg = validate_cookies_file_format("/app/data/cookies.txt")
        if not is_valid:
            logger.warning(msg)
    """
    # Check if file exists
    if not os.path.exists(cookies_path):
        return False, f"Cookies file not found at '{cookies_path}'"

    try:
        with open(cookies_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except IOError as e:
        return False, f"Could not read cookies file '{cookies_path}': {e}"

    # Empty file check
    if not lines:
        return False, f"'{cookies_path}' is empty"

    # Check for Netscape format indicators
    has_netscape_header = False
    has_valid_data_line = False

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Check for Netscape header comment
        if line.startswith('#'):
            lower_line = line.lower()
            if 'netscape' in lower_line and 'cookie' in lower_line:
                has_netscape_header = True
            elif 'http cookie file' in lower_line:
                has_netscape_header = True
            continue

        # Check for valid data line (7 tab-separated fields)
        # Format: domain, tailmatch, path, secure, expires, name, value
        fields = line.split('\t')
        if len(fields) >= 7:
            # Basic validation: tailmatch should be TRUE/FALSE, secure should be TRUE/FALSE
            tailmatch = fields[1].upper()
            secure = fields[3].upper()
            if tailmatch in ('TRUE', 'FALSE') and secure in ('TRUE', 'FALSE'):
                has_valid_data_line = True
                break  # Found at least one valid line

    # Determine result
    if has_netscape_header or has_valid_data_line:
        return True, f"Cookies file '{cookies_path}' appears to be valid Netscape format"
    else:
        return False, f"'{cookies_path}' does not look like a Netscape format cookies file"


def sync_all_settings_to_yaml(db_session) -> bool:
    """
    Sync all application settings from database to YAML configuration.
    
    This function supports User Story 3 by ensuring the YAML configuration
    file reflects the current database state for all application settings.
    
    Args:
        db_session: Database session for queries
        
    Returns:
        bool: True if sync successful, False on error
    """
    try:
        from app.models import ApplicationSettings
        
        # Get all settings from database
        settings = db_session.query(ApplicationSettings).all()
        
        if not settings:
            logger.warning("No application settings found in database for YAML sync")
            return True  # Not an error if no settings exist yet
        
        # Load current YAML config
        config = load_yaml_config()
        
        # Ensure settings section exists
        if 'settings' not in config:
            config['settings'] = {}
        
        # Sync each setting from database to YAML
        for setting in settings:
            try:
                # Convert database string values to appropriate types for YAML
                value = setting.value
                if setting.key == 'default_video_limit':
                    value = int(setting.value)  # Convert to integer for better YAML readability
                
                config['settings'][setting.key] = value
                logger.debug(f"Synced setting to YAML: {setting.key} = {value}")
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert setting {setting.key}={setting.value}: {e}")
                # Keep as string if conversion fails
                config['settings'][setting.key] = setting.value
        
        # Save updated config
        success = save_yaml_config(config)
        if success:
            logger.info(f"Synced {len(settings)} application settings to YAML configuration")
        
        return success
        
    except Exception as e:
        logger.error(f"Failed to sync all settings to YAML: {e}")
        return False