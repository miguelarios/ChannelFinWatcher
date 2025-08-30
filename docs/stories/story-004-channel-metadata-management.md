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

#### [x] Scenario: Download Channel Metadata - Happy Path
- **Given** a valid YouTube channel URL has been submitted
  - And the channel metadata has not been downloaded yet
  - And the /media directory is accessible
  - And the channel directory doesn't yet exist
  - And yt-dlp Python library is available
- **When** the button is clicked for `Add Channel for Monitoring` in the UI
- **Then** the metadata download process is triggered using yt-dlp Python extract_info() method
  - And the channel_id is extracted from the metadata response
  - And the channel_id is checked against existing channels in database to prevent duplicates
  - And if duplicate channel_id found, the operation is rejected with clear error message "Channel already being monitored"
  - And if unique, the process continues with directory creation and metadata storage

#### [x] Scenario: Directory Structure Creation
- **Given** channel metadata has been successfully downloaded
  - And the channel name is "Mrs. Rachel - Toddler Learning Videos"
  - And the channel ID is "UCG2CL6EUjG8TVT1Tpl9nJdg"
  - And the channel ID has been verified as unique in the system
- **When** the directory creation process runs
- **Then** a directory is created at `/media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]/`
  - And the channel ID is included for uniqueness

#### [x] Scenario: Metadata JSON Structure
- **Given** channel metadata has been extracted using yt-dlp extract_info()
- **When** the metadata is processed and saved to JSON file
- **Then** the complete channel metadata is saved including: channel_id, title, description, channel_follower_count, thumbnails array, and all other channel fields
  - And the `entries` key is removed to reduce file size from 24MB to ~5KB
  - And the file is saved as `Channel Name [channel_id].info.json`
  - And thumbnails array contains `avatar_uncropped` and `banner_uncropped` URLs directly accessible
  - And timestamp of metadata retrieval is included via epoch field

#### [x] Scenario: Cover image is downloaded
- **Given** channel metadata has been extracted using yt-dlp extract_info()
  - And the channel name is "Mrs. Rachel - Toddler Learning Videos"
  - And the channel ID is "UCG2CL6EUjG8TVT1Tpl9nJdg"
  - And the thumbnails array is available in the extracted metadata
- **When** the cover image download process runs
- **Then** the cover image URL is found directly in thumbnails array where id = `avatar_uncropped`
  - And the image is downloaded from that URL
  - And the file is named `cover.ext` in the location `/media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]/`

#### [x] Scenario: Backdrop image is downloaded
- **Given** channel metadata has been extracted using yt-dlp extract_info()
  - And the channel name is "Mrs. Rachel - Toddler Learning Videos"
  - And the channel ID is "UCG2CL6EUjG8TVT1Tpl9nJdg"
  - And the thumbnails array is available in the extracted metadata
- **When** the backdrop image download process runs
- **Then** the backdrop image URL is found directly in thumbnails array where id = `banner_uncropped`
  - And the image is downloaded from that URL
  - And the file is named `backdrop.ext` in the location `/media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]/`

#### [x] Scenario: Handle Existing Directories
- **Given** a channel directory already exists
  - And channel metadata is being refreshed
  - And channel is being monitored
- **When** the metadata download process runs
- **Then** channel metadata is extracted using yt-dlp Python extract_info() method
  - And channel metadata JSON file is updated with new information
  - And metadata saved in database is refreshed with latest data
  - And directory structure remains intact
  - And cover and backdrop images are redownloaded and overwrite existing file if any

#### [x] Scenario: Error Handling - Invalid Channel
- **Given** a channel ID that no longer exists or is private
- **When** metadata download is attempted
- **Then** an error is logged with specific failure reason
  - And the database is updated with error status
  - And no directory or files are created
  - And the system continues processing other channels

### Non-functional Requirements
- **Performance:** Metadata download completes within 30 seconds per channel
- **Security:** Image downloads validate URLs, file types, and enforce size limits to prevent malicious content
- **Reliability:** Failed metadata downloads can be retried without data corruption
- **Storage:** JSON files optimized to ~5KB by removing entries key to minimize disk usage

### Dependencies
- **Blocked by:** Story 1 (Add Channel via Web UI) - need channels in system
- **Blocks:** Future video download stories - need organized structure first

### Engineering TODOs
- [x] Determine optimal directory naming convention for media servers (Jellyfin compatibility)
- [x] Define metadata refresh strategy (manual vs automatic scheduling)
- [x] Establish storage cleanup policies for old metadata and images
- [x] Design error recovery patterns for partial metadata failures

---

## Section 2: Engineering Tasks

### Task Breakdown
*Each task should follow INVEST principles (Independent, Negotiable, Valuable, Estimable, Small, Testable)*

#### 1. [x] Backend Work - Metadata Extraction Optimization
- **Description:** Extend YouTubeService to implement single extract_info() call with entries removal optimization
- **Estimation:** 2-3 days
- **Acceptance Criteria:** 
  - [x] Modify extract_channel_info() to remove entries key for 24MB→5KB optimization
  - [x] Preserve all essential channel metadata (channel_id, title, description, thumbnails)
  - [x] Add JSON file saving functionality with proper encoding
  - [x] Include epoch timestamp for metadata retrieval tracking

#### 2. [x] Backend Work - Thumbnail and Image Processing
- **Description:** Create services for thumbnail extraction and secure image downloading
- **Estimation:** 3-4 days
- **Acceptance Criteria:** 
  - [x] Parse thumbnails array to extract avatar_uncropped and banner_uncropped URLs
  - [x] Implement secure image download with URL validation and file type checking
  - [x] Create cover.ext and backdrop.ext files with proper extension detection
  - [x] Handle download failures without breaking metadata save process

#### 3. [x] Backend Work - Error Recovery Patterns
- **Description:** Implement comprehensive error handling and rollback mechanisms
- **Estimation:** 2-3 days
- **Acceptance Criteria:** 
  - [x] Rollback directory creation if metadata extraction fails completely
  - [x] Handle partial failures (metadata succeeds, images fail) gracefully
  - [x] Implement retry logic for failed image downloads
  - [x] Ensure no orphaned files or directories remain after failures

#### 4. [x] Database Work - Schema and Duplicate Detection
- **Description:** Add metadata tracking fields and implement duplicate channel checking
- **Estimation:** 2 days
- **Acceptance Criteria:** 
  - [x] Add columns: metadata_path, directory_path, last_metadata_update, metadata_status
  - [x] Create migration with proper indexes for efficient status queries
  - [x] Implement channel_id duplicate checking with clear error messages
  - [x] Support metadata status tracking (pending, completed, failed, refreshing)

#### 5. [x] Integration Work - File System Operations
- **Description:** Create secure directory management with filesystem-safe naming
- **Estimation:** 2 days
- **Acceptance Criteria:** 
  - [x] Implement filesystem-safe naming function (preserve spaces, remove problematic chars)
  - [x] Create directory structure: `/media/[Channel Name] [channel_id]/`
  - [x] Validate paths to prevent directory traversal attacks
  - [x] Handle filesystem permission errors with clear logging

#### 6. [x] Frontend Work - Metadata Status Integration
- **Description:** Add minimal UI elements to show metadata download status and errors
- **Estimation:** 1-2 days
- **Acceptance Criteria:** 
  - [x] Display metadata download status in channel management interface
  - [x] Show error messages for failed metadata downloads with retry options
  - [x] Add progress indicators during metadata extraction process
  - [x] Display channel cover/backdrop images once downloaded

#### 7. [x] Testing Work - Metadata Workflow Coverage
- **Description:** Comprehensive testing of metadata extraction, optimization, and error scenarios
- **Estimation:** 3 days
- **Acceptance Criteria:** 
  - [x] Unit tests for entries removal and JSON size optimization verification
  - [x] Unit tests for thumbnail URL extraction from yt-dlp response structure
  - [x] Integration tests for complete metadata download workflow
  - [x] Error scenario testing (invalid channels, network failures, filesystem errors)
  - [x] Performance testing to verify 30-second completion requirement

#### 8. [x] Documentation Work - Technical Specifications
- **Description:** Document new metadata structure, processes, and troubleshooting
- **Estimation:** 1-2 days
- **Acceptance Criteria:** 
  - [x] Document optimized JSON structure (entries removed) with size comparisons
  - [x] Update API documentation for any endpoint changes
  - [x] Create troubleshooting guide for metadata download failures
  - [x] Document filesystem-safe naming conventions and directory structure

---

## Definition of Done

### Must Have
- [x] All happy path scenarios work
- [x] Error cases handled gracefully
- [x] Code works in target environment

### Should Have  
- [x] Basic tests written
- [x] Key functionality documented
- [x] No obvious performance issues

### Notes for Future
- Consider implementing metadata refresh scheduling (daily/weekly)

---

## Reference Materials

### Directory Naming Convention
```bash
# Target directory structure:
/media/
    Channel Name [channel_id]/                                                 # Show folder
        cover.ext                                                              # channel thumbnail
        backdrop.ext                                                           # channel banner
        Channel Name [channel_id].info.json                                    # channel metadata
        tvshow.nfo                                                             # NFO for TV Show (future feature)
        [Year:YYYY]/                                                           # Season folder (by year)
            season.nfo                                                         # NFO Season file
            Channel Name - YYYYMMDD - Title [video_id]/                        # Episode folder
                Channel Name - YYYYMMDD - Title [video_id].nfo                 # NFO Episode file
                Channel Name - YYYYMMDD - Title [video_id]-thumb.jpg           # thumbnail poster
                Channel Name - YYYYMMDD - Title [video_id].info.json           # metadata from youtube
                Channel Name - YYYYMMDD - Title [video_id].mkv                 # video
                Channel Name - YYYYMMDD - Title [video_id].[subtitles ext]     # subtitles

# Example for "Ms Rachel - Toddler Learning Videos":
`/media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]/`
```

### yt-dlp Python Library for Complete Channel Metadata
```python
# Extract complete channel metadata with single extract_info() call
import json
import yt_dlp

def extract_and_save_channel_metadata(url, output_path):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'playlistend': 10,  # Limit entries for faster extraction
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Extract all channel info without downloading
        info = ydl.extract_info(url, download=False)
        
        # Remove entries to reduce file size from 24MB to ~5KB
        if 'entries' in info:
            del info['entries']
        
        # Sanitize for JSON serialization
        sanitized_info = ydl.sanitize_info(info)
        
        # Save to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sanitized_info, f, indent=2, ensure_ascii=False)
        
        return sanitized_info

# Usage example:
# metadata = extract_and_save_channel_metadata(
#     "https://www.youtube.com/@msrachel",
#     "/media/channel_name/channel_info.json"
# )
# 
# # Access thumbnails directly:
# for thumb in metadata.get('thumbnails', []):
#     if thumb.get('id') == 'avatar_uncropped':
#         cover_url = thumb['url']
#     elif thumb.get('id') == 'banner_uncropped':
#         backdrop_url = thumb['url']
```


### Optimized Metadata Processing
```bash
# Single extract_info() call provides:
# 1. Complete channel metadata (channel_id, title, description, subscriber_count)
# 2. Direct thumbnail access (avatar_uncropped, banner_uncropped)
# 3. Compact file size (~5KB after removing entries)

# Example directory structure:
# /media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]/
#   ├── Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg].info.json  (5KB)
#   ├── cover.jpg     (from avatar_uncropped)
#   └── backdrop.jpg  (from banner_uncropped)
```

#### Actual Channel Metadata JSON Structure (entries removed for size optimization)
```json
{
    "id": "UCG2CL6EUjG8TVT1Tpl9nJdg",
    "channel": "Ms Rachel - Toddler Learning Videos",
    "channel_id": "UCG2CL6EUjG8TVT1Tpl9nJdg",
    "title": "Ms Rachel - Toddler Learning Videos - Videos",
    "channel_follower_count": 16100000,
    "description": "Toddler Learning Videos and Baby Learning Videos with a real teacher, Ms Rachel! Ms Rachel uses techniques recommended by speech therapists and early childhood experts to help children learn important milestones and preschool skills! You can trust Ms Rachel to provide interactive, high quality screen time!\n\nMs Rachel also gets kids moving through fun nursery rhymes & kids songs videos! Her videos for toddlers are informed by research and are full of learning standards that will help preschoolers thrive! Ms Rachel loves teaching letters, numbers, colors, animal sounds and more! She also has learn to talk videos and incorporates sign language!\n\nMs Rachel has a masters in music education from NYU and is almost finished a second masters in early childhood education. Parents and children can watch and learn together. Ms Rachel loves to teach and loves your wonderful family! Let's learn, grow and thrive! \n",
    "tags": [
        "toddler learning video",
        "toddler videos",
        "preschool",
        "toddler learning videos",
        "educational videos for toddlers",
        "first words",
        "toddler speech",
        "speech toddler",
        "baby's first words",
        "first words for babies",
        "songs for littles",
        "ms rachel",
        "miss rachel",
        "baby learning",
        "toddler learning",
        "best toddler learning video",
        "babies",
        "toddler shows",
        "wheels on the bus",
        "baby sign",
        "baby signs",
        "videos for toddlers",
        "learn colors",
        "learn to talk",
        "songs for kids",
        "kids songs",
        "nursery rhymes",
        "toddlers",
        "baby"
    ],
    "thumbnails": [
        {
            "url": "https://yt3.googleusercontent.com/DXRchzoMYp84nYIUeKWNZMyTK_0nMckzY3wQVe2RcvujPKw3E2DO9Y4scQUNlSxx_HsME7lP=w1060-fcrop64=1,00005a57ffffa5a8-k-c0xffffffff-no-nd-rj",
            "height": 175,
            "width": 1060,
            "preference": -10,
            "id": "0",
            "resolution": "1060x175"
        },
        {
            "url": "https://yt3.googleusercontent.com/DXRchzoMYp84nYIUeKWNZMyTK_0nMckzY3wQVe2RcvujPKw3E2DO9Y4scQUNlSxx_HsME7lP=w1138-fcrop64=1,00005a57ffffa5a8-k-c0xffffffff-no-nd-rj",
            "height": 188,
            "width": 1138,
            "preference": -10,
            "id": "1",
            "resolution": "1138x188"
        },
        {
            "url": "https://yt3.googleusercontent.com/DXRchzoMYp84nYIUeKWNZMyTK_0nMckzY3wQVe2RcvujPKw3E2DO9Y4scQUNlSxx_HsME7lP=w1707-fcrop64=1,00005a57ffffa5a8-k-c0xffffffff-no-nd-rj",
            "height": 283,
            "width": 1707,
            "preference": -10,
            "id": "2",
            "resolution": "1707x283"
        },
        {
            "url": "https://yt3.googleusercontent.com/DXRchzoMYp84nYIUeKWNZMyTK_0nMckzY3wQVe2RcvujPKw3E2DO9Y4scQUNlSxx_HsME7lP=w2120-fcrop64=1,00005a57ffffa5a8-k-c0xffffffff-no-nd-rj",
            "height": 351,
            "width": 2120,
            "preference": -10,
            "id": "3",
            "resolution": "2120x351"
        },
        {
            "url": "https://yt3.googleusercontent.com/DXRchzoMYp84nYIUeKWNZMyTK_0nMckzY3wQVe2RcvujPKw3E2DO9Y4scQUNlSxx_HsME7lP=w2276-fcrop64=1,00005a57ffffa5a8-k-c0xffffffff-no-nd-rj",
            "height": 377,
            "width": 2276,
            "preference": -10,
            "id": "4",
            "resolution": "2276x377"
        },
        {
            "url": "https://yt3.googleusercontent.com/DXRchzoMYp84nYIUeKWNZMyTK_0nMckzY3wQVe2RcvujPKw3E2DO9Y4scQUNlSxx_HsME7lP=w2560-fcrop64=1,00005a57ffffa5a8-k-c0xffffffff-no-nd-rj",
            "height": 424,
            "width": 2560,
            "preference": -10,
            "id": "5",
            "resolution": "2560x424"
        },
        {
            "url": "https://yt3.googleusercontent.com/DXRchzoMYp84nYIUeKWNZMyTK_0nMckzY3wQVe2RcvujPKw3E2DO9Y4scQUNlSxx_HsME7lP=s0",
            "id": "banner_uncropped",
            "preference": -5
        },
        {
            "url": "https://yt3.googleusercontent.com/C2nKGvtlPIpTO80svL80ZRRArA_512rEBMiZH6IWForDdVLd0SlVYQVObnmHxzVTeH9sOeNO=s900-c-k-c0x00ffffff-no-rj",
            "height": 900,
            "width": 900,
            "id": "7",
            "resolution": "900x900"
        },
        {
            "url": "https://yt3.googleusercontent.com/C2nKGvtlPIpTO80svL80ZRRArA_512rEBMiZH6IWForDdVLd0SlVYQVObnmHxzVTeH9sOeNO=s0",
            "id": "avatar_uncropped",
            "preference": 1
        }
    ],
    "uploader_id": "@msrachel",
    "uploader_url": "https://www.youtube.com/@msrachel",
    "uploader": "Ms Rachel - Toddler Learning Videos",
    "channel_url": "https://www.youtube.com/channel/UCG2CL6EUjG8TVT1Tpl9nJdg",
    "_type": "playlist",
    "extractor_key": "YoutubeTab",
    "extractor": "youtube:tab",
    "webpage_url": "https://www.youtube.com/@msrachel/videos",
    "webpage_url_basename": "videos",
    "webpage_url_domain": "youtube.com",
    "epoch": 1754539997,
    "_version": {
        "version": "2025.07.21",
        "release_git_head": "9951fdd0d08b655cb1af8cd7f32a3fb7e2b1324e",
        "repository": "yt-dlp/yt-dlp"
    }
}
```

#### Image Metadata Download

**Cover image download**
From json file example above the image file would come from `thumbnails[int].url` where id = `avatar_uncropped`

```bash
# Example filename
`/media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]/cover.[ext]`
```

**Backdrop image download**
From json file example above the image file would come from `thumbnails[int].url` where id = `banner_uncropped`

```bash
# Example filename
`/media/Ms Rachel - Toddler Learning Videos [UCG2CL6EUjG8TVT1Tpl9nJdg]/backdrop.[ext]`
```

### Filesystem Safe Name Generation (Python)
```python
import re
import unicodedata

def make_filesystem_safe(name, max_length=100):
    """Convert channel name to filesystem-safe directory name, preserving spaces."""
    # Normalize unicode characters
    name = unicodedata.normalize('NFKD', name)
    
    # Replace problematic filesystem characters but preserve spaces
    name = re.sub(r'[<>:"/\\|?*]', '', name)  # Remove problematic chars
    name = re.sub(r'\.+$', '', name)  # Remove trailing dots
    name = re.sub(r'\s+', ' ', name)  # Collapse multiple spaces to single space
    name = name.strip()  # Remove leading/trailing whitespace
    
    # Truncate if too long, but preserve channel ID space
    if len(name) > max_length:
        name = name[:max_length].strip()
    
    return name

# Example usage:
# "Mrs. Rachel - Toddler Learning Videos" -> "Mrs Rachel - Toddler Learning Videos"
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