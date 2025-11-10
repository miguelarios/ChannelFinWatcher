"""
NFO File Generation Service for Jellyfin Metadata

This service generates Jellyfin-compatible NFO metadata files from yt-dlp JSON metadata.
NFO files allow Jellyfin to display rich metadata (descriptions, dates, tags, etc.) for
YouTube channel content organized as TV shows.

Architecture:
- Service class pattern (matches existing codebase: video_download_service, metadata_service)
- Dependency injection for configuration and paths
- Graceful error handling (NFO failures don't block downloads)
- Atomic file writes (temp file + rename pattern)

File Types Generated:
- tvshow.nfo: Channel-level metadata (show description, genres, tags)
- season.nfo: Year-based season metadata (minimal, just year/title)
- episode.nfo: Video-level metadata (title, description, aired date, runtime, etc.)
"""

import os
import json
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, List
import xml.etree.ElementTree as ET
from xml.dom import minidom

logger = logging.getLogger(__name__)


class NFOService:
    """
    Service for generating and managing Jellyfin NFO metadata files.

    Why a service class?
    - Encapsulates NFO generation logic separate from download logic (Single Responsibility)
    - Allows dependency injection of config values (media path, enable/disable flags)
    - Makes testing easier (can mock the service)
    - Follows existing pattern in codebase (VideoDownloadService, MetadataService)
    """

    def __init__(self, media_path: str = "/media/YouTube"):
        """
        Initialize NFO service with media library path.

        Args:
            media_path: Root directory for YouTube downloads (default: /media/YouTube)

        Why pass media_path?
        - Makes service testable with different paths
        - Allows configuration override without changing code
        - Matches pattern in video_download_service.py:34
        """
        self.media_path = media_path
        logger.info(f"NFOService initialized with media_path: {media_path}")

    # =========================================================================
    # EPISODE NFO GENERATION
    # =========================================================================

    def generate_episode_nfo(
        self,
        video_file_path: str,
        channel
    ) -> Tuple[bool, Optional[str]]:
        """
        Generate episode.nfo file for a downloaded video.

        This is called AFTER a video download completes successfully.
        It reads the .info.json file created by yt-dlp and transforms it into
        Jellyfin-compatible episode.nfo XML format.

        Args:
            video_file_path: Full path to video file (e.g., "/media/.../video.mkv")
            channel: Channel database object (for channel name, metadata path, etc.)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            - (True, None) if NFO created successfully
            - (False, error_msg) if generation failed

        Why return tuple instead of raising exceptions?
        - NFO generation failures should NOT block video downloads
        - Caller can log error but continue processing other videos
        - Matches pattern in video_download_service.py:download_video()

        Example:
            success, error = nfo_service.generate_episode_nfo(
                "/media/YouTube/Channel [ID]/2021/Video [ID]/video.mkv",
                channel_obj
            )
            if not success:
                logger.warning(f"NFO generation failed: {error}")
                # Continue anyway - video download was successful
        """
        try:
            # Step 1: Construct path to .info.json file
            # yt-dlp creates .info.json with same basename as video file
            info_json_path = self._get_info_json_path(video_file_path)

            # Step 2: Verify .info.json exists (critical dependency)
            # Why check? yt-dlp has ignoreerrors=True, so it might fail silently
            if not os.path.exists(info_json_path):
                error_msg = f"Info JSON not found: {info_json_path}"
                logger.warning(error_msg)
                return False, error_msg

            # Step 3: Load and parse JSON metadata
            episode_info = self._load_json_file(info_json_path)
            if not episode_info:
                return False, f"Failed to parse JSON: {info_json_path}"

            # Step 4: Validate required fields (title and channel are essential)
            # Why validate? Corrupted metadata should skip NFO generation gracefully
            if not episode_info.get('title') or not episode_info.get('channel'):
                error_msg = f"Missing required fields (title/channel) in {info_json_path}"
                logger.warning(error_msg)
                return False, error_msg

            # Step 5: Generate XML content from JSON metadata
            nfo_content = self._create_episode_nfo_xml(episode_info)

            # Step 6: Write NFO file (same basename as video, .nfo extension)
            nfo_path = video_file_path.replace('.mkv', '.nfo').replace('.mp4', '.nfo').replace('.webm', '.nfo')
            self._write_nfo_file(nfo_path, nfo_content)

            logger.info(f"✓ Generated episode NFO: {nfo_path}")
            return True, None

        except Exception as e:
            error_msg = f"Episode NFO generation failed: {str(e)}"
            logger.error(f"{error_msg} (video: {video_file_path})")
            return False, error_msg

    def _create_episode_nfo_xml(self, episode_info: dict) -> bytes:
        """
        Create episode.nfo XML content from yt-dlp metadata.

        This is where the actual JSON → XML transformation happens.
        We map yt-dlp fields to Jellyfin's expected NFO schema.

        Args:
            episode_info: Dictionary from .info.json file

        Returns:
            Pretty-printed XML as UTF-8 encoded bytes

        Why return bytes instead of string?
        - XML files should be written in binary mode with proper encoding
        - prettify_xml() returns bytes with UTF-8 BOM declaration
        - File write operations work with bytes for proper character encoding

        Field Mapping (see story-008 docs line 789-840):
        JSON Field          → NFO Tag         | Transformation
        --------------------------------------------------------------
        title               → <title>         | Direct copy
        channel             → <showtitle>     | Direct copy (show name)
        description         → <plot>          | Direct copy (newlines preserved)
        upload_date         → <premiered>     | Format: 20211207 → 2021-12-07
        upload_date         → <aired>         | Format: 20211207 → 2021-12-07
        upload_date         → <year>          | Extract: 20211207 → 2021
        duration (seconds)  → <runtime>       | Convert: 922 → 15 (minutes)
        uploader            → <director>      | Direct copy
        id                  → <uniqueid>      | Wrap with type="youtube"
        categories[]        → <genre>         | One tag per category
        tags[]              → <tag>           | One tag per tag
        language            → <language>      | ISO 639-1 (en, es, etc.)
        """
        root = ET.Element('episodedetails')

        # Required: Episode title
        ET.SubElement(root, 'title').text = episode_info.get('title', 'Unknown Title')

        # Required: Show title (channel name)
        # Why showtitle? Jellyfin uses this to group episodes into shows
        ET.SubElement(root, 'showtitle').text = episode_info.get('channel', '')

        # Description/plot (preserves newlines automatically)
        # Why always create? Jellyfin expects plot element even if empty
        # Why no manual newline handling? ElementTree preserves them as-is
        description = episode_info.get('description', '')
        plot_elem = ET.SubElement(root, 'plot')
        if description:
            plot_elem.text = description

        # Optional: Language (ISO 639-1 codes: "en", "es", "fr", etc.)
        language = episode_info.get('language')
        if language:
            ET.SubElement(root, 'language').text = language

        # Date fields (upload_date format: YYYYMMDD)
        upload_date = episode_info.get('upload_date')
        if upload_date:
            try:
                # Transform YYYYMMDD → YYYY-MM-DD for Jellyfin <premiered> and <aired> tags
                # Why strptime/strftime? Safe date parsing with validation
                aired_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y-%m-%d")
                ET.SubElement(root, 'premiered').text = aired_date
                ET.SubElement(root, 'aired').text = aired_date

                # Extract year for <year> tag
                # Why separate year tag? Jellyfin uses it for filtering/sorting
                ET.SubElement(root, 'year').text = upload_date[:4]
            except ValueError as e:
                # Invalid date format - skip these fields
                logger.warning(f"Invalid upload_date format: {upload_date}")

        # Duration: Convert seconds to minutes (integer division)
        # Why minutes? Jellyfin expects <runtime> in minutes, not seconds
        # Example: 922 seconds → 15 minutes
        duration = episode_info.get('duration')
        if duration and duration > 0:
            runtime_minutes = duration // 60  # Floor division
            ET.SubElement(root, 'runtime').text = str(runtime_minutes)

        # Optional: Uploader/creator → director
        # Why director? Best semantic match in Jellyfin for content creator
        uploader = episode_info.get('uploader')
        if uploader:
            ET.SubElement(root, 'director').text = uploader

        # Studio: Always "YouTube"
        # Why hardcode? All content comes from YouTube platform
        ET.SubElement(root, 'studio').text = 'YouTube'

        # Unique ID: YouTube video ID
        # Why uniqueid? Allows Jellyfin to track videos across library rebuilds
        video_id = episode_info.get('id')
        if video_id:
            uniqueid_elem = ET.SubElement(root, 'uniqueid', type='youtube', default='true')
            uniqueid_elem.text = video_id

        # Genres: From categories array (broad categorization)
        # Example: ["Howto & Style", "Entertainment"]
        # Why categories → genre? YouTube categories are broad topic classifications
        for category in episode_info.get('categories', []):
            ET.SubElement(root, 'genre').text = category

        # Tags: From tags array (specific descriptors)
        # Example: ["mexican cocktails", "tequila cocktails", "cocktail recipe"]
        # Why separate from genres? Tags are user-defined, more specific than categories
        for tag in episode_info.get('tags', []):
            ET.SubElement(root, 'tag').text = tag

        # Date added: When file was added to library (current timestamp)
        # Why current time? This is when the video entered our library
        dateadded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ET.SubElement(root, 'dateadded').text = dateadded

        # Convert to pretty-printed XML with proper formatting
        return self._prettify_xml(root)

    # =========================================================================
    # SEASON NFO GENERATION
    # =========================================================================

    def generate_season_nfo(self, year_dir_path: str) -> Tuple[bool, Optional[str]]:
        """
        Generate season.nfo file for a year-based season directory.

        In ChannelFinWatcher, videos are organized by upload year (2021/, 2022/, etc.).
        Jellyfin treats each year as a "season" of the TV show.

        Season NFO files are very simple - just the year as title/season number.

        Args:
            year_dir_path: Path to year directory (e.g., "/media/.../Channel [ID]/2021/")

        Returns:
            Tuple of (success: bool, error_message: Optional[str])

        When to call:
        - When the first episode of a new year is downloaded
        - During batch regeneration
        - Check if season.nfo already exists to avoid unnecessary writes
        """
        try:
            # Extract year from directory path
            # Example: "/media/YouTube/Channel [ID]/2021/" → "2021"
            year = os.path.basename(year_dir_path.rstrip('/'))

            # Validate year format (should be 4-digit number)
            if not year.isdigit() or len(year) != 4:
                error_msg = f"Invalid year directory: {year_dir_path}"
                logger.warning(error_msg)
                return False, error_msg

            # Generate XML content
            nfo_content = self._create_season_nfo_xml(year)

            # Write season.nfo file
            nfo_path = os.path.join(year_dir_path, 'season.nfo')
            self._write_nfo_file(nfo_path, nfo_content)

            logger.info(f"✓ Generated season NFO: {nfo_path}")
            return True, None

        except Exception as e:
            error_msg = f"Season NFO generation failed: {str(e)}"
            logger.error(f"{error_msg} (year_dir: {year_dir_path})")
            return False, error_msg

    def _create_season_nfo_xml(self, year: str) -> bytes:
        """
        Create season.nfo XML content for year-based seasons.

        Season NFO includes:
        - Title: The year (e.g., "2025")
        - Season number: The year (e.g., 2025)
        - Premiered: Always January 1st of the year (e.g., "2025-01-01")
        - Release date: Same as premiered
        - Date added: Current timestamp
        - Lock data: Set to false (allows Jellyfin to update metadata)

        Args:
            year: Year string (e.g., "2021")

        Returns:
            Pretty-printed XML as UTF-8 encoded bytes
        """
        root = ET.Element('season')

        # Empty plot and outline (season has no description)
        # Why empty tags? Jellyfin expects these but we have no season-level descriptions
        ET.SubElement(root, 'plot')
        ET.SubElement(root, 'outline')

        # Lock data: false allows Jellyfin to update metadata if needed
        ET.SubElement(root, 'lockdata').text = 'false'

        # Current timestamp for when season was created
        dateadded = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ET.SubElement(root, 'dateadded').text = dateadded

        # Title and year both use the year value
        ET.SubElement(root, 'title').text = str(year)
        ET.SubElement(root, 'year').text = str(year)

        # Premiered and releasedate: Always January 1st of the year
        # Why January 1st? Provides consistent date for season organization
        # regardless of when first video was actually uploaded
        jan_first = f"{year}-01-01"
        ET.SubElement(root, 'premiered').text = jan_first
        ET.SubElement(root, 'releasedate').text = jan_first

        # Season number: Use the year for chronological sorting
        ET.SubElement(root, 'seasonnumber').text = str(year)
        ET.SubElement(root, 'season').text = str(year)

        return self._prettify_xml(root)

    # =========================================================================
    # TVSHOW NFO GENERATION
    # =========================================================================

    def generate_tvshow_nfo(
        self,
        channel_metadata_path: str,
        channel_dir: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Generate tvshow.nfo file for a channel (TV show level metadata).

        This reads the channel-level .info.json file and creates show-level metadata.
        Called when:
        - A new channel is added to monitoring
        - Channel metadata is manually refreshed
        - Batch regeneration is triggered

        Args:
            channel_metadata_path: Path to channel .info.json file
            channel_dir: Path to channel root directory

        Returns:
            Tuple of (success: bool, error_message: Optional[str])

        Important: Channel info.json does NOT have a 'categories' field
        (only episode-level info.json has categories). We map 'tags' to
        both <genre> and <tag> for completeness.
        """
        try:
            # Verify channel metadata file exists
            if not os.path.exists(channel_metadata_path):
                error_msg = f"Channel metadata not found: {channel_metadata_path}"
                logger.warning(error_msg)
                return False, error_msg

            # Load channel metadata JSON
            channel_info = self._load_json_file(channel_metadata_path)
            if not channel_info:
                return False, f"Failed to parse channel metadata: {channel_metadata_path}"

            # Validate required field (channel name)
            if not channel_info.get('channel'):
                error_msg = f"Missing 'channel' field in {channel_metadata_path}"
                logger.warning(error_msg)
                return False, error_msg

            # Generate XML content
            nfo_content = self._create_tvshow_nfo_xml(channel_info)

            # Write tvshow.nfo to channel root directory
            nfo_path = os.path.join(channel_dir, 'tvshow.nfo')
            self._write_nfo_file(nfo_path, nfo_content)

            logger.info(f"✓ Generated tvshow NFO: {nfo_path}")
            return True, None

        except Exception as e:
            error_msg = f"Tvshow NFO generation failed: {str(e)}"
            logger.error(f"{error_msg} (channel: {channel_dir})")
            return False, error_msg

    def _create_tvshow_nfo_xml(self, channel_info: dict) -> bytes:
        """
        Create tvshow.nfo XML content from channel metadata.

        Field Mapping (see story-008 docs line 773-786):
        JSON Field    → NFO Tag           | Notes
        --------------------------------------------------------
        channel       → <title>           | Channel name
        description   → <plot>            | Channel description
        id/channel_id → <uniqueid>        | YouTube channel ID
        hardcoded     → <studio>          | Always "YouTube"
        tags[]        → <tag>             | One tag per tag

        Args:
            channel_info: Dictionary from channel .info.json file

        Returns:
            Pretty-printed XML as UTF-8 encoded bytes
        """
        root = ET.Element('tvshow')

        # Channel name → title
        # Why just title? Simplified from previous implementation
        channel_name = channel_info.get('channel', '')
        ET.SubElement(root, 'title').text = channel_name

        # Channel description → plot
        description = channel_info.get('description', '')
        if description:
            ET.SubElement(root, 'plot').text = description

        # Unique ID: YouTube channel ID
        # Why uniqueid? Allows Jellyfin to track channels across library rebuilds
        # Try 'id' first, fallback to 'channel_id'
        channel_id = channel_info.get('id') or channel_info.get('channel_id')
        if channel_id:
            uniqueid_elem = ET.SubElement(root, 'uniqueid', type='youtube', default='true')
            uniqueid_elem.text = channel_id

        # Studio: Always YouTube
        ET.SubElement(root, 'studio').text = 'YouTube'

        # Channel tags → tags only (no genres)
        # Why tags only? Simpler metadata structure, tags are more specific
        for tag in channel_info.get('tags', []):
            ET.SubElement(root, 'tag').text = tag

        return self._prettify_xml(root)

    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================

    def _get_info_json_path(self, video_file_path: str) -> str:
        """
        Construct .info.json file path from video file path.

        Why a separate function?
        - Handles multiple video extensions (.mkv, .mp4, .webm, etc.)
        - Single source of truth for path construction
        - Easy to test independently

        Args:
            video_file_path: Path to video file

        Returns:
            Path to corresponding .info.json file
        """
        # Replace video extension with .info.json
        for ext in ['.mkv', '.mp4', '.webm', '.m4v', '.avi']:
            if video_file_path.endswith(ext):
                return video_file_path.replace(ext, '.info.json')

        # Fallback: just append .info.json
        return f"{video_file_path}.info.json"

    def _load_json_file(self, json_path: str) -> Optional[dict]:
        """
        Load and parse JSON file with error handling.

        Why separate function?
        - Consistent error handling across all JSON loads
        - Logs specific parse errors for debugging
        - Returns None on failure (graceful degradation)

        Args:
            json_path: Path to JSON file

        Returns:
            Parsed JSON as dictionary, or None if failed
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in {json_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to load JSON {json_path}: {e}")
            return None

    def _prettify_xml(self, elem: ET.Element) -> bytes:
        """
        Convert ElementTree element to pretty-printed XML bytes.

        Why pretty-print?
        - Human-readable NFO files (easier to debug/inspect)
        - Proper indentation (4 spaces per level)
        - UTF-8 encoding with XML declaration

        Why return bytes?
        - XML files should declare encoding in <?xml?> header
        - Writing bytes ensures proper encoding handling
        - Prevents Unicode errors on non-ASCII characters

        Args:
            elem: ElementTree Element (root of XML tree)

        Returns:
            UTF-8 encoded XML as bytes
        """
        # Convert to rough XML string
        rough_string = ET.tostring(elem, encoding='utf-8')

        # Parse and pretty-print with minidom
        reparsed = minidom.parseString(rough_string)

        # Return with 4-space indentation
        return reparsed.toprettyxml(indent="    ", encoding="utf-8")

    def _write_nfo_file(self, nfo_path: str, xml_content: bytes) -> None:
        """
        Write NFO content to file using atomic write pattern.

        Why atomic writes?
        - Prevents partial writes if process is interrupted
        - Temp file + rename is atomic on POSIX systems
        - If write fails, original file (if exists) is unchanged

        Pattern:
        1. Write to temporary file (.tmp suffix)
        2. Rename to final path (overwrites existing atomically)
        3. Clean up temp file on error

        This pattern is suggested in story-008 docs (line 641-648)

        Args:
            nfo_path: Destination path for NFO file
            xml_content: UTF-8 encoded XML bytes

        Raises:
            IOError: If file write fails (caller handles exception)
        """
        temp_path = f"{nfo_path}.tmp"

        try:
            # Create parent directory if it doesn't exist
            # Why? Season.nfo directory might not exist yet
            os.makedirs(os.path.dirname(nfo_path), exist_ok=True)

            # Write to temp file in binary mode (xml_content is bytes)
            with open(temp_path, 'wb') as f:
                f.write(xml_content)

            # Atomic rename (overwrites existing file)
            # Why atomic? Prevents corrupted NFO files if interrupted
            os.rename(temp_path, nfo_path)

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise IOError(f"Failed to write NFO file {nfo_path}: {e}")


# =========================================================================
# CONVENIENCE FUNCTIONS (For easy importing in other modules)
# =========================================================================

# Global service instance (initialized on first import)
# Why global? Matches pattern in codebase, allows simple imports
_nfo_service_instance = None


def get_nfo_service() -> NFOService:
    """
    Get or create global NFO service instance.

    Why singleton pattern?
    - NFOService is stateless (no per-request state)
    - Avoids creating multiple instances unnecessarily
    - Allows easy dependency injection for testing

    Returns:
        Global NFOService instance
    """
    global _nfo_service_instance
    if _nfo_service_instance is None:
        _nfo_service_instance = NFOService()
    return _nfo_service_instance