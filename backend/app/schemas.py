"""Pydantic schemas for API request/response validation."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, HttpUrl, Field


# Base schemas for common patterns
class TimestampMixin(BaseModel):
    """Mixin for models with timestamps."""
    created_at: datetime
    updated_at: datetime


# Channel schemas
class ChannelBase(BaseModel):
    """Base channel schema with common fields."""
    url: HttpUrl = Field(..., description="YouTube channel URL")
    name: str = Field(..., min_length=1, max_length=255, description="Channel display name")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum videos to keep")
    enabled: bool = Field(default=True, description="Whether channel monitoring is enabled")
    schedule_override: Optional[str] = Field(None, description="Custom cron schedule for this channel")
    quality_preset: str = Field(default="best", description="Video quality preset")


class ChannelCreate(BaseModel):
    """Schema for creating a new channel."""
    url: HttpUrl = Field(..., description="YouTube channel URL")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum videos to keep")
    enabled: bool = Field(default=True, description="Whether channel monitoring is enabled")
    schedule_override: Optional[str] = Field(None, description="Custom cron schedule for this channel")
    quality_preset: str = Field(default="best", description="Video quality preset")


class ChannelUpdate(BaseModel):
    """Schema for updating a channel (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    limit: Optional[int] = Field(None, ge=1, le=100)
    enabled: Optional[bool] = None
    schedule_override: Optional[str] = None
    quality_preset: Optional[str] = None


class Channel(ChannelBase, TimestampMixin):
    """Complete channel schema for API responses."""
    id: int
    channel_id: Optional[str] = Field(None, description="YouTube's internal channel ID")
    last_check: Optional[datetime] = Field(None, description="Last time channel was checked")

    class Config:
        from_attributes = True  # Allows creation from SQLAlchemy models


# Download schemas
class DownloadBase(BaseModel):
    """Base download schema."""
    video_id: str = Field(..., description="YouTube video ID")
    title: str = Field(..., min_length=1, description="Video title")
    upload_date: str = Field(..., description="Video upload date (YYYYMMDD format)")
    duration: Optional[str] = Field(None, description="Video duration")


class DownloadCreate(DownloadBase):
    """Schema for creating a download record."""
    channel_id: int = Field(..., description="Associated channel ID")


class Download(DownloadBase, TimestampMixin):
    """Complete download schema for API responses."""
    id: int
    channel_id: int
    file_path: Optional[str] = Field(None, description="Path to downloaded file")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    status: str = Field(..., description="Download status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    completed_at: Optional[datetime] = Field(None, description="When download completed")

    class Config:
        from_attributes = True


# Download History schemas
class DownloadHistoryBase(BaseModel):
    """Base download history schema."""
    channel_id: int = Field(..., description="Associated channel ID")
    videos_found: int = Field(default=0, ge=0, description="Videos found in channel")
    videos_downloaded: int = Field(default=0, ge=0, description="Videos successfully downloaded")
    videos_skipped: int = Field(default=0, ge=0, description="Videos skipped (already exist)")
    videos_failed: int = Field(default=0, ge=0, description="Videos that failed to download")


class DownloadHistoryCreate(DownloadHistoryBase):
    """Schema for creating download history record."""
    pass


class DownloadHistory(DownloadHistoryBase):
    """Complete download history schema for API responses."""
    id: int
    run_date: datetime = Field(..., description="When this download run occurred")
    duration_seconds: Optional[int] = Field(None, description="How long the run took")
    error_message: Optional[str] = Field(None, description="Run-level error message")
    status: str = Field(..., description="Overall run status")

    class Config:
        from_attributes = True


# Application Settings schemas
class ApplicationSettingBase(BaseModel):
    """Base application setting schema."""
    key: str = Field(..., min_length=1, description="Setting key")
    value: Optional[str] = Field(None, description="Setting value")
    description: Optional[str] = Field(None, description="Setting description")


class ApplicationSettingCreate(ApplicationSettingBase):
    """Schema for creating application setting."""
    pass


class ApplicationSettingUpdate(BaseModel):
    """Schema for updating application setting."""
    value: Optional[str] = None
    description: Optional[str] = None


class ApplicationSetting(ApplicationSettingBase, TimestampMixin):
    """Complete application setting schema for API responses."""
    id: int

    class Config:
        from_attributes = True


# Response schemas for collections
class ChannelList(BaseModel):
    """Schema for channel list responses."""
    channels: List[Channel]
    total: int = Field(..., description="Total number of channels")
    enabled: int = Field(..., description="Number of enabled channels")


class DownloadList(BaseModel):
    """Schema for download list responses."""
    downloads: List[Download]
    total: int = Field(..., description="Total number of downloads")


# Health check and system schemas
class DirectoryInfo(BaseModel):
    """Directory status information."""
    path: str
    exists: bool
    is_dir: bool
    writable: bool


class SystemHealth(BaseModel):
    """System health check response."""
    status: str
    service: str
    version: str
    database: str
    directories: dict[str, DirectoryInfo]


# Error response schemas
class ErrorDetail(BaseModel):
    """Error detail schema."""
    message: str
    code: Optional[str] = None
    field: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response schema."""
    error: str
    details: Optional[List[ErrorDetail]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)