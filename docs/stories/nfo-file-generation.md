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
- **episode.nfo**: Generated immediately after each episode download (metadata is available early in download process)
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
  - And the NFO contains `<originaltitle>` populated from `channel` field
  - And the NFO contains `<showtitle>` populated from `channel` field
  - And the NFO contains `<plot>` populated from `description` field
  - And the NFO contains `<studio>YouTube</studio>`
  - And the NFO contains `<genre>` tags for each item in the `tags` array
  - And the NFO contains matching `<tag>` elements for each genre

#### [ ] Scenario: Generate season.nfo when first episode of year is downloaded
- **Given** a video is being downloaded from a monitored channel
  - And the video's upload year creates a new year folder (e.g., `/2021/`)
  - And no season.nfo exists yet in that year folder
- **When** the first episode download begins and the year folder is created
- **Then** a `season.nfo` file is automatically created in the year directory
  - And the NFO contains `<title>` with the year (e.g., "2021")
  - And the NFO contains `<dateadded>` with the current timestamp in format `YYYY-MM-DD HH:MM:SS`
  - And the NFO contains empty `<plot />` and `<outline />` tags
  - And the NFO contains empty `<art />` tag

#### [ ] Scenario: Generate episode.nfo immediately after episode metadata is downloaded
- **Given** a video is being downloaded from a monitored channel
  - And yt-dlp creates the `.info.json` file with episode metadata
  - And the info.json contains fields: `title`, `description`, `upload_date`, `uploader`, `duration`, `tags`, `id`, `channel`, `channel_id`
- **When** the episode info.json file is written to disk (early in download process)
- **Then** an NFO file named `<basename>.nfo` is immediately created
  - And the NFO contains `<title>` from the `title` field
  - And the NFO contains `<showtitle>` from the `channel` field
  - And the NFO contains `<plot>` from the `description` field
  - And the NFO contains `<aired>` from `upload_date` field (formatted as YYYY-MM-DD)
  - And the NFO contains `<dateadded>` with the file creation time
  - And the NFO contains `<year>` extracted from `upload_date`
  - And the NFO contains `<runtime>` from `duration` field (converted to minutes)
  - And the NFO contains `<director>` tags populated from `uploader` field
  - And the NFO contains `<genre>` tags for each item in the `tags` array
  - And the NFO contains `<uniqueid type="youtube">` with the video `id`
  - And the NFO contains `<studio>YouTube</studio>`
  - But the video file download may still be in progress

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

### Non-functional Requirements
- **Performance:** NFO generation should complete for 1000 episodes within 10 seconds
- **Reliability:** Invalid or malformed JSON files should be logged and skipped without crashing the process
- **Usability:** Provide clear logging of which NFO files were created, skipped, or failed
- **Maintainability:** NFO generation logic should be modular and testable independently of download logic

### Dependencies
- **Blocked by:** None (can be developed independently)
- **Blocks:** None (enhancement to existing functionality)

### Engineering TODOs
- [ ] Research Jellyfin NFO XML schema validation requirements
- [ ] Determine if NFO generation should be part of post-download processing or a separate scheduled task
- [ ] Decide on configuration options: auto-generate on download, batch process, overwrite vs preserve
- [ ] Investigate if we need to handle special characters or encoding issues in XML output

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
  - [ ] Config option to enable/disable auto NFO generation
  - [ ] Config option to overwrite existing NFO files vs preserve
  - [ ] Config option to specify which NFO types to generate (show/season/episode)
  - [ ] Default configuration added to config/config.yaml

#### 3. [ ] Backend - Integrate NFO Generation into Download Workflow
- **Description:** Hook NFO generation into post-download processing
- **Estimation:** 4 hours
- **Acceptance Criteria:** 
  - [ ] NFO files are automatically generated after video download completes
  - [ ] NFO generation respects configuration settings
  - [ ] Failed NFO generation does not block download completion
  - [ ] NFO generation status is reflected in download logs

#### 4. [ ] Backend - Create Batch NFO Generation Endpoint
- **Description:** Create API endpoint to regenerate NFO files for existing media library
- **Estimation:** 4 hours
- **Acceptance Criteria:** 
  - [ ] API endpoint accepts channel/directory path parameter
  - [ ] Endpoint can process entire channel or specific season
  - [ ] Endpoint returns summary of files created/skipped/failed
  - [ ] Endpoint respects overwrite configuration
  - [ ] Endpoint is rate-limited to prevent resource exhaustion

#### 5. [ ] Testing - Unit Tests for NFO Generator
- **Description:** Write comprehensive unit tests for NFO generation logic
- **Estimation:** 4 hours
- **Acceptance Criteria:** 
  - [ ] Test tvshow.nfo generation with complete metadata
  - [ ] Test tvshow.nfo generation with minimal metadata
  - [ ] Test season.nfo generation for playlist and year directories
  - [ ] Test episode.nfo generation with all fields
  - [ ] Test episode.nfo generation with missing optional fields
  - [ ] Test XML validation and character escaping
  - [ ] Test file overwrite vs preserve logic

#### 6. [ ] Testing - Integration Tests for NFO Workflow
- **Description:** Test end-to-end NFO generation in download workflow
- **Estimation:** 3 hours
- **Acceptance Criteria:** 
  - [ ] Test NFO generation triggered by successful download
  - [ ] Test NFO generation with existing files (overwrite mode)
  - [ ] Test NFO generation with existing files (preserve mode)
  - [ ] Test error handling when info.json is malformed
  - [ ] Test batch generation endpoint

#### 7. [ ] Frontend - Add NFO Management UI
- **Description:** Add UI controls for NFO generation settings and manual triggers, including kebab menu option on channel cards
- **Estimation:** 6 hours
- **Acceptance Criteria:** 
  - [ ] Settings page has NFO generation configuration options
  - [ ] Channel card on dashboard has kebab menu (⋮) with "Regenerate NFO Files" option
  - [ ] Clicking "Regenerate NFO Files" shows confirmation dialog
  - [ ] Batch operation shows progress indicator with percentage/counts
  - [ ] Summary notification displays results (created/updated/failed counts)
  - [ ] UI displays NFO generation status in download history
  - [ ] UI shows validation errors for failed NFO generation

#### 8. [ ] Documentation - NFO Feature Documentation
- **Description:** Document NFO generation feature for users and developers
- **Estimation:** 2 hours
- **Acceptance Criteria:** 
  - [ ] User guide explains NFO generation feature
  - [ ] User guide shows Jellyfin configuration for NFO files
  - [ ] Technical docs explain NFO XML structure and mapping
  - [ ] API documentation updated for batch generation endpoint
  - [ ] Configuration reference updated with NFO settings

---

## Definition of Done

### Must Have
- [ ] tvshow.nfo, season.nfo, and episode.nfo files are generated with correct Jellyfin schema
- [ ] NFO files contain all available metadata from info.json files
- [ ] Configuration options work as documented
- [ ] Unit and integration tests pass
- [ ] Basic user documentation exists

### Should Have  
- [ ] Frontend UI for manual NFO regeneration
- [ ] Batch NFO generation API endpoint
- [ ] Comprehensive error handling and logging
- [ ] Performance acceptable for large media libraries

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
    <originaltitle>Steve the Bartender</originaltitle>
    <showtitle>Steve the Bartender</showtitle>
    <plot>
Want to know more about about Steve the Bartender? 
        
I have 20+ years of experience working in the hospitality industry...
    </plot>
    <studio>YouTube</studio>
    <genre>Bartender</genre>
    <genre>Cocktails</genre>
    <genre>Recipe</genre>
    <tag>Youtube</tag>
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
  <art />
</season>
```

### Example Episode-Level info.json Structure
```json
{
  "id": "Day4-sm3U1s",
  "title": "Paloma 3 Ways - Classic, Upgraded & Clarified!",
  "description": "Celebrating Patrón's Paloma Week...",
  "upload_date": "20211207",
  "uploader": "Steve the Bartender",
  "duration": 922,
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
    <aired>2021-12-07</aired>
    <year>2021</year>
    <runtime>15</runtime>
    <director>Steve the Bartender</director>
    <studio>YouTube</studio>
    <uniqueid type="youtube" default="true">Day4-sm3U1s</uniqueid>
    <genre>mexican cocktails</genre>
    <genre>tequila cocktails</genre>
    <genre>cocktail recipe</genre>
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
- `title`, `originaltitle`, `showtitle` - Show names
- `plot` - Show description
- `studio` - Studio/network (multiple allowed)
- `genre` - Multiple tags allowed
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

def prettify_xml(elem):
    """Return a pretty-printed XML string."""
    rough_string = ET.tostring(elem, encoding='utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="    ", encoding="utf-8")

def generate_tvshow_nfo(channel_info):
    """Generate tvshow.nfo from channel info.json"""
    root = ET.Element('tvshow')
    
    ET.SubElement(root, 'title').text = channel_info.get('channel', '')
    ET.SubElement(root, 'originaltitle').text = channel_info.get('channel', '')
    ET.SubElement(root, 'showtitle').text = channel_info.get('channel', '')
    ET.SubElement(root, 'plot').text = channel_info.get('description', '')
    ET.SubElement(root, 'studio').text = 'YouTube'
    
    for tag in channel_info.get('tags', []):
        ET.SubElement(root, 'genre').text = tag
        ET.SubElement(root, 'tag').text = tag
    
    return prettify_xml(root)
```

### File System Layout Example
```
/media/YouTube/Cocktails/
└── Steve the Bartender [UCfEJUzPnT-HdNqOqdX3A0lA]/
    ├── Steve the Bartender [@StevetheBartender_].info.json  # Channel metadata
    ├── tvshow.nfo                                             # Generated from above
    ├── 2021/                                                  # Season folder
    │   ├── season.nfo                                         # Generated (title="2021")
    │   └── Steve the Bartender - 20211207 - Paloma 3 Ways [Day4-sm3U1s]/
    │       ├── Steve the Bartender - 20211207 - Paloma 3 Ways [Day4-sm3U1s].mkv
    │       ├── Steve the Bartender - 20211207 - Paloma 3 Ways [Day4-sm3U1s].info.json
    │       └── Steve the Bartender - 20211207 - Paloma 3 Ways [Day4-sm3U1s].nfo  # Generated
    └── Cocktail Prep - Syrups, liqueurs, shrubs & cordials/  # Playlist folder
        ├── season.nfo                                         # Generated (title="Cocktail Prep...")
        └── Liqueurs - Allspice liqueur/
            ├── Liqueurs - Allspice liqueur.mkv
            ├── Liqueurs - Allspice liqueur.info.json
            └── Liqueurs - Allspice liqueur.nfo                # Generated
```

### Important Implementation Notes
1. **XML Escaping**: All text content must be properly XML-escaped (handle &, <, >, ", ')
2. **Duration Conversion**: yt-dlp provides duration in seconds, Jellyfin expects minutes in `<runtime>`
3. **Date Formatting**: 
   - `upload_date` from yt-dlp is in YYYYMMDD format
   - Jellyfin `<aired>` expects YYYY-MM-DD
   - Jellyfin `<dateadded>` expects YYYY-MM-DD HH:MM:SS
4. **Missing Data**: Handle cases where optional fields are None/null/missing
5. **File Naming**: Episode NFO must match video filename exactly (minus extension)
6. **UTF-8 Encoding**: Always use UTF-8 encoding with BOM declaration in XML header

### Jellyfin Library Configuration
To ensure Jellyfin reads NFO files:
1. Library Settings → Advanced → NFO mode: Enable "Local Metadata"
2. Metadata savers: Enable "NFO"
3. Metadata readers: Set priority for "NFO" high

### Error Scenarios to Handle
- info.json file missing or corrupted
- Missing required fields (title, channel)
- Invalid characters in XML content
- File write permissions issues
- Disk space issues
- Concurrent access to same NFO file
