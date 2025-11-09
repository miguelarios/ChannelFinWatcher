# User Story: Auto-Generate NFO Files for Jellyfin Media Library

## Section 1: Story Definition

### Feature
Automatically generate Jellyfin-compatible NFO metadata files (tvshow.nfo, season.nfo, and episode.nfo) from yt-dlp JSON metadata for YouTube channel content organized in a TV show structure.

### User Story
- **As a** Jellyfin media library administrator
- **I want** NFO metadata files automatically created for my YouTube channel downloads
- **So that** Jellyfin can properly display rich metadata (descriptions, dates, tags, etc.) without manual intervention

### Context
ChannelFinWatcher downloads YouTube videos using yt-dlp, which creates `.info.json` files containing comprehensive metadata. However, Jellyfin requires `.nfo` files in specific XML formats to display this metadata properly. Currently, users must manually create these files or rely on Jellyfin's limited ability to parse filenames. This feature will bridge the gap by automatically transforming the JSON metadata into Jellyfin-compatible NFO files for shows, seasons, and episodes.

**NFO Generation Workflow:**
- **tvshow.nfo**: Generated when channel is first added to monitoring
- **season.nfo**: Generated automatically when first episode of a year is downloaded (simple, year-based only)
- **episode.nfo**: Generated after each episode download completes successfully (ensures video filename is finalized)
- **Manual Regeneration**: Kebab menu on channel dashboard cards provides "Regenerate NFO Files" option to rebuild all NFO files recursively

### Functional Requirements

#### [ ] Scenario: Generate tvshow.nfo when channel is added to monitoring
- **Given** a user adds a YouTube channel to be monitored
  - And the channel metadata is downloaded with a channel-level info.json file
  - And the info.json contains fields: `channel`, `description`, `tags`, and `channel_id`
  - And the channel directory is created at the show level (e.g., `/Steve the Bartender [UCfEJUzPnT-HdNqOqdX3A0lA]/`)
- **When** the channel is first added and metadata is retrieved
- **Then** a `tvshow.nfo` file is automatically created in the channel directory
  - And the NFO contains `<title>` populated from `channel` field
  - And the NFO contains `<plot>` populated from `description` field
  - And the NFO contains `<uniqueid type="youtube">` populated from channel `id` field
  - And the NFO contains `<studio>YouTube</studio>`
  - And the NFO contains `<tag>` elements for each tag
  - And `nfo_last_generated` is set to current timestamp

#### [ ] Scenario: Regenerate tvshow.nfo when channel metadata is manually updated
- **Given** a channel exists with a tvshow.nfo file
  - And the user manually triggers a channel metadata update (refresh)
- **When** the channel metadata update completes successfully
  - And the channel-level info.json is updated with new metadata
- **Then** the tvshow.nfo file is automatically regenerated
  - And the NFO is updated with the latest `channel`, `description`, and `tags` values
  - And `nfo_last_generated` timestamp is updated
  - And a log entry indicates tvshow.nfo was regenerated due to metadata update

#### [ ] Scenario: Generate season.nfo when first episode of year is downloaded
- **Given** a video is being downloaded from a monitored channel
  - And the video's upload year creates a new year folder (e.g., `/2021/`)
  - And no season.nfo exists yet in that year folder
- **When** the first episode download begins and the year folder is created
- **Then** a `season.nfo` file is automatically created in the year directory
  - And the NFO contains `<title>` with the year (e.g., "2021")
  - And the NFO contains `<season>` with the year as the season number (e.g., "2021")
  - And the NFO contains `<dateadded>` with the current timestamp in format `YYYY-MM-DD HH:MM:SS`
  - And the NFO contains empty `<plot />` and `<outline />` tags
  - And the NFO contains empty `<art />` tag

#### [ ] Scenario: Generate episode.nfo after episode download completes
- **Given** a video download from a monitored channel has completed successfully
  - And yt-dlp has created the `.info.json` file with episode metadata
  - And the info.json contains fields: `title`, `description`, `upload_date`, `uploader`, `duration`, `tags`, `id`, `channel`, `channel_id`
  - And the video file has been finalized with its permanent filename
- **When** the video download completes and post-processing finishes
- **Then** an NFO file named `<basename>.nfo` is created matching the video filename
  - And the NFO contains `<title>` from the `title` field
  - And the NFO contains `<showtitle>` from the `channel` field
  - And the NFO contains `<plot>` from the `description` field
  - And the NFO contains `<aired>` from `upload_date` field (formatted as YYYY-MM-DD)
  - And the NFO contains `<dateadded>` with the file creation time
  - And the NFO contains `<year>` extracted from `upload_date`
  - And the NFO contains `<runtime>` from `duration` field (converted to minutes)
  - And the NFO contains `<director>` tags populated from `uploader` field
  - And the NFO contains `<genre>` tags for each item in the `categories` array
  - And the NFO contains `<tag>` tags for each item in the `tags` array
  - And the NFO contains `<uniqueid type="youtube">` with the video `id`
  - And the NFO contains `<studio>YouTube</studio>`

#### [ ] Scenario: Handle missing optional metadata fields
- **Given** a video info.json file with missing optional fields (e.g., no tags, no description)
- **When** the NFO generation process runs
- **Then** the episode.nfo file is still created with available data
  - And missing fields are either omitted or contain empty tags as appropriate
  - But required fields (title, channel) must be present or generation fails with a warning

#### [ ] Scenario: Overwrite existing NFO files
- **Given** an NFO file already exists for a show/season/episode
  - And the corresponding info.json file has been updated or regenerated
- **When** the NFO generation process runs with overwrite enabled
- **Then** the existing NFO file is replaced with newly generated content
  - And a log entry indicates the file was overwritten

#### [ ] Scenario: Skip existing NFO files (preserve mode)
- **Given** an NFO file already exists for a show/season/episode
  - And the user has configured preserve existing NFO files
- **When** the NFO generation process runs
- **Then** the existing NFO file is not modified
  - And a log entry indicates the file was skipped

#### [ ] Scenario: Manual regeneration via kebab menu on channel card
- **Given** a channel card is displayed on the dashboard
  - And the channel has existing episodes with or without NFO files
- **When** the user clicks the kebab (⋮) menu icon on the channel card
  - And selects "Regenerate NFO Files" from the menu
- **Then** a confirmation dialog appears asking to confirm the regeneration
- **When** the user confirms the action
- **Then** the system recursively processes the entire channel directory
  - And generates/regenerates tvshow.nfo in the channel root directory
  - And generates/regenerates season.nfo in each year/season subdirectory
  - And generates/regenerates episode.nfo for each video with an info.json file
  - And displays a progress indicator during the process
  - And shows a summary notification with counts of files created/updated/failed
  - And respects the overwrite configuration setting
  - And logs all operations performed
  - And updates the `nfo_last_generated` timestamp in the database

#### [ ] Scenario: Delete NFO files when videos are cleaned up
- **Given** the retention cleanup process deletes old videos to maintain channel limits
  - And deleted videos have associated NFO files
  - And deleted videos may be in year/season directories
- **When** a video file is deleted by the cleanup process
- **Then** the corresponding episode.nfo file is also deleted
  - And if the video directory becomes empty, the entire directory is removed
  - And if a year/season directory becomes empty after cleanup, the season.nfo is also deleted
  - And the empty year/season directory is removed
  - And deletion is logged with video ID and file paths
- **Given** all videos in a channel are deleted (channel removal)
- **When** the channel cleanup process runs
- **Then** the tvshow.nfo file is deleted along with the channel directory
  - And all associated season.nfo and episode.nfo files are removed
  - And `nfo_last_generated` is set to NULL (or channel record is removed)

#### [ ] Scenario: Backfill NFO files for existing channels after migration
- **Given** the NFO feature schema migration has run
  - And existing channels have `nfo_last_generated = NULL` (no NFO files generated yet)
  - And the user navigates to Settings → NFO Generation
- **When** the settings page loads
  - And there are channels with `nfo_last_generated = NULL`
- **Then** a prominent notification appears indicating backfill is needed
  - And displays: "X channels need NFO files generated. [Start Backfill] [Dismiss]"
- **When** the user clicks "Start Backfill"
- **Then** a background job begins processing channels sequentially
  - And processes one channel at a time (avoids overwhelming disk I/O)
  - And for each channel:
    - Generates tvshow.nfo in channel root
    - Scans all year/season directories and generates season.nfo files
    - Scans all video directories and generates episode.nfo files
    - Sets `nfo_last_generated = current_timestamp` when channel completes
  - And displays a progress indicator showing: "Generating NFO files... Channel 5 of 23"
  - And allows user to pause/resume the backfill process
  - And is resumable if interrupted (only processes channels where `nfo_last_generated IS NULL`)
  - And shows final summary: "NFO backfill complete: 23 channels, 1,234 files created"
- **Given** backfill is running
  - And the user closes the browser or navigates away
- **Then** the backfill continues running in the background
  - And progress is saved to database (via `nfo_last_generated` timestamp)
  - And can be monitored by returning to Settings → NFO Generation page

### Non-functional Requirements
- **Performance:** NFO generation should not noticeably delay download completion or manual regeneration operations
- **Reliability:** Invalid or malformed JSON files should be logged and skipped without crashing the process
- **Usability:** Provide clear logging of which NFO files were created, skipped, or failed
- **Maintainability:** NFO generation logic should be modular and testable independently of download logic

### Dependencies
- **Blocked by:** None (can be developed independently)
- **Blocks:** None (enhancement to existing functionality)

### Channel Metadata Download (Already Implemented)
The system already downloads channel-level metadata using `youtube_service.extract_channel_metadata_full()`:
- Called when a new channel is added to monitoring
- Uses `yt_dlp.YoutubeDL.extract_info(url, download=False)` with `extract_flat=False` and `playlistend=1`
- Removes the `entries` key to reduce file size from ~24MB to ~5KB
- Saves to `{channel_name} [{channel_id}].info.json` in the channel root directory
- This file contains: `channel`, `channel_id`, `description`, `tags`, `channel_follower_count`, etc.
- **Note**: Channel info.json does NOT have a `categories` field (only episode-level info.json has categories)

---

## Section 2: Engineering Tasks

### Task Breakdown

#### 1. [ ] Backend - Create NFO Generator Service
- **Description:** Implement a Python service to parse info.json files and generate NFO XML files according to Jellyfin specifications
- **Estimation:** 8 hours
- **Acceptance Criteria:** 
  - [ ] Service can read channel-level info.json and generate tvshow.nfo
  - [ ] Service can generate season.nfo from directory names
  - [ ] Service can read episode-level info.json and generate episode.nfo
  - [ ] Service handles missing optional fields gracefully
  - [ ] Service logs all actions (created, skipped, failed)
  - [ ] Service validates XML output structure

#### 2. [ ] Backend - Add NFO Configuration Settings
- **Description:** Add configuration options to control NFO generation behavior
- **Estimation:** 2 hours
- **Acceptance Criteria:**
  - [ ] Config option to enable/disable auto NFO generation (all-or-nothing)
  - [ ] Config option to overwrite existing NFO files vs preserve
  - [ ] Default configuration added to config/config.yaml

**Example config/config.yaml structure:**
```yaml
# NFO file generation for Jellyfin metadata
nfo:
  # Enable/disable automatic NFO generation for all channels
  enabled: true

  # Overwrite existing NFO files on regeneration
  # true: Always overwrite existing files
  # false: Preserve existing files (skip if already exists)
  overwrite_existing: false
```

#### 2.5. [ ] Backend - Add Database Schema for NFO Tracking
- **Description:** Add database field to track NFO generation timestamps
- **Estimation:** 1 hour
- **Acceptance Criteria:**
  - [ ] Add `nfo_last_generated` timestamp field to Channel table (nullable, default NULL)
  - [ ] Create database migration for new field
  - [ ] Migration leaves `nfo_last_generated = NULL` for existing channels (enables backfill detection)
  - [ ] New channels created after migration get `nfo_last_generated` set when tvshow.nfo is created
  - [ ] Update ORM models to include new field
  - [ ] Add database index on `nfo_last_generated` for efficient backfill queries

#### 3. [ ] Backend - Integrate NFO Generation into Download Workflow
- **Description:** Hook NFO generation into post-download processing and cleanup
- **Estimation:** 5 hours
- **Acceptance Criteria:**
  - [ ] NFO files are automatically generated after video download completes
  - [ ] NFO files are automatically deleted when videos are cleaned up (retention limits)
  - [ ] Empty directories and season.nfo files are cleaned up when all videos in season/year are deleted
  - [ ] NFO generation respects configuration settings
  - [ ] Failed NFO generation does not block download completion
  - [ ] NFO generation and deletion status is reflected in download logs

#### 4. [ ] Backend - Create Batch NFO Generation Endpoint
- **Description:** Create API endpoint to regenerate NFO files for existing media library
- **Estimation:** 4 hours
- **Acceptance Criteria:**
  - [ ] API endpoint accepts channel/directory path parameter
  - [ ] Endpoint can process entire channel or specific season
  - [ ] Endpoint returns summary of files created/skipped/failed
  - [ ] Endpoint respects overwrite configuration
  - [ ] Endpoint is rate-limited to prevent resource exhaustion
  - [ ] Endpoint updates `nfo_last_generated` timestamp after successful generation

#### 4.5. [ ] Backend - Create NFO Backfill Background Job
- **Description:** Implement background job to process NFO backfill for existing channels after migration
- **Estimation:** 4 hours
- **Acceptance Criteria:**
  - [ ] Background job queries for channels where `nfo_last_generated IS NULL`
  - [ ] Processes channels sequentially (one at a time) to avoid disk I/O overload
  - [ ] For each channel: generates tvshow.nfo, all season.nfo, all episode.nfo files
  - [ ] Updates `nfo_last_generated` timestamp after each channel completes
  - [ ] Job is resumable if interrupted (idempotent based on NULL check)
  - [ ] Provides progress updates via WebSocket or polling endpoint
  - [ ] Allows pause/resume functionality
  - [ ] Logs detailed progress and errors
  - [ ] Respects global NFO generation configuration (overwrite mode, etc.)

#### 5. [ ] Testing - Unit Tests for NFO Generator
- **Description:** Write comprehensive unit tests for NFO generation logic
- **Estimation:** 4 hours
- **Acceptance Criteria:** 
  - [ ] Test tvshow.nfo generation with complete metadata
  - [ ] Test tvshow.nfo generation with minimal metadata
  - [ ] Test season.nfo generation for year directories
  - [ ] Test episode.nfo generation with all fields
  - [ ] Test episode.nfo generation with missing optional fields
  - [ ] Test XML validation and character escaping
  - [ ] Test file overwrite vs preserve logic

#### 6. [ ] Testing - Integration Tests for NFO Workflow
- **Description:** Test end-to-end NFO generation in download workflow
- **Estimation:** 5 hours
- **Acceptance Criteria:**
  - [ ] Test NFO generation triggered by successful download
  - [ ] Test NFO generation with existing files (overwrite mode)
  - [ ] Test NFO generation with existing files (preserve mode)
  - [ ] Test NFO deletion when video is deleted during retention cleanup
  - [ ] Test season.nfo deletion when all videos in year/season are deleted
  - [ ] Test empty directory cleanup after NFO and video deletion
  - [ ] Test channel metadata update triggers tvshow.nfo regeneration
  - [ ] Test error handling when info.json is missing (NFO generation skipped)
  - [ ] Test error handling when info.json is malformed (NFO generation skipped)
  - [ ] Test batch generation endpoint
  - [ ] Test backfill process with multiple channels
  - [ ] Test backfill resume after interruption (only processes channels with NULL timestamp)
  - [ ] Test backfill pause/resume functionality
  - [ ] Test that new channels after migration get `nfo_last_generated` set immediately
  - [ ] Test backfill skips channels where `nfo_last_generated IS NOT NULL`

#### 7. [ ] Frontend - Add NFO Management UI
- **Description:** Add UI controls for NFO generation settings and manual triggers, including kebab menu option on channel cards
- **Estimation:** 8 hours
- **Acceptance Criteria:**
  - [ ] **Global Settings page** has NFO generation configuration:
    - Enable/disable NFO generation (applies to all channels)
    - Overwrite existing NFO files vs preserve mode
  - [ ] Settings page detects channels needing backfill (`nfo_last_generated IS NULL`)
  - [ ] Prominent notification banner on Settings page when backfill needed
  - [ ] "Start Backfill" button triggers background job
  - [ ] Real-time progress indicator for backfill: "Generating NFO files... Channel 5 of 23"
  - [ ] Pause/Resume buttons for backfill process
  - [ ] Final summary notification when backfill completes
  - [ ] **Per-channel manual trigger** via kebab menu (⋮) on channel dashboard cards:
    - "Regenerate NFO Files" option in kebab menu
    - Clicking shows confirmation dialog
    - Manual regeneration shows progress indicator with percentage/counts
    - Summary notification displays results (created/updated/failed counts)
  - [ ] Download history shows brief NFO generation status (e.g., "NFO: Created" or "NFO: Failed")
  - [ ] UI shows validation errors for failed NFO generation

#### 8. [ ] Documentation - NFO Feature Documentation
- **Description:** Document NFO generation feature for users and developers
- **Estimation:** 3 hours
- **Acceptance Criteria:**
  - [ ] User guide explains NFO generation feature
  - [ ] User guide shows Jellyfin configuration for NFO files
  - [ ] User guide documents backfill process for existing installations
  - [ ] User guide explains migration-triggered backfill detection
  - [ ] Technical docs explain NFO XML structure and mapping
  - [ ] Technical docs explain backfill architecture and resumability
  - [ ] API documentation updated for batch generation endpoint
  - [ ] API documentation updated for backfill endpoints
  - [ ] Configuration reference updated with NFO settings
  - [ ] Database schema changes documented in migration notes

---

## Definition of Done

### Must Have
- [ ] tvshow.nfo, season.nfo, and episode.nfo files are generated with correct Jellyfin schema
- [ ] NFO files contain all available metadata from info.json files
- [ ] NFO files generated automatically after video downloads complete
- [ ] Database schema migration adds tracking field (`nfo_last_generated`)
- [ ] NFO generation controlled by global configuration only (no per-channel disable)
- [ ] Backfill process detects existing channels via NULL timestamp
- [ ] Backfill is resumable if interrupted (idempotent based on timestamp)
- [ ] Configuration options work as documented
- [ ] Unit and integration tests pass
- [ ] Basic user documentation exists
- [ ] Backfill process documented for existing installations

### Should Have
- [ ] Frontend UI for manual NFO regeneration via kebab menu
- [ ] Frontend UI for backfill notification and progress
- [ ] Pause/resume functionality for backfill process
- [ ] Batch NFO generation API endpoint
- [ ] Comprehensive error handling and logging
- [ ] Performance acceptable for large media libraries (sequential processing)

### Notes for Future
- Consider adding support for additional NFO metadata fields (ratings, actors, thumbnails)
- Explore automatic thumbnail/poster extraction and linking in NFO files
- Consider NFO file validation/repair tool for troubleshooting
- May want to add NFO preview in UI before writing to disk

---

## Reference Materials

### Example Channel-Level info.json Structure
```json
{
    "id": "@StevetheBartender_",
    "channel": "Steve the Bartender",
    "channel_id": "UCfEJUzPnT-HdNqOqdX3A0lA",
    "title": "Steve the Bartender",
    "channel_follower_count": 777000,
    "description": "Want to know more about about Steve the Bartender?\n\nI have 20+ years of experience...",
    "tags": [
        "Bartender",
        "Cocktails",
        "Recipe"
    ],
    "uploader_id": "@StevetheBartender_",
    "uploader_url": "https://www.youtube.com/@StevetheBartender_",
    "playlist_count": 3,
    "uploader": "Steve the Bartender",
    "channel_url": "https://www.youtube.com/channel/UCfEJUzPnT-HdNqOqdX3A0lA"
}
```

### Example tvshow.nfo Output
```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<tvshow>
    <title>Steve the Bartender</title>
    <plot>
Want to know more about about Steve the Bartender?

I have 20+ years of experience working in the hospitality industry...
    </plot>
    <uniqueid type="youtube" default="true">UCfEJUzPnT-HdNqOqdX3A0lA</uniqueid>
    <studio>YouTube</studio>
    <tag>Bartender</tag>
    <tag>Cocktails</tag>
    <tag>Recipe</tag>
</tvshow>
```

### Example season.nfo Output
```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<season>
  <plot />
  <outline />
  <dateadded>2024-11-14 14:49:22</dateadded>
  <title>2021</title>
  <season>2021</season>
  <art />
</season>
```

**Note on Numbering**:
- `<season>`: Uses the upload year as the season number (e.g., "2021")
- `<episode>`: Intentionally omitted - Jellyfin will use alphabetical/date sorting within each season

### Example Episode-Level info.json Structure
```json
{
  "id": "Day4-sm3U1s",
  "title": "Paloma 3 Ways - Classic, Upgraded & Clarified!",
  "description": "Celebrating Patrón's Paloma Week...",
  "upload_date": "20211207",
  "uploader": "Steve the Bartender",
  "duration": 922,
  "language": "en",
  "categories": ["Howto & Style"],
  "tags": [
    "mexican cocktails",
    "tequila cocktails",
    "cocktail recipe"
  ],
  "channel": "Steve the Bartender",
  "channel_id": "UCfEJUzPnT-HdNqOqdX3A0lA"
}
```

### Example episode.nfo Output (based on Jellyfin docs)
```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<episodedetails>
    <title>Paloma 3 Ways - Classic, Upgraded & Clarified!</title>
    <showtitle>Steve the Bartender</showtitle>
    <plot>Celebrating Patrón's Paloma Week...</plot>
    <language>en</language>
    <aired>2021-12-07</aired>
    <year>2021</year>
    <runtime>15</runtime>
    <director>Steve the Bartender</director>
    <studio>YouTube</studio>
    <uniqueid type="youtube" default="true">Day4-sm3U1s</uniqueid>
    <genre>Howto & Style</genre>
    <tag>mexican cocktails</tag>
    <tag>tequila cocktails</tag>
    <tag>cocktail recipe</tag>
    <dateadded>2021-12-07 00:00:00</dateadded>
</episodedetails>
```

### Jellyfin NFO Schema Requirements
Per Jellyfin documentation at https://jellyfin.org/docs/general/server/metadata/nfo/:

**Naming Convention:**
- TV Shows: `tvshow.nfo` in show directory
- TV Season: `season.nfo` in season directory  
- Episode: `<filename of the episode>.nfo` in same directory as video

**Key Episode Tags (from Jellyfin docs):**
- `title` - Episode title
- `showtitle` - Show name (for episodes)
- `plot` - Description/summary
- `aired` - Air date (YYYY-MM-DD format)
- `dateadded` - When added to library (UTC timestamp)
- `year` - Year of release
- `runtime` - Duration in minutes
- `director` - Creator/uploader
- `genre` - Multiple tags allowed
- `studio` - Multiple tags allowed
- `uniqueid` - Provider ID (type attribute specifies provider)
- `season` - Season number (for episodes)
- `episode` - Episode number (for episodes)

**Key Show Tags:**
- `title` - Show name
- `plot` - Show description
- `uniqueid` - Unique identifier for channel tracking
- `studio` - Studio/network (multiple allowed)
- `tag` - Multiple tags allowed

**Key Season Tags:**
- `title` - Season name/number
- `plot` - Season description
- `dateadded` - When added
- `art` - Artwork references

### Python XML Generation Pattern
```python
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime

def prettify_xml(elem):
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ", encoding="utf-8")

def generate_tvshow_nfo(channel_info):
    """Generate tvshow.nfo from channel info.json

    Simplified structure with uniqueid for channel tracking.
    Tags only (no genres) for cleaner metadata.
    """
    root = ET.Element('tvshow')

    ET.SubElement(root, 'title').text = channel_info.get('channel', '')
    ET.SubElement(root, 'plot').text = channel_info.get('description', '')

    # Unique ID: YouTube channel ID
    channel_id = channel_info.get('id') or channel_info.get('channel_id')
    if channel_id:
        uniqueid_elem = ET.SubElement(root, 'uniqueid', type='youtube', default='true')
        uniqueid_elem.text = channel_id

    ET.SubElement(root, 'studio').text = 'YouTube'

    # Channel tags (no genres)
    for tag in channel_info.get('tags', []):
        ET.SubElement(root, 'tag').text = tag

    return prettify_xml(root)

def generate_season_nfo(year):
    """Generate season.nfo for year-based seasons

    Args:
        year: Year string (e.g., "2021") extracted from directory name
    """
    root = ET.Element('season')

    # Empty plot and outline tags
    ET.SubElement(root, 'plot')
    ET.SubElement(root, 'outline')

    # Current timestamp for dateadded
    dateadded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ET.SubElement(root, 'dateadded').text = dateadded

    # Title and season number both use the year
    ET.SubElement(root, 'title').text = str(year)
    ET.SubElement(root, 'season').text = str(year)

    # Empty art tag
    ET.SubElement(root, 'art')

    return prettify_xml(root)

def generate_episode_nfo(episode_info):
    """Generate episode.nfo from video info.json"""
    root = ET.Element('episodedetails')

    # Required fields
    ET.SubElement(root, 'title').text = episode_info.get('title', 'Unknown Title')
    ET.SubElement(root, 'showtitle').text = episode_info.get('channel', '')

    # Optional description (newlines preserved automatically)
    description = episode_info.get('description')
    if description:
        ET.SubElement(root, 'plot').text = description

    # Language (ISO 639-1: en, es, etc.)
    language = episode_info.get('language')
    if language:
        ET.SubElement(root, 'language').text = language

    # Date fields (upload_date: YYYYMMDD → YYYY-MM-DD)
    upload_date = episode_info.get('upload_date')
    if upload_date:
        aired_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")
        ET.SubElement(root, 'aired').text = aired_date
        ET.SubElement(root, 'year').text = upload_date[:4]

    # Duration (seconds → minutes)
    duration = episode_info.get('duration')
    if duration and duration > 0:
        runtime_minutes = duration // 60
        ET.SubElement(root, 'runtime').text = str(runtime_minutes)

    # Optional fields
    uploader = episode_info.get('uploader')
    if uploader:
        ET.SubElement(root, 'director').text = uploader

    ET.SubElement(root, 'studio').text = 'YouTube'

    # Unique ID
    video_id = episode_info.get('id')
    if video_id:
        uniqueid_elem = ET.SubElement(root, 'uniqueid', type='youtube', default='true')
        uniqueid_elem.text = video_id

    # Categories → genres
    for category in episode_info.get('categories', []):
        ET.SubElement(root, 'genre').text = category

    # Tags → tags
    for tag in episode_info.get('tags', []):
        ET.SubElement(root, 'tag').text = tag

    # Date added (current timestamp)
    dateadded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ET.SubElement(root, 'dateadded').text = dateadded

    return prettify_xml(root)

def write_nfo_file(nfo_path, xml_content):
    """Write NFO content to file with proper UTF-8 encoding and atomic write

    Args:
        nfo_path: Absolute path to .nfo file
        xml_content: XML bytes from prettify_xml()

    Raises:
        IOError: If file write fails
    """
    import os
    import logging

    logger = logging.getLogger(__name__)

    # Write atomically using temp file + rename (atomic on POSIX systems)
    temp_path = f"{nfo_path}.tmp"
    try:
        with open(temp_path, 'wb') as f:
            f.write(xml_content)

        # Atomic rename (overwrites existing file)
        os.rename(temp_path, nfo_path)
        logger.info(f"Created NFO file: {nfo_path}")

    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        logger.error(f"Failed to write NFO: {nfo_path}, Error: {e}")
        raise

def get_nfo_paths(video_info_json_path):
    """Construct NFO file paths from video info.json path

    Args:
        video_info_json_path: Absolute path to episode .info.json file

    Returns:
        dict: Paths for all three NFO types
            {
                'tvshow': '/channel/tvshow.nfo',
                'season': '/channel/2021/season.nfo',
                'episode': '/channel/2021/video/video.nfo'
            }

    Example:
        Input: /channel/2021/video [ID]/video [ID].info.json
        Output: {
            'episode': /channel/2021/video [ID]/video [ID].nfo
            'season': /channel/2021/season.nfo
            'tvshow': /channel/tvshow.nfo
        }
    """
    import os

    # Construct episode NFO path (same basename as .info.json)
    base_path = video_info_json_path.replace('.info.json', '')
    episode_nfo = f"{base_path}.nfo"

    # Navigate up directory tree to find season and channel paths
    video_dir = os.path.dirname(video_info_json_path)  # Video directory
    season_dir = os.path.dirname(video_dir)             # Year folder (e.g., "2021")
    channel_dir = os.path.dirname(season_dir)           # Channel root

    season_nfo = os.path.join(season_dir, 'season.nfo')
    tvshow_nfo = os.path.join(channel_dir, 'tvshow.nfo')

    return {
        'tvshow': tvshow_nfo,
        'season': season_nfo,
        'episode': episode_nfo
    }

def discover_videos_for_backfill(channel_dir):
    """Find all videos in channel directory that need NFO files

    Args:
        channel_dir: Absolute path to channel root directory

    Returns:
        list: Paths to .info.json files for all episodes (not channel metadata)

    Note:
        Only returns .info.json files that have corresponding video files.
        Skips channel-level info.json (which has no video file).
    """
    import os

    info_json_files = []

    # Walk channel directory recursively looking for .info.json files
    for root, dirs, files in os.walk(channel_dir):
        for file in files:
            # Skip hidden files and non-json files
            if not file.endswith('.info.json') or file.startswith('.'):
                continue

            info_path = os.path.join(root, file)

            # Check if corresponding video file exists
            # Try common video extensions
            base_path = info_path.replace('.info.json', '')
            video_extensions = ['.mkv', '.mp4', '.webm', '.m4v']

            has_video = any(
                os.path.exists(f"{base_path}{ext}")
                for ext in video_extensions
            )

            if has_video:
                info_json_files.append(info_path)

    return sorted(info_json_files)  # Consistent ordering
```

### File System Layout Example
```
/media/YouTube/Cocktails/
└── Steve the Bartender [UCfEJUzPnT-HdNqOqdX3A0lA]/
    ├── Steve the Bartender [@StevetheBartender_].info.json  # Channel metadata
    ├── tvshow.nfo                                             # Generated from above
    ├── 2021/                                                  # Season folder (year-based)
    │   ├── season.nfo                                         # Generated (title="2021", season="2021")
    │   └── Steve the Bartender - 20211207 - Paloma 3 Ways [Day4-sm3U1s]/
    │       ├── Steve the Bartender - 20211207 - Paloma 3 Ways [Day4-sm3U1s].mkv
    │       ├── Steve the Bartender - 20211207 - Paloma 3 Ways [Day4-sm3U1s].info.json
    │       └── Steve the Bartender - 20211207 - Paloma 3 Ways [Day4-sm3U1s].nfo  # Generated
    └── 2022/                                                  # Another season folder
        └── season.nfo                                         # Generated (title="2022", season="2022")
```

### Important Implementation Notes
1. **XML Character Escaping**: Python's `xml.etree.ElementTree` automatically handles XML character escaping for special characters (&, <, >, ", ')
2. **Duration Conversion**: yt-dlp provides duration in seconds, Jellyfin expects minutes in `<runtime>`
3. **Date Formatting**:
   - `upload_date` from yt-dlp is in YYYYMMDD format
   - Jellyfin `<aired>` expects YYYY-MM-DD
   - Jellyfin `<dateadded>` expects YYYY-MM-DD HH:MM:SS
4. **Missing Data**: Handle cases where optional fields are None/null/missing
5. **File Naming**: Episode NFO must match video filename exactly (minus extension)
6. **UTF-8 Encoding**: Always use UTF-8 encoding with BOM declaration in XML header
7. **Newline Handling in Descriptions**:
   - JSON `\n` escape sequences are automatically converted to actual newlines by `json.load()`
   - ElementTree preserves newlines as-is in XML text content
   - No manual replacement needed - Jellyfin displays newlines correctly

### Complete tvshow.nfo Field Mapping

| NFO Field | JSON Source | Transformation Required | Required? | Notes |
|-----------|-------------|------------------------|-----------|-------|
| `<title>` | `channel` | None - direct copy | ✅ Required | Channel name |
| `<plot>` | `description` | None - newlines preserved automatically | ⚠️ Optional | Channel description |
| `<uniqueid type="youtube">` | `id` or `channel_id` | Wrap in uniqueid tag with attributes | ✅ Required | YouTube channel ID |
| `<studio>` | *hardcoded* | Always set to `YouTube` | ✅ Required | Platform identifier |
| `<tag>` (multiple) | `tags` array | Create one `<tag>` tag per tag | ⚠️ Optional | Channel tags |

**Note**: Simplified tvshow.nfo structure uses tags only (no genres) for cleaner metadata. The uniqueid allows Jellyfin to track channels across library rebuilds.

### Complete Episode NFO Field Mapping

| NFO Field | JSON Source | Transformation Required | Required? | Notes |
|-----------|-------------|------------------------|-----------|-------|
| `<title>` | `title` | None - direct copy | ✅ Required | Episode title |
| `<showtitle>` | `channel` | None - direct copy | ✅ Required | Channel name |
| `<plot>` | `description` | None - newlines preserved automatically | ⚠️ Optional | Episode description |
| `<language>` | `language` | None - direct copy (ISO 639-1) | ⚠️ Optional | ISO 639-1 codes: "en", "es", etc. |
| `<aired>` | `upload_date` | **Format conversion**: `20211207` → `2021-12-07` | ✅ Required | Upload date |
| `<year>` | `upload_date` | **Extract year**: `20211207` → `2021` | ✅ Required | Upload year |
| `<runtime>` | `duration` | **Convert seconds to minutes**: `922` → `15` | ⚠️ Optional | Video duration |
| `<director>` | `uploader` | None - direct copy | ⚠️ Optional | Channel uploader/creator |
| `<studio>` | *hardcoded* | Always set to `YouTube` | ✅ Required | Platform identifier |
| `<uniqueid type="youtube">` | `id` | Wrap in uniqueid tag with attributes | ✅ Required | YouTube video ID |
| `<genre>` (multiple) | `categories` array | Create one `<genre>` tag per category | ⚠️ Optional | Broad categorization (e.g., "Howto & Style") |
| `<tag>` (multiple) | `tags` array | Create one `<tag>` tag per tag | ⚠️ Optional | Specific descriptors (e.g., "cocktails") |
| `<dateadded>` | *file creation time* | **Format as**: `YYYY-MM-DD HH:MM:SS` | ⚠️ Optional | When file was added to library |

**Key Distinction - Categories vs Tags:**
- **`categories`** → **`<genre>`**: Broad YouTube categories (e.g., "Entertainment", "Education", "Howto & Style")
- **`tags`** → **`<tag>`**: Specific user-defined tags (e.g., "mexican cocktails", "tequila cocktails")

**Transformation Examples:**

```python
# Date formatting (upload_date → aired)
from datetime import datetime
upload_date = "20211207"
aired_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")
# Result: "2021-12-07"

# Duration conversion (duration → runtime)
duration_seconds = 922
runtime_minutes = duration_seconds // 60  # Integer division
# Result: 15

# Year extraction (upload_date → year)
upload_date = "20211207"
year = upload_date[:4]  # First 4 characters
# Result: "2021"

# Categories → genres (multiple elements)
for category in info.get('categories', []):
    ET.SubElement(root, 'genre').text = category

# Tags → tags (multiple elements)
for tag in info.get('tags', []):
    ET.SubElement(root, 'tag').text = tag

# Language (ISO 639-1)
language = info.get('language')
if language:
    ET.SubElement(root, 'language').text = language
```

### Jellyfin Library Configuration
To ensure Jellyfin reads NFO files:
1. Library Settings → Advanced → NFO mode: Enable "Local Metadata"
2. Metadata savers: Enable "NFO"
3. Metadata readers: Set priority for "NFO" high

### Error Scenarios to Handle

**Critical Errors (Skip NFO generation and log):**
- **info.json file missing**: If .info.json doesn't exist, skip NFO generation entirely (critical dependency)
- **info.json file corrupted**: If JSON parsing fails, skip NFO generation and log error with file path
- **Missing required fields**: If `title` or `channel` fields are missing from info.json, skip NFO generation and log warning

**Recoverable Errors (Generate NFO with available data):**
- **Missing optional fields**: Generate NFO with available data, omit missing optional fields
- **Invalid characters in XML**: ElementTree handles escaping automatically, but log if unexpected characters cause issues
- **File write permissions**: Log error with file path, mark channel NFO generation as failed, continue with other channels
- **Disk space issues**: Log error, mark generation as failed, alert user via notification

**Concurrency Errors:**
- **Concurrent NFO access**: Use file locking or atomic writes to prevent corruption
- **Multiple regeneration requests**: Queue requests and process sequentially per channel
