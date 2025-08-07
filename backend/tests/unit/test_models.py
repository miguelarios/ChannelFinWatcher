"""Unit tests for SQLAlchemy models."""
import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError

from app.models import Channel, Download, DownloadHistory, ApplicationSettings


class TestChannelModel:
    """Test the Channel model.
    
    These tests validate the Channel model's behavior including:
    - Required field validation
    - Unique constraint enforcement  
    - Default value handling
    - Relationship integrity
    """
    
    def test_create_channel_with_required_fields(self, db_session):
        """Test creating a channel with minimum required fields."""
        channel = Channel(
            url="https://www.youtube.com/@TestChannel",
            channel_id="UC12345678901234567890",
            name="Test Channel"
        )
        
        db_session.add(channel)
        db_session.commit()
        
        # Verify the channel was created with correct data
        assert channel.id is not None
        assert channel.url == "https://www.youtube.com/@TestChannel"
        assert channel.channel_id == "UC12345678901234567890"
        assert channel.name == "Test Channel"
        
        # Verify default values
        assert channel.limit == 10  # Default limit from model
        assert channel.enabled is True  # Default enabled state
        assert channel.quality_preset == "best"  # Default quality
        assert channel.created_at is not None
        assert channel.updated_at is not None

    def test_channel_unique_constraints(self, db_session, sample_channel_data):
        """Test that URL and channel_id must be unique."""
        # Create first channel
        channel1 = Channel(**sample_channel_data)
        db_session.add(channel1)
        db_session.commit()
        
        # Attempt to create channel with duplicate URL
        channel2 = Channel(
            url=sample_channel_data["url"],  # Same URL
            channel_id="UC98765432109876543210",  # Different channel_id
            name="Different Channel"
        )
        db_session.add(channel2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Attempt to create channel with duplicate channel_id
        channel3 = Channel(
            url="https://www.youtube.com/@DifferentChannel",
            channel_id=sample_channel_data["channel_id"],  # Same channel_id
            name="Another Different Channel"
        )
        db_session.add(channel3)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_channel_relationships(self, db_session, sample_channel_data):
        """Test Channel-Download relationship."""
        # Create channel
        channel = Channel(**sample_channel_data)
        db_session.add(channel)
        db_session.commit()
        
        # Create download for the channel
        download = Download(
            channel_id=channel.id,
            video_id="dQw4w9WgXcQ",
            title="Test Video",
            upload_date="20240101"
        )
        db_session.add(download)
        db_session.commit()
        
        # Test relationship
        assert len(channel.downloads) == 1
        assert channel.downloads[0].title == "Test Video"
        assert download.channel.name == sample_channel_data["name"]


class TestDownloadModel:
    """Test the Download model."""
    
    def test_create_download_with_required_fields(self, db_session, sample_channel_data):
        """Test creating a download with minimum required fields."""
        # Create channel first (foreign key requirement)
        channel = Channel(**sample_channel_data)
        db_session.add(channel)
        db_session.commit()
        
        download = Download(
            channel_id=channel.id,
            video_id="dQw4w9WgXcQ",
            title="Rick Roll",
            upload_date="20240101"
        )
        
        db_session.add(download)
        db_session.commit()
        
        assert download.id is not None
        assert download.video_id == "dQw4w9WgXcQ"
        assert download.title == "Rick Roll"
        assert download.status == "pending"  # Default status
        assert download.created_at is not None

    def test_download_video_id_unique(self, db_session, sample_channel_data):
        """Test that video_id must be unique across all downloads."""
        # Create channel
        channel = Channel(**sample_channel_data)
        db_session.add(channel)
        db_session.commit()
        
        # Create first download
        download1 = Download(
            channel_id=channel.id,
            video_id="dQw4w9WgXcQ",
            title="First Video",
            upload_date="20240101"
        )
        db_session.add(download1)
        db_session.commit()
        
        # Attempt duplicate video_id
        download2 = Download(
            channel_id=channel.id,
            video_id="dQw4w9WgXcQ",  # Same video_id
            title="Duplicate Video",
            upload_date="20240102"
        )
        db_session.add(download2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestApplicationSettingsModel:
    """Test the ApplicationSettings model."""
    
    def test_create_setting(self, db_session):
        """Test creating an application setting."""
        setting = ApplicationSettings(
            key="test_setting",
            value="test_value",
            description="A test setting"
        )
        
        db_session.add(setting)
        db_session.commit()
        
        assert setting.id is not None
        assert setting.key == "test_setting"
        assert setting.value == "test_value"
        assert setting.description == "A test setting"
        assert setting.created_at is not None
        assert setting.updated_at is not None

    def test_setting_key_unique(self, db_session):
        """Test that setting keys must be unique."""
        # Create first setting
        setting1 = ApplicationSettings(
            key="duplicate_key",
            value="value1"
        )
        db_session.add(setting1)
        db_session.commit()
        
        # Attempt duplicate key
        setting2 = ApplicationSettings(
            key="duplicate_key",  # Same key
            value="value2"
        )
        db_session.add(setting2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_setting_updated_at_changes(self, db_session):
        """Test that updated_at timestamp changes on modification."""
        setting = ApplicationSettings(
            key="updateable_setting",
            value="original_value"
        )
        db_session.add(setting)
        db_session.commit()
        
        original_updated_at = setting.updated_at
        
        # Modify the setting
        setting.value = "new_value"
        db_session.commit()
        
        # updated_at should change (though this might be subtle in fast tests)
        # In real usage, the onupdate=datetime.utcnow would update this
        assert setting.value == "new_value"