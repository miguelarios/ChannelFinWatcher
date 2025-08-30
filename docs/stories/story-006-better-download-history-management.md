# User Story: Better Download History Management

## Section 1: Story Definition

### Feature
Eliminate archive.txt dependency and provide channel-specific download history management with optional media deletion

### User Story
- **As a** user monitoring YouTube channels
- **I want** to completely remove a channel's download history when I delete it, with the option to also delete downloaded media files
- **So that** I can start fresh if I re-add the channel later and have confidence that removing a channel truly removes its history

### Context
Currently, the system uses a global archive.txt file shared by all channels, making it impossible to cleanly remove a channel's download history. Users cannot reset a channel without affecting others, and there's no visibility into what files are actually on disk versus what the system thinks it has downloaded.

### Functional Requirements

#### [ ] Scenario: Delete channel without deleting media files
- **Given** a channel exists with downloaded videos
  - And the channel has 10 videos downloaded
  - And the videos exist in /media/ChannelName [channel_id]/ folder
- **When** user deletes the channel and chooses NOT to delete media
  - And confirms the deletion
- **Then** the channel is removed from the database
  - And all download history records are deleted (cascade)
  - And the media files remain on disk
  - And if the channel is re-added, it can detect existing files and avoid re-downloading

#### [ ] Scenario: Delete channel with media deletion
- **Given** a channel exists with downloaded videos
  - And the channel has videos in /media/ChannelName [channel_id]/
- **When** user deletes the channel and chooses to delete media
  - And confirms the deletion
- **Then** the channel is removed from the database
  - And all download history records are deleted
  - And the entire /media/ChannelName [channel_id]/ folder is deleted
  - And if the channel is re-added, all videos will be downloaded fresh

#### [ ] Scenario: Download deduplication without archive.txt
- **Given** archive.txt has been eliminated from the system
  - And a channel is being processed for downloads
- **When** the system checks if a video should be downloaded
- **Then** it first checks the Download table for the video_id
  - And if found with status='completed' and file_exists=true, it skips
  - And if found with file_exists=false, it re-downloads
  - And if not in database, it checks disk for [video_id] in filename
  - And if found on disk, creates a Download record and skips download

#### [ ] Scenario: Reindex channel after manual file changes
- **Given** a user has manually deleted or renamed video files
  - And the database is out of sync with actual disk state
- **When** user triggers a reindex for the channel
- **Then** the system scans the channel's media folder
  - And updates Download records to match disk state
  - And marks missing files as file_exists=false
  - And creates records for orphaned files found on disk
  - And returns a summary of changes

#### [ ] Scenario: Handle missing media folder during deletion
- **Given** a channel's media folder has been manually deleted
- **When** user deletes the channel with media deletion option
- **Then** the database deletion proceeds normally
  - And the system handles the missing folder gracefully
  - And no error is shown to the user

### Non-functional Requirements
- **Performance:** Database lookups should be O(1) with proper indexing on video_id, channel_id, status, and compound (channel_id, status)
- **Security:** Path traversal protection when deleting folders - use os.path.commonpath validation, sanitize channel names
- **Reliability:** Proper operation ordering for best-effort consistency (FS operations before DB commits where safe)
- **Usability:** Clear feedback on what will be deleted before confirmation

### Dependencies
- **Blocked by:** None (can be implemented independently)
- **Blocks:** Future stories that depend on improved download tracking

### Engineering TODOs
- [ ] Add file_exists column to Download model with proper indexes
- [ ] Remove all archive.txt references from codebase
- [ ] Implement database-based deduplication logic with batch disk scanning
- [ ] Add media deletion option to channel delete endpoint with path safety
- [ ] Create reindex endpoint for channel media reconciliation with batch operations
- [ ] Handle edge cases (missing folders, .part files, concurrent downloads)

---

## Section 2: Engineering Tasks

### Task Breakdown

#### 1. [ ] Database Schema Update
- **Description:** Add file_exists column to track whether downloaded files are present on disk
- **Estimation:** 1 hour
- **Acceptance Criteria:** 
  - [ ] Migration adds file_exists Boolean column to downloads table
  - [ ] Column defaults to True for existing records
  - [ ] Column is NOT NULL with proper indexing
  - [ ] Add indexes on channel_id, status, and compound (channel_id, status) for query performance

#### 2. [ ] Remove Archive.txt Dependencies
- **Description:** Eliminate all references to archive.txt from the video download service
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [ ] Remove download_archive from yt-dlp configuration
  - [ ] Remove self.archive_file initialization
  - [ ] Update tests to not expect archive.txt
  - [ ] Delete existing archive.txt file (or rename to archive_legacy.txt)

#### 3. [ ] Implement Database Deduplication
- **Description:** Replace archive.txt checking with database and disk checks
- **Estimation:** 3 hours
- **Acceptance Criteria:** 
  - [ ] Check Download table for video_id before downloading
  - [ ] Implement batch disk scanning (single pass) for [video_id] pattern in filenames
  - [ ] Create Download records for files found on disk with proper file paths
  - [ ] Handle file_exists=false cases with re-download
  - [ ] Optimize for O(1) lookups with pre-scanned Set/Dict of video_ids

#### 4. [ ] Enhanced Channel Deletion API
- **Description:** Add optional media deletion to channel delete endpoint
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [ ] Add delete_media boolean parameter to DELETE endpoint
  - [ ] Use settings.media_dir instead of hardcoded paths
  - [ ] Implement path validation using os.path.commonpath
  - [ ] Create channel_dir_name() helper for safe path construction
  - [ ] Safely delete media folder when requested (FS operation before DB)
  - [ ] Handle missing folders gracefully
  - [ ] Return structured result with files_deleted count

#### 5. [ ] Channel Reindex Endpoint
- **Description:** Create endpoint to reconcile database with actual disk state
- **Estimation:** 3 hours
- **Acceptance Criteria:** 
  - [ ] POST /api/v1/channels/{id}/reindex endpoint created
  - [ ] Single-pass scan of channel media folder for video files
  - [ ] Prefetch all channel downloads into dict for O(1) lookups
  - [ ] Batch database operations for performance
  - [ ] Update Download records based on disk state with file paths
  - [ ] Return statistics (found, missing, added)
  - [ ] Ignore .part files during scan
  - [ ] Handle IntegrityError on concurrent inserts gracefully

#### 6. [ ] Update Frontend (Optional - Future Story)
- **Description:** Add UI controls for new deletion and reindex features
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [ ] Delete modal shows "Also delete media files" checkbox
  - [ ] Reindex button added to channel page
  - [ ] Display reindex results to user

#### 7. [ ] Testing
- **Description:** Comprehensive tests for new functionality
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [ ] Unit tests for deduplication logic
  - [ ] Integration tests for delete with/without media
  - [ ] Tests for reindex functionality
  - [ ] Edge case tests (missing folders, concurrent access)
  - [ ] Path safety tests (traversal attempts, forbidden paths)
  - [ ] Idempotency tests (repeated operations should be safe)
  - [ ] Performance tests for batch scanning

---

## Definition of Done

### Must Have
- [ ] Archive.txt completely removed from system
- [ ] Channel deletion removes all download history from database
- [ ] Optional media deletion works correctly
- [ ] No duplicate downloads after eliminating archive.txt
- [ ] Reindex correctly syncs database with disk

### Should Have  
- [ ] Comprehensive test coverage (>80%)
- [ ] Performance remains acceptable (no significant slowdown)
- [ ] Clear logging for debugging
- [ ] Frontend UI updated (can be separate story)

### Notes for Future
- Consider adding dry-run option for deletions to preview what will be removed
- Could add scheduled reindex to automatically detect out-of-sync files
- Might want to add "move to trash" instead of hard delete for safety
- Consider adding bulk operations (delete multiple channels at once)

---

## Reference Materials

### Current Download Model Schema
```python
# backend/app/models.py
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
    status = Column(String, default="pending", index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    # ADD: file_exists = Column(Boolean, default=True, nullable=False)
```

### Migration for Adding file_exists Column
```python
# backend/alembic/versions/xxx_add_file_exists_to_downloads.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add file_exists column
    op.add_column('downloads', 
        sa.Column('file_exists', sa.Boolean(), nullable=False, server_default='true')
    )
    
    # Add performance indexes (video_id already has unique index)
    op.create_index('idx_download_file_exists', 'downloads', ['file_exists'])
    op.create_index('idx_download_channel_status', 'downloads', ['channel_id', 'status'])

def downgrade():
    op.drop_index('idx_download_channel_status', 'downloads')
    op.drop_index('idx_download_file_exists', 'downloads')
    op.drop_column('downloads', 'file_exists')
```

### New Deduplication Logic (Replaces archive.txt)
```python
# backend/app/video_download_service.py
def should_download_video(self, video_id: str, channel: Channel, db: Session) -> Tuple[bool, Optional[Download]]:
    """
    Determine if a video should be downloaded based on database and disk state.
    
    Returns: (should_download, existing_download_record)
    """
    # Check database first
    download = db.query(Download).filter(
        Download.video_id == video_id,
        Download.channel_id == channel.id
    ).first()
    
    if download:
        if download.status == 'completed' and download.file_exists:
            return False, download  # Skip - already have it
        elif not download.file_exists:
            return True, download   # Re-download missing file
    
    # No DB record - check disk
    settings = get_settings()
    channel_dir = channel_dir_name(channel)  # Helper function for safe path construction
    media_path = os.path.join(settings.media_dir, channel_dir)
    if self.check_video_on_disk(video_id, media_path):
        # Create DB record for existing file
        download = Download(
            channel_id=channel.id,
            video_id=video_id,
            title="Found on disk",
            status='completed',
            file_exists=True
        )
        db.add(download)
        db.commit()
        return False, download  # Skip - found on disk
    
    return True, None  # Need to download

def check_video_on_disk(self, video_id: str, media_path: str) -> bool:
    """Check if video file exists on disk by looking for [video_id] in filename."""
    if not os.path.exists(media_path):
        return False
    
    for root, dirs, files in os.walk(media_path):
        for file in files:
            if f"[{video_id}]" in file and not file.endswith('.part'):
                return True
    return False
```

### Enhanced Delete Channel Endpoint
```python
# backend/app/api.py
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
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Store info for response before deletion
    settings = get_settings()
    channel_name = channel.name
    channel_dir = channel_dir_name(channel)  # Safe path construction helper
    media_path = os.path.join(settings.media_dir, channel_dir)
    
    # Optionally delete media files BEFORE database (for better consistency)
    media_deleted = False
    files_deleted = 0
    if delete_media and os.path.exists(media_path):
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
        except Exception as e:
            logger.warning(f"Failed to delete media for channel {channel_id}: {e}")
    
    # Delete from database AFTER filesystem operations (cascade deletes Download records)
    db.delete(channel)
    db.commit()
    
    # Remove from YAML config
    try:
        remove_channel_from_yaml(channel.url)
    except Exception as e:
        logger.warning(f"Failed to remove channel from YAML: {e}")
    
    return {
        "message": f"Channel '{channel_name}' deleted successfully",
        "media_deleted": media_deleted,
        "files_deleted": files_deleted if media_deleted else 0
    }
```

### Reindex Endpoint
```python
# backend/app/api.py
@router.post("/channels/{channel_id}/reindex")
async def reindex_channel(channel_id: int, db: Session = Depends(get_db)):
    """
    Reindex a channel's media folder to sync database with disk state.
    
    This will:
    - Find all video files on disk
    - Update/create Download records to match
    - Mark missing files as file_exists=False
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    settings = get_settings()
    channel_dir = channel_dir_name(channel)  # Safe path construction
    media_path = os.path.join(settings.media_dir, channel_dir)
    
    stats = {
        "channel": channel.name,
        "found": 0,
        "missing": 0,
        "added": 0,
        "errors": []
    }
    
    # Find all video files on disk
    video_ids_on_disk = set()
    if os.path.exists(media_path):
        for root, dirs, files in os.walk(media_path):
            for file in files:
                # Skip partial downloads
                if file.endswith('.part'):
                    continue
                
                # Extract video ID from filename [video_id]
                import re
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
                        download = Download(
                            channel_id=channel_id,
                            video_id=video_id,
                            title=file.split('[')[0].strip(),
                            status='completed',
                            file_exists=True,
                            file_path=os.path.join(root, file),
                            completed_at=datetime.utcnow()
                        )
                        db.add(download)
                        stats["added"] += 1
    
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
    
    return stats
```

### Remove Archive.txt from VideoDownloadService
```python
# backend/app/video_download_service.py
class VideoDownloadService:
    def __init__(self):
        settings = get_settings()
        
        # Base paths for media organization
        self.media_path = settings.media_dir
        self.temp_path = settings.temp_dir
        
        # REMOVE THESE LINES:
        # data_path = os.path.dirname(settings.database_url.replace("sqlite:///", "/app/"))
        # self.archive_file = os.path.join(data_path, "archive.txt")
        
        # Ensure required directories exist
        os.makedirs(self.media_path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)
        
        # yt-dlp configuration for video downloads
        self.download_opts = {
            'paths': {
                'temp': self.temp_path,
                'home': self.media_path
            },
            'outtmpl': '%(channel)s [%(channel_id)s]/%(upload_date>%Y)s/%(channel)s - %(upload_date)s - %(title)s [%(id)s]/%(channel)s - %(upload_date)s - %(title)s [%(id)s].%(ext)s',
            'format': 'bv*+ba/b',
            # REMOVE THIS LINE:
            # 'download_archive': self.archive_file,
            # ... rest of config
        }
```

### Test Cases
```python
# backend/tests/integration/test_download_history_management.py
def test_delete_channel_keeps_media():
    """Test that deleting channel without delete_media keeps files."""
    # Create channel and download
    # Delete channel with delete_media=False
    # Assert files still exist
    # Assert database records deleted

def test_delete_channel_removes_media():
    """Test that delete_media=True removes video files."""
    # Create channel and download
    # Delete channel with delete_media=True
    # Assert files deleted
    # Assert database records deleted

def test_reindex_finds_orphaned_files():
    """Test that reindex creates records for files on disk."""
    # Manually copy video file to channel folder
    # Run reindex
    # Assert Download record created

def test_reindex_marks_missing_files():
    """Test that reindex marks deleted files as missing."""
    # Create Download record
    # Delete actual file
    # Run reindex
    # Assert file_exists=False

def test_no_duplicate_downloads_without_archive():
    """Test deduplication works without archive.txt."""
    # Download video
    # Try to download same video again
    # Assert skipped (not downloaded twice)
```

### Important Notes
1. **No archive.txt migration** - We start fresh, existing archive.txt is ignored
2. **File pattern matching** - We rely on [video_id] in filenames for disk detection
3. **Cascade deletion** - Channel deletion automatically removes Download records via foreign key cascade
4. **Path safety** - Always validate paths using os.path.commonpath to prevent directory traversal attacks
5. **Concurrent downloads** - Use database unique constraint on video_id to prevent race conditions
6. **Settings usage** - Always use settings.media_dir instead of hardcoded paths
7. **Helper functions** - Create channel_dir_name() helper to safely construct channel directory names

### Helper Function for Safe Path Construction
```python
# backend/app/utils.py
import re
from app.models import Channel

def channel_dir_name(channel: Channel) -> str:
    """
    Generate safe directory name for channel.
    Sanitizes channel name to prevent path traversal.
    
    Returns: Safe directory name in format "ChannelName [channel_id]"
    """
    # Remove unsafe characters from channel name
    safe_name = re.sub(r'[^\w\s-]', '', channel.name)
    safe_name = re.sub(r'[-\s]+', ' ', safe_name).strip()
    
    # Ensure channel_id is present and valid
    if not channel.channel_id:
        raise ValueError(f"Channel {channel.id} has no channel_id")
    
    return f"{safe_name} [{channel.channel_id}]"
```