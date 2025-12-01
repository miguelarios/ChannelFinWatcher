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
            "id": "dQw4w9WgXcQ",  # Valid 11-character video ID
            "title": "Test Video 1",
            "upload_date": "20250120",
            "duration": 300,
            "duration_string": "5:00",
            "view_count": 1000,
            "webpage_url": "https://youtube.com/watch?v=dQw4w9WgXcQ",
            "channel": "Test Channel",
            "channel_id": "UC123456789"
        },
        {
            "id": "jNQXAC9IVRw", # Valid 11-character video ID
            "title": "Test Video 2",
            "upload_date": "20250119",
            "duration": 240,
            "duration_string": "4:00",
            "view_count": 2000,
            "webpage_url": "https://youtube.com/watch?v=jNQXAC9IVRw",
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
        assert service.download_opts['format'] == 'bv*+ba/b'
        assert service.download_opts['merge_output_format'] == 'mkv'

    @patch('app.video_download_service.logger.isEnabledFor')
    def test_service_initialization_debug_mode(self, mock_is_enabled, mock_settings):
        """Test that yt-dlp options respect DEBUG logging level."""
        mock_is_enabled.return_value = True  # Simulate DEBUG level

        service = VideoDownloadService()

        # In DEBUG mode, yt-dlp should be verbose
        assert service.download_opts['quiet'] is False
        assert service.download_opts['noprogress'] is False
        assert service.download_opts['no_warnings'] is False

    @patch('app.video_download_service.logger.isEnabledFor')
    def test_service_initialization_info_mode(self, mock_is_enabled, mock_settings):
        """Test that yt-dlp options are quiet in INFO logging level."""
        mock_is_enabled.return_value = False  # Simulate INFO level

        service = VideoDownloadService()

        # In INFO mode, yt-dlp should be quiet
        assert service.download_opts['quiet'] is True
        assert service.download_opts['noprogress'] is True
        assert service.download_opts['no_warnings'] is True

    @patch('app.video_download_service.yt_dlp.YoutubeDL')
    def test_get_recent_videos_success(self, mock_ydl_class, mock_settings, sample_video_info):
        """Test successful retrieval of recent videos from a channel."""
        # Create 5 videos to satisfy the limit requirement
        extended_videos = sample_video_info + [
            {
                "id": "3rd_Video_ID",
                "title": "Test Video 3",
                "upload_date": "20250118",
                "duration": 180,
                "duration_string": "3:00",
                "view_count": 3000,
                "webpage_url": "https://youtube.com/watch?v=3rd_Video_ID",
                "channel": "Test Channel",
                "channel_id": "UC123456789"
            },
            {
                "id": "4th_Video_ID",
                "title": "Test Video 4",
                "upload_date": "20250117",
                "duration": 200,
                "duration_string": "3:20",
                "view_count": 4000,
                "webpage_url": "https://youtube.com/watch?v=4th_Video_ID",
                "channel": "Test Channel",
                "channel_id": "UC123456789"
            },
            {
                "id": "5th_Video_ID",
                "title": "Test Video 5",
                "upload_date": "20250116",
                "duration": 150,
                "duration_string": "2:30",
                "view_count": 5000,
                "webpage_url": "https://youtube.com/watch?v=5th_Video_ID",
                "channel": "Test Channel",
                "channel_id": "UC123456789"
            }
        ]

        # Mock yt-dlp behavior
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {
            'entries': extended_videos
        }

        service = VideoDownloadService()
        success, videos, error = service.get_recent_videos("https://youtube.com/@testchannel", limit=5)

        assert success is True
        assert error is None
        assert len(videos) == 5
        assert videos[0]['id'] == 'dQw4w9WgXcQ'
        assert videos[0]['title'] == 'Test Video 1'

        # Verify yt-dlp was called with correct parameters
        mock_ydl.extract_info.assert_called_once_with("https://youtube.com/@testchannel", download=False)

    @patch('app.video_download_service.yt_dlp.YoutubeDL')
    def test_get_recent_videos_no_entries(self, mock_ydl_class, mock_settings):
        """Test handling of channels with no videos (tries all fallbacks then fails)."""
        mock_ydl = Mock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl
        mock_ydl.extract_info.return_value = {'entries': []}
        
        service = VideoDownloadService()
        success, videos, error = service.get_recent_videos("https://youtube.com/@testchannel")
        
        # Current behavior: if no entries found after all fallbacks, it fails
        # This could be changed to success with empty list, but current behavior is reasonable
        assert success is False
        assert videos == []
        assert "Could not extract videos using any method" in error

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
        # Create channel directory that the service expects
        channel_dir = os.path.join(mock_settings.media_dir, f"{test_channel.name} [{test_channel.channel_id}]")
        os.makedirs(channel_dir, exist_ok=True)

        # Create a dummy video file to simulate successful download
        video_file = os.path.join(channel_dir, "Test Video 1 [dQw4w9WgXcQ].mkv")
        with open(video_file, 'w') as f:
            f.write("dummy video content")

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
        expected_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
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
        mock_get_recent_videos.assert_called_once_with(test_channel.url, test_channel.limit, test_channel.channel_id)
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

    def test_extract_upload_date_from_info_json_success(self, mock_settings):
        """Test successful extraction of upload_date from .info.json file."""
        service = VideoDownloadService()

        # Create test directory structure
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123]", "2023")
        os.makedirs(test_dir, exist_ok=True)

        # Create test video file and .info.json
        video_path = os.path.join(test_dir, "Test Video [abc123].mkv")
        info_json_path = os.path.join(test_dir, "Test Video [abc123].info.json")

        # Write test .info.json with valid upload_date
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "upload_date": "20231115",
                "title": "Test Video",
                "id": "abc123"
            }, f)

        upload_date = service.extract_upload_date_from_info_json(video_path)

        assert upload_date == "20231115"

    def test_extract_upload_date_from_info_json_missing_file(self, mock_settings):
        """Test handling when .info.json file doesn't exist."""
        service = VideoDownloadService()

        # Path to non-existent video file
        video_path = "/nonexistent/path/video.mkv"

        upload_date = service.extract_upload_date_from_info_json(video_path)

        assert upload_date is None

    def test_extract_upload_date_from_info_json_no_upload_date_field(self, mock_settings):
        """Test handling when .info.json exists but has no upload_date field."""
        service = VideoDownloadService()

        # Create test directory and files
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123]", "2023")
        os.makedirs(test_dir, exist_ok=True)

        video_path = os.path.join(test_dir, "Test Video [xyz789].mkv")
        info_json_path = os.path.join(test_dir, "Test Video [xyz789].info.json")

        # Write .info.json WITHOUT upload_date field
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "title": "Test Video",
                "id": "xyz789"
            }, f)

        upload_date = service.extract_upload_date_from_info_json(video_path)

        assert upload_date is None

    def test_extract_upload_date_from_info_json_invalid_format(self, mock_settings):
        """Test validation of upload_date format (should be YYYYMMDD - 8 digits)."""
        service = VideoDownloadService()

        test_cases = [
            ("2023-11-15", "Dashed format"),  # Wrong format
            ("20231", "Too short"),           # Too short
            ("202311151234", "Too long"),     # Too long
            ("abcd1234", "Non-numeric"),      # Contains letters
            ("", "Empty string"),             # Empty
        ]

        for invalid_date, description in test_cases:
            # Create test files
            test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123]", "2023")
            os.makedirs(test_dir, exist_ok=True)

            video_path = os.path.join(test_dir, f"Test Video [{description}].mkv")
            info_json_path = os.path.join(test_dir, f"Test Video [{description}].info.json")

            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump({"upload_date": invalid_date}, f)

            upload_date = service.extract_upload_date_from_info_json(video_path)

            assert upload_date is None, f"Expected None for {description}, got {upload_date}"

    def test_extract_upload_date_from_info_json_malformed_json(self, mock_settings):
        """Test handling of malformed JSON in .info.json file."""
        service = VideoDownloadService()

        # Create test directory
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123]", "2023")
        os.makedirs(test_dir, exist_ok=True)

        video_path = os.path.join(test_dir, "Test Video [bad123].mkv")
        info_json_path = os.path.join(test_dir, "Test Video [bad123].info.json")

        # Write malformed JSON
        with open(info_json_path, 'w', encoding='utf-8') as f:
            f.write("{invalid json content")

        upload_date = service.extract_upload_date_from_info_json(video_path)

        assert upload_date is None

    def test_extract_upload_date_from_info_json_different_extensions(self, mock_settings):
        """Test that extraction works with different video file extensions."""
        service = VideoDownloadService()

        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123]", "2023")
        os.makedirs(test_dir, exist_ok=True)

        # Test multiple video extensions
        # Note: video ID should not contain the extension to avoid .replace() issues
        for idx, ext in enumerate(['.mkv', '.mp4', '.webm', '.avi']):
            ext_name = ext[1:]  # Remove leading dot
            video_path = os.path.join(test_dir, f"Test Video {idx} [vid{idx}]{ext}")
            info_json_path = os.path.join(test_dir, f"Test Video {idx} [vid{idx}].info.json")

            # Write valid .info.json
            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump({"upload_date": "20231120"}, f)

            upload_date = service.extract_upload_date_from_info_json(video_path)

            assert upload_date == "20231120", f"Failed for extension {ext}"

    def test_extract_upload_date_from_info_json_null_path(self, mock_settings):
        """Test handling of None/empty video_file_path."""
        service = VideoDownloadService()

        # Test None path
        upload_date = service.extract_upload_date_from_info_json(None)
        assert upload_date is None

        # Test empty string path
        upload_date = service.extract_upload_date_from_info_json("")
        assert upload_date is None

    def test_extract_upload_date_invalid_semantic_dates(self, mock_settings):
        """Test that semantic date validation rejects invalid calendar dates."""
        service = VideoDownloadService()

        test_cases = [
            ("99999999", "Invalid year"),        # Year 9999
            ("20251399", "Invalid month"),       # Month 13
            ("20251132", "Invalid day"),         # Day 32
            ("20250230", "Invalid Feb 30"),      # Feb 30th doesn't exist
            ("20230431", "Invalid April 31"),    # April 31st doesn't exist
        ]

        for invalid_date, description in test_cases:
            # Create test files
            test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123]", "2023")
            os.makedirs(test_dir, exist_ok=True)

            video_path = os.path.join(test_dir, f"Test Video [{description.replace(' ', '_')}].mkv")
            info_json_path = os.path.join(test_dir, f"Test Video [{description.replace(' ', '_')}].info.json")

            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump({"upload_date": invalid_date}, f)

            upload_date = service.extract_upload_date_from_info_json(video_path)

            assert upload_date is None, f"Expected None for {description} ({invalid_date}), got {upload_date}"

    def test_wait_for_info_json_ready_success(self, mock_settings):
        """Test that _wait_for_info_json_ready successfully detects a ready file."""
        service = VideoDownloadService()

        # Create test directory and files
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123]", "2023")
        os.makedirs(test_dir, exist_ok=True)

        video_path = os.path.join(test_dir, "Test Video [xyz789].mkv")
        info_json_path = os.path.join(test_dir, "Test Video [xyz789].info.json")

        # Write .info.json file (simulating yt-dlp finished writing)
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump({"upload_date": "20231115", "title": "Test"}, f)

        # Should detect file is ready quickly
        result = service._wait_for_info_json_ready(video_path, timeout=5)

        assert result is True

    def test_wait_for_info_json_ready_timeout(self, mock_settings):
        """Test that _wait_for_info_json_ready times out when file doesn't exist."""
        service = VideoDownloadService()

        # Create test directory but NO .info.json file
        test_dir = os.path.join(mock_settings.media_dir, "Test Channel [UC123]", "2023")
        os.makedirs(test_dir, exist_ok=True)

        video_path = os.path.join(test_dir, "Test Video [missing].mkv")

        # Should timeout after specified duration
        result = service._wait_for_info_json_ready(video_path, timeout=0.5)

        assert result is False

    def test_wait_for_info_json_ready_null_path(self, mock_settings):
        """Test that _wait_for_info_json_ready handles null path gracefully."""
        service = VideoDownloadService()

        result = service._wait_for_info_json_ready(None)
        assert result is False

        result = service._wait_for_info_json_ready("")
        assert result is False

    def test_global_service_instance(self):
        """Test that global service instance is properly configured."""
        # The global instance should be importable and configured
        from app.video_download_service import video_download_service

        assert video_download_service is not None
        assert hasattr(video_download_service, 'get_recent_videos')
        assert hasattr(video_download_service, 'download_video')
        assert hasattr(video_download_service, 'process_channel_downloads')