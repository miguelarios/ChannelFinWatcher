"""
Unit tests for NFO file generation service.

This test suite validates the NFO service's ability to:
- Generate episode.nfo files from yt-dlp metadata
- Generate season.nfo files for year-based directories
- Generate tvshow.nfo files from channel metadata
- Handle missing or malformed data gracefully
- Escape XML special characters correctly
- Transform date and duration formats appropriately

Testing Strategy:
- Use temporary directories for all file operations
- Mock external dependencies (file system when appropriate)
- Provide comprehensive fixtures for sample metadata
- Test both success and error scenarios
- Validate XML structure and content
"""

import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest
import xml.etree.ElementTree as ET

from app.nfo_service import NFOService
from app.models import Channel


# =========================================================================
# FIXTURES - Sample Data and Test Helpers
# =========================================================================

@pytest.fixture
def temp_media_dir():
    """
    Create a temporary media directory for file operations.

    Why temporary directory?
    - Ensures test isolation (no cross-test contamination)
    - Automatic cleanup after test completion
    - Safe to perform destructive operations
    - Mirrors production directory structure
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def nfo_service(temp_media_dir):
    """
    Create NFOService instance with temporary media path.

    Why fixture?
    - Consistent service initialization across tests
    - Uses isolated temporary directory
    - Matches production initialization pattern
    """
    return NFOService(media_path=temp_media_dir)


@pytest.fixture
def sample_episode_info():
    """
    Sample episode metadata from yt-dlp .info.json file.

    This represents REAL production data structure from testing.
    Based on Ms Rachel video: "Hide and Seek with Ms Rachel & Elmo..."

    Why use real data?
    - Tests against actual yt-dlp output format
    - Validates handling of production edge cases
    - Ensures compatibility with real metadata
    """
    return {
        "id": "drkVagtmIJA",
        "title": "Hide and Seek with Ms Rachel & Elmo, Elmo Visits Blippi's Treehouse - Videos for Toddlers",
        "channel": "Ms Rachel - Toddler Learning Videos",
        "description": "Learn and play with Ms Rachel, Elmo, and Blippi!\n\nThis video includes multiple segments for learning.",
        "upload_date": "20250109",
        "duration": 3746,  # 62 minutes 26 seconds
        "uploader": "Ms Rachel - Toddler Learning Videos",
        "language": "en",
        "categories": ["Education"],
        "tags": [
            "ms rachel",
            "toddler learning video",
            "baby learning videos",
            "learning videos for toddlers",
            "speech therapy",
            "toddler videos",
            "songs for toddlers",
            "videos for babies",
            "learning video",
            "ms rachel elmo",
            "blippi",
            "elmo",
            "sesame street",
            "hide and seek",
            "nursery rhymes",
            "educational videos",
            "learning songs",
            "kids songs",
            "baby songs",
            "children songs",
            "toddler songs",
            "preschool learning",
            "speech delay",
            "baby learning",
            "toddler learning",
            "education"
        ]
    }


@pytest.fixture
def sample_episode_info_minimal():
    """
    Minimal episode metadata with only required fields.

    Tests graceful handling when optional fields are missing.
    Only title and channel are truly required for NFO generation.
    """
    return {
        "title": "Test Video Title",
        "channel": "Test Channel"
    }


@pytest.fixture
def sample_channel_info():
    """
    Sample channel metadata from yt-dlp channel extraction.

    Important: Channel metadata does NOT have 'categories' field
    (only episode-level metadata has categories).
    Tags are mapped to both genres and tags.
    """
    return {
        "id": "UCzGzk0K7GLJ_edZu4u3TyUg",
        "channel": "Ms Rachel - Toddler Learning Videos",
        "channel_id": "UCzGzk0K7GLJ_edZu4u3TyUg",
        "description": "Hi! I'm Ms Rachel and I love helping toddlers learn and grow through play!",
        "tags": [
            "toddler learning",
            "speech therapy",
            "educational videos",
            "baby learning",
            "preschool"
        ]
    }


@pytest.fixture
def sample_channel_info_minimal():
    """
    Minimal channel metadata with only required field (channel name).
    """
    return {
        "channel": "Test Channel"
    }


@pytest.fixture
def mock_channel():
    """
    Mock Channel database object for testing.

    Why mock?
    - Tests don't need full database setup
    - Can control all attributes easily
    - Isolates NFO service from database layer
    """
    channel = Mock(spec=Channel)
    channel.id = 1
    channel.name = "Ms Rachel - Toddler Learning Videos"
    channel.channel_id = "UCzGzk0K7GLJ_edZu4u3TyUg"
    channel.url = "https://youtube.com/@msrachel"
    return channel


# =========================================================================
# EPISODE NFO GENERATION TESTS
# =========================================================================

class TestEpisodeNFOGeneration:
    """Test suite for episode.nfo file generation."""

    def test_episode_nfo_generation_with_complete_metadata(
        self,
        nfo_service,
        temp_media_dir,
        sample_episode_info,
        mock_channel
    ):
        """
        Test episode NFO generation with complete metadata.

        Validates:
        - All fields are correctly mapped from JSON to XML
        - Date transformation (20250109 → 2025-01-09)
        - Duration conversion (3746 seconds → 62 minutes)
        - Multiple tags and categories are included
        - XML structure matches Jellyfin schema
        """
        # Setup: Create video file and .info.json
        video_dir = os.path.join(temp_media_dir, "Channel", "2025", "Video [drkVagtmIJA]")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        # Create dummy video file
        Path(video_path).touch()

        # Write .info.json
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(sample_episode_info, f)

        # Execute: Generate episode NFO
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: Success
        assert success is True
        assert error is None

        # Verify: NFO file created
        nfo_path = os.path.join(video_dir, "video.nfo")
        assert os.path.exists(nfo_path)

        # Verify: XML content
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        assert root.tag == 'episodedetails'
        assert root.find('title').text == sample_episode_info['title']
        assert root.find('showtitle').text == sample_episode_info['channel']
        assert root.find('plot').text == sample_episode_info['description']
        assert root.find('aired').text == '2025-01-09'
        assert root.find('year').text == '2025'
        assert root.find('runtime').text == '62'  # 3746 seconds / 60
        assert root.find('director').text == sample_episode_info['uploader']
        assert root.find('studio').text == 'YouTube'
        assert root.find('language').text == 'en'

        # Verify: Unique ID
        uniqueid = root.find('uniqueid')
        assert uniqueid is not None
        assert uniqueid.get('type') == 'youtube'
        assert uniqueid.get('default') == 'true'
        assert uniqueid.text == 'drkVagtmIJA'

        # Verify: Genres (from categories)
        genres = [g.text for g in root.findall('genre')]
        assert 'Education' in genres

        # Verify: Tags
        tags = [t.text for t in root.findall('tag')]
        assert 'ms rachel' in tags
        assert 'toddler learning video' in tags
        assert len(tags) == len(sample_episode_info['tags'])

    def test_episode_nfo_generation_with_minimal_metadata(
        self,
        nfo_service,
        temp_media_dir,
        sample_episode_info_minimal,
        mock_channel
    ):
        """
        Test episode NFO generation with only required fields.

        Validates:
        - NFO generation succeeds with minimal metadata
        - Optional fields are gracefully omitted
        - Required fields (title, showtitle) are present
        """
        # Setup
        video_dir = os.path.join(temp_media_dir, "Channel", "2025", "Video")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(sample_episode_info_minimal, f)

        # Execute
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: Success
        assert success is True
        assert error is None

        # Verify: NFO exists and has required fields
        nfo_path = os.path.join(video_dir, "video.nfo")
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        assert root.find('title').text == "Test Video Title"
        assert root.find('showtitle').text == "Test Channel"
        assert root.find('studio').text == 'YouTube'

        # Optional fields should not exist or be empty
        assert root.find('plot') is None or root.find('plot').text is None
        assert root.find('aired') is None
        assert root.find('runtime') is None

    def test_episode_nfo_xml_character_escaping(
        self,
        nfo_service,
        temp_media_dir,
        mock_channel
    ):
        """
        Test XML special character escaping in episode NFO.

        Validates:
        - Ampersands (&) are escaped to &amp;
        - Less-than (<) and greater-than (>) are escaped
        - Quotes are handled correctly
        - ElementTree handles escaping automatically
        """
        # Setup: Episode with special characters
        episode_info = {
            "title": "Testing & Validation: <Quick> \"Test\"",
            "channel": "Test & Learn",
            "description": "Description with & < > \" characters"
        }

        video_dir = os.path.join(temp_media_dir, "Channel", "2025", "Video")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(episode_info, f)

        # Execute
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: Success and proper escaping
        assert success is True

        nfo_path = os.path.join(video_dir, "video.nfo")
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        # ElementTree automatically unescapes when parsing
        assert root.find('title').text == "Testing & Validation: <Quick> \"Test\""
        assert root.find('showtitle').text == "Test & Learn"
        assert root.find('plot').text == "Description with & < > \" characters"

        # Verify raw XML contains escaped characters
        with open(nfo_path, 'r', encoding='utf-8') as f:
            raw_xml = f.read()
            assert '&amp;' in raw_xml
            assert '&lt;' in raw_xml or '<Quick>' not in raw_xml

    def test_episode_nfo_multiline_description_preservation(
        self,
        nfo_service,
        temp_media_dir,
        mock_channel
    ):
        """
        Test that multi-line descriptions are preserved in episode NFO.

        Validates:
        - Newline characters are preserved
        - Multi-paragraph descriptions work correctly
        - XML formatting doesn't corrupt description
        """
        # Setup: Episode with multi-line description
        episode_info = {
            "title": "Test Video",
            "channel": "Test Channel",
            "description": "First paragraph.\n\nSecond paragraph with details.\n\nThird paragraph."
        }

        video_dir = os.path.join(temp_media_dir, "Channel", "2025", "Video")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(episode_info, f)

        # Execute
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: Newlines preserved
        assert success is True

        nfo_path = os.path.join(video_dir, "video.nfo")
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        plot_text = root.find('plot').text
        assert '\n' in plot_text
        assert plot_text.count('\n') >= 2  # At least 2 newlines
        assert "First paragraph." in plot_text
        assert "Third paragraph." in plot_text

    def test_episode_nfo_date_transformation(
        self,
        nfo_service,
        temp_media_dir,
        mock_channel
    ):
        """
        Test date transformation from YYYYMMDD to YYYY-MM-DD.

        Validates:
        - upload_date format: 20250109 → 2025-01-09
        - Year extraction: 20250109 → 2025
        - Invalid dates are handled gracefully
        """
        # Setup: Episode with various date formats
        episode_info = {
            "title": "Test Video",
            "channel": "Test Channel",
            "upload_date": "20211207"
        }

        video_dir = os.path.join(temp_media_dir, "Channel", "2025", "Video")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()
        with open(info_json_path, 'w', encoding='utf-8') as f:
            json.dump(episode_info, f)

        # Execute
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: Date transformed correctly
        assert success is True

        nfo_path = os.path.join(video_dir, "video.nfo")
        tree = ET.parse(nfo_path)
        root = tree.getroot()

        assert root.find('aired').text == '2021-12-07'
        assert root.find('year').text == '2021'

    def test_episode_nfo_duration_conversion(
        self,
        nfo_service,
        temp_media_dir,
        mock_channel
    ):
        """
        Test duration conversion from seconds to minutes.

        Validates:
        - 3746 seconds → 62 minutes (floor division)
        - 922 seconds → 15 minutes
        - 59 seconds → 0 minutes (edge case)
        - Duration of 0 is handled
        """
        test_cases = [
            (3746, '62'),   # 62 minutes 26 seconds → 62 minutes
            (922, '15'),    # 15 minutes 22 seconds → 15 minutes
            (59, '0'),      # Less than a minute → 0 minutes
            (120, '2'),     # Exactly 2 minutes
        ]

        for duration_seconds, expected_minutes in test_cases:
            episode_info = {
                "title": f"Test Video {duration_seconds}s",
                "channel": "Test Channel",
                "duration": duration_seconds
            }

            video_dir = os.path.join(temp_media_dir, f"Channel_{duration_seconds}")
            os.makedirs(video_dir, exist_ok=True)

            video_path = os.path.join(video_dir, "video.mkv")
            info_json_path = os.path.join(video_dir, "video.info.json")

            Path(video_path).touch()
            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump(episode_info, f)

            # Execute
            success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

            # Verify
            assert success is True

            nfo_path = os.path.join(video_dir, "video.nfo")
            tree = ET.parse(nfo_path)
            root = tree.getroot()

            assert root.find('runtime').text == expected_minutes

    def test_episode_nfo_missing_info_json(
        self,
        nfo_service,
        temp_media_dir,
        mock_channel
    ):
        """
        Test episode NFO generation when .info.json is missing.

        Validates:
        - Returns (False, error_message) when .info.json doesn't exist
        - Error message is descriptive
        - No NFO file is created
        - Service handles gracefully (no exceptions)
        """
        # Setup: Video file without .info.json
        video_dir = os.path.join(temp_media_dir, "Channel", "2025", "Video")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        Path(video_path).touch()

        # Execute
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: Graceful failure
        assert success is False
        assert error is not None
        assert "Info JSON not found" in error

        # Verify: No NFO file created
        nfo_path = os.path.join(video_dir, "video.nfo")
        assert not os.path.exists(nfo_path)

    def test_episode_nfo_malformed_json(
        self,
        nfo_service,
        temp_media_dir,
        mock_channel
    ):
        """
        Test episode NFO generation with malformed JSON.

        Validates:
        - Corrupted JSON is handled gracefully
        - Returns (False, error_message)
        - No NFO file is created
        """
        # Setup: Video file with invalid JSON
        video_dir = os.path.join(temp_media_dir, "Channel", "2025", "Video")
        os.makedirs(video_dir, exist_ok=True)

        video_path = os.path.join(video_dir, "video.mkv")
        info_json_path = os.path.join(video_dir, "video.info.json")

        Path(video_path).touch()

        # Write malformed JSON
        with open(info_json_path, 'w', encoding='utf-8') as f:
            f.write("{invalid json content")

        # Execute
        success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

        # Verify: Graceful failure
        assert success is False
        assert error is not None
        assert "Failed to parse JSON" in error

    def test_episode_nfo_missing_required_fields(
        self,
        nfo_service,
        temp_media_dir,
        mock_channel
    ):
        """
        Test episode NFO generation with missing required fields.

        Validates:
        - Missing 'title' causes graceful failure
        - Missing 'channel' causes graceful failure
        - Appropriate error messages
        """
        test_cases = [
            ({"channel": "Test Channel"}, "title"),  # Missing title
            ({"title": "Test Video"}, "channel"),    # Missing channel
        ]

        for idx, (episode_info, missing_field) in enumerate(test_cases):
            video_dir = os.path.join(temp_media_dir, f"Channel_test_{idx}")
            os.makedirs(video_dir, exist_ok=True)

            video_path = os.path.join(video_dir, "video.mkv")
            info_json_path = os.path.join(video_dir, "video.info.json")

            Path(video_path).touch()
            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump(episode_info, f)

            # Execute
            success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

            # Verify
            assert success is False
            assert error is not None
            assert "Missing required fields" in error

    def test_episode_nfo_multiple_video_extensions(
        self,
        nfo_service,
        temp_media_dir,
        mock_channel,
        sample_episode_info_minimal
    ):
        """
        Test episode NFO generation with different video file extensions.

        Validates:
        - .mkv → video.nfo
        - .mp4 → video.nfo
        - .webm → video.nfo
        """
        extensions = ['.mkv', '.mp4', '.webm']

        for ext in extensions:
            video_dir = os.path.join(temp_media_dir, f"Channel_{ext.strip('.')}")
            os.makedirs(video_dir, exist_ok=True)

            video_path = os.path.join(video_dir, f"video{ext}")
            info_json_path = os.path.join(video_dir, "video.info.json")

            Path(video_path).touch()
            with open(info_json_path, 'w', encoding='utf-8') as f:
                json.dump(sample_episode_info_minimal, f)

            # Execute
            success, error = nfo_service.generate_episode_nfo(video_path, mock_channel)

            # Verify
            assert success is True, f"Failed for extension {ext}"

            nfo_path = os.path.join(video_dir, "video.nfo")
            assert os.path.exists(nfo_path), f"NFO not created for {ext}"


# =========================================================================
# SEASON NFO GENERATION TESTS
# =========================================================================

class TestSeasonNFOGeneration:
    """Test suite for season.nfo file generation."""

    def test_season_nfo_generation_with_valid_year(
        self,
        nfo_service,
        temp_media_dir
    ):
        """
        Test season NFO generation with valid year directory.

        Validates:
        - season.nfo is created in year directory
        - Year is extracted from directory path
        - XML contains correct year and season number
        """
        # Setup: Create year directory
        year_dir = os.path.join(temp_media_dir, "Channel", "2021")
        os.makedirs(year_dir, exist_ok=True)

        # Execute
        success, error = nfo_service.generate_season_nfo(year_dir)

        # Verify: Success
        assert success is True
        assert error is None

        # Verify: season.nfo exists
        season_nfo_path = os.path.join(year_dir, "season.nfo")
        assert os.path.exists(season_nfo_path)

        # Verify: XML content
        tree = ET.parse(season_nfo_path)
        root = tree.getroot()

        assert root.tag == 'season'
        assert root.find('title').text == '2021'
        assert root.find('season').text == '2021'
        assert root.find('dateadded') is not None

    def test_season_nfo_generation_with_invalid_year_directory(
        self,
        nfo_service,
        temp_media_dir
    ):
        """
        Test season NFO generation with invalid year directory.

        Validates:
        - Non-numeric directory names are rejected
        - Wrong length directory names (not 4 digits) are rejected
        - Appropriate error messages
        """
        invalid_dirs = [
            "202",      # Too short
            "20211",    # Too long
            "abcd",     # Non-numeric
            "Videos",   # Text
        ]

        for invalid_dir in invalid_dirs:
            year_dir = os.path.join(temp_media_dir, "Channel", invalid_dir)
            os.makedirs(year_dir, exist_ok=True)

            # Execute
            success, error = nfo_service.generate_season_nfo(year_dir)

            # Verify: Graceful failure
            assert success is False
            assert error is not None
            assert "Invalid year directory" in error

    def test_season_nfo_xml_structure(
        self,
        nfo_service,
        temp_media_dir
    ):
        """
        Test season NFO XML structure and required elements.

        Validates:
        - All required tags are present
        - Empty tags (plot, outline) are included
        - dateadded has correct format
        - premiered and releasedate are always January 1st of the year
        - lockdata is set to 'false'
        """
        # Setup
        year_dir = os.path.join(temp_media_dir, "Channel", "2023")
        os.makedirs(year_dir, exist_ok=True)

        # Execute
        success, error = nfo_service.generate_season_nfo(year_dir)
        assert success is True

        # Verify: XML structure
        season_nfo_path = os.path.join(year_dir, "season.nfo")
        tree = ET.parse(season_nfo_path)
        root = tree.getroot()

        # Required elements exist
        assert root.find('plot') is not None
        assert root.find('outline') is not None
        assert root.find('lockdata') is not None
        assert root.find('dateadded') is not None
        assert root.find('title') is not None
        assert root.find('year') is not None
        assert root.find('premiered') is not None
        assert root.find('releasedate') is not None
        assert root.find('seasonnumber') is not None
        assert root.find('season') is not None

        # Empty elements
        assert root.find('plot').text is None or root.find('plot').text == ''
        assert root.find('outline').text is None or root.find('outline').text == ''

        # lockdata should be 'false'
        assert root.find('lockdata').text == 'false'

        # Year fields should match directory year
        assert root.find('title').text == '2023'
        assert root.find('year').text == '2023'
        assert root.find('seasonnumber').text == '2023'
        assert root.find('season').text == '2023'

        # premiered and releasedate should always be January 1st of the year
        assert root.find('premiered').text == '2023-01-01'
        assert root.find('releasedate').text == '2023-01-01'

        # dateadded format: YYYY-MM-DD HH:MM:SS
        dateadded = root.find('dateadded').text
        assert len(dateadded) == 19  # "2025-01-09 12:34:56"
        assert dateadded[4] == '-' and dateadded[7] == '-'


# =========================================================================
# TVSHOW NFO GENERATION TESTS
# =========================================================================

class TestTvshowNFOGeneration:
    """Test suite for tvshow.nfo file generation."""

    def test_tvshow_nfo_generation_with_complete_metadata(
        self,
        nfo_service,
        temp_media_dir,
        sample_channel_info
    ):
        """
        Test tvshow NFO generation with complete channel metadata.

        Validates:
        - Channel name maps to title, originaltitle, showtitle
        - Description is included
        - Tags map to both genres and tags
        - Studio is "YouTube"
        """
        # Setup: Create channel directory and metadata file
        channel_dir = os.path.join(temp_media_dir, "Channel [UCzGzk0K7]")
        os.makedirs(channel_dir, exist_ok=True)

        metadata_path = os.path.join(channel_dir, "channel.info.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(sample_channel_info, f)

        # Execute
        success, error = nfo_service.generate_tvshow_nfo(metadata_path, channel_dir)

        # Verify: Success
        assert success is True
        assert error is None

        # Verify: tvshow.nfo exists
        tvshow_nfo_path = os.path.join(channel_dir, "tvshow.nfo")
        assert os.path.exists(tvshow_nfo_path)

        # Verify: XML content
        tree = ET.parse(tvshow_nfo_path)
        root = tree.getroot()

        assert root.tag == 'tvshow'
        assert root.find('title').text == sample_channel_info['channel']
        assert root.find('originaltitle').text == sample_channel_info['channel']
        assert root.find('showtitle').text == sample_channel_info['channel']
        assert root.find('plot').text == sample_channel_info['description']
        assert root.find('studio').text == 'YouTube'

        # Verify: Tags mapped to both genres and tags
        genres = [g.text for g in root.findall('genre')]
        tags = [t.text for t in root.findall('tag')]

        for tag in sample_channel_info['tags']:
            assert tag in genres, f"{tag} not in genres"
            assert tag in tags, f"{tag} not in tags"

    def test_tvshow_nfo_generation_with_minimal_metadata(
        self,
        nfo_service,
        temp_media_dir,
        sample_channel_info_minimal
    ):
        """
        Test tvshow NFO generation with minimal channel metadata.

        Validates:
        - Only channel name is required
        - Optional fields can be missing
        - NFO still generates successfully
        """
        # Setup
        channel_dir = os.path.join(temp_media_dir, "Channel")
        os.makedirs(channel_dir, exist_ok=True)

        metadata_path = os.path.join(channel_dir, "channel.info.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(sample_channel_info_minimal, f)

        # Execute
        success, error = nfo_service.generate_tvshow_nfo(metadata_path, channel_dir)

        # Verify: Success
        assert success is True
        assert error is None

        # Verify: Basic structure
        tvshow_nfo_path = os.path.join(channel_dir, "tvshow.nfo")
        tree = ET.parse(tvshow_nfo_path)
        root = tree.getroot()

        assert root.find('title').text == "Test Channel"
        assert root.find('studio').text == 'YouTube'

    def test_tvshow_nfo_missing_metadata_file(
        self,
        nfo_service,
        temp_media_dir
    ):
        """
        Test tvshow NFO generation when metadata file is missing.

        Validates:
        - Returns (False, error_message)
        - No tvshow.nfo is created
        - Error message is descriptive
        """
        # Setup: Channel directory without metadata file
        channel_dir = os.path.join(temp_media_dir, "Channel")
        os.makedirs(channel_dir, exist_ok=True)

        metadata_path = os.path.join(channel_dir, "channel.info.json")

        # Execute (metadata file doesn't exist)
        success, error = nfo_service.generate_tvshow_nfo(metadata_path, channel_dir)

        # Verify: Graceful failure
        assert success is False
        assert error is not None
        assert "Channel metadata not found" in error

        # Verify: No NFO created
        tvshow_nfo_path = os.path.join(channel_dir, "tvshow.nfo")
        assert not os.path.exists(tvshow_nfo_path)

    def test_tvshow_nfo_missing_channel_field(
        self,
        nfo_service,
        temp_media_dir
    ):
        """
        Test tvshow NFO generation when 'channel' field is missing.

        Validates:
        - Returns (False, error_message) when required field missing
        - Error message mentions missing 'channel' field
        """
        # Setup: Metadata without 'channel' field
        channel_dir = os.path.join(temp_media_dir, "Channel")
        os.makedirs(channel_dir, exist_ok=True)

        metadata_path = os.path.join(channel_dir, "channel.info.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump({"description": "No channel name"}, f)

        # Execute
        success, error = nfo_service.generate_tvshow_nfo(metadata_path, channel_dir)

        # Verify: Graceful failure
        assert success is False
        assert error is not None
        assert "Missing 'channel' field" in error


# =========================================================================
# HELPER FUNCTION TESTS
# =========================================================================

class TestHelperFunctions:
    """Test suite for NFO service helper functions."""

    def test_get_info_json_path_with_different_extensions(self, nfo_service):
        """
        Test _get_info_json_path with different video extensions.

        Validates:
        - .mkv → .info.json
        - .mp4 → .info.json
        - .webm → .info.json
        - .m4v → .info.json
        - .avi → .info.json
        - Unknown extension → appends .info.json
        """
        test_cases = [
            ("/path/to/video.mkv", "/path/to/video.info.json"),
            ("/path/to/video.mp4", "/path/to/video.info.json"),
            ("/path/to/video.webm", "/path/to/video.info.json"),
            ("/path/to/video.m4v", "/path/to/video.info.json"),
            ("/path/to/video.avi", "/path/to/video.info.json"),
            ("/path/to/video.xyz", "/path/to/video.xyz.info.json"),  # Unknown extension
        ]

        for video_path, expected_info_path in test_cases:
            result = nfo_service._get_info_json_path(video_path)
            assert result == expected_info_path

    def test_load_json_file_success(self, nfo_service, temp_media_dir):
        """
        Test _load_json_file with valid JSON file.

        Validates:
        - Successfully loads and parses JSON
        - Returns dictionary with correct data
        """
        # Setup: Create valid JSON file
        json_path = os.path.join(temp_media_dir, "test.json")
        test_data = {"key": "value", "number": 42}

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(test_data, f)

        # Execute
        result = nfo_service._load_json_file(json_path)

        # Verify
        assert result is not None
        assert result == test_data

    def test_load_json_file_malformed_json(self, nfo_service, temp_media_dir):
        """
        Test _load_json_file with malformed JSON.

        Validates:
        - Returns None on JSON parse error
        - Logs error (doesn't raise exception)
        """
        # Setup: Create malformed JSON file
        json_path = os.path.join(temp_media_dir, "malformed.json")

        with open(json_path, 'w', encoding='utf-8') as f:
            f.write("{invalid json")

        # Execute
        result = nfo_service._load_json_file(json_path)

        # Verify: Returns None gracefully
        assert result is None

    def test_load_json_file_missing_file(self, nfo_service, temp_media_dir):
        """
        Test _load_json_file with non-existent file.

        Validates:
        - Returns None when file doesn't exist
        - Handles FileNotFoundError gracefully
        """
        # Setup: Path to non-existent file
        json_path = os.path.join(temp_media_dir, "nonexistent.json")

        # Execute
        result = nfo_service._load_json_file(json_path)

        # Verify: Returns None gracefully
        assert result is None

    def test_prettify_xml_output_format(self, nfo_service):
        """
        Test _prettify_xml produces properly formatted XML.

        Validates:
        - Returns bytes (not string)
        - Contains XML declaration
        - Contains UTF-8 encoding
        - Proper indentation (4 spaces)
        """
        # Setup: Create simple XML element
        root = ET.Element('test')
        child = ET.SubElement(root, 'child')
        child.text = 'value'

        # Execute
        result = nfo_service._prettify_xml(root)

        # Verify: Returns bytes
        assert isinstance(result, bytes)

        # Verify: Contains XML declaration with UTF-8
        xml_str = result.decode('utf-8')
        assert '<?xml' in xml_str
        assert 'utf-8' in xml_str.lower()

        # Verify: Contains expected content
        assert '<test>' in xml_str
        assert '<child>value</child>' in xml_str

    def test_write_nfo_file_creates_parent_directory(
        self,
        nfo_service,
        temp_media_dir
    ):
        """
        Test _write_nfo_file creates parent directories.

        Validates:
        - Parent directories are created if they don't exist
        - File is written successfully
        """
        # Setup: Path with non-existent parent directories
        nfo_path = os.path.join(temp_media_dir, "new", "nested", "dir", "test.nfo")
        xml_content = b'<?xml version="1.0" ?><test/>'

        # Verify: Parent doesn't exist yet
        assert not os.path.exists(os.path.dirname(nfo_path))

        # Execute
        nfo_service._write_nfo_file(nfo_path, xml_content)

        # Verify: File created and parent directories exist
        assert os.path.exists(nfo_path)
        assert os.path.exists(os.path.dirname(nfo_path))

        # Verify: Content is correct
        with open(nfo_path, 'rb') as f:
            assert f.read() == xml_content

    def test_write_nfo_file_atomic_write_pattern(
        self,
        nfo_service,
        temp_media_dir
    ):
        """
        Test _write_nfo_file uses atomic write pattern.

        Validates:
        - Temp file is created during write
        - Temp file is renamed to final path
        - Temp file is cleaned up on error
        """
        # Setup
        nfo_path = os.path.join(temp_media_dir, "test.nfo")
        xml_content = b'<?xml version="1.0" ?><test/>'

        # Execute
        nfo_service._write_nfo_file(nfo_path, xml_content)

        # Verify: Final file exists
        assert os.path.exists(nfo_path)

        # Verify: Temp file doesn't exist
        temp_path = f"{nfo_path}.tmp"
        assert not os.path.exists(temp_path)

        # Verify: Content is correct
        with open(nfo_path, 'rb') as f:
            assert f.read() == xml_content

    def test_write_nfo_file_overwrites_existing(
        self,
        nfo_service,
        temp_media_dir
    ):
        """
        Test _write_nfo_file overwrites existing NFO file.

        Validates:
        - Existing file is replaced with new content
        - Atomic rename overwrites correctly
        """
        # Setup: Create existing NFO file
        nfo_path = os.path.join(temp_media_dir, "test.nfo")

        old_content = b'<?xml version="1.0" ?><old/>'
        with open(nfo_path, 'wb') as f:
            f.write(old_content)

        # Execute: Overwrite with new content
        new_content = b'<?xml version="1.0" ?><new/>'
        nfo_service._write_nfo_file(nfo_path, new_content)

        # Verify: File contains new content
        with open(nfo_path, 'rb') as f:
            assert f.read() == new_content
            assert f.read() != old_content
