"""Video download service for YouTube channels using yt-dlp."""
import os
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
import yt_dlp

from app.models import Channel, Download, DownloadHistory
from app.config import get_settings
from app.utils import channel_dir_name

logger = logging.getLogger(__name__)


class VideoDownloadService:
    """
    Service for downloading videos from YouTube channels using yt-dlp.
    
    This service handles the core video download functionality, including:
    - Querying channels for recent videos without downloading
    - Downloading individual videos with proper organization
    - Sequential processing of multiple videos per channel
    - Status tracking and error handling
    
    Key Features:
    - Uses database records to prevent duplicate downloads
    - Organizes files in Jellyfin-compatible directory structure
    - Sequential downloads to avoid overwhelming system resources
    - Comprehensive error handling for network and storage issues
    
    Example:
        service = VideoDownloadService()
        success, count, error = service.process_channel_downloads(channel, db)
        if success:
            print(f"Downloaded {count} new videos")
    """
    
    def __init__(self):
        """
        Initialize the video download service with yt-dlp configuration.
        
        Configuration based on the reference bash script from Story 5,
        optimized for Jellyfin directory structure and reliable downloads.
        """
        settings = get_settings()
        
        # Base paths for media organization
        self.media_path = settings.media_dir
        self.temp_path = settings.temp_dir
        
        # Configuration file path
        self.cookie_file = settings.cookies_file
        
        # Ensure required directories exist
        os.makedirs(self.media_path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)
        
        # yt-dlp configuration for video downloads
        # Based on exact parameters from TDD reference bash script
        # Added anti-bot detection headers
        # Multi-client fallback strategy to handle YouTube changes
        self.download_opts = {
            'paths': {
                'temp': self.temp_path,
                'home': self.media_path
            },
            'outtmpl': '%(channel)s [%(channel_id)s]/%(upload_date>%Y)s/%(channel)s - %(upload_date)s - %(title)s [%(id)s]/%(channel)s - %(upload_date)s - %(title)s [%(id)s].%(ext)s',
            'format': 'bv*+ba/b',  # Best video + best audio
            'merge_output_format': 'mkv',
            'writeinfojson': True,
            'writethumbnail': True,
            'embedthumbnail': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'es', '-live_chat'],
            'embedsubtitles': True,
            'addmetadata': True,
            'embedmetadata': True,
            'parse_metadata': [
                'description:(?s)(?P<meta_comment>.+)',
                'upload_date:(?s)(?P<meta_DATE_RELEASED>.+)',
                'uploader:%(meta_ARTIST)s'
            ],
            'concurrent_fragments': 4,
            'ignoreerrors': True,  # Continue on individual video errors
            'no_warnings': False,  # Show warnings for troubleshooting
            # NOTE: Removed extractor_args player_client override
            # yt-dlp 2025.09.26+ has smart automatic client selection that works better
            # than manual overrides. Let yt-dlp choose the optimal client for each video.
            # Anti-bot detection headers
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            },
            'sleep_interval': 1,        # Wait 1 second between requests
            'max_sleep_interval': 5,    # Random sleep up to 5 seconds
        }
        
        # Add cookie file if it exists for age-restricted content
        if os.path.exists(self.cookie_file):
            self.download_opts['cookiefile'] = self.cookie_file
        
        # Query-only configuration for getting recent videos
        # Using flat-playlist approach for fast, lightweight video ID extraction
        self.query_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,   # Flat playlist - only get IDs and titles (like --flat-playlist)
            'ignoreerrors': True,
            'match_filter': self._filter_shorts,  # Filter out YouTube Shorts at extraction time
            # NOTE: Removed extractor_args player_client override
            # yt-dlp 2025.09.26+ automatically selects optimal client
            # Minimal headers to avoid bot detection during light queries
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
            'sleep_interval': 1,
            'max_sleep_interval': 2,  # Shorter sleep for lighter requests
        }
        
        # Add cookie file to query_opts for auth/region context
        if os.path.exists(self.cookie_file):
            self.query_opts['cookiefile'] = self.cookie_file

    def _filter_shorts(self, info, *, incomplete):
        """
        Filter to exclude YouTube Shorts during yt-dlp extraction.

        This function is called by yt-dlp for each video during extraction.
        It allows us to skip shorts at the source, so yt-dlp automatically
        fetches additional videos to meet the requested limit.

        Checks in order:
        1. URL pattern (/shorts/) - most definitive indicator
        2. Duration (≤60 seconds) - fallback for edge cases

        Args:
            info: Video information dict from yt-dlp
            incomplete: Whether extraction is incomplete (required by yt-dlp)

        Returns:
            None to accept video, string reason to reject it
        """
        # Check URL first (most reliable indicator)
        url = info.get('url', '') or info.get('webpage_url', '')
        if '/shorts/' in url:
            return 'YouTube Short (URL pattern)'

        # Fallback to duration check (catches shorts in playlists)
        duration = info.get('duration')
        if duration and duration <= 60:
            return 'YouTube Short (≤60s duration)'

        return None  # Accept the video

    def _extract_video_id(self, entry: Dict) -> Optional[str]:
        """
        Extract video ID from various entry formats.
        
        YouTube entries can provide video IDs in multiple ways:
        - Direct 'id' field
        - Embedded in 'url' field (watch?v=, youtu.be/, shorts/)
        
        Args:
            entry: Dictionary containing video entry data
            
        Returns:
            11-character video ID if found, None otherwise
        """
        import re
        
        # Try direct ID first
        video_id = entry.get('id')
        if video_id and len(video_id) == 11 and video_id.isalnum():
            return video_id
        
        # Parse from URL if available
        url = entry.get('url', '') or entry.get('webpage_url', '')
        if not url:
            return None
        
        # Match common YouTube URL patterns
        patterns = [
            r'watch\?v=([a-zA-Z0-9_-]{11})',      # youtube.com/watch?v=...
            r'youtu\.be/([a-zA-Z0-9_-]{11})',     # youtu.be/...
            r'shorts/([a-zA-Z0-9_-]{11})',        # youtube.com/shorts/...
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                extracted_id = match.group(1)
                if len(extracted_id) == 11:
                    return extracted_id
        
        return None
    
    def should_download_video(self, video_id: str, channel: Channel, db: Session) -> Tuple[bool, Optional[Download]]:
        """
        Determine if a video should be downloaded based on database and disk state.
        
        Args:
            video_id: YouTube video ID
            channel: Channel database model
            db: Database session
        
        Returns:
            Tuple of (should_download, existing_download_record)
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
        """
        Check if video file exists on disk by looking for [video_id] in filename.

        Only matches actual video files, not metadata (.info.json), thumbnails, or subtitles.
        Uses the same video extension list as _find_video_file_path for consistency.
        """
        if not os.path.exists(media_path):
            return False

        # Video file extensions - must match _find_video_file_path
        video_extensions = ('.mkv', '.mp4', '.webm', '.avi', '.mov', '.flv', '.m4v', '.3gp')

        for root, dirs, files in os.walk(media_path):
            for file in files:
                # Must contain video ID AND be an actual video file AND not be a partial download
                if (f"[{video_id}]" in file and
                    file.lower().endswith(video_extensions) and
                    not file.endswith('.part')):
                    return True
        return False

    def _find_video_file_path(self, video_id: str, channel_dir_path: str) -> Optional[str]:
        """
        Find the actual video file path by searching for video_id in filename.

        This method performs filesystem verification after yt-dlp download to confirm
        the video file actually exists. With ignoreerrors=True, yt-dlp may "succeed"
        without creating a file, so this verification is critical.

        Args:
            video_id: YouTube video ID (11 characters)
            channel_dir_path: Full path to channel directory to search

        Returns:
            Full path to video file if found, None otherwise

        The search:
        - Walks the entire channel directory tree
        - Looks for files containing [video_id] in filename
        - Excludes partial downloads (.part files)
        - Only matches actual video files (mkv, mp4, webm, etc.)
        - Ignores metadata files (.info.json, thumbnails, etc.)
        """
        if not os.path.exists(channel_dir_path):
            logger.warning(f"Channel directory not found: {channel_dir_path}")
            return None

        # Video file extensions we recognize (lowercase for case-insensitive matching)
        video_extensions = ('.mkv', '.mp4', '.webm', '.avi', '.mov', '.flv', '.m4v', '.3gp')

        # Walk directory tree looking for video file
        for root, dirs, files in os.walk(channel_dir_path):
            for filename in files:
                # Check if filename contains the video ID in [brackets]
                if f"[{video_id}]" in filename:
                    # Exclude partial downloads
                    if filename.endswith('.part'):
                        logger.debug(f"Found partial download (skipping): {filename}")
                        continue

                    # Check if it's a video file (not .info.json, .jpg, etc.)
                    if filename.lower().endswith(video_extensions):
                        full_path = os.path.join(root, filename)
                        logger.debug(f"Found video file for {video_id}: {full_path}")
                        return full_path

        logger.warning(f"No video file found for video_id={video_id} in {channel_dir_path}")
        return None
    
    def get_recent_videos(self, channel_url: str, limit: int = 10, channel_id: str = None) -> Tuple[bool, List[Dict], Optional[str]]:
        """
        Query channel for recent videos using robust fallback approach.

        This method tries multiple extraction strategies in order:
        1. Channel /videos tab - excludes shorts and live streams naturally
        2. Uploads playlist (UC -> UU conversion) - fallback, includes all content
        3. Original channel URL
        4. Non-flat extraction as last resort

        Args:
            channel_url: YouTube channel URL (fallback if channel_id not provided)
            limit: Maximum number of recent videos to return
            channel_id: YouTube channel ID (UC...) - preferred for direct access

        Returns:
            Tuple of (success, list_of_video_dicts, error_message)

        Example:
            success, videos, error = service.get_recent_videos("https://youtube.com/@MrsRachel", 10, "UCfInIsouvaKEtbtGHeTy1oA")
            if success:
                for video in videos:
                    print(f"Video: {video['title']} ({video['id']})")
        """
        cookies_applied = os.path.exists(self.cookie_file)
        logger.info(f"Discovering videos for channel {channel_id or 'from URL'} (limit: {limit})")
        
        # Define fallback URLs to try in order
        fallback_attempts = []

        # 1. Channel videos tab (excludes shorts and live streams naturally)
        if channel_id and channel_id.startswith('UC'):
            fallback_attempts.append({
                'url': f"https://www.youtube.com/channel/{channel_id}/videos",
                'description': 'channel videos tab',
                'opts_override': {'extractor_args': {'youtube': {'tab': ['videos']}}}
            })

        # 2. Uploads playlist (fallback - includes shorts and lives)
        if channel_id and channel_id.startswith('UC'):
            uploads_id = 'UU' + channel_id[2:]  # Convert UC to UU
            fallback_attempts.append({
                'url': f"https://www.youtube.com/playlist?list={uploads_id}",
                'description': 'uploads playlist',
                'opts_override': {}
            })
        
        # 3. Original channel URL
        fallback_attempts.append({
            'url': channel_url,
            'description': 'original channel URL',
            'opts_override': {}
        })
        
        # 4. Non-flat extraction (last resort)
        fallback_attempts.append({
            'url': channel_url,
            'description': 'non-flat extraction',
            'opts_override': {
                'extract_flat': False,
                'noplaylist': True,  # Avoid heavy enumeration
                'quiet': False,      # Show more details for debugging
                'no_warnings': False
            }
        })
        
        # Try each fallback in order
        for attempt_num, attempt in enumerate(fallback_attempts, 1):
            try:
                # Configure yt-dlp options
                opts = self.query_opts.copy()
                opts['playlistend'] = limit
                opts.update(attempt['opts_override'])

                logger.info(f"Attempt {attempt_num}/{len(fallback_attempts)}: Trying {attempt['description']} - {attempt['url']}")

                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(attempt['url'], download=False)

                    if not info:
                        logger.warning(f"Attempt {attempt_num}: No info returned")
                        continue
                    
                    # Log extraction details
                    info_type = info.get('_type', 'unknown')
                    entries = info.get('entries', [])
                    raw_entries_count = len(entries)

                    logger.info(f"Extraction successful (Attempt {attempt_num}): Found {raw_entries_count} entries")

                    if not entries:
                        logger.warning(f"No entries returned, trying next fallback")
                        continue

                    # Process entries using flexible ID extraction
                    logger.info(f"Processing {min(len(entries), limit)} entries")

                    videos = []
                    skipped_count = 0

                    for idx, entry in enumerate(entries[:limit], 1):  # Ensure we don't exceed limit
                        if not entry:
                            continue

                        # Use flexible video ID extraction
                        video_id = self._extract_video_id(entry)
                        if not video_id:
                            skipped_count += 1
                            logger.debug(f"  ⏭️  Entry {idx}: Skipped (no valid video ID) - {entry.get('title', 'Unknown')}")
                            continue

                        # Build video info with flexible parsing
                        video_info = {
                            'id': video_id,
                            'title': entry.get('title', 'Unknown Title'),
                            'upload_date': entry.get('upload_date'),
                            'duration': entry.get('duration'),
                            'duration_string': entry.get('duration_string'),
                            'view_count': entry.get('view_count'),
                            'webpage_url': entry.get('webpage_url') or entry.get('url') or f"https://www.youtube.com/watch?v={video_id}",
                            'channel': entry.get('channel') or entry.get('uploader'),
                            'channel_id': entry.get('channel_id') or channel_id,
                        }

                        # Validate video info
                        if video_info['title'] != 'Unknown Title':
                            videos.append(video_info)
                            logger.debug(f"  ✅ Entry {idx}: {video_info['title'][:60]} ({video_id})")
                        else:
                            skipped_count += 1
                            logger.debug(f"  ⏭️  Entry {idx}: Skipped (no title) - ID: {video_id}")

                    logger.info(f"Extracted {len(videos)} valid videos ({skipped_count} skipped)")

                    # Check if we got suspiciously few videos compared to what we requested
                    # If we asked for 10 videos but only got 1-2, try the next fallback method
                    # This handles cases where the uploads playlist (UC→UU) is broken/incomplete
                    if len(videos) > 0 and len(videos) < max(3, limit // 3):
                        logger.warning(f"Got only {len(videos)}/{limit} videos, trying next fallback method")
                        continue  # Try next fallback method

                    # Success! Return even if videos list is empty (valid channel with no videos)
                    if videos:
                        # Log first few video titles for validation
                        sample_titles = [v['title'][:50] + '...' if len(v['title']) > 50 else v['title']
                                       for v in videos[:3]]
                        logger.info(f"Sample videos (first {min(3, len(videos))}): {sample_titles}")

                    logger.info(f"Discovery complete: Found {len(videos)} videos")
                    return True, videos, None
                        
            except yt_dlp.DownloadError as e:
                error_msg = str(e)
                logger.warning(f"Attempt {attempt_num}: yt-dlp error - {error_msg}")
                
                # Check for permanent errors that shouldn't be retried
                if any(msg in error_msg.lower() for msg in ["private", "does not exist", "unavailable"]):
                    return False, [], f"Channel error: {error_msg}"
                
                # Continue to next fallback for other errors
                continue
                
            except Exception as e:
                logger.warning(f"Attempt {attempt_num}: Unexpected error - {str(e)}")
                continue
        
        # All fallbacks failed
        logger.error("All extraction attempts failed")
        return False, [], "Could not extract videos using any method"
    
    def download_video(self, video_info: Dict, channel: Channel, db: Session) -> Tuple[bool, Optional[str]]:
        """
        Download a single video with status tracking.
        
        This method downloads an individual video, tracks its progress in the database,
        and handles errors gracefully to avoid stopping the overall download process.
        
        Args:
            video_info: Dictionary containing video metadata
            channel: Channel database model
            db: Database session for status updates
            
        Returns:
            Tuple of (success, error_message)
        """
        video_id = video_info['id']
        video_title = video_info['title']
        
        try:
            # Check if download record already exists
            existing_download = db.query(Download).filter(
                Download.video_id == video_id,
                Download.channel_id == channel.id
            ).first()
            
            if existing_download and existing_download.status == 'completed':
                logger.info(f"Video {video_id} already downloaded successfully")
                return True, None
            
            # Create or update download record
            if existing_download:
                download = existing_download
                download.status = 'downloading'
                download.error_message = None
            else:
                download = Download(
                    channel_id=channel.id,
                    video_id=video_id,
                    title=video_title,
                    upload_date=video_info.get('upload_date', ''),
                    duration=video_info.get('duration_string'),
                    status='downloading'
                )
                db.add(download)
            
            db.commit()
            
            # Configure yt-dlp for this specific video
            opts = self.download_opts.copy()
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            
            logger.info(f"Starting download: {video_title} ({video_id})")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Download the video
                ydl.download([video_url])

                # CRITICAL: With ignoreerrors=True, yt-dlp doesn't throw exceptions on failure
                # We MUST verify the file actually exists on disk before marking as successful

                # Build channel directory path for verification
                channel_dir = channel_dir_name(channel)
                channel_dir_path = os.path.join(self.media_path, channel_dir)

                # Brief delay to ensure filesystem has flushed
                time.sleep(0.5)

                # Verify download by finding the actual video file on disk
                video_file_path = self._find_video_file_path(video_id, channel_dir_path)

                if video_file_path and os.path.exists(video_file_path):
                    # SUCCESS: Video file exists on disk
                    download.status = 'completed'
                    download.file_exists = True
                    download.file_path = video_file_path
                    download.file_size = os.path.getsize(video_file_path)
                    download.completed_at = datetime.utcnow()
                    db.commit()

                    logger.info(f"Successfully downloaded: {video_title} → {video_file_path}")
                    return True, None
                else:
                    # FAILURE: yt-dlp completed but no video file found
                    # This happens when yt-dlp encounters errors but doesn't throw (ignoreerrors=True)
                    error_msg = "yt-dlp completed but video file not found on disk (check logs for yt-dlp errors)"
                    download.status = 'failed'
                    download.file_exists = False
                    download.error_message = error_msg[:500]
                    db.commit()

                    logger.error(f"Download failed for {video_title} ({video_id}): {error_msg}")
                    return False, error_msg
                
        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            logger.warning(f"Download failed for {video_title} ({video_id}): {error_msg}")
            
            # Update download record with error
            if 'download' in locals():
                download.status = 'failed'
                download.error_message = error_msg[:500]  # Truncate long error messages
                db.commit()
            
            return False, f"Download error: {error_msg}"
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Unexpected error downloading {video_title} ({video_id}): {error_msg}")
            
            # Update download record with error
            if 'download' in locals():
                download.status = 'failed'
                download.error_message = error_msg[:500]
                db.commit()
            
            return False, f"Unexpected error: {error_msg}"
    
    def process_channel_downloads(self, channel: Channel, db: Session) -> Tuple[bool, int, Optional[str]]:
        """
        Process downloads for a channel sequentially.

        This is the main orchestration method that:
        1. Queries the channel for recent videos
        2. Downloads new videos sequentially
        3. Updates channel and download history
        4. Handles errors gracefully

        Args:
            channel: Channel database model
            db: Database session

        Returns:
            Tuple of (success, videos_downloaded, error_message)
        """
        logger.info(f"Starting download process for '{channel.name}' (limit: {channel.limit})")

        if not channel.enabled:
            logger.warning(f"Channel '{channel.name}' is disabled, skipping")
            return False, 0, "Channel is disabled"
        
        # Create download history record
        history = DownloadHistory(
            channel_id=channel.id,
            run_date=datetime.utcnow(),
            videos_found=0,
            videos_downloaded=0,
            videos_skipped=0,
            status='running'
        )
        db.add(history)
        db.commit()
        
        try:
            # Get recent videos using flat-playlist approach with channel ID
            success, videos, error = self.get_recent_videos(channel.url, channel.limit, channel.channel_id)

            if not success:
                history.status = 'failed'
                history.error_message = error
                history.completed_at = datetime.utcnow()
                db.commit()
                return False, 0, error

            history.videos_found = len(videos)
            db.commit()

            logger.info(f"Found {len(videos)} videos for channel '{channel.name}'")

            if not videos:
                # No videos found, but not an error
                history.status = 'completed'
                history.completed_at = datetime.utcnow()
                channel.last_check = datetime.utcnow()
                db.commit()
                logger.info(f"⚠️  No videos found for channel: {channel.name}")
                return True, 0, None

            # Process each video sequentially
            downloaded_count = 0
            skipped_count = 0

            logger.info(f"Processing {len(videos)} videos for download")

            for idx, video_info in enumerate(videos, 1):
                # Use new deduplication logic
                should_download, existing_download = self.should_download_video(video_info['id'], channel, db)

                video_title_short = video_info['title'][:50] + '...' if len(video_info['title']) > 50 else video_info['title']

                if not should_download:
                    skipped_count += 1
                    logger.info(f"  ⏭️  Video {idx}/{len(videos)}: SKIPPED (already exists) - {video_title_short}")
                    continue

                # Download the video
                logger.info(f"  ⬇️  Video {idx}/{len(videos)}: DOWNLOADING - {video_title_short}")
                download_success, download_error = self.download_video(video_info, channel, db)

                if download_success:
                    downloaded_count += 1
                    logger.info(f"  ✅ Video {idx}/{len(videos)}: SUCCESS - {video_title_short}")
                else:
                    # Log error but continue with remaining videos
                    logger.warning(f"  ❌ Video {idx}/{len(videos)}: FAILED - {video_title_short}: {download_error}")
            
            # Update history and channel
            history.videos_downloaded = downloaded_count
            history.videos_skipped = skipped_count
            history.status = 'completed'
            history.completed_at = datetime.utcnow()

            channel.last_check = datetime.utcnow()

            db.commit()

            logger.info(f"Channel '{channel.name}' complete: {downloaded_count} downloaded, {skipped_count} skipped, {len(videos)} total")

            return True, downloaded_count, None
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Unexpected error processing channel {channel.name}: {error_msg}")
            
            history.status = 'failed'
            history.error_message = error_msg[:500]
            history.completed_at = datetime.utcnow()
            channel.last_check = datetime.utcnow()
            db.commit()
            
            return False, 0, error_msg
    
    def _make_filesystem_safe(self, name: str, max_length: int = 100) -> str:
        """
        Convert text to filesystem-safe name, preserving spaces.
        
        Args:
            name: Original text
            max_length: Maximum length for the safe name
            
        Returns:
            str: Filesystem-safe name
        """
        import unicodedata
        import re
        
        # Normalize unicode characters
        name = unicodedata.normalize('NFKD', name)
        
        # Replace problematic filesystem characters but preserve spaces
        name = re.sub(r'[<>:"/\\|?*]', '', name)  # Remove problematic chars
        name = re.sub(r'\.+$', '', name)  # Remove trailing dots
        name = re.sub(r'\s+', ' ', name)  # Collapse multiple spaces to single space
        name = name.strip()  # Remove leading/trailing whitespace
        
        # Truncate if too long
        if len(name) > max_length:
            name = name[:max_length].strip()
        
        return name


# Global instance
video_download_service = VideoDownloadService()