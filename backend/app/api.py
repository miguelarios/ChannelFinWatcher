"""API endpoints for the application."""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, Download, DownloadHistory, ApplicationSettings
from app.youtube_service import youtube_service
from app.schemas import (
    Channel as ChannelSchema,
    ChannelCreate,
    ChannelUpdate,
    ChannelList,
    SystemHealth,
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
    
    # Create new channel record with extracted YouTube metadata
    db_channel = Channel(
        url=normalized_url,                              # Normalized URL for consistency
        channel_id=channel_info['channel_id'],           # YouTube's unique channel identifier
        name=channel_info['name'],                       # Channel name extracted from YouTube
        limit=channel.limit,                             # User-specified video limit
        enabled=channel.enabled,                         # Monitoring enabled/disabled
        schedule_override=channel.schedule_override,     # Custom schedule (if any)
        quality_preset=channel.quality_preset,          # Video quality preference
    )
    
    # Persist to database
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)  # Refresh to get auto-generated fields (id, timestamps)
    
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
    """Update a channel's settings."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Update only provided fields
    update_data = channel_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(channel, field, value)
    
    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, db: Session = Depends(get_db)):
    """Delete a channel and all its downloads."""
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    db.delete(channel)
    db.commit()
    return {"message": "Channel deleted successfully"}