"""Unit tests for metadata service functionality."""
import json
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import pytest
from sqlalchemy.orm import Session

from app.metadata_service import MetadataService, metadata_service
from app.models import Channel
from app.config import Settings


@pytest.fixture
def mock_settings():
    """Mock settings with temporary media directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        settings = Settings(media_dir=temp_dir)
        with patch('app.metadata_service.get_settings', return_value=settings):
            yield settings


@pytest.fixture
def test_channel():
    """Create a test channel instance."""
    return Channel(
        id=1,
        url="https://youtube.com/@testchannel",
        name="Test Channel",
        channel_id="UC123456789",
        limit=10,
        enabled=True,
        metadata_status="pending"
    )


@pytest.fixture
def sample_metadata():
    """Sample YouTube channel metadata."""
    return {
        "id": "UC123456789",
        "channel_id": "UC123456789",
        "channel": "Test Channel",
        "title": "Test Channel - Videos",
        "description": "A test channel description",
        "channel_follower_count": 1000,
        "thumbnails": [
            {
                "id": "avatar_uncropped",
                "url": "https://yt3.googleusercontent.com/test-avatar.jpg"
            },
            {
                "id": "banner_uncropped", 
                "url": "https://yt3.googleusercontent.com/test-banner.jpg"
            }
        ],
        "epoch": 1640995200
    }


class TestMetadataService:
    """Test cases for MetadataService."""
    
    def test_initialization(self, mock_settings):
        """Test MetadataService initialization."""
        service = MetadataService()
        assert service.media_root == mock_settings.media_dir
    
    @patch('app.metadata_service.youtube_service.extract_channel_info')
    def test_create_channel_directory_success(self, mock_extract, mock_settings):
        """Test successful channel directory creation."""
        # Mock YouTube service response
        mock_extract.return_value = (True, {
            'name': 'Test Channel',
            'channel_id': 'UC123456789'
        }, None)
        
        service = MetadataService()
        
        # Test directory creation
        success, directory_path, error = service._create_channel_directory(
            "https://youtube.com/@testchannel"
        )
        
        assert success is True
        assert error is None
        assert directory_path is not None
        assert os.path.exists(directory_path)
        assert "Test Channel [UC123456789]" in directory_path
    
    @patch('app.metadata_service.youtube_service.extract_channel_info')
    def test_create_channel_directory_extraction_failure(self, mock_extract, mock_settings):
        """Test directory creation when channel info extraction fails."""
        # Mock YouTube service failure
        mock_extract.return_value = (False, None, "Channel not found")
        
        service = MetadataService()
        
        success, directory_path, error = service._create_channel_directory(
            "https://youtube.com/@invalid"
        )
        
        assert success is False
        assert directory_path is None
        assert "Could not extract channel info" in error
    
    @patch('app.youtube_service.youtube_service.extract_channel_info')
    @patch('app.metadata_service.youtube_service.extract_channel_metadata_full')
    @patch('app.metadata_service.image_service.download_channel_images')
    def test_process_channel_metadata_success(self, mock_image_download, mock_metadata_extract,
                                            mock_extract_info, mock_settings, test_channel, sample_metadata):
        """Test successful metadata processing workflow."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No duplicates

        # Create test directory
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123456789]")
        os.makedirs(test_dir, exist_ok=True)

        # Mock channel info extraction (for directory creation)
        mock_extract_info.return_value = (True, {
            'name': 'Test Channel',
            'channel_id': 'UC123456789'
        }, None)

        # Mock YouTube metadata extraction
        mock_metadata_extract.return_value = (True, sample_metadata, None)

        # Mock image downloads
        mock_image_download.return_value = (True, {
            'cover': f"{test_dir}/cover.jpg",
            'backdrop': f"{test_dir}/backdrop.jpg"
        }, [])

        service = MetadataService()

        success, errors = service.process_channel_metadata(
            mock_db, test_channel, "https://youtube.com/@testchannel"
        )

        assert success is True
        assert len(errors) == 0
        assert test_channel.metadata_status == "completed"
        assert test_channel.channel_id == "UC123456789"
        mock_db.commit.assert_called()
    
    @patch('app.youtube_service.youtube_service.extract_channel_info')
    @patch('app.metadata_service.youtube_service.extract_channel_metadata_full')
    def test_process_channel_metadata_duplicate_channel(self, mock_metadata_extract, mock_extract_info,
                                                      mock_settings, test_channel, sample_metadata):
        """Test metadata processing with duplicate channel ID."""
        # Mock database session with existing channel
        existing_channel = Mock()
        existing_channel.name = "Existing Channel"
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_channel

        # Create test directory
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123456789]")
        os.makedirs(test_dir, exist_ok=True)

        # Mock channel info extraction (for directory creation)
        mock_extract_info.return_value = (True, {
            'name': 'Test Channel',
            'channel_id': 'UC123456789'
        }, None)

        # Mock YouTube metadata extraction
        mock_metadata_extract.return_value = (True, sample_metadata, None)

        service = MetadataService()

        success, errors = service.process_channel_metadata(
            mock_db, test_channel, "https://youtube.com/@testchannel"
        )

        assert success is False
        assert any("already being monitored" in error for error in errors)
        assert test_channel.metadata_status == "failed"
    
    @patch('app.youtube_service.youtube_service.extract_channel_info')
    @patch('app.metadata_service.youtube_service.extract_channel_metadata_full')
    def test_process_channel_metadata_extraction_failure(self, mock_metadata_extract, mock_extract_info,
                                                        mock_settings, test_channel):
        """Test metadata processing when extraction fails."""
        # Mock database session
        mock_db = Mock(spec=Session)

        # Create test directory
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123456789]")
        os.makedirs(test_dir, exist_ok=True)

        # Mock channel info extraction (for directory creation)
        mock_extract_info.return_value = (True, {
            'name': 'Test Channel',
            'channel_id': 'UC123456789'
        }, None)

        # Mock YouTube extraction failure
        mock_metadata_extract.return_value = (False, None, "Private channel")

        service = MetadataService()

        success, errors = service.process_channel_metadata(
            mock_db, test_channel, "https://youtube.com/@testchannel"
        )

        assert success is False
        assert any("Metadata extraction failed" in error for error in errors)
        assert test_channel.metadata_status == "failed"
    
    @patch('app.youtube_service.youtube_service.extract_channel_info')
    @patch('app.metadata_service.youtube_service.extract_channel_metadata_full')
    @patch('app.metadata_service.image_service.download_channel_images')
    def test_process_channel_metadata_image_failure_partial_success(self, mock_image_download,
                                                                   mock_metadata_extract,
                                                                   mock_extract_info,
                                                                   mock_settings, test_channel,
                                                                   sample_metadata):
        """Test metadata processing when images fail but metadata succeeds."""
        # Mock database session
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Create test directory
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123456789]")
        os.makedirs(test_dir, exist_ok=True)

        # Mock channel info extraction (for directory creation)
        mock_extract_info.return_value = (True, {
            'name': 'Test Channel',
            'channel_id': 'UC123456789'
        }, None)

        # Mock successful metadata extraction
        mock_metadata_extract.return_value = (True, sample_metadata, None)

        # Mock image download failure
        mock_image_download.return_value = (False, {'cover': None, 'backdrop': None},
                                          ["Network error downloading images"])

        service = MetadataService()

        success, errors = service.process_channel_metadata(
            mock_db, test_channel, "https://youtube.com/@testchannel"
        )

        # Should succeed overall since metadata extraction worked
        assert success is True
        assert len(errors) > 0  # But should have warnings about images
        assert test_channel.metadata_status == "completed"
        assert any("Image download" in error for error in errors)
    
    def test_validate_directory_structure_valid(self, mock_settings):
        """Test directory structure validation for valid directory."""
        service = MetadataService()
        
        # Create valid test directory
        test_dir = os.path.join(mock_settings.media_dir, "test_channel")
        os.makedirs(test_dir)
        
        valid, errors = service.validate_directory_structure(test_dir)
        
        assert valid is True
        assert len(errors) == 0
    
    def test_validate_directory_structure_missing(self, mock_settings):
        """Test directory structure validation for missing directory."""
        service = MetadataService()
        
        missing_dir = os.path.join(mock_settings.media_dir, "missing")
        
        valid, errors = service.validate_directory_structure(missing_dir)
        
        assert valid is False
        assert any("does not exist" in error for error in errors)
    
    def test_validate_directory_structure_outside_media_root(self, mock_settings):
        """Test directory structure validation for path outside media root."""
        service = MetadataService()

        # Create a directory outside media root
        outside_dir = "/tmp/outside_media"
        os.makedirs(outside_dir, exist_ok=True)

        valid, errors = service.validate_directory_structure(outside_dir)

        assert valid is False
        assert any("outside media root" in error for error in errors)
    
    @patch('app.metadata_service.youtube_service.extract_channel_metadata_full')
    @patch('app.metadata_service.image_service.download_channel_images')
    def test_refresh_channel_metadata_success(self, mock_image_download, mock_metadata_extract,
                                            mock_settings, sample_metadata):
        """Test successful metadata refresh for existing channel."""
        # Create test channel with existing directory
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123456789]")
        os.makedirs(test_dir)
        
        channel = Channel(
            id=1,
            url="https://youtube.com/@testchannel",
            name="Test Channel",
            channel_id="UC123456789",
            directory_path=test_dir,
            metadata_status="completed"
        )
        
        # Mock database session
        mock_db = Mock(spec=Session)
        
        # Mock successful metadata refresh
        mock_metadata_extract.return_value = (True, sample_metadata, None)
        mock_image_download.return_value = (True, {
            'cover': f"{test_dir}/cover.jpg",
            'backdrop': f"{test_dir}/backdrop.jpg"
        }, [])
        
        service = MetadataService()
        
        success, errors = service.refresh_channel_metadata(mock_db, channel)
        
        assert success is True
        assert len(errors) == 0
        assert channel.metadata_status == "completed"
    
    @patch('app.metadata_service.youtube_service.extract_channel_metadata_full')
    def test_refresh_channel_metadata_missing_directory(self, mock_metadata_extract,
                                                       mock_settings, sample_metadata):
        """Test metadata refresh when channel directory is missing."""
        # Channel with missing directory
        channel = Channel(
            id=1,
            url="https://youtube.com/@testchannel", 
            name="Test Channel",
            channel_id="UC123456789",
            directory_path="/nonexistent/path",
            metadata_status="completed"
        )
        
        mock_db = Mock(spec=Session)
        
        # Mock the process_channel_metadata call that will be triggered
        service = MetadataService()
        
        with patch.object(service, 'process_channel_metadata') as mock_process:
            mock_process.return_value = (True, [])
            
            success, errors = service.refresh_channel_metadata(mock_db, channel)
            
            # Should trigger full reprocessing
            mock_process.assert_called_once_with(mock_db, channel, channel.url)


class TestMetadataServiceRollback:
    """Test rollback functionality."""
    
    def test_rollback_operations_directory(self, mock_settings):
        """Test rollback of directory creation."""
        service = MetadataService()
        
        # Create test directory
        test_dir = os.path.join(mock_settings.media_dir, "test_rollback")
        os.makedirs(test_dir)
        assert os.path.exists(test_dir)
        
        # Rollback directory creation
        rollback_actions = [('remove_directory', test_dir)]
        service._rollback_operations(rollback_actions)
        
        # Directory should be removed
        assert not os.path.exists(test_dir)
    
    def test_rollback_operations_file(self, mock_settings):
        """Test rollback of file creation."""
        service = MetadataService()
        
        # Create test file
        test_file = os.path.join(mock_settings.media_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        assert os.path.exists(test_file)
        
        # Rollback file creation
        rollback_actions = [('remove_file', test_file)]
        service._rollback_operations(rollback_actions)
        
        # File should be removed
        assert not os.path.exists(test_file)
    
    def test_rollback_operations_error_handling(self, mock_settings):
        """Test rollback error handling for missing files."""
        service = MetadataService()
        
        # Try to rollback non-existent file (should not raise exception)
        rollback_actions = [('remove_file', '/nonexistent/file.txt')]
        
        # Should not raise exception
        service._rollback_operations(rollback_actions)


class TestMetadataServiceIntegration:
    """Integration test scenarios."""
    
    @patch('app.metadata_service.youtube_service')
    @patch('app.metadata_service.image_service')
    def test_end_to_end_workflow(self, mock_image_service, mock_youtube_service, mock_settings, sample_metadata):
        """Test complete end-to-end metadata workflow."""
        # Mock all external dependencies
        mock_youtube_service.extract_channel_info.return_value = (True, {
            'name': 'Test Channel',
            'channel_id': 'UC123456789'
        }, None)
        
        mock_youtube_service.extract_channel_metadata_full.return_value = (True, sample_metadata, None)
        mock_youtube_service._make_filesystem_safe.return_value = "Test Channel"
        
        mock_image_service.download_channel_images.return_value = (True, {
            'cover': 'cover.jpg',
            'backdrop': 'backdrop.jpg'
        }, [])
        
        # Mock database
        mock_db = Mock(spec=Session)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Create test channel
        channel = Channel(
            id=1,
            url="https://youtube.com/@testchannel",
            name="Test Channel",
            channel_id="UC123456789",
            metadata_status="pending"
        )
        
        service = MetadataService()
        
        success, errors = service.process_channel_metadata(
            mock_db, channel, "https://youtube.com/@testchannel"
        )
        
        # Verify end-to-end success
        assert success is True
        assert len(errors) == 0
        assert channel.metadata_status == "completed"
        assert channel.directory_path is not None
        assert channel.metadata_path is not None
        
        # Verify all services were called
        mock_youtube_service.extract_channel_metadata_full.assert_called_once()
        mock_image_service.download_channel_images.assert_called_once()
        mock_db.commit.assert_called()