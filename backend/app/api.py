"""API endpoints for the application."""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, Download, DownloadHistory, ApplicationSettings
from app.youtube_service import youtube_service
from app.utils import update_channel_in_yaml, remove_channel_from_yaml, sync_setting_to_yaml, get_default_video_limit as get_default_limit_setting
from app.schemas import (
    Channel as ChannelSchema,
    ChannelCreate,
    ChannelUpdate,
    ChannelList,
    SystemHealth,
    DefaultVideoLimitUpdate,
    DefaultVideoLimitResponse,
)

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()


@router.get("/channels", response_model=ChannelList)
async def list_channels(db: Session = Depends(get_db)):
    """List all channels with summary statistics."""
    channels = db.query(Channel).all()
    enabled_count = db.query(Channel).filter(Channel.enabled == True).count()
    
    return ChannelList(
        channels=channels,
        total=len(channels),
        enabled=enabled_count
    )


@router.post("/channels", response_model=ChannelSchema)
async def create_channel(channel: ChannelCreate, db: Session = Depends(get_db)):
    """
    Create a new YouTube channel for monitoring.
    
    This endpoint handles the complete channel addition workflow:
    1. Validates and normalizes the YouTube URL
    2. Extracts channel metadata using yt-dlp (without downloading videos)
    3. Checks for duplicate channels using YouTube's channel_id
    4. Stores the channel in the database for future monitoring
    
    Args:
        channel: Channel creation data including URL and monitoring settings
        db: Database session dependency
    
    Returns:
        Channel: The created channel with extracted metadata
        
    Raises:
        HTTPException 400: If URL is invalid or channel already exists
        HTTPException 400: If YouTube channel cannot be accessed or doesn't exist
        
    Example:
        POST /api/v1/channels
        {
            "url": "https://www.youtube.com/@MrsRachel",
            "limit": 10,
            "enabled": true,
            "quality_preset": "best"
        }
    """
    # Normalize URL to consistent format (handles www, mobile URLs, etc.)
    # This prevents duplicates when users enter different URL formats for same channel
    normalized_url = youtube_service.normalize_channel_url(str(channel.url))
    
    # Extract channel metadata using yt-dlp (Story 1: metadata only, no video downloads)
    success, channel_info, error = youtube_service.extract_channel_info(normalized_url)
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to extract channel information: {error}")
    
    # Check for duplicate channels using YouTube's unique channel_id
    # This prevents adding the same channel multiple times even with different URL formats
    # (e.g., /@handle vs /channel/UC... URLs for the same channel)
    existing = db.query(Channel).filter(Channel.channel_id == channel_info['channel_id']).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"This channel is already being monitored as '{existing.name}' with URL: {existing.url}"
        )
    
    # === APPLY DEFAULT VIDEO LIMIT (User Story 3) ===
    # If no limit specified, use the global default setting
    # This implements the core functionality of User Story 3
    channel_limit = channel.limit
    if channel_limit is None:
        channel_limit = get_default_limit_setting(db)
        logger.info(f"Applied default video limit {channel_limit} to new channel: {channel_info['name']}")
    
    # Create new channel record with extracted YouTube metadata
    db_channel = Channel(
        url=normalized_url,                              # Normalized URL for consistency
        channel_id=channel_info['channel_id'],           # YouTube's unique channel identifier
        name=channel_info['name'],                       # Channel name extracted from YouTube
        limit=channel_limit,                             # User-specified or default video limit
        enabled=channel.enabled,                         # Monitoring enabled/disabled
        schedule_override=channel.schedule_override,     # Custom schedule (if any)
        quality_preset=channel.quality_preset,          # Video quality preference
    )
    
    # Persist to database
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)  # Refresh to get auto-generated fields (id, timestamps)
    
    # Sync to YAML configuration
    try:
        channel_dict = {
            "url": db_channel.url,
            "name": db_channel.name,
            "limit": db_channel.limit,
            "enabled": db_channel.enabled,
            "quality_preset": db_channel.quality_preset,
            "schedule_override": db_channel.schedule_override,
        }
        update_channel_in_yaml(channel_dict)
    except Exception as e:
        logger.warning(f"Failed to sync new channel to YAML: {e}")
        # Don't fail the API call if YAML sync fails
    
    return db_channel


@router.get("/channels/{channel_id}", response_model=ChannelSchema)
async def get_channel(channel_id: int, db: Session = Depends(get_db)):
    """Get a specific channel by ID."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.put("/channels/{channel_id}", response_model=ChannelSchema)
async def update_channel(
    channel_id: int, 
    channel_update: ChannelUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update a channel's settings including video limit.
    
    This endpoint implements User Story 2: Configure Channel Video Limit
    
    Supports partial updates - only provided fields are modified:
    - limit: Video limit (1-100, validated by Pydantic)
    - enabled: Enable/disable monitoring 
    - name: Channel display name
    - schedule_override: Custom cron schedule
    - quality_preset: Video quality preference
    
    Features:
    - Input validation via Pydantic schemas (1-100 range for limits)
    - Automatic YAML configuration sync after database update
    - Graceful error handling - YAML sync failures don't fail API call
    - Returns complete updated channel object
    
    Args:
        channel_id: Database ID of channel to update
        channel_update: Partial channel update data (only changed fields)
        
    Returns:
        Channel: Complete updated channel object with new timestamps
        
    Raises:
        HTTPException 404: Channel not found
        HTTPException 422: Validation error (invalid limit range, etc.)
        
    Example:
        PUT /api/v1/channels/123
        {
            "limit": 25
        }
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Update only provided fields
    update_data = channel_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(channel, field, value)
    
    db.commit()
    db.refresh(channel)
    
    # === YAML CONFIGURATION SYNC ===
    # Keep YAML config file in sync with database changes for User Story 2
    # This ensures web UI changes are reflected in the configuration file
    try:
        channel_dict = {
            "url": channel.url,
            "name": channel.name,
            "limit": channel.limit,                    # Updated limit from user input
            "enabled": channel.enabled,
            "quality_preset": channel.quality_preset,
            "schedule_override": channel.schedule_override,
        }
        update_channel_in_yaml(channel_dict)          # Thread-safe YAML update
    except Exception as e:
        # Graceful degradation: Log warning but don't fail the API call
        # Database update succeeded, YAML sync is supplementary
        logger.warning(f"Failed to sync channel update to YAML: {e}")
        # API continues to return success since database update worked
    
    return channel


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    """Delete a channel and all its downloads."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Store URL for YAML cleanup before deletion
    channel_url = channel.url
    
    db.delete(channel)
    db.commit()
    
    # Remove from YAML configuration
    try:
        remove_channel_from_yaml(channel_url)
    except Exception as e:
        logger.warning(f"Failed to remove channel from YAML: {e}")
        # Don't fail the API call if YAML sync fails
    
    return {"message": "Channel deleted successfully"}


# === APPLICATION SETTINGS ENDPOINTS (User Story 3) ===

@router.get("/settings/default-video-limit", response_model=DefaultVideoLimitResponse)
async def get_default_video_limit(db: Session = Depends(get_db)):
    """
    Get the current default video limit setting.
    
    This endpoint supports User Story 3: Set Global Default Video Limit
    by providing access to the current default limit configuration.
    
    The default video limit is applied to new channels automatically
    when they are created without specifying a custom limit.
    
    Returns:
        DefaultVideoLimitResponse: Current default limit with metadata
        
    Raises:
        HTTPException 404: If default setting is not found
        HTTPException 500: If database error occurs
        
    Example:
        GET /api/v1/settings/default-video-limit
        Response: {
            "limit": 10,
            "description": "Default number of videos to keep per channel...",
            "updated_at": "2024-01-01T12:00:00"
        }
    """
    try:
        # Query the default video limit setting from database
        setting = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == 'default_video_limit'
        ).first()
        
        if not setting:
            raise HTTPException(
                status_code=404, 
                detail="Default video limit setting not found. Please check application initialization."
            )
        
        # Convert string value to integer with validation
        try:
            limit_value = int(setting.value)
            if not (1 <= limit_value <= 100):
                raise ValueError(f"Invalid limit value: {limit_value}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid default video limit in database: {setting.value}")
            raise HTTPException(
                status_code=500,
                detail=f"Invalid default video limit value in database: {setting.value}"
            )
        
        return DefaultVideoLimitResponse(
            limit=limit_value,
            description=setting.description or "Default video limit for new channels",
            updated_at=setting.updated_at
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Failed to get default video limit: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while retrieving default video limit"
        )


@router.put("/settings/default-video-limit", response_model=DefaultVideoLimitResponse)
async def update_default_video_limit(
    setting_update: DefaultVideoLimitUpdate,
    db: Session = Depends(get_db)
):
    """
    Update the default video limit setting.
    
    This endpoint supports User Story 3: Set Global Default Video Limit
    by allowing users to configure the default limit applied to new channels.
    
    The new default will apply to:
    - All channels created after this change
    - Channels imported from YAML without explicit limits
    - Manual channel additions via web UI (unless user specifies custom limit)
    
    Existing channels are NOT affected and retain their current limits.
    
    Args:
        setting_update: New default video limit (1-100)
        
    Returns:
        DefaultVideoLimitResponse: Updated setting with metadata
        
    Raises:
        HTTPException 400: If limit is outside valid range (handled by Pydantic)
        HTTPException 404: If default setting is not found
        HTTPException 500: If database error occurs
        
    Example:
        PUT /api/v1/settings/default-video-limit
        Body: {"limit": 25}
        Response: {
            "limit": 25,
            "description": "Default number of videos to keep per channel...",
            "updated_at": "2024-01-01T12:30:00"
        }
    """
    try:
        # Find the existing default video limit setting
        setting = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == 'default_video_limit'
        ).first()
        
        if not setting:
            raise HTTPException(
                status_code=404,
                detail="Default video limit setting not found. Please check application initialization."
            )
        
        # Update the setting value and timestamp
        from datetime import datetime
        setting.value = str(setting_update.limit)
        setting.updated_at = datetime.utcnow()
        
        # Commit to database
        db.commit()
        db.refresh(setting)
        
        logger.info(f"Default video limit updated to {setting_update.limit}")
        
        # === YAML CONFIGURATION SYNC ===
        # Sync the updated setting to YAML configuration for transparency
        # This ensures the YAML file reflects the current database state
        try:
            sync_success = sync_setting_to_yaml('default_video_limit', str(setting_update.limit))
            if sync_success:
                logger.info("Default video limit synced to YAML configuration")
            else:
                logger.warning("Failed to sync default video limit to YAML configuration")
                # Don't fail the API call since database update succeeded
        except Exception as e:
            logger.warning(f"YAML sync failed for default video limit: {e}")
            # Continue - YAML sync is supplementary to database update
        
        return DefaultVideoLimitResponse(
            limit=setting_update.limit,
            description=setting.description or "Default video limit for new channels",
            updated_at=setting.updated_at
        )
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Failed to update default video limit: {e}")
        db.rollback()  # Rollback any partial database changes
        raise HTTPException(
            status_code=500,
            detail="Internal server error while updating default video limit"
        )