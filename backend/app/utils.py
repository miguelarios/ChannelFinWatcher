"""Utility functions for the application."""
import os
import logging
import yaml
import threading
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import get_settings
from app.time_utils import utc_now

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
                    created_at=utc_now(),
                    updated_at=utc_now()
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


def is_retryable_error(error_message: str) -> bool:
    """
    Determine if a download error is transient and worth retrying.

    Shared by channel-level retry (scheduled_download_job) and per-video
    retry (video_download_service) so both layers agree on what counts
    as transient.

    Retryable: network timeouts, connection issues, rate limiting,
    temporary service unavailability.
    Non-retryable: deleted/private videos, invalid URLs, auth failures.

    Args:
        error_message: Error message string from a failed operation

    Returns:
        True if the error should be retried, False otherwise
    """
    if not error_message:
        return False

    retryable_keywords = [
        "network", "timeout", "connection", "temporary",
        "rate limit", "quota", "503", "502", "504",
        "429"  # Too Many Requests
    ]

    error_lower = error_message.lower()
    return any(keyword in error_lower for keyword in retryable_keywords)


class YtdlpErrorCapture:
    """Capture yt-dlp's own error/warning output for later inspection.

    Why this exists: our download options set ``ignoreerrors=True`` so a single
    bad video never aborts a whole channel run. The trade-off is that yt-dlp
    swallows the exception internally — ``ydl.download()`` returns normally even
    when nothing was downloaded, and the *real* reason (bot check, private
    video, format gone, stale player code, …) is lost. The caller is left only
    with "the file isn't on disk", which is useless for troubleshooting.

    yt-dlp accepts any object exposing ``debug``/``info``/``warning``/``error``
    as its ``logger`` option and routes all of its messages through it. By
    plugging this in we keep a copy of the error/warning lines (the ones that
    explain *why* a download produced no file) so we can translate them into a
    friendly message, while still forwarding everything to the app logger at
    DEBUG level so nothing is silently dropped.
    """

    def __init__(self, app_logger: Optional[logging.Logger] = None):
        # Forward to the module logger by default; callers may pass their own
        self._app_logger = app_logger or logger
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def debug(self, msg: str) -> None:
        # yt-dlp funnels both debug and info lines through debug(); keep them
        # at DEBUG so INFO-mode logs stay quiet but nothing is lost in DEBUG.
        self._app_logger.debug("[yt-dlp] %s", msg)

    def info(self, msg: str) -> None:
        self._app_logger.debug("[yt-dlp] %s", msg)

    def warning(self, msg: str) -> None:
        self.warnings.append(msg)
        self._app_logger.debug("[yt-dlp][warning] %s", msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)
        self._app_logger.debug("[yt-dlp][error] %s", msg)

    @property
    def messages(self) -> List[str]:
        """Captured lines most relevant to diagnosing the failure.

        yt-dlp is noisy: a failed run often logs several *benign* warnings
        (thumbnail/subtitle failures, format fallbacks, "some formats are
        missing") alongside the one fatal ERROR. Under ``ignoreerrors=True`` the
        fatal cause is reported through ``error()``, so we classify on the error
        lines when any exist and only fall back to warnings when none were
        captured.

        Why this matters beyond the message text: the translated message is
        also fed to ``is_retryable_error`` (see
        ``download_video_with_retry``). If an incidental warning outranked the
        real cause, a genuinely transient failure could be mislabeled
        non-retryable and silently skip its within-run retry. Preferring the
        error lines keeps both the user-facing message and the retry decision
        anchored to what actually failed.
        """
        return self.errors or self.warnings


def friendly_download_error(raw_messages: Optional[List[str]]) -> Optional[str]:
    """Translate raw yt-dlp error/warning text into a short, human-friendly reason.

    Turns yt-dlp's technical output into something a non-technical user can act
    on ("refresh your cookies", "the video is private", "update the app"). This
    is intentionally keyword-based rather than regex-heavy: yt-dlp's wording
    shifts between releases, so we match on stable substrings and keep the rules
    ordered from most specific/most common to least.

    Args:
        raw_messages: Captured yt-dlp error/warning lines (see YtdlpErrorCapture)

    Returns:
        A friendly one-line explanation, or None if nothing usable was captured
        (the caller should then fall back to its own generic message).

    Invariants worth preserving if you add rules:
    - Each rule is matched against a *single* line, and rules are tried in
      priority order, so the highest-priority category any one line describes
      wins. Matching per-line (rather than over one joined blob) prevents a
      multi-keyword rule from being satisfied by keywords bleeding across two
      unrelated lines (e.g. "geo" in one line + "restrict" in another).
    - Age restriction is ordered before the generic bot rule because both begin
      with "Sign in to confirm ..." ("...your age" vs "...you're not a bot").
    - This output is fed to is_retryable_error() by the retry layer. Retryable
      causes (rate-limit/network) MUST keep a keyword it recognizes ("429",
      "network", …) in their friendly text; non-retryable causes must not. The
      last-resort branch preserves the raw line, so unclassified transient
      errors stay retryable by keyword survival.
    """
    non_empty = [m for m in (raw_messages or []) if m and m.strip()]
    if not non_empty:
        return None

    lines = [m.lower() for m in non_empty]

    # Each rule: (clauses, friendly_message). A line matches the rule if it
    # satisfies ANY clause; a clause is a tuple of substrings that must ALL be
    # present in that one line. Keeping AND-groups within a single line is what
    # prevents cross-line keyword bleeding. Ordered most-specific first.
    rules = [
        # Age restriction — specific phrases, not a bare "age" (which would also
        # fire on "storage", "message", "usage", …).
        ([("confirm your age",), ("age-restricted",), ("age restricted",),
          ("inappropriate for some users",)],
         "This video is age-restricted. Cookies from a signed-in, age-verified account are required."),
        # Bot detection / missing-expired cookies — the most common cause of
        # "downloads stopped working" after a period of running fine.
        ([("sign in to confirm",), ("not a bot",), ("confirm you", "bot")],
         "YouTube blocked the download with a bot check. Your cookies are "
         "likely missing or expired — export a fresh cookies file from a "
         "signed-in browser session."),
        # Video no longer downloadable for account/visibility reasons
        ([("private video",)],
         "This video is private and can no longer be downloaded."),
        ([("video unavailable",), ("no longer available",), ("removed by the uploader",),
          ("account associated",), ("has been terminated",)],
         "This video is unavailable (deleted, removed, or the channel was terminated)."),
        ([("members-only",), ("members only",), ("join this channel",)],
         "This video is members-only and needs a channel membership (and matching cookies) to download."),
        # Region / format issues
        ([("available in your country",), ("blocked it in your country",), ("geo", "restrict")],
         "This video is geo-blocked in your region and can't be downloaded from here."),
        ([("requested format is not available",), ("requested format not available",)],
         "The selected quality/format isn't available for this video. Try a different quality preset."),
        # Stale yt-dlp vs. YouTube player changes — the fix is to update yt-dlp
        ([("nsig",), ("unable to extract",), ("signature", "extract"), ("player", "extract")],
         "YouTube changed its player and the installed yt-dlp can't decode this "
         "video. Update yt-dlp (rebuild the container) and try again."),
        # Transient conditions (must keep an is_retryable_error keyword)
        ([("http error 429",), ("too many requests",)],
         "YouTube is rate-limiting downloads (HTTP 429). Wait a while before retrying."),
        ([("timed out",), ("timeout",), ("connection",), ("network",), ("getaddrinfo",),
          ("temporary failure in name resolution",)],
         "A network error interrupted the download. This is usually temporary — retry later."),
    ]

    def line_matches(line: str, clauses) -> bool:
        return any(all(keyword in line for keyword in clause) for clause in clauses)

    for clauses, message in rules:
        if any(line_matches(line, clauses) for line in lines):
            return message

    # We captured something we don't have a canned message for. Surfacing the
    # real (trimmed) yt-dlp line still beats an opaque "file not found".
    last = non_empty[-1].strip()
    # Drop one leading "ERROR: "/"WARNING: " prefix for readability
    for prefix in ("ERROR: ", "WARNING: "):
        if last.startswith(prefix):
            last = last[len(prefix):]
            break
    return f"Download failed: {last}" if last else None


def get_default_quality_preset(db_session=None) -> str:
    """
    Get the default video quality preset for new channels (US-015).

    Priority order (same 3-tier scheme as get_default_video_limit):
    1. Database application_settings table (default_quality_preset)
    2. YAML configuration file (supports US-008 file-based configuration)
    3. Hardcoded fallback ('best')

    Args:
        db_session: Optional database session for direct queries

    Returns:
        str: Quality preset name (e.g., 'best', '1080p')
    """
    try:
        if db_session:
            from app.models import ApplicationSettings
            setting = db_session.query(ApplicationSettings).filter(
                ApplicationSettings.key == 'default_quality_preset'
            ).first()
            if setting and setting.value:
                return setting.value

        # Fallback to YAML configuration (advanced users may edit the file
        # directly without ever using the settings API)
        config = load_yaml_config()
        if 'settings' in config and config['settings'].get('default_quality_preset'):
            return str(config['settings']['default_quality_preset'])
    except Exception as e:
        logger.warning(f"Failed to read default quality preset, using 'best': {e}")

    return 'best'
