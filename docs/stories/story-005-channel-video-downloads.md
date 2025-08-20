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

#### [ ] Scenario: Download Single Channel Videos - Happy Path
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

#### [ ] Scenario: No New Videos Available
- **Given** a channel with all recent videos already downloaded
  - And the download archive contains existing video IDs
- **When** download process runs for the channel
- **Then** no downloads are initiated
  - And last_check timestamp is updated
  - And download history shows "0 new videos found"

#### [ ] Scenario: Individual Video Download Failure
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
- [ ] Design VideoDownloadService following YouTubeService pattern for sequential downloads
- [ ] Implement recent video detection using yt-dlp extract_info with archive.txt integration
- [ ] Configure yt-dlp with exact parameters from reference bash script for Jellyfin structure
- [ ] Design simple download tracking using existing Download/DownloadHistory models

---

## Section 2: Engineering Tasks

### Task Breakdown
*Each task should follow INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)*

#### 1. [ ] VideoDownloadService - Backend Core Logic
- **Description:** Create service class for sequential video downloads with yt-dlp integration
- **Estimation:** 4-5 hours
- **Acceptance Criteria:** 
  - [ ] VideoDownloadService class follows YouTubeService pattern
  - [ ] Method to detect recent videos for a channel using yt-dlp extract_info
  - [ ] Method to download individual videos sequentially with basic status tracking
  - [ ] Integration with existing Download and DownloadHistory database models
  - [ ] Exact yt-dlp parameters from bash script for Jellyfin organization
  - [ ] archive.txt integration to prevent duplicate downloads

#### 2. [ ] Download API Endpoints - REST Integration
- **Description:** Create API endpoints for triggering and monitoring downloads
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [ ] POST /api/v1/channels/{id}/download endpoint for manual triggers
  - [ ] GET /api/v1/channels/{id}/downloads endpoint for download history
  - [ ] GET /api/v1/downloads/{id} endpoint for individual download status
  - [ ] Proper HTTP status codes and error responses
  - [ ] Request validation and authentication (if applicable)

#### 3. [ ] Database Download Tracking - Data Management
- **Description:** Enhance existing Download model for basic status tracking
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [ ] Use existing Download table for individual video download records
  - [ ] Use existing DownloadHistory table for channel-level download runs
  - [ ] Basic status fields: pending/downloading/completed/failed
  - [ ] File paths stored for successful downloads
  - [ ] Simple error message storage for failed downloads

#### 4. [ ] yt-dlp Integration Configuration - External System
- **Description:** Configure yt-dlp with exact parameters from reference bash script
- **Estimation:** 3 hours
- **Acceptance Criteria:** 
  - [ ] Use identical output template for Jellyfin directory structure from Story 4
  - [ ] Configure video format selection (-f bv*+ba/b)
  - [ ] Enable thumbnail and metadata embedding
  - [ ] Set up subtitle downloading (en/es languages)
  - [ ] Configure fragment downloads (-N 4) for individual videos
  - [ ] Handle cookie file for age-restricted content

#### 5. [ ] Download Testing Infrastructure - Quality Assurance
- **Description:** Create basic tests for download functionality using existing test patterns
- **Estimation:** 3 hours
- **Acceptance Criteria:** 
  - [ ] Unit tests for VideoDownloadService methods following existing patterns
  - [ ] Integration tests for basic download workflow
  - [ ] Mock yt-dlp responses for consistent testing
  - [ ] Test error scenarios (network failures, invalid videos)
  - [ ] Test file organization matches Jellyfin structure
  - [ ] Test archive.txt duplicate prevention

#### 6. [ ] Error Handling and Logging - Operational Support
- **Description:** Implement basic error handling and logging following existing patterns
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [ ] Basic logging for each download step using existing logger
  - [ ] Simple error categorization (network, video unavailable, storage)
  - [ ] Clean failure recovery without corrupted state
  - [ ] Error messages stored in database for troubleshooting
  - [ ] Failed videos don't stop remaining downloads

#### 7. [ ] Download Status Display - Frontend Work
- **Description:** Create UI components to show basic download status and progress
- **Estimation:** 2-3 hours
- **Acceptance Criteria:** 
  - [ ] Channel card shows download status (idle/downloading/completed/failed)
  - [ ] Last download timestamp displayed on channel cards
  - [ ] Download button for manual trigger on channel cards
  - [ ] Basic error message display when downloads fail
  - [ ] Download count and status in channel overview

#### 8. [ ] Documentation Updates - Developer & User Guides
- **Description:** Document download functionality and configuration
- **Estimation:** 1-2 hours
- **Acceptance Criteria:** 
  - [ ] API documentation for download endpoints added to existing docs
  - [ ] User guide section explaining download behavior
  - [ ] Basic troubleshooting guide for common download issues
  - [ ] YAML configuration examples for download settings

---

## Definition of Done

### Must Have
- [ ] Videos download successfully using yt-dlp with Jellyfin directory structure
- [ ] Sequential downloads work reliably for individual channels
- [ ] Downloads tracked in existing database models with basic status
- [ ] Archive.txt prevents duplicate downloads
- [ ] Individual video failures don't stop remaining downloads

### Should Have  
- [ ] Basic UI shows download status on channel cards
- [ ] Simple test coverage for core download functionality
- [ ] Basic logging for troubleshooting download issues
- [ ] Manual download trigger works through API

### Notes for Future
- Concurrent channel processing (multiple channels simultaneously)
- Real-time progress updates and WebSocket integration
- Advanced retry logic with exponential backoff
- Download queue management and priority system
- Performance optimization and bandwidth throttling

---

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