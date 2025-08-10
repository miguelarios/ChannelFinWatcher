"""Image processing service for downloading channel thumbnails and cover images."""
import os
import logging
from typing import Dict, Optional, Tuple, List
from pathlib import Path
import requests
from urllib.parse import urlparse
import mimetypes

logger = logging.getLogger(__name__)


class ImageService:
    """
    Service for downloading and processing channel images (cover and backdrop).
    
    This service handles secure image downloads from YouTube thumbnail URLs
    with proper validation, file type checking, and size limits to prevent
    malicious content.
    
    Key Features:
    - Secure image download with URL validation
    - File type checking and extension detection
    - Size limits to prevent abuse
    - Cover and backdrop image processing from thumbnails array
    
    Example:
        service = ImageService()
        success, path = service.download_cover_image(metadata, "/media/channel/")
    """
    
    # Security limits
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB max file size
    ALLOWED_MIME_TYPES = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/webp': '.webp',
        'image/gif': '.gif',
    }
    TIMEOUT_SECONDS = 30
    
    def __init__(self):
        """Initialize image service with secure defaults."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ChannelFinWatcher/1.0 (image downloader)'
        })
    
    def download_channel_images(self, metadata: Dict, output_dir: str) -> Tuple[bool, Dict[str, Optional[str]], List[str]]:
        """
        Download both cover and backdrop images from channel metadata.
        
        Args:
            metadata: Channel metadata containing thumbnails array
            output_dir: Directory to save images
            
        Returns:
            Tuple of (success, image_paths_dict, error_messages)
            
        Examples:
            success, paths, errors = service.download_channel_images(metadata, "/media/channel/")
            if success:
                print(f"Cover saved to: {paths['cover']}")
                print(f"Backdrop saved to: {paths['backdrop']}")
        """
        results = {
            'cover': None,
            'backdrop': None
        }
        errors = []
        
        # Ensure output directory exists
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            return False, results, [f"Failed to create output directory: {e}"]
        
        # Download cover image (avatar_uncropped)
        cover_success, cover_path, cover_error = self.download_cover_image(metadata, output_dir)
        if cover_success:
            results['cover'] = cover_path
        else:
            errors.append(f"Cover image: {cover_error}")
        
        # Download backdrop image (banner_uncropped)
        backdrop_success, backdrop_path, backdrop_error = self.download_backdrop_image(metadata, output_dir)
        if backdrop_success:
            results['backdrop'] = backdrop_path
        else:
            errors.append(f"Backdrop image: {backdrop_error}")
        
        # Consider success if at least one image downloaded successfully
        overall_success = cover_success or backdrop_success
        
        return overall_success, results, errors
    
    def download_cover_image(self, metadata: Dict, output_dir: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Download channel cover image from avatar_uncropped thumbnail.
        
        Args:
            metadata: Channel metadata containing thumbnails array
            output_dir: Directory to save image
            
        Returns:
            Tuple of (success, file_path, error_message)
        """
        thumbnails = metadata.get('thumbnails', [])
        if not thumbnails:
            return False, None, "No thumbnails found in metadata"
        
        # Find avatar_uncropped thumbnail
        avatar_url = None
        for thumb in thumbnails:
            if thumb.get('id') == 'avatar_uncropped':
                avatar_url = thumb.get('url')
                break
        
        if not avatar_url:
            return False, None, "No avatar_uncropped thumbnail found"
        
        return self._download_image(avatar_url, output_dir, 'cover')
    
    def download_backdrop_image(self, metadata: Dict, output_dir: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Download channel backdrop image from banner_uncropped thumbnail.
        
        Args:
            metadata: Channel metadata containing thumbnails array
            output_dir: Directory to save image
            
        Returns:
            Tuple of (success, file_path, error_message)
        """
        thumbnails = metadata.get('thumbnails', [])
        if not thumbnails:
            return False, None, "No thumbnails found in metadata"
        
        # Find banner_uncropped thumbnail
        banner_url = None
        for thumb in thumbnails:
            if thumb.get('id') == 'banner_uncropped':
                banner_url = thumb.get('url')
                break
        
        if not banner_url:
            return False, None, "No banner_uncropped thumbnail found"
        
        return self._download_image(banner_url, output_dir, 'backdrop')
    
    def _download_image(self, url: str, output_dir: str, filename_base: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Securely download an image from a URL with validation and safety checks.
        
        Args:
            url: Image URL to download
            output_dir: Directory to save image
            filename_base: Base filename (cover or backdrop)
            
        Returns:
            Tuple of (success, file_path, error_message)
        """
        if not self._validate_image_url(url):
            return False, None, "Invalid or unsafe image URL"
        
        try:
            # Download with streaming to check content-type and size
            response = self.session.get(url, stream=True, timeout=self.TIMEOUT_SECONDS)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if content_type not in self.ALLOWED_MIME_TYPES:
                return False, None, f"Unsupported image type: {content_type}"
            
            # Check content length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.MAX_FILE_SIZE:
                return False, None, f"Image too large: {content_length} bytes"
            
            # Determine file extension
            extension = self.ALLOWED_MIME_TYPES[content_type]
            
            # Generate output path
            output_path = os.path.join(output_dir, f"{filename_base}{extension}")
            
            # Download file with size checking
            downloaded_size = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # filter out keep-alive chunks
                        downloaded_size += len(chunk)
                        if downloaded_size > self.MAX_FILE_SIZE:
                            os.remove(output_path)  # Clean up partial file
                            return False, None, f"Image too large during download: {downloaded_size} bytes"
                        f.write(chunk)
            
            logger.info(f"Successfully downloaded {filename_base} image to: {output_path}")
            return True, output_path, None
            
        except requests.exceptions.RequestException as e:
            return False, None, f"Network error downloading image: {e}"
        except Exception as e:
            logger.error(f"Unexpected error downloading image from {url}: {e}")
            return False, None, f"Failed to download image: {e}"
    
    def _validate_image_url(self, url: str) -> bool:
        """
        Validate that the URL is safe for downloading images.
        
        Args:
            url: URL to validate
            
        Returns:
            bool: True if URL is safe to download from
        """
        if not url or not isinstance(url, str):
            return False
        
        try:
            parsed = urlparse(url)
            
            # Must be HTTPS
            if parsed.scheme != 'https':
                return False
            
            # Must be from YouTube/Google domains
            allowed_domains = [
                'yt3.googleusercontent.com',
                'i.ytimg.com',
                'yt3.ggpht.com',
            ]
            
            if not any(parsed.netloc == domain or parsed.netloc.endswith('.' + domain) 
                      for domain in allowed_domains):
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"URL validation error for {url}: {e}")
            return False


# Global instance
image_service = ImageService()