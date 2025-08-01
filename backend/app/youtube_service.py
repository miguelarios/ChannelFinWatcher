"""YouTube service for channel metadata extraction using yt-dlp."""
import re
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
import yt_dlp

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
        
        Configuration optimized for metadata extraction only:
        - quiet: Suppress yt-dlp output
        - extract_flat: Don't download videos, just get playlist/channel info
        - ignoreerrors: Continue processing even if some videos fail
        """
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Don't download, just get metadata
            'ignoreerrors': True,
        }
    
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
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
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


# Global instance
youtube_service = YouTubeService()