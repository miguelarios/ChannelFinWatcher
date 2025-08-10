"""Unit tests for image service functionality."""
import os
import tempfile
import json
from unittest.mock import Mock, patch, mock_open
import pytest
import requests

from app.image_service import ImageService, image_service


@pytest.fixture
def sample_metadata():
    """Sample channel metadata with thumbnails."""
    return {
        "thumbnails": [
            {
                "id": "avatar_uncropped",
                "url": "https://yt3.googleusercontent.com/test-avatar.jpg"
            },
            {
                "id": "banner_uncropped",
                "url": "https://yt3.googleusercontent.com/test-banner.jpg"
            },
            {
                "id": "other_thumbnail",
                "url": "https://yt3.googleusercontent.com/other.jpg"
            }
        ]
    }


@pytest.fixture
def mock_response():
    """Mock HTTP response for image downloads."""
    response = Mock()
    response.ok = True
    response.headers = {
        'content-type': 'image/jpeg',
        'content-length': '1024'
    }
    response.iter_content.return_value = [b'fake_image_data']
    return response


class TestImageService:
    """Test cases for ImageService."""
    
    def test_initialization(self):
        """Test ImageService initialization."""
        service = ImageService()
        assert service.MAX_FILE_SIZE == 10 * 1024 * 1024
        assert 'image/jpeg' in service.ALLOWED_MIME_TYPES
        assert service.TIMEOUT_SECONDS == 30
    
    def test_validate_image_url_valid(self):
        """Test URL validation for valid YouTube image URLs."""
        service = ImageService()
        
        valid_urls = [
            "https://yt3.googleusercontent.com/avatar.jpg",
            "https://i.ytimg.com/banner.png",
            "https://yt3.ggpht.com/thumbnail.webp"
        ]
        
        for url in valid_urls:
            assert service._validate_image_url(url) is True
    
    def test_validate_image_url_invalid(self):
        """Test URL validation for invalid URLs."""
        service = ImageService()
        
        invalid_urls = [
            "http://yt3.googleusercontent.com/avatar.jpg",  # HTTP not HTTPS
            "https://malicious.com/image.jpg",              # Wrong domain
            "https://example.com/yt3.googleusercontent.com/fake.jpg",  # Subdomain attack
            "",                                             # Empty string
            None,                                          # None value
            "not-a-url"                                    # Invalid format
        ]
        
        for url in invalid_urls:
            assert service._validate_image_url(url) is False
    
    def test_download_cover_image_success(self, sample_metadata, mock_response):
        """Test successful cover image download."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service.session, 'get', return_value=mock_response):
                with patch('builtins.open', mock_open()) as mock_file:
                    
                    success, file_path, error = service.download_cover_image(
                        sample_metadata, temp_dir
                    )
                    
                    assert success is True
                    assert error is None
                    assert file_path.endswith('cover.jpg')
                    mock_file.assert_called_once()
    
    def test_download_cover_image_no_thumbnails(self):
        """Test cover image download when no thumbnails exist."""
        service = ImageService()
        metadata_no_thumbs = {"other_field": "value"}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            success, file_path, error = service.download_cover_image(
                metadata_no_thumbs, temp_dir
            )
            
            assert success is False
            assert file_path is None
            assert "No thumbnails found" in error
    
    def test_download_cover_image_no_avatar(self, sample_metadata):
        """Test cover image download when avatar_uncropped not found."""
        service = ImageService()
        
        # Remove avatar_uncropped from thumbnails
        metadata_no_avatar = {
            "thumbnails": [thumb for thumb in sample_metadata["thumbnails"] 
                          if thumb["id"] != "avatar_uncropped"]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            success, file_path, error = service.download_cover_image(
                metadata_no_avatar, temp_dir
            )
            
            assert success is False
            assert file_path is None
            assert "No avatar_uncropped thumbnail found" in error
    
    def test_download_backdrop_image_success(self, sample_metadata, mock_response):
        """Test successful backdrop image download."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service.session, 'get', return_value=mock_response):
                with patch('builtins.open', mock_open()) as mock_file:
                    
                    success, file_path, error = service.download_backdrop_image(
                        sample_metadata, temp_dir
                    )
                    
                    assert success is True
                    assert error is None
                    assert file_path.endswith('backdrop.jpg')
                    mock_file.assert_called_once()
    
    def test_download_backdrop_image_no_banner(self, sample_metadata):
        """Test backdrop image download when banner_uncropped not found."""
        service = ImageService()
        
        # Remove banner_uncropped from thumbnails
        metadata_no_banner = {
            "thumbnails": [thumb for thumb in sample_metadata["thumbnails"] 
                          if thumb["id"] != "banner_uncropped"]
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            success, file_path, error = service.download_backdrop_image(
                metadata_no_banner, temp_dir
            )
            
            assert success is False
            assert file_path is None
            assert "No banner_uncropped thumbnail found" in error
    
    def test_download_image_invalid_url(self):
        """Test image download with invalid URL."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            success, file_path, error = service._download_image(
                "https://malicious.com/image.jpg", temp_dir, "test"
            )
            
            assert success is False
            assert file_path is None
            assert "Invalid or unsafe image URL" in error
    
    def test_download_image_unsupported_content_type(self, sample_metadata):
        """Test image download with unsupported content type."""
        service = ImageService()
        
        # Mock response with unsupported content type
        mock_response = Mock()
        mock_response.ok = True
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.raise_for_status.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service.session, 'get', return_value=mock_response):
                
                success, file_path, error = service._download_image(
                    "https://yt3.googleusercontent.com/test.jpg", temp_dir, "test"
                )
                
                assert success is False
                assert file_path is None
                assert "Unsupported image type" in error
    
    def test_download_image_too_large_content_length(self, sample_metadata):
        """Test image download with content-length exceeding limit."""
        service = ImageService()
        
        # Mock response with large content-length
        mock_response = Mock()
        mock_response.ok = True
        mock_response.headers = {
            'content-type': 'image/jpeg',
            'content-length': str(service.MAX_FILE_SIZE + 1)
        }
        mock_response.raise_for_status.return_value = None
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service.session, 'get', return_value=mock_response):
                
                success, file_path, error = service._download_image(
                    "https://yt3.googleusercontent.com/test.jpg", temp_dir, "test"
                )
                
                assert success is False
                assert file_path is None
                assert "Image too large" in error
    
    def test_download_image_too_large_during_download(self, sample_metadata):
        """Test image download that exceeds size limit during streaming."""
        service = ImageService()
        
        # Mock response that streams too much data
        mock_response = Mock()
        mock_response.ok = True
        mock_response.headers = {'content-type': 'image/jpeg'}
        mock_response.raise_for_status.return_value = None
        # Create chunks that exceed max size
        large_chunk = b'x' * (service.MAX_FILE_SIZE + 1)
        mock_response.iter_content.return_value = [large_chunk]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service.session, 'get', return_value=mock_response):
                
                success, file_path, error = service._download_image(
                    "https://yt3.googleusercontent.com/test.jpg", temp_dir, "test"
                )
                
                assert success is False
                assert file_path is None
                assert "Image too large during download" in error
    
    def test_download_image_network_error(self, sample_metadata):
        """Test image download network error handling."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service.session, 'get', side_effect=requests.exceptions.RequestException("Network error")):
                
                success, file_path, error = service._download_image(
                    "https://yt3.googleusercontent.com/test.jpg", temp_dir, "test"
                )
                
                assert success is False
                assert file_path is None
                assert "Network error downloading image" in error
    
    def test_download_channel_images_success(self, sample_metadata):
        """Test downloading both cover and backdrop images successfully."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service, 'download_cover_image') as mock_cover:
                with patch.object(service, 'download_backdrop_image') as mock_backdrop:
                    
                    # Mock successful downloads
                    mock_cover.return_value = (True, f"{temp_dir}/cover.jpg", None)
                    mock_backdrop.return_value = (True, f"{temp_dir}/backdrop.jpg", None)
                    
                    success, paths, errors = service.download_channel_images(
                        sample_metadata, temp_dir
                    )
                    
                    assert success is True
                    assert paths['cover'].endswith('cover.jpg')
                    assert paths['backdrop'].endswith('backdrop.jpg')
                    assert len(errors) == 0
    
    def test_download_channel_images_partial_success(self, sample_metadata):
        """Test downloading images with partial success (cover fails, backdrop succeeds)."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service, 'download_cover_image') as mock_cover:
                with patch.object(service, 'download_backdrop_image') as mock_backdrop:
                    
                    # Mock partial success
                    mock_cover.return_value = (False, None, "Cover download failed")
                    mock_backdrop.return_value = (True, f"{temp_dir}/backdrop.jpg", None)
                    
                    success, paths, errors = service.download_channel_images(
                        sample_metadata, temp_dir
                    )
                    
                    assert success is True  # Overall success if at least one succeeds
                    assert paths['cover'] is None
                    assert paths['backdrop'].endswith('backdrop.jpg')
                    assert len(errors) == 1
                    assert "Cover image" in errors[0]
    
    def test_download_channel_images_complete_failure(self, sample_metadata):
        """Test downloading images with complete failure."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service, 'download_cover_image') as mock_cover:
                with patch.object(service, 'download_backdrop_image') as mock_backdrop:
                    
                    # Mock complete failure
                    mock_cover.return_value = (False, None, "Cover download failed")
                    mock_backdrop.return_value = (False, None, "Backdrop download failed")
                    
                    success, paths, errors = service.download_channel_images(
                        sample_metadata, temp_dir
                    )
                    
                    assert success is False
                    assert paths['cover'] is None
                    assert paths['backdrop'] is None
                    assert len(errors) == 2
    
    def test_download_channel_images_directory_creation_failure(self, sample_metadata):
        """Test image download when directory creation fails."""
        service = ImageService()
        
        # Use invalid directory path
        with patch('os.makedirs', side_effect=OSError("Permission denied")):
            success, paths, errors = service.download_channel_images(
                sample_metadata, "/invalid/path"
            )
            
            assert success is False
            assert paths['cover'] is None
            assert paths['backdrop'] is None
            assert len(errors) == 1
            assert "Failed to create output directory" in errors[0]


class TestImageServiceSecurity:
    """Security-focused tests for ImageService."""
    
    def test_url_validation_subdomain_attack(self):
        """Test protection against subdomain attacks."""
        service = ImageService()
        
        malicious_urls = [
            "https://evil.com/yt3.googleusercontent.com/fake.jpg",
            "https://yt3.googleusercontent.com.evil.com/fake.jpg",
            "https://notyt3.googleusercontent.com/fake.jpg"
        ]
        
        for url in malicious_urls:
            assert service._validate_image_url(url) is False
    
    def test_file_size_limits_enforced(self):
        """Test that file size limits are properly enforced."""
        service = ImageService()
        
        # Verify size constants are reasonable
        assert service.MAX_FILE_SIZE <= 50 * 1024 * 1024  # No more than 50MB
        assert service.MAX_FILE_SIZE >= 1 * 1024 * 1024   # At least 1MB
    
    def test_allowed_mime_types_restricted(self):
        """Test that only safe mime types are allowed."""
        service = ImageService()
        
        # Should only contain image types
        for mime_type in service.ALLOWED_MIME_TYPES.keys():
            assert mime_type.startswith('image/')
        
        # Should not allow dangerous types
        dangerous_types = ['text/html', 'application/javascript', 'text/javascript']
        for dangerous_type in dangerous_types:
            assert dangerous_type not in service.ALLOWED_MIME_TYPES
    
    def test_timeout_configured(self):
        """Test that network timeout is configured."""
        service = ImageService()
        
        # Timeout should be reasonable (not too long, not too short)
        assert 10 <= service.TIMEOUT_SECONDS <= 60


class TestImageServicePerformance:
    """Performance-related tests for ImageService."""
    
    def test_streaming_download_efficiency(self, mock_response):
        """Test that downloads use streaming for memory efficiency."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service.session, 'get', return_value=mock_response) as mock_get:
                with patch('builtins.open', mock_open()):
                    
                    service._download_image(
                        "https://yt3.googleusercontent.com/test.jpg", temp_dir, "test"
                    )
                    
                    # Verify streaming was used
                    mock_get.assert_called_once()
                    call_kwargs = mock_get.call_args[1]
                    assert call_kwargs['stream'] is True
    
    def test_chunk_size_reasonable(self, mock_response):
        """Test that chunk size is reasonable for performance."""
        service = ImageService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(service.session, 'get', return_value=mock_response):
                with patch('builtins.open', mock_open()):
                    
                    service._download_image(
                        "https://yt3.googleusercontent.com/test.jpg", temp_dir, "test"
                    )
                    
                    # Verify iter_content was called with reasonable chunk size
                    mock_response.iter_content.assert_called_once_with(chunk_size=8192)


class TestGlobalInstance:
    """Test the global image_service instance."""
    
    def test_global_instance_exists(self):
        """Test that global image_service instance exists."""
        assert image_service is not None
        assert isinstance(image_service, ImageService)
    
    def test_global_instance_is_singleton(self):
        """Test that global instance behaves like singleton."""
        from app.image_service import image_service as service1
        from app.image_service import image_service as service2
        
        # Should be the same instance
        assert service1 is service2