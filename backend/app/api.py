"""API endpoints for the application."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Channel, Download, DownloadHistory, ApplicationSettings
from app.schemas import (
    Channel as ChannelSchema,
    ChannelCreate,
    ChannelUpdate,
    ChannelList,
    SystemHealth,
)

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
    """Create a new channel for monitoring."""
    # Check if channel URL already exists
    existing = db.query(Channel).filter(Channel.url == str(channel.url)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Channel URL already exists")
    
    # Create new channel
    db_channel = Channel(
        url=str(channel.url),
        name=channel.name,
        limit=channel.limit,
        enabled=channel.enabled,
        schedule_override=channel.schedule_override,
        quality_preset=channel.quality_preset,
    )
    
    db.add(db_channel)
    db.commit()
    db.refresh(db_channel)
    
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