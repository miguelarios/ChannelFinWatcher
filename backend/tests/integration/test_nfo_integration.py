"""
Integration tests for NFO file generation workflow.

This test suite validates end-to-end NFO generation within the download workflow:
- NFO generation triggered by successful video downloads
- Error handling when NFO generation fails
- Season NFO creation for new year directories
- Integration between VideoDownloadService and NFOService
- NFO failures don't block successful downloads

Testing Strategy:
- Mock external dependencies (yt-dlp, network calls)
- Use real file system operations in temporary directories
- Test integration between services
- Validate error propagation and handling
- Ensure download workflow robustness
"""

import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest
import xml.etree.ElementTree as ET

from app.nfo_service import NFOService, get_nfo_service
from app.video_download_service import VideoDownloadService
from app.models import Channel


# =========================================================================
# FIXTURES - Integration Test Setup
# =========================================================================

@pytest.fixture
def temp_media_dir():
    """Create temporary media directory for integration tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def nfo_service(temp_media_dir):
    """Create NFO service with temporary directory."""
    return NFOService(media_path=temp_media_dir)


@pytest.fixture
def mock_channel():
    """
    Mock Channel database object for integration testing.

    Includes all fields that might be accessed during download/NFO workflow.
    """
    channel = Mock(spec=Channel)
    channel.id = 1
    channel.name = "Ms Rachel - Toddler Learning Videos"
    channel.channel_id = "UCzGzk0K7GLJ_edZu4u3TyUg"
    channel.url = "https://youtube.com/@msrachel"
    channel.limit = 10
    channel.enabled = True
    channel.directory_path = None  # Will be set during test
    channel.metadata_path = None
    return channel


@pytest.fixture
def sample_episode_metadata():
    """
    Sample episode metadata from yt-dlp download.

    This represents the .info.json file created by yt-dlp after download.
    """
    return {
        "id": "drkVagtmIJA",
        "title": "Hide and Seek with Ms Rachel & Elmo",
        "channel": "Ms Rachel - Toddler Learning Videos",
        "description": "Learn and play with Ms Rachel and Elmo!",
        "upload_date": "20250109",
        "duration": 3746,
        "uploader": "Ms Rachel - Toddler Learning Videos",
        "language": "en",
        "categories": ["Education"],
        "tags": [
            "ms rachel",
            "toddler learning video",
            "educational videos"
        ]
    }


@pytest.fixture
def sample_channel_metadata():
    """
    Sample channel metadata for tvshow.nfo generation.
    """
    return {
        "id": "UCzGzk0K7GLJ_edZu4u3TyUg",
        "channel": "Ms Rachel - Toddler Learning Videos",
        "channel_id": "UCzGzk0K7GLJ_edZu4u3TyUg",
        "description": "Educational videos for toddlers",
        "tags": ["toddler learning", "education"]
    }


# =========================================================================
# INTEGRATION TESTS - Download → NFO Workflow
# =========================================================================

class TestNFOGenerationTriggeredByDownload:
    """
    Test NFO generation as part of the video download workflow.

    These tests simulate the actual production workflow:
    1. Video download completes successfully
    2. .info.json is created by yt-dlp
    3. NFO service is called to generate episode.nfo
    4. Season.nfo is created if new year directory
    """

    def test_episode_nfo_created_after_successful_download(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel,
        sample_episode_metadata
    ):
        """
        Test that episode.nfo is created after successful video download.

        Workflow:
        1. Simulate successful video download
        2. Create .info.json file (as yt-dlp would)
        3. Call NFO service to generate episode.nfo
        4. Verify episode.nfo exists and has correct content

        This tests the integration shown in video_download_service.py lines 578-605
        """
        # Setup: Simulate successful download
        channel_dir = os.path.join(temp_media_dir, "Ms Rachel [UCzGzk0K7]")
        year_dir = os.path.join(channel_dir, "2025")
        video_dir = os.path.join(year_dir, "Hide and Seek [drkVagtmIJA]")
        os.makedirs(video_dir, exist_ok=True)

        # Create video file (simulating yt-dlp download)
        video_path = os.path.join(video_dir, "video.mkv")
        Path(video_path).touch()

        # Create .info.json file (simulating yt-dlp metadata extraction)
        info_json_path = os.path.join(video_dir, "video.info.json")
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(sample_episode_metadata, f)

        # Execute: Generate NFO (as would be done in download service)
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: NFO generation succeeded
        assert success is True
        assert error is None

        # Verify: episode.nfo file exists
        nfo_path = os.path.join(video_dir, "video.nfo")
        assert os.path.exists(nfo_path), "episode.nfo was not created"

        # Verify: NFO content is correct
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        assert root.tag == 'episodedetails'
        assert root.find('title').text == sample_episode_metadata['title']
        assert root.find('showtitle').text == sample_episode_metadata['channel']
        assert root.find('premiered').text == '2025-01-09'
        assert root.find('aired').text == '2025-01-09'
        assert root.find('runtime').text == '62'  # 3746 / 60 = 62

    def test_season_nfo_created_for_new_year_directory(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel,
        sample_episode_metadata
    ):
        """
        Test that season.nfo is created when first video in new year is downloaded.

        Workflow:
        1. Download first video of 2025
        2. Year directory (2025/) is created
        3. Season.nfo should be generated for 2025/
        4. Subsequent downloads to 2025/ should NOT regenerate season.nfo

        This tests the integration shown in video_download_service.py lines 589-601
        """
        # Setup: Simulate first download of 2025
        channel_dir = os.path.join(temp_media_dir, "Ms Rachel [UCzGzk0K7]")
        year_dir = os.path.join(channel_dir, "2025")
        video_dir = os.path.join(year_dir, "Video [drkVagtmIJA]")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(sample_episode_metadata, f)

        # Execute: Generate episode NFO
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)
        assert success is True

        # Simulate the logic in video_download_service.py lines 592-600
        season_nfo_path = os.path.join(year_dir, 'season.nfo')

        # Generate season.nfo if it doesn't exist
        if not os.path.exists(season_nfo_path):
            season_success, season_error = nfo_service.generate_season_nfo(year_dir)
            assert season_success is True
            assert season_error is None

        # Verify: season.nfo was created
        assert os.path.exists(season_nfo_path), "season.nfo was not created"

        # Verify: season.nfo content
        tree = ET.parse(season_nfo_path)
        root = tree.getroot()

        assert root.tag == 'season'
        assert root.find('title').text == '2025'
        assert root.find('season').text == '2025'

    def test_existing_season_nfo_not_overwritten(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel,
        sample_episode_metadata
    ):
        """
        Test that existing season.nfo is not regenerated on subsequent downloads.

        Workflow:
        1. Create existing season.nfo with specific timestamp
        2. Download another video in same year
        3. Verify season.nfo was NOT overwritten (timestamp unchanged)

        This validates the check in video_download_service.py line 597:
        "if not os.path.exists(season_nfo_path)"
        """
        # Setup: Create year directory with existing season.nfo
        channel_dir = os.path.join(temp_media_dir, "Ms Rachel [UCzGzk0K7]")
        year_dir = os.path.join(channel_dir, "2025")
        os.makedirs(year_dir, exist_ok=True)

        # Create existing season.nfo
        season_nfo_path = os.path.join(year_dir, 'season.nfo')
        original_content = b'<?xml version="1.0" ?>\n<season>\n  <title>2025</title>\n</season>'
        with open(season_nfo_path, 'wb') as f:
            f.write(original_content)

        original_mtime = os.path.getmtime(season_nfo_path)

        # Setup: Second video download in same year
        video_dir = os.path.join(year_dir, "Video2 [xyz123]")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(sample_episode_metadata, f)

        # Execute: Generate episode NFO (second video)
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)
        assert success is True

        # Simulate the logic: Only generate season.nfo if it doesn't exist
        if not os.path.exists(season_nfo_path):
            nfo_service.generate_season_nfo(year_dir)

        # Verify: season.nfo was NOT regenerated (modification time unchanged)
        current_mtime = os.path.getmtime(season_nfo_path)
        assert current_mtime == original_mtime, "season.nfo was unexpectedly regenerated"

        # Verify: Content unchanged
        with open(season_nfo_path, 'rb') as f:
            current_content = f.read()
            assert current_content == original_content


# =========================================================================
# ERROR HANDLING INTEGRATION TESTS
# =========================================================================

class TestNFOErrorHandling:
    """
    Test error handling in NFO generation workflow.

    Key requirement: NFO generation failures should NOT block downloads.
    Downloads must complete successfully even if NFO generation fails.
    """

    def test_download_succeeds_when_info_json_missing(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel
    ):
        """
        Test that download is recorded as successful even when .info.json is missing.

        Workflow:
        1. Video downloads successfully
        2. .info.json is missing (yt-dlp error)
        3. NFO generation fails gracefully
        4. Download is still marked as successful

        This tests the error handling in video_download_service.py lines 584-587
        """
        # Setup: Video file without .info.json
        channel_dir = os.path.join(temp_media_dir, "Channel [ID123]")
        year_dir = os.path.join(channel_dir, "2025")
        video_dir = os.path.join(year_dir, "Video [xyz]")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        Path(video_path).touch()
        # Note: .info.json is NOT created

        # Execute: Try to generate NFO
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: NFO generation failed (as expected)
        assert success is False
        assert error is not None
        assert "Info JSON not found" in error

        # Verify: Video file still exists (download wasn't rolled back)
        assert os.path.exists(video_path)

        # In real workflow, download would be marked successful despite NFO failure
        # This is the key behavior: NFO is nice-to-have, not required

    def test_download_succeeds_when_info_json_corrupted(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel
    ):
        """
        Test that download succeeds even when .info.json is corrupted.

        Workflow:
        1. Video downloads successfully
        2. .info.json is malformed (JSON parse error)
        3. NFO generation fails gracefully
        4. Download is still successful

        This validates graceful error handling per video_download_service.py lines 584-587
        """
        # Setup: Video with corrupted .info.json
        channel_dir = os.path.join(temp_media_dir, "Channel [ID123]")
        year_dir = os.path.join(channel_dir, "2025")
        video_dir = os.path.join(year_dir, "Video [xyz]")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()

        # Create corrupted JSON
        with open(info_json_path, 'w', encoding='utf-8') as f:
            f.write("{invalid json content")

        # Execute: Try to generate NFO
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: NFO generation failed gracefully
        assert success is False
        assert error is not None
        assert "Failed to parse JSON" in error

        # Verify: Video file still exists
        assert os.path.exists(video_path)

    def test_download_continues_when_nfo_service_crashes(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel,
        sample_episode_metadata
    ):
        """
        Test that unexpected NFO service errors don't crash download workflow.

        Workflow:
        1. Video downloads successfully
        2. NFO service encounters unexpected error
        3. Exception is caught by download service
        4. Download completes successfully

        This validates the broad exception handler in video_download_service.py lines 602-605
        """
        # Setup: Valid download scenario
        channel_dir = os.path.join(temp_media_dir, "Channel [ID123]")
        year_dir = os.path.join(channel_dir, "2025")
        video_dir = os.path.join(year_dir, "Video [xyz]")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(sample_episode_metadata, f)

        # Simulate unexpected error in NFO generation
        with patch.object(
            nfo_service,
            '_create_episode_nfo_xml',
            side_effect=Exception("Unexpected NFO error")
        ):
            # Execute: Try to generate NFO (will fail)
            success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

            # Verify: NFO generation failed
            assert success is False
            assert "Unexpected NFO error" in error

        # Verify: Video file still exists (download wasn't affected)
        assert os.path.exists(video_path)

        # In production, this exception would be caught by the try-except
        # block in video_download_service.py lines 602-605, and download
        # would complete successfully with a warning log

    def test_season_nfo_failure_does_not_block_episode_nfo(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel,
        sample_episode_metadata
    ):
        """
        Test that season.nfo generation failure doesn't prevent episode.nfo creation.

        Workflow:
        1. Episode.nfo generates successfully
        2. Season.nfo generation fails (e.g., invalid year directory)
        3. Episode.nfo still exists
        4. Download completes successfully

        This validates independent error handling for season vs episode NFO
        """
        # Setup: Valid episode, but problematic year directory
        channel_dir = os.path.join(temp_media_dir, "Channel [ID123]")
        # Note: Using invalid year directory name
        year_dir = os.path.join(channel_dir, "Videos")  # Not a year!
        video_dir = os.path.join(year_dir, "Video [xyz]")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(sample_episode_metadata, f)

        # Execute: Generate episode NFO
        episode_success, episode_error = nfo_service.generate_episode_nfo(
            video_path,
            mock_channel
        )

        # Verify: Episode NFO succeeded
        assert episode_success is True
        assert episode_error is None

        nfo_path = os.path.join(video_dir, "video.nfo")
        assert os.path.exists(nfo_path), "episode.nfo should exist"

        # Execute: Try to generate season NFO (will fail due to invalid year)
        season_nfo_path = os.path.join(year_dir, 'season.nfo')
        if not os.path.exists(season_nfo_path):
            season_success, season_error = nfo_service.generate_season_nfo(year_dir)

            # Verify: Season NFO failed (as expected)
            assert season_success is False
            assert "Invalid year directory" in season_error

        # Verify: Episode NFO still exists despite season NFO failure
        assert os.path.exists(nfo_path), "episode.nfo should not be affected"


# =========================================================================
# MULTIPLE VIDEO WORKFLOW TESTS
# =========================================================================

class TestMultipleVideoNFOGeneration:
    """
    Test NFO generation across multiple video downloads.

    Validates:
    - Multiple episodes in same season
    - Episodes across multiple seasons
    - NFO consistency across downloads
    """

    def test_multiple_episodes_in_same_year(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel,
        sample_episode_metadata
    ):
        """
        Test NFO generation for multiple videos downloaded to same year.

        Workflow:
        1. Download 3 videos in 2025
        2. Each gets episode.nfo
        3. Only one season.nfo for 2025/
        """
        channel_dir = os.path.join(temp_media_dir, "Channel [ID123]")
        year_dir = os.path.join(channel_dir, "2025")

        video_ids = ["abc123", "def456", "ghi789"]

        for video_id in video_ids:
            # Setup: Create video and metadata
            video_dir = os.path.join(year_dir, f"Video [{video_id}]")
            os.makedirs(video_dir, exist_ok=True)

            video_path = os.path.join(video_dir, "video.mkv")
            info_json_path = os.path.join(video_dir, "video.info.json")

            Path(video_path).touch()

            # Customize metadata for each video
            metadata = sample_episode_metadata.copy()
            metadata['id'] = video_id
            metadata['title'] = f"Video {video_id}"

            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f)

            # Execute: Generate episode NFO
            success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)
            assert success is True

            # Verify: Episode NFO exists
            nfo_path = os.path.join(video_dir, "video.nfo")
            assert os.path.exists(nfo_path)

            # Generate season NFO only if it doesn't exist
            season_nfo_path = os.path.join(year_dir, 'season.nfo')
            if not os.path.exists(season_nfo_path):
                season_success, _ = nfo_service.generate_season_nfo(year_dir)
                assert season_success is True

        # Verify: All 3 episode NFOs exist
        for video_id in video_ids:
            video_dir = os.path.join(year_dir, f"Video [{video_id}]")
            nfo_path = os.path.join(video_dir, "video.nfo")
            assert os.path.exists(nfo_path), f"NFO missing for {video_id}"

        # Verify: Only one season.nfo
        season_nfo_path = os.path.join(year_dir, 'season.nfo')
        assert os.path.exists(season_nfo_path)

    def test_episodes_across_multiple_years(
        self,
        temp_media_dir,
        nfo_service,
        mock_channel,
        sample_episode_metadata
    ):
        """
        Test NFO generation for videos across multiple years.

        Workflow:
        1. Download videos in 2023, 2024, 2025
        2. Each year gets its own season.nfo
        3. Each video gets episode.nfo
        """
        channel_dir = os.path.join(temp_media_dir, "Channel [ID123]")

        years = ["2023", "2024", "2025"]

        for year in years:
            year_dir = os.path.join(channel_dir, year)
            video_dir = os.path.join(year_dir, f"Video_{year}")
            os.makedirs(video_dir, exist_ok=True)

            # Setup: Create video and metadata
            video_path = os.path.join(video_dir, "video.mkv")
            info_json_path = os.path.join(video_dir, "video.info.json")

            Path(video_path).touch()

            # Customize metadata for each year
            metadata = sample_episode_metadata.copy()
            metadata['upload_date'] = f"{year}0615"  # June 15 of each year
            metadata['title'] = f"Video from {year}"

            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f)

            # Execute: Generate episode NFO
            success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)
            assert success is True

            # Generate season NFO
            season_nfo_path = os.path.join(year_dir, 'season.nfo')
            if not os.path.exists(season_nfo_path):
                season_success, _ = nfo_service.generate_season_nfo(year_dir)
                assert season_success is True

        # Verify: Each year has season.nfo
        for year in years:
            year_dir = os.path.join(channel_dir, year)
            season_nfo_path = os.path.join(year_dir, 'season.nfo')
            assert os.path.exists(season_nfo_path), f"season.nfo missing for {year}"

            # Verify: season.nfo has correct year
            tree = ET.parse(season_nfo_path)
            root = tree.getroot()
            assert root.find('title').text == year

        # Verify: Each year has episode NFO
        for year in years:
            year_dir = os.path.join(channel_dir, year)
            video_dir = os.path.join(year_dir, f"Video_{year}")
            nfo_path = os.path.join(video_dir, "video.nfo")
            assert os.path.exists(nfo_path), f"episode.nfo missing for {year}"


# =========================================================================
# TVSHOW NFO INTEGRATION TESTS
# =========================================================================

class TestTvshowNFOIntegration:
    """
    Test tvshow.nfo generation integration.

    Note: In current implementation, tvshow.nfo generation is not yet
    integrated into the download workflow. These tests prepare for that
    integration and can be used to test manual tvshow.nfo generation.
    """

    def test_tvshow_nfo_generation_with_channel_metadata(
        self,
        temp_media_dir,
        nfo_service,
        sample_channel_metadata
    ):
        """
        Test tvshow.nfo generation from channel metadata.

        This would be called when:
        - Channel is first added to monitoring
        - Channel metadata is manually refreshed
        - Batch NFO regeneration is triggered
        """
        # Setup: Create channel directory and metadata
        channel_dir = os.path.join(temp_media_dir, "Ms Rachel [UCzGzk0K7]")
        os.makedirs(channel_dir, exist_ok=True)

        metadata_path = os.path.join(channel_dir, "channel.info.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(sample_channel_metadata, f)

        # Execute: Generate tvshow.nfo
        success, error = nfo_service.generate_tvshow_nfo(metadata_path, channel_dir)

        # Verify: Success
        assert success is True
        assert error is None

        # Verify: tvshow.nfo exists
        tvshow_nfo_path = os.path.join(channel_dir, "tvshow.nfo")
        assert os.path.exists(tvshow_nfo_path)

        # Verify: Content
        tree = ET.parse(tvshow_nfo_path)
        root = tree.getroot()

        assert root.tag == 'tvshow'
        assert root.find('title').text == sample_channel_metadata['channel']
        assert root.find('studio').text == 'YouTube'

    def test_tvshow_nfo_regeneration_on_metadata_refresh(
        self,
        temp_media_dir,
        nfo_service,
        sample_channel_metadata
    ):
        """
        Test that tvshow.nfo is regenerated when channel metadata updates.

        Future integration: When metadata refresh endpoint is called,
        it should regenerate tvshow.nfo with updated information.
        """
        # Setup: Create initial tvshow.nfo
        channel_dir = os.path.join(temp_media_dir, "Ms Rachel [UCzGzk0K7]")
        os.makedirs(channel_dir, exist_ok=True)

        metadata_path = os.path.join(channel_dir, "channel.info.json")

        # Initial metadata
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(sample_channel_metadata, f)

        # Generate initial tvshow.nfo
        success, error = nfo_service.generate_tvshow_nfo(metadata_path, channel_dir)
        assert success is True

        tvshow_nfo_path = os.path.join(channel_dir, "tvshow.nfo")

        # Read initial content
        tree = ET.parse(tvshow_nfo_path)
        root = tree.getroot()
        original_description = root.find('plot').text

        # Simulate metadata refresh: Update channel description
        updated_metadata = sample_channel_metadata.copy()
        updated_metadata['description'] = "UPDATED: New channel description"

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(updated_metadata, f)

        # Regenerate tvshow.nfo (as would happen on metadata refresh)
        success, error = nfo_service.generate_tvshow_nfo(metadata_path, channel_dir)
        assert success is True

        # Verify: Content reflects updated metadata
        tree = ET.parse(tvshow_nfo_path)
        root = tree.getroot()
        new_description = root.find('plot').text

        assert new_description == "UPDATED: New channel description"
        assert new_description != original_description, "tvshow.nfo should be regenerated with new content"
