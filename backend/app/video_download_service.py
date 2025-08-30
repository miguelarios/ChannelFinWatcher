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
    - Uses archive.txt to prevent duplicate downloads
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
        
        # Derive data and config paths from the database URL and config file
        data_path = os.path.dirname(settings.database_url.replace("sqlite:///", "/app/"))
        config_path = os.path.dirname(settings.config_file)
        
        self.archive_file = os.path.join(data_path, "archive.txt")
        self.cookie_file = settings.cookies_file
        
        # Ensure required directories exist
        os.makedirs(self.media_path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)
        
        # yt-dlp configuration for video downloads
        # Based on exact parameters from TDD reference bash script
        # Added anti-bot detection headers
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
            'download_archive': self.archive_file,
            'concurrent_fragments': 4,
            'ignoreerrors': True,  # Continue on individual video errors
            'no_warnings': False,  # Show warnings for troubleshooting
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
    
    def get_recent_videos(self, channel_url: str, limit: int = 10, channel_id: str = None) -> Tuple[bool, List[Dict], Optional[str]]:
        """
        Query channel for recent videos using robust fallback approach.
        
        This method tries multiple extraction strategies in order:
        1. Uploads playlist (UC -> UU conversion) - most reliable
        2. Channel /videos tab with extractor args
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
        logger.info(f"Starting video extraction for channel_id={channel_id}, limit={limit}, cookies={cookies_applied}")
        
        # Define fallback URLs to try in order
        fallback_attempts = []
        
        # 1. Uploads playlist (most reliable)
        if channel_id and channel_id.startswith('UC'):
            uploads_id = 'UU' + channel_id[2:]  # Convert UC to UU
            fallback_attempts.append({
                'url': f"https://www.youtube.com/playlist?list={uploads_id}",
                'description': 'uploads playlist',
                'opts_override': {}
            })
        
        # 2. Channel videos tab
        if channel_id and channel_id.startswith('UC'):
            fallback_attempts.append({
                'url': f"https://www.youtube.com/channel/{channel_id}/videos",
                'description': 'channel videos tab',
                'opts_override': {'extractor_args': {'youtube': {'tab': ['videos']}}}
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
                    logger.info(f"Attempt {attempt_num}: info_type={info_type}, entries_count={len(entries)}")
                    
                    if entries:
                        # Log first entry keys for debugging
                        first_entry = entries[0] if entries else {}
                        logger.info(f"Attempt {attempt_num}: First entry keys: {list(first_entry.keys())}")
                    
                    if not entries:
                        logger.info(f"Attempt {attempt_num}: No entries found, trying next fallback")
                        continue
                    
                    # Process entries using flexible ID extraction
                    videos = []
                    skipped_count = 0
                    
                    for entry in entries[:limit]:  # Ensure we don't exceed limit
                        if not entry:
                            continue
                        
                        # Use flexible video ID extraction
                        video_id = self._extract_video_id(entry)
                        if not video_id:
                            skipped_count += 1
                            logger.debug(f"Skipping entry with no valid video ID: {entry.get('title', 'Unknown')}")
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
                        else:
                            skipped_count += 1
                    
                    logger.info(f"Attempt {attempt_num}: Found {len(videos)} valid videos, skipped {skipped_count}")
                    
                    if videos:
                        # Success! Log first few video titles for validation
                        sample_titles = [v['title'][:50] + '...' if len(v['title']) > 50 else v['title'] 
                                       for v in videos[:3]]
                        logger.info(f"Sample video titles: {sample_titles}")
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
                
                # If we get here, download was successful
                download.status = 'completed'
                download.completed_at = datetime.utcnow()
                
                # Try to determine file path (simplified approach)
                # The actual file path would be determined by the output template
                channel_name = channel.name
                upload_date = video_info.get('upload_date', '')
                if upload_date and len(upload_date) >= 4:
                    year = upload_date[:4]
                    safe_channel = self._make_filesystem_safe(channel_name)
                    safe_title = self._make_filesystem_safe(video_title)
                    
                    expected_dir = os.path.join(
                        self.media_path,
                        f"{safe_channel} [{channel.channel_id}]",
                        year,
                        f"{safe_channel} - {upload_date} - {safe_title} [{video_id}]"
                    )
                    expected_file = f"{safe_channel} - {upload_date} - {safe_title} [{video_id}].mkv"
                    full_path = os.path.join(expected_dir, expected_file)
                    
                    if os.path.exists(full_path):
                        download.file_path = full_path
                        download.file_size = os.path.getsize(full_path)
                
                db.commit()
                logger.info(f"Successfully downloaded: {video_title}")
                return True, None
                
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
        if not channel.enabled:
            return False, 0, "Channel is disabled"
        
        logger.info(f"Starting download process for channel: {channel.name}")
        
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
            
            if not videos:
                # No videos found, but not an error
                history.status = 'completed'
                history.completed_at = datetime.utcnow()
                channel.last_check = datetime.utcnow()
                db.commit()
                logger.info(f"No videos found for channel: {channel.name}")
                return True, 0, None
            
            # Process each video sequentially
            downloaded_count = 0
            skipped_count = 0
            
            for video_info in videos:
                # Check if video already downloaded via archive.txt or database
                existing = db.query(Download).filter(
                    Download.video_id == video_info['id'],
                    Download.status == 'completed'
                ).first()
                
                if existing:
                    skipped_count += 1
                    logger.info(f"Skipping already downloaded video: {video_info['title']}")
                    continue
                
                # Download the video
                download_success, download_error = self.download_video(video_info, channel, db)
                
                if download_success:
                    downloaded_count += 1
                else:
                    # Log error but continue with remaining videos
                    logger.warning(f"Failed to download video {video_info['title']}: {download_error}")
            
            # Update history and channel
            history.videos_downloaded = downloaded_count
            history.videos_skipped = skipped_count
            history.status = 'completed'
            history.completed_at = datetime.utcnow()
            
            channel.last_check = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Completed download process for {channel.name}: {downloaded_count} downloaded, {skipped_count} skipped")
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