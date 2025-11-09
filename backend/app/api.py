"""API endpoints for the application."""
import os
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, Download, DownloadHistory, ApplicationSettings
from app.youtube_service import youtube_service
from app.metadata_service import metadata_service
from app.video_download_service import video_download_service
from app.utils import update_channel_in_yaml, remove_channel_from_yaml, sync_setting_to_yaml, get_default_video_limit as get_default_limit_setting, channel_dir_name
from app.schemas import (
    Channel as ChannelSchema,
    ChannelCreate,
    ChannelUpdate,
    ChannelList,
    SystemHealth,
    DefaultVideoLimitUpdate,
    DefaultVideoLimitResponse,
    Download as DownloadSchema,
    DownloadList,
    DownloadHistory as DownloadHistorySchema,
    DownloadTriggerResponse,
    SchedulerStatusResponse,
    UpdateScheduleRequest,
    UpdateScheduleResponse,
    SchedulerEnableRequest,
    ValidateCronResponse,
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
        metadata_status="pending",                       # Initial metadata status
    )
    
    # Persist to database
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)  # Refresh to get auto-generated fields (id, timestamps)
    
    # === METADATA PROCESSING (Story 004) ===
    # Process complete channel metadata including directory creation and image downloads
    metadata_success, metadata_errors = metadata_service.process_channel_metadata(db, db_channel, normalized_url)
    
    if not metadata_success:
        logger.warning(f"Metadata processing failed for channel {db_channel.id}: {metadata_errors}")
        # Channel was created successfully, metadata processing is supplementary
        # Don't fail the API call, but log the warnings
    else:
        # === VIDEO DOWNLOADS (Story 005) ===
        # After successful metadata extraction, automatically start downloading recent videos
        logger.info(f"🚀 API: Triggering initial video downloads for new channel: {db_channel.name}")
        logger.info(f"📝 API: Channel details - ID: {db_channel.id}, URL: {db_channel.url}, channel_id: {db_channel.channel_id}, limit: {db_channel.limit}")
        try:
            logger.info(f"🔄 API: Calling video_download_service.process_channel_downloads()...")
            download_success, videos_downloaded, download_error = video_download_service.process_channel_downloads(db_channel, db)
            logger.info(f"✅ API: process_channel_downloads() returned - success: {download_success}, count: {videos_downloaded}, error: {download_error}")
            if download_success:
                logger.info(f"✅ API: Initial download completed for {db_channel.name}: {videos_downloaded} videos downloaded")
            else:
                logger.warning(f"⚠️  API: Initial download failed for {db_channel.name}: {download_error}")
                # Don't fail channel creation if initial downloads fail
        except Exception as e:
            logger.error(f"❌ API: Unexpected error during initial downloads for {db_channel.name}: {e}")
            import traceback
            logger.error(f"Stack trace: {traceback.format_exc()}")
            # Don't fail channel creation if downloads encounter errors
    
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
        logger.info(f"Delete requested for channel_id={channel_id}, but channel was not found")
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


@router.post("/channels/{channel_id}/refresh-metadata")
async def refresh_channel_metadata(channel_id: int, db: Session = Depends(get_db)):
    """
    Refresh channel metadata including directory structure and images.
    
    This endpoint implements metadata refresh functionality for Story 004.
    It extracts fresh metadata from YouTube, updates the JSON file,
    and redownloads cover/backdrop images.
    
    Args:
        channel_id: Database ID of channel to refresh
        
    Returns:
        dict: Status message and any warnings
        
    Raises:
        HTTPException 404: Channel not found
        HTTPException 400: Metadata refresh failed
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Refresh metadata using metadata service
    success, errors = metadata_service.refresh_channel_metadata(db, channel)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Metadata refresh failed: {'; '.join(errors)}"
        )
    
    response_data = {"message": "Channel metadata refreshed successfully"}
    if errors:
        response_data["warnings"] = errors
    
    return response_data


@router.post("/channels/{channel_id}/reindex")
async def reindex_channel(channel_id: int, db: Session = Depends(get_db)):
    """
    Reindex a channel's media folder to sync database with disk state.
    
    This will:
    - Find all video files on disk
    - Update/create Download records to match
    - Mark missing files as file_exists=False
    
    Args:
        channel_id: Database ID of channel to reindex
        db: Database session
        
    Returns:
        dict: Statistics about reindex operation
        
    Raises:
        HTTPException 404: If channel not found
    """
    from app.config import get_settings
    from datetime import datetime
    import re
    
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    settings = get_settings()
    
    # Find channel media directory - first try stored path, then directory search
    media_path = None
    
    # Method 1: Try database-stored directory path
    if channel.directory_path and os.path.exists(channel.directory_path):
        media_path = channel.directory_path
        logger.info(f"Using stored directory path for reindex: {media_path}")
    else:
        # Method 2: Fallback directory search
        import glob
        all_dirs = glob.glob(os.path.join(settings.media_dir, '*/')) 
        for directory in all_dirs:
            if channel.channel_id in os.path.basename(directory.rstrip('/')):
                media_path = directory.rstrip('/')
                # Update the database with the found path for next time
                channel.directory_path = media_path
                db.add(channel)
                db.commit()
                logger.info(f"Found and saved media directory for reindex: {media_path}")
                break
    
    stats = {
        "channel": channel.name,
        "found": 0,
        "missing": 0,
        "added": 0,
        "errors": []
    }
    
    try:
        # Find all video files on disk
        video_ids_on_disk = set()
        if media_path and os.path.exists(media_path):
            for root, dirs, files in os.walk(media_path):
                for file in files:
                    # Skip partial downloads
                    if file.endswith('.part'):
                        continue
                    
                    # Extract video ID from filename [video_id]
                    match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', file)
                    if match:
                        video_id = match.group(1)
                        video_ids_on_disk.add(video_id)
                        
                        # Check if we have a record
                        download = db.query(Download).filter(
                            Download.video_id == video_id,
                            Download.channel_id == channel_id
                        ).first()
                        
                        if download:
                            if not download.file_exists:
                                download.file_exists = True
                                download.file_path = os.path.join(root, file)
                                stats["found"] += 1
                        else:
                            # Create new record for orphaned file
                            try:
                                download = Download(
                                    channel_id=channel_id,
                                    video_id=video_id,
                                    title=file.split('[')[0].strip() if '[' in file else "Found on disk",
                                    status='completed',
                                    file_exists=True,
                                    file_path=os.path.join(root, file),
                                    completed_at=datetime.utcnow()
                                )
                                db.add(download)
                                stats["added"] += 1
                            except Exception as e:
                                stats["errors"].append(f"Failed to add record for {video_id}: {str(e)}")
        
        # Mark missing files in database
        db_downloads = db.query(Download).filter(
            Download.channel_id == channel_id,
            Download.status == 'completed'
        ).all()
        
        for download in db_downloads:
            if download.video_id not in video_ids_on_disk:
                if download.file_exists:
                    download.file_exists = False
                    stats["missing"] += 1
        
        db.commit()
        
        logger.info(f"Reindex completed for channel {channel.name}: found={stats['found']}, missing={stats['missing']}, added={stats['added']}")
        
        return stats
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error during reindex of channel {channel_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Reindex failed: {str(e)}"
        )


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: int, 
    delete_media: bool = False,
    db: Session = Depends(get_db)
):
    """
    Delete a channel with optional media deletion.
    
    Args:
        channel_id: ID of channel to delete
        delete_media: If True, also delete downloaded video files
        db: Database session
        
    Returns:
        dict: Deletion status with media deletion summary
    """
    from app.config import get_settings
    
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Store info for response before deletion
    settings = get_settings()
    channel_id = channel.id  # Store ID before deletion
    channel_name = channel.name
    channel_url = channel.url
    
    # Find channel media directory - first try stored path, then directory search
    media_path = None
    
    # Method 1: Try database-stored directory path
    if channel.directory_path and os.path.exists(channel.directory_path):
        media_path = channel.directory_path
        logger.info(f"Using stored directory path: {media_path}")
    else:
        # Method 2: Fallback directory search
        import glob
        all_dirs = glob.glob(os.path.join(settings.media_dir, '*/')) 
        for directory in all_dirs:
            if channel.channel_id in os.path.basename(directory.rstrip('/')):
                media_path = directory.rstrip('/')
                # Update the database with the found path for next time
                channel.directory_path = media_path
                logger.info(f"Found and saved media directory: {media_path}")
                break
    
    # Optionally delete media files BEFORE database (for better consistency)
    media_deleted = False
    files_deleted = 0
    if delete_media and media_path and os.path.exists(media_path):
        try:
            # Safety check - ensure we're only deleting within media directory
            media_path = os.path.abspath(media_path)
            media_root = os.path.abspath(settings.media_dir)
            # Use commonpath for safer validation
            if os.path.commonpath([media_path, media_root]) == media_root:
                import shutil
                # Count files before deletion
                for root, dirs, files in os.walk(media_path):
                    files_deleted += len(files)
                shutil.rmtree(media_path)
                media_deleted = True
                logger.info(f"Deleted {files_deleted} files from {media_path}")
        except Exception as e:
            logger.warning(f"Failed to delete media for channel {channel_id}: {e}")
    
    # Delete from database AFTER filesystem operations (cascade deletes Download records)
    db.delete(channel)
    db.commit()
    
    # Remove from YAML config
    try:
        remove_channel_from_yaml(channel_url)
    except Exception as e:
        logger.warning(f"Failed to remove channel from YAML: {e}")
    
    return {
        "message": f"Channel '{channel_name}' deleted successfully",
        "channel_id": channel_id,
        "channel_name": channel_name,
        "media_deleted": media_deleted,
        "files_deleted": files_deleted if media_deleted else 0
    }


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


# === DOWNLOAD ENDPOINTS (User Story 5) ===

@router.post("/channels/{channel_id}/download", response_model=DownloadTriggerResponse)
async def trigger_channel_download(channel_id: int, db: Session = Depends(get_db)):
    """
    Manually trigger download process for a specific channel.

    This endpoint initiates the download process for a channel's recent videos,
    implementing the core functionality of User Story 5. Downloads are processed
    sequentially to avoid overwhelming system resources.

    BE-007: Coordinate Manual Trigger with Scheduler Lock
    - If scheduler is running: Returns 202 Accepted and queues the request
    - If scheduler is idle: Returns 200 OK and executes immediately

    Args:
        channel_id: Database ID of the channel to download from
        db: Database session dependency

    Returns:
        DownloadTriggerResponse: Results of the download operation or queue status

    Raises:
        HTTPException 404: If channel not found
        HTTPException 400: If channel is disabled
        HTTPException 500: If download process fails unexpectedly

    Example (Immediate Execution - 200 OK):
        POST /api/v1/channels/123/download
        Response:
        {
            "success": true,
            "videos_downloaded": 3,
            "error_message": null,
            "download_history_id": 456,
            "status": "completed"
        }

    Example (Queued - 202 Accepted):
        POST /api/v1/channels/123/download
        Response:
        {
            "status": "queued",
            "message": "Scheduled job in progress. Manual download queued.",
            "position": 1,
            "success": null,
            "videos_downloaded": null
        }
    """
    from fastapi import Response
    from app.manual_trigger_queue import add_to_queue

    # Find the channel
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    if not channel.enabled:
        raise HTTPException(status_code=400, detail="Channel is disabled")

    logger.info(f"Manual download triggered for channel: {channel.name} (ID: {channel_id})")

    # === BE-007: CHECK SCHEDULER LOCK ===
    # Check if scheduled job is currently running
    scheduler_running_flag = db.query(ApplicationSettings).filter(
        ApplicationSettings.key == "scheduled_downloads_running"
    ).first()

    if scheduler_running_flag and scheduler_running_flag.value == "true":
        # Scheduler is running - queue this manual request
        logger.info(
            f"Scheduler is running, queueing manual download for channel {channel_id}"
        )

        try:
            position = add_to_queue(db, channel_id)

            # Return 202 Accepted with queue status
            return DownloadTriggerResponse(
                status="queued",
                message="Scheduled job in progress. Manual download queued.",
                position=position,
                success=None,
                videos_downloaded=None,
                error_message=None,
                download_history_id=None
            )

        except Exception as e:
            logger.error(f"Failed to queue manual download for channel {channel_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to queue download request: {str(e)}"
            )

    # === IMMEDIATE EXECUTION (Scheduler not running) ===
    try:
        # Process channel downloads using the video download service
        success, videos_downloaded, error_message = video_download_service.process_channel_downloads(channel, db)

        # Get the most recent download history record for this channel
        download_history = db.query(DownloadHistory).filter(
            DownloadHistory.channel_id == channel_id
        ).order_by(DownloadHistory.run_date.desc()).first()

        return DownloadTriggerResponse(
            success=success,
            videos_downloaded=videos_downloaded,
            error_message=error_message,
            download_history_id=download_history.id if download_history else None,
            status="completed"
        )

    except Exception as e:
        logger.error(f"Unexpected error during manual download for channel {channel_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Download process failed: {str(e)}"
        )


@router.get("/channels/{channel_id}/downloads", response_model=DownloadList)
async def get_channel_downloads(
    channel_id: int,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get download history for a specific channel.
    
    Returns a paginated list of video downloads for the specified channel,
    ordered by creation date (most recent first). Useful for monitoring
    download activity and troubleshooting issues.
    
    Args:
        channel_id: Database ID of the channel
        limit: Maximum number of downloads to return (default: 50)
        offset: Number of downloads to skip for pagination (default: 0)
        db: Database session dependency
    
    Returns:
        DownloadList: Paginated list of downloads
        
    Raises:
        HTTPException 404: If channel not found
        
    Example:
        GET /api/v1/channels/123/downloads?limit=10&offset=0
    """
    # Verify channel exists
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Query downloads for this channel with pagination
    downloads_query = db.query(Download).filter(
        Download.channel_id == channel_id
    ).order_by(Download.created_at.desc())
    
    total_downloads = downloads_query.count()
    downloads = downloads_query.offset(offset).limit(limit).all()
    
    return DownloadList(
        downloads=downloads,
        total=total_downloads
    )


@router.get("/downloads/{download_id}", response_model=DownloadSchema)
async def get_download_details(download_id: int, db: Session = Depends(get_db)):
    """
    Get details for a specific download.
    
    Returns complete information about an individual video download,
    including status, file information, and any error messages.
    
    Args:
        download_id: Database ID of the download
        db: Database session dependency
    
    Returns:
        Download: Complete download information
        
    Raises:
        HTTPException 404: If download not found
        
    Example:
        GET /api/v1/downloads/789
    """
    download = db.query(Download).filter(Download.id == download_id).first()
    if not download:
        raise HTTPException(status_code=404, detail="Download not found")
    
    return download


@router.get("/channels/{channel_id}/download-history", response_model=List[DownloadHistorySchema])
async def get_channel_download_history(
    channel_id: int,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """
    Get download run history for a channel.
    
    Returns a list of download runs (each representing one execution of the
    download process for this channel), showing summary statistics and timing.
    
    Args:
        channel_id: Database ID of the channel
        limit: Maximum number of history records to return (default: 20)
        db: Database session dependency
    
    Returns:
        List[DownloadHistory]: List of download run records
        
    Raises:
        HTTPException 404: If channel not found
        
    Example:
        GET /api/v1/channels/123/download-history?limit=10
    """
    # Verify channel exists
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Query download history for this channel
    history = db.query(DownloadHistory).filter(
        DownloadHistory.channel_id == channel_id
    ).order_by(DownloadHistory.run_date.desc()).limit(limit).all()

    return history


# Scheduler Management Endpoints (Story 007)

@router.get("/scheduler/status", response_model=SchedulerStatusResponse, tags=["Scheduler"])
async def get_scheduler_status(db: Session = Depends(get_db)):
    """
    Get current scheduler status and configuration.

    Returns comprehensive information about the scheduler state including:
    - Whether scheduler is running and enabled
    - Current cron schedule
    - Next and last run times
    - Active jobs count

    Returns:
        SchedulerStatusResponse: Current scheduler status

    Example:
        GET /api/v1/scheduler/status
    """
    from app.scheduler_service import scheduler_service

    # Get scheduler status from service
    scheduler_status = scheduler_service.get_schedule_status()

    # Get database settings
    cron_setting = db.query(ApplicationSettings).filter(
        ApplicationSettings.key == "cron_schedule"
    ).first()

    enabled_setting = db.query(ApplicationSettings).filter(
        ApplicationSettings.key == "scheduler_enabled"
    ).first()

    last_run_setting = db.query(ApplicationSettings).filter(
        ApplicationSettings.key == "scheduler_last_run"
    ).first()

    return {
        # Explicit None check to ensure boolean type (handles None from scheduler_status)
        "scheduler_running": scheduler_status.get("scheduler_running") or False,
        "scheduler_enabled": enabled_setting.value == "true" if enabled_setting else False,
        "cron_schedule": cron_setting.value if cron_setting else None,
        "next_run": scheduler_status.get("next_run_time"),
        "last_run": last_run_setting.value if last_run_setting else None,
        "download_job_active": scheduler_status.get("download_job_active", False),
        "total_jobs": scheduler_status.get("total_jobs", 0)
    }


@router.post("/scheduler/schedule", response_model=UpdateScheduleResponse, tags=["Scheduler"])
async def update_scheduler_schedule(
    request: UpdateScheduleRequest,
    db: Session = Depends(get_db)
):
    """
    Update the cron schedule for automatic downloads.

    Validates the cron expression and updates the scheduler if valid.
    Returns the next 5 scheduled run times for verification.

    Args:
        request: UpdateScheduleRequest with cron_expression
        db: Database session dependency

    Returns:
        UpdateScheduleResponse: Updated schedule details with next runs

    Raises:
        HTTPException 400: If cron expression is invalid

    Example:
        POST /api/v1/scheduler/schedule
        {"cron_expression": "0 */6 * * *"}
    """
    from app.cron_validation import validate_cron_expression, get_cron_schedule_info
    from app.scheduler_service import scheduler_service

    cron_expr = request.cron_expression

    # Validate cron expression
    is_valid, error_msg, trigger = validate_cron_expression(cron_expr)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # Update database setting
    cron_setting = db.query(ApplicationSettings).filter(
        ApplicationSettings.key == "cron_schedule"
    ).first()

    if cron_setting:
        cron_setting.value = cron_expr
        cron_setting.updated_at = datetime.utcnow()
    else:
        cron_setting = ApplicationSettings(
            key="cron_schedule",
            value=cron_expr,
            description="Cron expression for automatic downloads",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(cron_setting)

    db.commit()

    # Update scheduler job
    try:
        scheduler_service.update_download_schedule(cron_expr)
    except Exception as e:
        logger.error(f"Failed to update scheduler: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update scheduler: {str(e)}")

    # Get schedule info for response
    schedule_info = get_cron_schedule_info(cron_expr)

    return {
        "success": True,
        "schedule": cron_expr,
        "next_run": schedule_info.get("next_run"),
        "next_5_runs": schedule_info.get("next_5_runs", []),
        "human_readable": schedule_info.get("human_readable", "")
    }


@router.put("/scheduler/enable", tags=["Scheduler"])
async def toggle_scheduler(
    request: SchedulerEnableRequest,
    db: Session = Depends(get_db)
):
    """
    Enable or disable the scheduler.

    When disabled, scheduled downloads will not run, but the schedule
    configuration is preserved.

    Args:
        request: SchedulerEnableRequest with enabled boolean
        db: Database session dependency

    Returns:
        dict: Success status and new enabled state

    Example:
        PUT /api/v1/scheduler/enable
        {"enabled": false}
    """
    enabled_setting = db.query(ApplicationSettings).filter(
        ApplicationSettings.key == "scheduler_enabled"
    ).first()

    new_value = "true" if request.enabled else "false"

    if enabled_setting:
        enabled_setting.value = new_value
        enabled_setting.updated_at = datetime.utcnow()
    else:
        enabled_setting = ApplicationSettings(
            key="scheduler_enabled",
            value=new_value,
            description="Enable/disable automatic scheduled downloads",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(enabled_setting)

    db.commit()

    return {
        "success": True,
        "enabled": request.enabled,
        "message": f"Scheduler {'enabled' if request.enabled else 'disabled'} successfully"
    }


@router.get("/scheduler/validate", response_model=ValidateCronResponse, tags=["Scheduler"])
async def validate_cron_expression(expression: str):
    """
    Validate a cron expression without saving it.

    Useful for real-time validation in the UI before the user saves.
    Returns validation status and next run times if valid.

    Args:
        expression: Cron expression to validate (query parameter)

    Returns:
        ValidateCronResponse: Validation result with next runs

    Example:
        GET /api/v1/scheduler/validate?expression=0%20*%2F6%20*%20*%20*
    """
    from app.cron_validation import get_cron_schedule_info

    schedule_info = get_cron_schedule_info(expression)

    return {
        "valid": schedule_info.get("valid", False),
        "error": schedule_info.get("error"),
        "next_run": schedule_info.get("next_run"),
        "next_5_runs": schedule_info.get("next_5_runs", []),
        "time_until_next": schedule_info.get("time_until_next"),
        "human_readable": schedule_info.get("human_readable", "")
    }


# === NFO BACKFILL ENDPOINTS (Story 008) ===

@router.post("/nfo/backfill/start", tags=["NFO"])
async def start_nfo_backfill():
    """
    Start NFO backfill process for existing channels.

    This endpoint initiates the background job that retroactively generates
    NFO files for channels that were added before the NFO generation feature
    was implemented.

    The backfill process:
    1. Identifies channels with nfo_last_generated = NULL
    2. Processes each channel sequentially (one at a time)
    3. Generates tvshow.nfo, season.nfo, and episode.nfo files
    4. Updates nfo_last_generated timestamp when complete

    Returns:
        dict: 202 Accepted with job status

    Raises:
        HTTPException 409: If backfill is already running

    Example:
        POST /api/v1/nfo/backfill/start
        Response:
        {
            "status": "started",
            "total_channels": 5,
            "message": "NFO backfill job started"
        }
    """
    import asyncio
    from app.nfo_backfill_service import nfo_backfill_service

    try:
        # Check if already running
        if nfo_backfill_service.running:
            raise HTTPException(status_code=409, detail="Backfill job is already running")

        # Get count of channels needing backfill
        total_channels = nfo_backfill_service.get_channels_needing_backfill()

        # Start backfill in background (fire and forget)
        # Why asyncio.create_task? Allows API to return immediately while job runs
        # This follows the pattern from scheduled_download_job.py
        asyncio.create_task(nfo_backfill_service.start_backfill())

        return {
            "status": "started",
            "total_channels": total_channels,
            "message": "NFO backfill job started in background"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start NFO backfill: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start backfill: {str(e)}")


@router.post("/nfo/backfill/pause", tags=["NFO"])
async def pause_nfo_backfill():
    """
    Pause currently running NFO backfill job.

    The job will finish processing the current channel and then pause
    before starting the next channel. This ensures no partial processing.

    Returns:
        dict: Current status with pause confirmation

    Example:
        POST /api/v1/nfo/backfill/pause
        Response:
        {
            "status": "pausing",
            "message": "Backfill will pause after current channel completes",
            "current_channel": "Mrs Rachel",
            "channels_processed": 2,
            "total_channels": 5
        }
    """
    from app.nfo_backfill_service import nfo_backfill_service

    result = nfo_backfill_service.pause()
    return result


@router.post("/nfo/backfill/resume", tags=["NFO"])
async def resume_nfo_backfill():
    """
    Resume paused NFO backfill job.

    Continues processing from where it left off. The idempotent nature
    of backfill (based on NULL timestamps) means we can safely restart
    even if interrupted unexpectedly.

    Returns:
        dict: 202 Accepted with resume confirmation

    Example:
        POST /api/v1/nfo/backfill/resume
        Response:
        {
            "status": "resumed",
            "message": "NFO backfill job resumed"
        }
    """
    import asyncio
    from app.nfo_backfill_service import nfo_backfill_service

    try:
        # Check if not paused
        if not nfo_backfill_service.paused:
            return {
                "status": "not_paused",
                "message": "Backfill is not currently paused"
            }

        # Resume in background (fire and forget)
        asyncio.create_task(nfo_backfill_service.resume())

        return {
            "status": "resumed",
            "message": "NFO backfill job resumed"
        }

    except Exception as e:
        logger.error(f"Failed to resume NFO backfill: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to resume backfill: {str(e)}")


@router.get("/nfo/backfill/status", tags=["NFO"])
async def get_nfo_backfill_status():
    """
    Get current NFO backfill job status.

    Returns comprehensive status information including:
    - Whether job is running or paused
    - Current channel being processed
    - Progress (channels processed/total)
    - File counts (created/skipped/failed)

    Returns:
        dict: Current status with progress details

    Example:
        GET /api/v1/nfo/backfill/status
        Response:
        {
            "running": true,
            "paused": false,
            "current_channel_id": 3,
            "current_channel_name": "Mrs Rachel",
            "total_channels": 5,
            "channels_processed": 2,
            "channels_remaining": 3,
            "files_created": 127,
            "files_skipped": 5,
            "files_failed": 2,
            "started_at": "2025-11-08T22:30:00"
        }
    """
    from app.nfo_backfill_service import nfo_backfill_service

    status = nfo_backfill_service.get_status()
    return status


@router.get("/nfo/backfill/needed", tags=["NFO"])
async def get_nfo_backfill_needed(db: Session = Depends(get_db)):
    """
    Check how many channels need NFO backfill.

    Queries the database for channels with nfo_last_generated = NULL.
    Useful for UI to show backfill status before starting.

    Args:
        db: Database session dependency

    Returns:
        dict: Count of channels needing backfill

    Example:
        GET /api/v1/nfo/backfill/needed
        Response:
        {
            "channels_needing_backfill": 5,
            "message": "5 channels need NFO backfill"
        }
    """
    from app.nfo_backfill_service import nfo_backfill_service

    count = nfo_backfill_service.get_channels_needing_backfill()

    return {
        "channels_needing_backfill": count,
        "message": f"{count} channel{'s' if count != 1 else ''} need{'s' if count == 1 else ''} NFO backfill"
    }


@router.post("/channels/{channel_id}/nfo/regenerate", tags=["NFO"])
async def regenerate_channel_nfo(channel_id: int, db: Session = Depends(get_db)):
    """
    Regenerate all NFO files for a specific channel.

    This endpoint regenerates tvshow.nfo, season.nfo files, and episode.nfo
    files for all videos in the specified channel. Useful for:
    - Fixing corrupted NFO files
    - Updating metadata after manual changes
    - Re-generating NFO files after Jellyfin issues

    The regeneration process:
    1. Generates/overwrites tvshow.nfo (channel-level metadata)
    2. Generates/overwrites season.nfo for each year directory
    3. Generates/overwrites episode.nfo for each video
    4. Updates nfo_last_generated timestamp

    Args:
        channel_id: Database ID of channel to regenerate NFO files for
        db: Database session dependency

    Returns:
        dict: Regeneration results with file counts

    Raises:
        HTTPException 404: If channel not found
        HTTPException 400: If channel directory doesn't exist
        HTTPException 500: If regeneration fails

    Example:
        POST /api/v1/channels/123/nfo/regenerate
        Response:
        {
            "success": true,
            "channel_name": "Mrs Rachel",
            "files_created": 127,
            "files_skipped": 5,
            "files_failed": 0,
            "message": "Successfully regenerated NFO files for Mrs Rachel"
        }
    """
    import asyncio
    from app.nfo_backfill_service import nfo_backfill_service

    try:
        # Verify channel exists first
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

        logger.info(f"NFO regeneration requested for channel: {channel.name} (ID: {channel_id})")

        # Run regeneration (async operation)
        result = await nfo_backfill_service.regenerate_channel_nfo(channel_id)

        if not result["success"]:
            # Check if it's a "not found" error (shouldn't happen since we checked above)
            if "not found" in result.get("error", "").lower():
                raise HTTPException(status_code=404, detail=result["error"])
            # Check if it's a directory error
            elif "directory not found" in result.get("error", "").lower():
                raise HTTPException(status_code=400, detail=result["error"])
            # Other errors
            else:
                raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

        # Success response
        return {
            "success": True,
            "channel_name": result["channel_name"],
            "files_created": result["files_created"],
            "files_skipped": result["files_skipped"],
            "files_failed": result["files_failed"],
            "message": f"Successfully regenerated NFO files for {result['channel_name']}"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error regenerating NFO for channel {channel_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate NFO files: {str(e)}"
        )
