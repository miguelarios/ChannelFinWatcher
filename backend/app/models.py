"""SQLAlchemy database models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base


class Channel(Base):
    """
    YouTube channel configuration for monitoring and downloading.
    
    This model stores channel information and monitoring settings.
    Each channel represents a YouTube channel that will be periodically
    checked for new videos to download.
    
    Key Design Decisions:
    - channel_id is unique to prevent duplicate channels with different URLs
    - url is also unique for user clarity and consistency
    - limit controls how many recent videos to keep per channel
    - enabled allows temporary disabling without deletion
    """
    __tablename__ = "channels"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # YouTube identifiers (both unique to prevent duplicates)
    url = Column(String, unique=True, index=True, nullable=False)          # User-provided URL (normalized)
    channel_id = Column(String, unique=True, index=True)                   # YouTube's unique channel ID
    
    # Channel metadata (extracted from YouTube)
    name = Column(String, nullable=False)                                  # Channel display name
    
    # Monitoring configuration
    limit = Column(Integer, default=10)                                    # Max videos to keep
    enabled = Column(Boolean, default=True, index=True)                    # Enable/disable monitoring
    schedule_override = Column(String, nullable=True)                      # Custom cron schedule
    quality_preset = Column(String, default="best")                       # Video quality preference
    
    # Metadata management (Story 004)
    metadata_path = Column(String, nullable=True)                         # Path to channel metadata JSON
    directory_path = Column(String, nullable=True)                        # Path to channel directory
    last_metadata_update = Column(DateTime, nullable=True)                # Last metadata extraction
    metadata_status = Column(String, default="pending", index=True)       # pending, completed, failed, refreshing
    cover_image_path = Column(String, nullable=True)                      # Path to cover image
    backdrop_image_path = Column(String, nullable=True)                   # Path to backdrop image
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)                 # When channel was added
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Last modified
    last_check = Column(DateTime, nullable=True)                           # Last time videos were checked

    # Relationships
    downloads = relationship("Download", back_populates="channel", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index('idx_channel_enabled_lastcheck', 'enabled', 'last_check'),
        Index('idx_channel_metadata_status', 'metadata_status'),
    )


class Download(Base):
    """Video download record model."""
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    video_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    upload_date = Column(String, nullable=True)
    duration = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    status = Column(String, default="pending", index=True)  # pending, downloading, completed, failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    channel = relationship("Channel", back_populates="downloads")

    # Indexes
    __table_args__ = (
        Index('idx_download_channel_status', 'channel_id', 'status'),
        Index('idx_download_video_id', 'video_id'),
        Index('idx_download_upload_date', 'upload_date'),
    )


class DownloadHistory(Base):
    """Download history and statistics model."""
    __tablename__ = "download_history"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False, index=True)
    run_date = Column(DateTime, default=datetime.utcnow, index=True)
    videos_found = Column(Integer, default=0)
    videos_downloaded = Column(Integer, default=0)
    videos_skipped = Column(Integer, default=0)
    videos_failed = Column(Integer, default=0)
    duration_seconds = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    status = Column(String, default="running")  # running, completed, failed
    completed_at = Column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_history_channel_date', 'channel_id', 'run_date'),
    )


class ApplicationSettings(Base):
    """Application settings model."""
    __tablename__ = "application_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index('idx_settings_key', 'key'),
    )