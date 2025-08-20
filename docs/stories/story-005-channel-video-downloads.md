# User Story: Channel Video Downloads

## Section 1: Story Definition

### Feature
Download recent videos from monitored channels sequentially with basic status tracking

### User Story
- **As a** user managing monitored YouTube channels
- **I want** to automatically download the most recent videos from each channel
- **So that** I have offline access to new content without manual intervention

### Context
Core download functionality that makes channel monitoring useful. This initial implementation focuses on reliable, sequential downloads with proper file organization, building on the metadata management from Story 4.

### Functional Requirements

#### [x] Scenario: Download Single Channel Videos - Happy Path
- **Given** a channel is configured and enabled
  - And the channel has metadata extracted (from Story 4)
  - And download limit is set (e.g., 10 videos)
- **When** download process is triggered for the channel
  - And system queries for recent videos using yt-dlp
- **Then** system downloads up to 10 most recent videos sequentially
  - And videos are organized in Jellyfin-compatible directory structure
  - And already downloaded videos are skipped using archive.txt
  - And download status is tracked in database
  - And last_check timestamp is updated

#### [x] Scenario: No New Videos Available
- **Given** a channel with all recent videos already downloaded
  - And the download archive contains existing video IDs
- **When** download process runs for the channel
- **Then** no downloads are initiated
  - And last_check timestamp is updated
  - And download history shows "0 new videos found"

#### [x] Scenario: Individual Video Download Failure
- **Given** channel has multiple videos to download
  - And one video fails (network issue, unavailable, private)
- **When** video download encounters error
- **Then** error is logged with specific details
  - And remaining videos continue downloading sequentially
  - And failed video is marked with error status in database
  - And overall channel download completes with partial success

### Non-functional Requirements
- **Performance:** Sequential video downloads complete efficiently using yt-dlp fragment downloads (-N 4)
- **Security:** Download operations handle age-restricted content using cookie file
- **Reliability:** Individual video failures don't stop processing remaining videos in channel
- **Usability:** Download status visible through database tracking and channel UI updates

### Dependencies
- **Blocked by:** Story 1 (channel management), Story 4 (channel metadata)
- **Blocks:** Story 10 (real-time progress UI), Story 7 (automatic cleanup)

### Engineering TODOs
- [x] Design VideoDownloadService following YouTubeService pattern for sequential downloads
- [x] Implement recent video detection using yt-dlp extract_info with archive.txt integration
- [x] Configure yt-dlp with exact parameters from reference bash script for Jellyfin structure
- [x] Design simple download tracking using existing Download/DownloadHistory models

---

## Section 2: Engineering Tasks

### Task Breakdown
*Each task should follow INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)*

#### 1. [x] VideoDownloadService - Backend Core Logic
- **Description:** Create service class for sequential video downloads with yt-dlp integration
- **Estimation:** 4-5 hours
- **Acceptance Criteria:** 
  - [x] VideoDownloadService class follows YouTubeService pattern
  - [x] Method to detect recent videos for a channel using yt-dlp extract_info
  - [x] Method to download individual videos sequentially with basic status tracking
  - [x] Integration with existing Download and DownloadHistory database models
  - [x] Exact yt-dlp parameters from bash script for Jellyfin organization
  - [x] archive.txt integration to prevent duplicate downloads

#### 2. [x] Download API Endpoints - REST Integration
- **Description:** Create API endpoints for triggering and monitoring downloads
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [x] POST /api/v1/channels/{id}/download endpoint for manual triggers
  - [x] GET /api/v1/channels/{id}/downloads endpoint for download history
  - [x] GET /api/v1/downloads/{id} endpoint for individual download status
  - [x] Proper HTTP status codes and error responses
  - [x] Request validation and authentication (if applicable)

#### 3. [x] Database Download Tracking - Data Management
- **Description:** Enhance existing Download model for basic status tracking
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [x] Use existing Download table for individual video download records
  - [x] Use existing DownloadHistory table for channel-level download runs
  - [x] Basic status fields: pending/downloading/completed/failed
  - [x] File paths stored for successful downloads
  - [x] Simple error message storage for failed downloads

#### 4. [x] yt-dlp Integration Configuration - External System
- **Description:** Configure yt-dlp with exact parameters from reference bash script
- **Estimation:** 3 hours
- **Acceptance Criteria:** 
  - [x] Use identical output template for Jellyfin directory structure from Story 4
  - [x] Configure video format selection (-f bv*+ba/b)
  - [x] Enable thumbnail and metadata embedding
  - [x] Set up subtitle downloading (en/es languages)
  - [x] Configure fragment downloads (-N 4) for individual videos
  - [x] Handle cookie file for age-restricted content

#### 5. [x] Download Testing Infrastructure - Quality Assurance
- **Description:** Create basic tests for download functionality using existing test patterns
- **Estimation:** 3 hours
- **Acceptance Criteria:** 
  - [x] Unit tests for VideoDownloadService methods following existing patterns
  - [x] Integration tests for basic download workflow
  - [x] Mock yt-dlp responses for consistent testing
  - [x] Test error scenarios (network failures, invalid videos)
  - [x] Test file organization matches Jellyfin structure
  - [x] Test archive.txt duplicate prevention

#### 6. [x] Error Handling and Logging - Operational Support
- **Description:** Implement basic error handling and logging following existing patterns
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [x] Basic logging for each download step using existing logger
  - [x] Simple error categorization (network, video unavailable, storage)
  - [x] Clean failure recovery without corrupted state
  - [x] Error messages stored in database for troubleshooting
  - [x] Failed videos don't stop remaining downloads

#### 7. [x] Download Status Display - Frontend Work
- **Description:** Create UI components to show basic download status and progress
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [x] Channel card shows download status (idle/downloading/completed/failed)
  - [x] Last download timestamp displayed on channel cards
  - [x] Download button for manual trigger on channel cards
  - [x] Basic error message display when downloads fail
  - [x] Download count and status in channel overview

#### 8. [x] Documentation Updates - Developer & User Guides
- **Description:** Document download functionality and configuration
- **Estimation:** 1-2 hours
- **Acceptance Criteria:** 
  - [x] API documentation for download endpoints added to existing docs
  - [x] User guide section explaining download behavior
  - [x] Basic troubleshooting guide for common download issues
  - [x] YAML configuration examples for download settings

---

## Definition of Done

### Must Have
- [x] Videos download successfully using yt-dlp with Jellyfin directory structure
- [x] Sequential downloads work reliably for individual channels
- [x] Downloads tracked in existing database models with basic status
- [x] Archive.txt prevents duplicate downloads
- [x] Individual video failures don't stop remaining downloads

### Should Have  
- [x] Basic UI shows download status on channel cards
- [x] Simple test coverage for core download functionality
- [x] Basic logging for troubleshooting download issues
- [x] Manual download trigger works through API

### Implementation Notes

**Key Fix Applied**: Implemented flat-playlist approach for video discovery to solve the original issue where video downloads weren't being triggered after metadata extraction. The system now uses lightweight queries (equivalent to `yt-dlp --flat-playlist`) to get video IDs quickly, then performs full downloads sequentially.

**Architecture**: Separates concerns between video discovery (fast, minimal requests) and video downloading (heavy, full metadata extraction) to avoid bot detection and improve reliability.

**Status**: ✅ **COMPLETED** - All scenarios working as designed, including automatic triggering after metadata extraction and proper handling of already-downloaded videos via archive.txt.

### Notes for Future
- Concurrent channel processing (multiple channels simultaneously)
- Real-time progress updates and WebSocket integration
- Advanced retry logic with exponential backoff
- Download queue management and priority system
- Performance optimization and bandwidth throttling

---

## Configuration Examples

### YAML Configuration for Download Settings

Basic channel configuration with download settings:

```yaml
# config/config.yaml
channels:
  - url: "https://www.youtube.com/@MrsRachel"
    name: "Ms Rachel - Toddler Learning Videos"  
    limit: 10                    # Number of recent videos to keep
    enabled: true                # Enable/disable downloads
    quality_preset: "best"       # Video quality: best, 1080p, 720p, 480p
    schedule_override: null      # Custom schedule (future enhancement)

  - url: "https://www.youtube.com/@InsideTheBusPod"
    name: "Inside The Bus"
    limit: 5
    enabled: true
    quality_preset: "1080p"

# Global application settings
settings:
  default_video_limit: 10        # Default limit for new channels
  download_quality: "best"       # Default quality setting
  max_concurrent_downloads: 1    # Sequential downloads for stability
```

### Environment Variables for Download Configuration

```bash
# docker-compose.dev.yml or .env
MEDIA_DIR=/app/media             # Where videos are stored
TEMP_DIR=/app/temp               # Temporary download location  
CONFIG_FILE=/app/config/config.yaml
COOKIES_FILE=/app/cookies.txt    # For age-restricted content
```

### Manual Download API Examples

```bash
# Trigger download for specific channel
curl -X POST http://localhost:8000/api/v1/channels/1/download

# Check download status  
curl http://localhost:8000/api/v1/channels/1/downloads

# View download history
curl http://localhost:8000/api/v1/channels/1/download-history
```

## Reference Materials

### yt-dlp Download Configuration (from TDD bash script)
```bash
yt-dlp \
    --paths "temp:${temp_path}" \
    --paths "home:${category_path}" \
    --output "%(channel)s [%(channel_id)s]/%(upload_date>%Y)s/%(channel)s - %(upload_date)s - %(title)s [%(id)s]/%(channel)s - %(upload_date)s - %(title)s [%(id)s].%(ext)s" \
    -f bv*+ba/b \
    --embed-thumbnail \
    --write-thumbnail \
    --write-subs \
    --write-auto-sub \
    --sub-langs "en,es",-live_chat \
    --embed-subs \
    --write-info-json \
    --parse-metadata "description:(?s)(?P<meta_comment>.+)" \
    --parse-metadata "upload_date:(?s)(?P<meta_DATE_RELEASED>.+)" \
    --parse-metadata "uploader:%(meta_ARTIST)s" \
    --embed-metadata \
    --add-metadata \
    --merge-output-format mkv \
    --download-archive "archive.txt" \
    --cookies ${cookie} \
    --concurrent-fragments 4
```

### Target Directory Structure (from Story 4)
```
/media/
    Channel Name [channel_id]/                                                 
        cover.ext                                                              
        backdrop.ext                                                           
        Channel Name [channel_id].info.json                                    
        [Year:YYYY]/                                                           
            Channel Name - YYYYMMDD - Title [video_id]/                        
                Channel Name - YYYYMMDD - Title [video_id].nfo                 
                Channel Name - YYYYMMDD - Title [video_id]-thumb.jpg           
                Channel Name - YYYYMMDD - Title [video_id].info.json           
                Channel Name - YYYYMMDD - Title [video_id].mkv                 
                Channel Name - YYYYMMDD - Title [video_id].[subtitles ext]     
```

### Recent Video Detection Algorithm (Simplified)
```python
def get_recent_videos(channel_url, limit=10):
    """
    Query channel for recent videos without downloading.
    Simple implementation for initial Story 5.
    """
    opts = {
        'quiet': True,
        'extract_flat': False,
        'playlistend': limit,
    }
    
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
        return info.get('entries', [])[:limit]
```

### Basic Download Status Tracking
```python
# Simple status tracking using existing database models
# Download.status: 'pending' -> 'downloading' -> 'completed'/'failed'
# DownloadHistory tracks overall channel download run

def update_download_status(download_id, status, error_message=None):
    """Update download record with current status."""
    # Implementation uses existing database patterns from other services
    pass
```

### Database Status Flow (Simplified)
```
Download Status Flow:
pending -> downloading -> completed (success)
pending -> downloading -> failed (with error_message)

DownloadHistory Status Flow:
running -> completed (with video count and duration)
running -> failed (with error summary)
```

### Basic Error Categories
```python
# Common errors to handle in initial implementation
- yt_dlp.DownloadError: Network/availability issues
- FileExistsError: Duplicate file handling
- PermissionError: File system access issues  
- OSError: Storage/disk space problems

# Error handling strategy: Log error, mark as failed, continue to next video
```

### yt-dlp Basic Configuration
```python
# Minimal configuration for reliable downloads
ydl_opts = {
    'outtmpl': 'Channel/Year/VideoFolder/VideoFile.%(ext)s',
    'format': 'bv*+ba/b',
    'writeinfojson': True,
    'writethumbnail': True,
    'embedthumbnail': True,
    'merge_output_format': 'mkv',
    'download_archive': 'archive.txt',
    'concurrent_fragments': 4  # Only concurrency in initial version
}
```