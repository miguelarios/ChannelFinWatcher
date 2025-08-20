"""Unit tests for video download service functionality."""
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.video_download_service import VideoDownloadService, video_download_service
from app.models import Channel, Download, DownloadHistory
from app.config import Settings


@pytest.fixture
def mock_settings():
    """Mock settings with temporary directories for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        media_dir = os.path.join(temp_dir, "media")
        temp_path = os.path.join(temp_dir, "temp") 
        data_dir = os.path.join(temp_dir, "data")
        
        os.makedirs(media_dir, exist_ok=True)
        os.makedirs(temp_path, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        
        settings = Settings(
            media_dir=media_dir,
            temp_dir=temp_path,
            database_url=f"sqlite:///{data_dir}/test.db",
            config_file=f"{data_dir}/config.yaml",
            cookies_file=f"{data_dir}/cookies.txt"
        )
        
        with patch('app.video_download_service.get_settings', return_value=settings):
            yield settings


@pytest.fixture
def test_channel():
    """Create a test channel instance with metadata."""
    return Channel(
        id=1,
        url="https://youtube.com/@testchannel",
        name="Test Channel",
        channel_id="UC123456789",
        limit=5,
        enabled=True,
        metadata_status="completed"
    )


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def sample_video_info():
    """Sample video information from yt-dlp."""
    return [
        {
            "id": "video123",
            "title": "Test Video 1",
            "upload_date": "20250120",
            "duration": 300,
            "duration_string": "5:00",
            "view_count": 1000,
            "webpage_url": "https://youtube.com/watch?v=video123",
            "channel": "Test Channel",
            "channel_id": "UC123456789"
        },
        {
            "id": "video456", 
            "title": "Test Video 2",
            "upload_date": "20250119",
            "duration": 240,
            "duration_string": "4:00",
            "view_count": 2000,
            "webpage_url": "https://youtube.com/watch?v=video456",
            "channel": "Test Channel",
            "channel_id": "UC123456789"
        }
    ]


class TestVideoDownloadService:
    """Test suite for VideoDownloadService functionality."""

    def test_service_initialization(self, mock_settings):
        """Test that service initializes correctly with proper settings."""
        service = VideoDownloadService()
        
        assert service.media_path == mock_settings.media_dir
        assert service.temp_path == mock_settings.temp_dir
        assert "archive.txt" in service.archive_file
        assert service.download_opts['format'] == 'bv*+ba/b'
        assert service.download_opts['merge_output_format'] == 'mkv'

    @patch('app.video_download_service.yt_dlp.YoutubeDL')
    def test_get_recent_videos_success(self, mock_ydl_class, mock_settings, sample_video_info):
        """Test successful retrieval of recent videos from a channel."""
        # Mock yt-dlp behavior
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'entries': sample_video_info
        }
        
        service = VideoDownloadService()
        success, videos, error = service.get_recent_videos("https://youtube.com/@testchannel", limit=5)
        
        assert success is True
        assert error is None
        assert len(videos) == 2
        assert videos[0]['id'] == 'video123'
        assert videos[0]['title'] == 'Test Video 1'
        
        # Verify yt-dlp was called with correct parameters
        mock_ydl.extract_info.assert_called_once_with("https://youtube.com/@testchannel", download=False)

    @patch('app.video_download_service.yt_dlp.YoutubeDL')
    def test_get_recent_videos_no_entries(self, mock_ydl_class, mock_settings):
        """Test handling of channels with no videos."""
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {'entries': []}
        
        service = VideoDownloadService()
        success, videos, error = service.get_recent_videos("https://youtube.com/@testchannel")
        
        assert success is True
        assert error is None
        assert len(videos) == 0

    @patch('app.video_download_service.yt_dlp.YoutubeDL')
    def test_get_recent_videos_yt_dlp_error(self, mock_ydl_class, mock_settings):
        """Test handling of yt-dlp download errors."""
        from yt_dlp import DownloadError
        
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.side_effect = DownloadError("Channel is private")
        
        service = VideoDownloadService()
        success, videos, error = service.get_recent_videos("https://youtube.com/@privatechannel")
        
        assert success is False
        assert videos == []
        assert "Channel is private" in error

    @patch('app.video_download_service.yt_dlp.YoutubeDL')
    def test_download_video_success(self, mock_ydl_class, mock_settings, test_channel, mock_db, sample_video_info):
        """Test successful video download with database tracking."""
        # Mock yt-dlp behavior
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.download.return_value = None  # Successful download
        
        # Mock database queries
        mock_db.query.return_value.filter.return_value.first.return_value = None  # No existing download
        
        service = VideoDownloadService()
        video_info = sample_video_info[0]
        
        success, error = service.download_video(video_info, test_channel, mock_db)
        
        assert success is True
        assert error is None
        
        # Verify database interaction
        mock_db.add.assert_called()
        mock_db.commit.assert_called()
        
        # Verify yt-dlp was called with video URL
        expected_url = "https://www.youtube.com/watch?v=video123"
        mock_ydl.download.assert_called_once_with([expected_url])

    @patch('app.video_download_service.yt_dlp.YoutubeDL')
    def test_download_video_already_exists(self, mock_ydl_class, mock_settings, test_channel, mock_db, sample_video_info):
        """Test skipping video that's already downloaded successfully."""
        # Mock existing completed download
        existing_download = Mock()
        existing_download.status = 'completed'
        mock_db.query.return_value.filter.return_value.first.return_value = existing_download
        
        service = VideoDownloadService()
        video_info = sample_video_info[0]
        
        success, error = service.download_video(video_info, test_channel, mock_db)
        
        assert success is True
        assert error is None
        
        # Verify yt-dlp was not called since video already exists
        mock_ydl_class.assert_not_called()

    @patch('app.video_download_service.yt_dlp.YoutubeDL')
    def test_download_video_yt_dlp_failure(self, mock_ydl_class, mock_settings, test_channel, mock_db, sample_video_info):
        """Test handling of yt-dlp download failures."""
        from yt_dlp import DownloadError
        
        # Mock yt-dlp failure
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.download.side_effect = DownloadError("Video unavailable")
        
        # Mock database - no existing download
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = VideoDownloadService()
        video_info = sample_video_info[0]
        
        success, error = service.download_video(video_info, test_channel, mock_db)
        
        assert success is False
        assert "Video unavailable" in error
        
        # Verify error was stored in database
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @patch('app.video_download_service.VideoDownloadService.get_recent_videos')
    @patch('app.video_download_service.VideoDownloadService.download_video')
    def test_process_channel_downloads_success(self, mock_download_video, mock_get_recent_videos, 
                                             mock_settings, test_channel, mock_db, sample_video_info):
        """Test successful processing of channel downloads."""
        # Mock getting recent videos
        mock_get_recent_videos.return_value = (True, sample_video_info, None)
        
        # Mock successful video downloads
        mock_download_video.return_value = (True, None)
        
        # Mock database queries for existing downloads
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        service = VideoDownloadService()
        success, count, error = service.process_channel_downloads(test_channel, mock_db)
        
        assert success is True
        assert count == 2  # Two videos downloaded
        assert error is None
        
        # Verify methods were called correctly
        mock_get_recent_videos.assert_called_once_with(test_channel.url, test_channel.limit)
        assert mock_download_video.call_count == 2
        
        # Verify download history was created
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @patch('app.video_download_service.VideoDownloadService.get_recent_videos')
    def test_process_channel_downloads_disabled_channel(self, mock_get_recent_videos, 
                                                       mock_settings, test_channel, mock_db):
        """Test that disabled channels are not processed."""
        test_channel.enabled = False
        
        service = VideoDownloadService()
        success, count, error = service.process_channel_downloads(test_channel, mock_db)
        
        assert success is False
        assert count == 0
        assert "Channel is disabled" in error
        
        # Verify no API calls were made
        mock_get_recent_videos.assert_not_called()

    @patch('app.video_download_service.VideoDownloadService.get_recent_videos')
    def test_process_channel_downloads_no_videos_found(self, mock_get_recent_videos, 
                                                      mock_settings, test_channel, mock_db):
        """Test handling when no videos are found in channel."""
        # Mock no videos found
        mock_get_recent_videos.return_value = (True, [], None)
        
        service = VideoDownloadService()
        success, count, error = service.process_channel_downloads(test_channel, mock_db)
        
        assert success is True
        assert count == 0
        assert error is None
        
        # Verify download history was still created
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @patch('app.video_download_service.VideoDownloadService.get_recent_videos')
    def test_process_channel_downloads_get_videos_failure(self, mock_get_recent_videos, 
                                                         mock_settings, test_channel, mock_db):
        """Test handling when getting recent videos fails."""
        # Mock failure to get videos
        mock_get_recent_videos.return_value = (False, [], "Channel not found")
        
        service = VideoDownloadService()
        success, count, error = service.process_channel_downloads(test_channel, mock_db)
        
        assert success is False
        assert count == 0
        assert "Channel not found" in error

    def test_make_filesystem_safe(self, mock_settings):
        """Test filesystem-safe name generation."""
        service = VideoDownloadService()
        
        # Test problematic characters are removed
        unsafe_name = 'Test<>:"/\\|?*Channel'
        safe_name = service._make_filesystem_safe(unsafe_name)
        assert safe_name == "TestChannel"
        
        # Test spaces are preserved
        name_with_spaces = "Test Channel Name"
        safe_name = service._make_filesystem_safe(name_with_spaces)
        assert safe_name == "Test Channel Name"
        
        # Test length truncation
        long_name = "A" * 150
        safe_name = service._make_filesystem_safe(long_name, max_length=50)
        assert len(safe_name) == 50

    def test_global_service_instance(self):
        """Test that global service instance is properly configured."""
        # The global instance should be importable and configured
        from app.video_download_service import video_download_service
        
        assert video_download_service is not None
        assert hasattr(video_download_service, 'get_recent_videos')
        assert hasattr(video_download_service, 'download_video')
        assert hasattr(video_download_service, 'process_channel_downloads')