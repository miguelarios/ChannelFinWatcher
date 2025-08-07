# User Story: Channel Metadata Management

## Section 1: Story Definition

### Feature
Download and store YouTube channel metadata with organized directory structure for media management

### User Story
- **As a** ChannelFinWatcher user
- **I want** the system to download channel metadata and create organized directories
- **So that** I have structured storage with channel information for media server integration

### Context
When channels are added, we need to collect comprehensive metadata about the channel and establish a proper directory structure in the media folder. This enables better organization, media server compatibility, and provides essential channel information for future features like thumbnails, descriptions, and channel artwork.

### Functional Requirements

#### [ ] Scenario: Download Channel Metadata - Happy Path
- **Given** a valid YouTube channel has been added to the system
  - And the channel metadata has not been downloaded yet
  - And the /media directory is accessible
- **When** the metadata download process is triggered
  - And the channel information is successfully retrieved from YouTube
- **Then** channel metadata is saved as JSON file
  - And a directory structure is created following the naming convention
  - And channel artwork/thumbnails are downloaded if available
  - But no video files are downloaded (future feature)

#### [ ] Scenario: Directory Structure Creation
- **Given** channel metadata has been successfully downloaded
  - And the channel name is "Mrs. Rachel - Toddler Learning Videos"
  - And the channel ID is "UC9_p50tH3WmMslWRWKnM7dQ"
- **When** the directory creation process runs
- **Then** a directory is created at `/media/channels/Mrs_Rachel_-_Toddler_Learning_Videos_[UC9_p50tH3WmMslWRWKnM7dQ]/`
  - And the directory name uses safe filesystem characters
  - And the channel ID is included for uniqueness
  - And subdirectories are created: `metadata/`, `thumbnails/`, `videos/`

#### [ ] Scenario: Metadata JSON Structure
- **Given** channel metadata has been retrieved from YouTube
- **When** the metadata is saved to JSON file
- **Then** the JSON includes: channel_id, name, description, subscriber_count, video_count, thumbnail_urls, upload_playlist_id, created_date
  - And the file is saved as `metadata/channel_info.json`
  - And the JSON structure is properly formatted and validated
  - And timestamp of metadata retrieval is included

#### [ ] Scenario: Handle Existing Directories
- **Given** a channel directory already exists
  - And channel metadata is being refreshed
- **When** the metadata download process runs
- **Then** existing metadata is backed up with timestamp
  - And new metadata overwrites the current file
  - And directory structure remains intact
  - But existing video files are not affected

#### [ ] Scenario: Error Handling - Invalid Channel
- **Given** a channel ID that no longer exists or is private
- **When** metadata download is attempted
- **Then** an error is logged with specific failure reason
  - And the database is updated with error status
  - And no directory or files are created
  - And the system continues processing other channels

### Non-functional Requirements
- **Performance:** Metadata download completes within 30 seconds per channel
- **Security:** API credentials are properly managed and not logged
- **Reliability:** Failed metadata downloads can be retried without data corruption
- **Usability:** Directory names are filesystem-safe and human-readable

### Dependencies
- **Blocked by:** Story 1 (Add Channel via Web UI) - need channels in system
- **Blocks:** Future video download stories - need organized structure first

### Engineering TODOs
- [ ] Determine optimal directory naming convention for media servers (Jellyfin compatibility)
- [ ] Research YouTube API rate limits for metadata retrieval
- [ ] Design metadata refresh strategy (daily? weekly? on-demand?)

---

## Section 2: Engineering Tasks

### Task Breakdown
*Each task should follow INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)*

#### 1. [ ] Backend API - Metadata Download Service
- **Description:** Create service to fetch YouTube channel metadata using yt-dlp
- **Estimation:** 4-6 hours
- **Acceptance Criteria:** 
  - [ ] Service can extract comprehensive channel information
  - [ ] Handles API rate limiting and errors gracefully
  - [ ] Returns structured metadata object
  - [ ] Logs all operations for debugging

#### 2. [ ] Backend Logic - Directory Management
- **Description:** Create directory structure management with safe naming conventions
- **Estimation:** 3-4 hours
- **Acceptance Criteria:** 
  - [ ] Generates filesystem-safe directory names from channel names
  - [ ] Creates consistent directory structure (metadata/, thumbnails/, videos/)
  - [ ] Handles special characters and international names properly
  - [ ] Ensures directory uniqueness using channel ID

#### 3. [ ] Database Schema - Metadata Storage
- **Description:** Extend channel model to track metadata status and file paths
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [ ] Add fields: metadata_path, directory_path, last_metadata_update, metadata_status
  - [ ] Create database migration for new fields
  - [ ] Update channel model and relationships

#### 4. [ ] Backend API - Metadata Management Endpoints
- **Description:** Create endpoints to trigger and monitor metadata download
- **Estimation:** 3-4 hours
- **Acceptance Criteria:** 
  - [ ] POST /api/v1/channels/{id}/metadata endpoint for manual trigger
  - [ ] GET /api/v1/channels/{id}/metadata endpoint for status check
  - [ ] Proper error responses and status codes
  - [ ] Background job integration for async processing

#### 5. [ ] File System Operations - JSON Storage
- **Description:** Implement JSON file creation and management with proper structure
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [ ] Creates well-structured channel_info.json files
  - [ ] Handles file backup and versioning
  - [ ] Validates JSON structure before writing
  - [ ] Manages file permissions properly

#### 6. [ ] Testing Work - Comprehensive Test Coverage
- **Description:** Unit and integration tests for metadata download functionality
- **Estimation:** 4-5 hours
- **Acceptance Criteria:** 
  - [ ] Unit tests for directory naming functions
  - [ ] Integration tests for metadata download flow
  - [ ] Error handling tests for various failure scenarios
  - [ ] File system operation tests

#### 7. [ ] Frontend Integration - UI Indicators
- **Description:** Add UI elements to show metadata status and trigger manual updates
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [ ] Channel cards show metadata status (downloaded/pending/error)
  - [ ] Manual "Update Metadata" button for each channel
  - [ ] Progress indicators during metadata download
  - [ ] Error messages displayed to user

---

## Definition of Done

### Must Have
- [ ] Channel metadata is successfully downloaded and stored
- [ ] Directory structure is created with proper naming convention
- [ ] JSON files contain comprehensive channel information
- [ ] Error handling works for failed downloads

### Should Have  
- [ ] Unit and integration tests cover core functionality
- [ ] UI shows metadata status and allows manual triggers
- [ ] Logging provides sufficient debugging information

### Notes for Future
- Consider implementing metadata refresh scheduling (daily/weekly)
- Thumbnail download and management could be expanded
- Directory structure might need adjustment for different media servers

---

## Reference Materials

### Directory Naming Convention
```bash
# Target directory structure:
/media/channels/
├── Channel_Name_Safe_[CHANNEL_ID]/
│   ├── metadata/
│   │   ├── channel_info.json
│   │   └── channel_info.backup.YYYY-MM-DD.json
│   ├── thumbnails/
│   │   ├── channel_avatar.jpg
│   │   └── channel_banner.jpg
│   └── videos/
│       └── (future video files)

# Example for "Mrs. Rachel - Toddler Learning Videos":
/media/channels/Mrs_Rachel_-_Toddler_Learning_Videos_[UC9_p50tH3WmMslWRWKnM7dQ]/
```

### Channel Metadata JSON Structure
```json
{
  "channel_id": "UC9_p50tH3WmMslWRWKnM7dQ",
  "name": "Mrs. Rachel - Toddler Learning Videos",
  "display_name": "Mrs. Rachel - Toddler Learning Videos",
  "description": "Channel description...",
  "subscriber_count": 1500000,
  "video_count": 245,
  "view_count": 850000000,
  "created_date": "2019-04-15T00:00:00Z",
  "upload_playlist_id": "UU9_p50tH3WmMslWRWKnM7dQ",
  "thumbnails": {
    "avatar": "https://yt3.googleusercontent.com/...",
    "banner": "https://yt3.googleusercontent.com/..."
  },
  "metadata_retrieved_at": "2024-08-07T15:30:00Z",
  "metadata_version": "1.0"
}
```

### yt-dlp Command for Metadata Extraction
```bash
# Extract channel info without downloading videos
yt-dlp --dump-json --playlist-end 0 "https://www.youtube.com/@MrsRachel"

# Extract just channel metadata
yt-dlp --dump-json --no-download --skip-download "https://www.youtube.com/@MrsRachel/videos"
```

### Filesystem Safe Name Generation (Python)
```python
import re
import unicodedata

def make_filesystem_safe(name, max_length=100):
    """Convert channel name to filesystem-safe directory name."""
    # Normalize unicode characters
    name = unicodedata.normalize('NFKD', name)
    
    # Replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = re.sub(r'\s+', '_', name)  # Replace spaces with underscores
    name = re.sub(r'_{2,}', '_', name)  # Collapse multiple underscores
    name = name.strip('._')  # Remove leading/trailing dots and underscores
    
    # Truncate if too long, but preserve channel ID space
    if len(name) > max_length:
        name = name[:max_length]
    
    return name

# Example usage:
# "Mrs. Rachel - Toddler Learning Videos" -> "Mrs_Rachel_-_Toddler_Learning_Videos"
```

### Database Migration Example
```sql
-- Add metadata management fields to channels table
ALTER TABLE channels ADD COLUMN metadata_path VARCHAR(500);
ALTER TABLE channels ADD COLUMN directory_path VARCHAR(500);
ALTER TABLE channels ADD COLUMN last_metadata_update TIMESTAMP;
ALTER TABLE channels ADD COLUMN metadata_status VARCHAR(20) DEFAULT 'pending';

-- Index for efficient metadata status queries
CREATE INDEX idx_channels_metadata_status ON channels(metadata_status);
```

### Error Handling Scenarios
Common error cases to handle:
- Channel deleted/private: Update database status, don't create directories
- Network timeout: Retry with exponential backoff
- Filesystem permission issues: Log error, alert admin
- Invalid JSON from yt-dlp: Use fallback metadata structure
- Disk space full: Graceful failure with clear error message