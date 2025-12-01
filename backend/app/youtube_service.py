"""YouTube service for channel metadata extraction using yt-dlp."""
import re
import logging
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
import yt_dlp
from app.config import get_settings

logger = logging.getLogger(__name__)


class YouTubeService:
    """
    Service for interacting with YouTube channels via yt-dlp.
    
    This service provides methods to validate YouTube URLs, extract channel metadata,
    and normalize URLs to prevent duplicate channels with different URL formats.
    
    Key Features:
    - Validates multiple YouTube URL formats (/@handle, /channel/UC..., /c/name, /user/name)
    - Extracts channel metadata without downloading videos
    - Normalizes URLs to consistent format to prevent duplicates
    
    Example:
        service = YouTubeService()
        success, info, error = service.extract_channel_info("https://youtube.com/@MrsRachel")
        if success:
            print(f"Channel: {info['name']} (ID: {info['channel_id']})")
    """
    
    def __init__(self):
        """
        Initialize the YouTube service with yt-dlp configuration.
        
        Creates shared base configuration with anti-bot measures that both
        extraction methods can use to avoid HTTP 403 errors.
        """
        settings = get_settings()
        
        # Base configuration shared by all extraction methods
        self.base_ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            # Anti-bot detection headers - crucial for avoiding 403 errors
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
            'max_sleep_interval': 3,    # Random sleep up to 3 seconds
        }
        
        # Add cookies file if it exists
        if os.path.exists(settings.cookies_file):
            self.base_ydl_opts['cookiefile'] = settings.cookies_file
            logger.info(f"[YouTubeService] Using cookies file: {settings.cookies_file}")
        else:
            logger.warning(f"[YouTubeService] Cookies file not found at {settings.cookies_file}")

        # Legacy ydl_opts for backward compatibility (basic extraction)
        self.ydl_opts = {**self.base_ydl_opts, 'extract_flat': True}
    
    def validate_youtube_url(self, url: str) -> bool:
        """
        Validate if the provided URL is a valid YouTube channel URL.
        
        Args:
            url: The URL to validate
            
        Returns:
            bool: True if valid YouTube channel URL, False otherwise
        """
        if not url:
            return False
            
        # Normalize URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        try:
            parsed = urlparse(url)
            
            if parsed.netloc not in ['youtube.com', 'www.youtube.com', 'm.youtube.com']:
                return False
                
            # Check for valid channel URL patterns
            path = parsed.path
            valid_patterns = [
                r'^/channel/UC[a-zA-Z0-9_-]{22}',    # /channel/UCxxxx (may have trailing content)
                r'^/c/[a-zA-Z0-9_-]+',               # /c/channelname
                r'^/@[a-zA-Z0-9_.-]+',               # /@handle  
                r'^/user/[a-zA-Z0-9_-]+',            # /user/username (legacy)
            ]
            
            return any(re.search(pattern, path) for pattern in valid_patterns)
            
        except Exception as e:
            logger.warning(f"URL validation error for {url}: {e}")
            return False
    
    def extract_channel_info(self, url: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Extract channel information from a YouTube URL.
        
        Args:
            url: YouTube channel URL
            
        Returns:
            Tuple of (success, channel_info_dict, error_message)
            
        Examples:
            success, info, error = service.extract_channel_info("https://youtube.com/@MrsRachel")
            if success:
                print(f"Channel: {info['name']} (ID: {info['channel_id']})")
        """
        if not self.validate_youtube_url(url):
            return False, None, "Invalid YouTube channel URL format"
        
        try:
            # Use base configuration with extract_flat for basic info extraction
            basic_opts = {**self.base_ydl_opts, 'extract_flat': True, 'playlistend': 1}
            with yt_dlp.YoutubeDL(basic_opts) as ydl:
                # Extract channel information without downloading
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return False, None, "Could not extract channel information"
                
                # yt-dlp returns different formats depending on URL type
                # Channel pages return 'playlist' type, individual videos return different structure
                if info.get('_type') == 'playlist':
                    # Channel page response - most comprehensive data
                    channel_info = {
                        'channel_id': info.get('channel_id') or info.get('id'),
                        'name': info.get('channel') or info.get('title') or info.get('uploader'),
                        'description': info.get('description', ''),
                        'subscriber_count': info.get('subscriber_count'),
                        'video_count': info.get('playlist_count') or len(info.get('entries', [])),
                        'url': url,
                        'webpage_url': info.get('webpage_url', url),
                    }
                else:
                    # Single video or other format - extract channel info from video metadata
                    channel_info = {
                        'channel_id': info.get('channel_id'),
                        'name': info.get('channel') or info.get('uploader'),
                        'description': info.get('channel_description', ''),
                        'subscriber_count': info.get('channel_follower_count'),
                        'video_count': None,  # Not available from video metadata
                        'url': url,
                        'webpage_url': info.get('channel_url', url),
                    }
                
                # Validate that we got the essential information
                if not channel_info.get('channel_id'):
                    return False, None, "Could not extract channel ID from URL"
                
                if not channel_info.get('name'):
                    return False, None, "Could not extract channel name from URL"
                
                # Remove None values to keep response clean
                channel_info = {k: v for k, v in channel_info.items() if v is not None}
                
                logger.info(f"Successfully extracted channel info: {channel_info['name']} ({channel_info['channel_id']})")
                return True, channel_info, None
                
        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            if "Private video" in error_msg or "This channel does not exist" in error_msg:
                return False, None, "Channel is private or does not exist"
            return False, None, f"YouTube error: {error_msg}"
            
        except Exception as e:
            logger.error(f"Unexpected error extracting channel info from {url}: {e}")
            return False, None, f"Failed to extract channel information: {str(e)}"
    
    def normalize_channel_url(self, url: str) -> str:
        """
        Normalize a YouTube channel URL to a standard format.
        
        Args:
            url: Input URL
            
        Returns:
            str: Normalized URL
        """
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            
        # Ensure we use www.youtube.com for consistency (avoid double www)
        url = url.replace('://youtube.com', '://www.youtube.com')
        url = url.replace('://m.youtube.com', '://www.youtube.com')
        # Don't double-add www if it already exists
        url = url.replace('://www.www.youtube.com', '://www.youtube.com')
        
        return url
    
    def extract_channel_metadata_full(self, url: str, output_dir: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Extract complete channel metadata and save to JSON file.
        
        This method downloads full channel metadata using yt-dlp's extract_info()
        method, removes the 'entries' key to reduce file size from ~24MB to ~5KB,
        and saves the optimized metadata to a JSON file.
        
        Args:
            url: YouTube channel URL
            output_dir: Directory path where metadata JSON will be saved
            
        Returns:
            Tuple of (success, full_metadata_dict, error_message)
        """
        if not self.validate_youtube_url(url):
            return False, None, "Invalid YouTube channel URL format"
        
        try:
            # Use base configuration with extract_flat=False for comprehensive extraction
            # This includes all anti-bot headers and delays to avoid HTTP 403 errors
            # playlistend=1 limits processing to prevent rate limiting
            full_metadata_opts = {**self.base_ydl_opts, 'extract_flat': False, 'playlistend': 1}
            
            with yt_dlp.YoutubeDL(full_metadata_opts) as ydl:
                # Extract all channel info without downloading
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return False, None, "Could not extract channel metadata"
                
                # Remove entries to reduce file size from 24MB to ~5KB
                if 'entries' in info:
                    del info['entries']
                
                # Sanitize for JSON serialization
                sanitized_info = ydl.sanitize_info(info)
                
                # Add epoch timestamp for metadata retrieval tracking
                sanitized_info['epoch'] = int(time.time())
                
                # Ensure output directory exists
                os.makedirs(output_dir, exist_ok=True)
                
                # Generate filesystem-safe filename
                channel_name = sanitized_info.get('channel') or sanitized_info.get('title', 'Unknown')
                channel_id = sanitized_info.get('channel_id') or sanitized_info.get('id')
                
                if not channel_id:
                    return False, None, "Could not extract channel ID from metadata"
                
                safe_name = self._make_filesystem_safe(channel_name)
                filename = f"{safe_name} [{channel_id}].info.json"
                output_path = os.path.join(output_dir, filename)
                
                # Save to file
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(sanitized_info, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Saved channel metadata to: {output_path}")
                
                return True, sanitized_info, None
                
        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            if "Private video" in error_msg or "This channel does not exist" in error_msg:
                return False, None, "Channel is private or does not exist"
            return False, None, f"YouTube error: {error_msg}"
            
        except Exception as e:
            logger.error(f"Unexpected error extracting full metadata from {url}: {e}")
            return False, None, f"Failed to extract channel metadata: {str(e)}"
    
    def _make_filesystem_safe(self, name: str, max_length: int = 100) -> str:
        """
        Convert channel name to filesystem-safe directory name, preserving spaces.
        
        Args:
            name: Original channel name
            max_length: Maximum length for the safe name
            
        Returns:
            str: Filesystem-safe name
        """
        import unicodedata
        
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


# Global instance
youtube_service = YouTubeService()