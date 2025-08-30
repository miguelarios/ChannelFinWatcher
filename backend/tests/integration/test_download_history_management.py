"""Integration tests for Story 006 - Better Download History Management."""
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.video_download_service import VideoDownloadService
from app.models import Channel, Download
from app.config import Settings


@pytest.fixture
def mock_settings():
    """Mock settings with temporary directories for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        media_dir = os.path.join(temp_dir, "media")
        temp_path = os.path.join(temp_dir, "temp")
        
        os.makedirs(media_dir, exist_ok=True)
        os.makedirs(temp_path, exist_ok=True)
        
        settings = Settings(
            media_dir=media_dir,
            temp_dir=temp_path,
            database_url=f"sqlite:///{temp_dir}/test.db",
            config_file=f"{temp_dir}/config.yaml",
            cookies_file=f"{temp_dir}/cookies.txt"
        )
        
        with patch('app.video_download_service.get_settings', return_value=settings):
            yield settings


@pytest.fixture
def test_channel():
    """Create a test channel instance."""
    return Channel(
        id=1,
        url="https://youtube.com/@testchannel",
        name="Test Channel",
        channel_id="UC123456789",
        limit=5,
        enabled=True
    )


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


class TestDownloadHistoryManagement:
    """Test suite for download history management without archive.txt."""

    def test_should_download_video_no_existing_record(self, mock_settings, test_channel, mock_db):
        """Test should_download_video when no database record exists and no file on disk."""
        service = VideoDownloadService()
        video_id = "testVideo123"
        
        # Mock database query returns None (no existing record)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock no file on disk
        with patch.object(service, 'check_video_on_disk', return_value=False):
            should_download, existing_download = service.should_download_video(video_id, test_channel, mock_db)
        
        assert should_download is True
        assert existing_download is None

    def test_should_download_video_completed_and_exists(self, mock_settings, test_channel, mock_db):
        """Test should_download_video when record exists with completed status and file_exists=True."""
        service = VideoDownloadService()
        video_id = "testVideo123"
        
        # Mock existing completed download
        existing_download = Mock()
        existing_download.status = 'completed'
        existing_download.file_exists = True
        mock_db.query.return_value.filter.return_value.first.return_value = existing_download
        
        should_download, returned_download = service.should_download_video(video_id, test_channel, mock_db)
        
        assert should_download is False
        assert returned_download == existing_download

    def test_should_download_video_file_missing(self, mock_settings, test_channel, mock_db):
        """Test should_download_video when record exists but file_exists=False (re-download case)."""
        service = VideoDownloadService()
        video_id = "testVideo123"
        
        # Mock existing download with missing file
        existing_download = Mock()
        existing_download.status = 'completed'
        existing_download.file_exists = False
        mock_db.query.return_value.filter.return_value.first.return_value = existing_download
        
        should_download, returned_download = service.should_download_video(video_id, test_channel, mock_db)
        
        assert should_download is True  # Should re-download
        assert returned_download == existing_download

    def test_should_download_video_found_on_disk(self, mock_settings, test_channel, mock_db):
        """Test should_download_video when no DB record but file exists on disk."""
        service = VideoDownloadService()
        video_id = "testVideo123"
        
        # Mock database query returns None (no existing record)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        # Mock file found on disk
        with patch.object(service, 'check_video_on_disk', return_value=True):
            should_download, existing_download = service.should_download_video(video_id, test_channel, mock_db)
        
        assert should_download is False  # Should skip - found on disk
        # Verify database record was created
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    def test_check_video_on_disk_exists(self, mock_settings):
        """Test check_video_on_disk when video file exists."""
        service = VideoDownloadService()
        video_id = "testVideo123"
        
        # Create test file structure
        channel_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123456789]")
        video_dir = os.path.join(channel_dir, "2024", "Test Channel - 20240101 - Test Video [testVideo123]")
        os.makedirs(video_dir, exist_ok=True)
        
        # Create test video file
        test_file = os.path.join(video_dir, "Test Channel - 20240101 - Test Video [testVideo123].mkv")
        with open(test_file, 'w') as f:
            f.write("test video content")
        
        result = service.check_video_on_disk(video_id, channel_dir)
        assert result is True

    def test_check_video_on_disk_not_exists(self, mock_settings):
        """Test check_video_on_disk when video file does not exist."""
        service = VideoDownloadService()
        video_id = "testVideo123"
        
        # Create empty channel directory
        channel_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123456789]")
        os.makedirs(channel_dir, exist_ok=True)
        
        result = service.check_video_on_disk(video_id, channel_dir)
        assert result is False

    def test_check_video_on_disk_ignores_part_files(self, mock_settings):
        """Test check_video_on_disk ignores .part files (partial downloads)."""
        service = VideoDownloadService()
        video_id = "testVideo123"
        
        # Create test file structure
        channel_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123456789]")
        video_dir = os.path.join(channel_dir, "2024", "Test Channel - 20240101 - Test Video [testVideo123]")
        os.makedirs(video_dir, exist_ok=True)
        
        # Create .part file (should be ignored)
        part_file = os.path.join(video_dir, "Test Channel - 20240101 - Test Video [testVideo123].mkv.part")
        with open(part_file, 'w') as f:
            f.write("partial download")
        
        result = service.check_video_on_disk(video_id, channel_dir)
        assert result is False  # Should not find .part files

    def test_check_video_on_disk_missing_directory(self, mock_settings):
        """Test check_video_on_disk handles missing directory gracefully."""
        service = VideoDownloadService()
        video_id = "testVideo123"
        
        # Path that doesn't exist
        nonexistent_path = os.path.join(mock_settings.media_dir, "NonExistent Channel")
        
        result = service.check_video_on_disk(video_id, nonexistent_path)
        assert result is False