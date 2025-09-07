"""Integration tests for API endpoints."""
import pytest
from unittest.mock import patch, MagicMock

from app.models import Channel, ApplicationSettings


class TestHealthEndpoint:
    """Test the health check endpoint."""
    
    def test_health_endpoint_success(self, test_client):
        """Test health endpoint returns successful response."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database_status" in data
        assert "timestamp" in data


class TestChannelsAPI:
    """Test channel management API endpoints."""
    
    def test_list_channels_empty(self, test_client):
        """Test listing channels when none exist."""
        response = test_client.get("/api/v1/channels")
        
        assert response.status_code == 200
        data = response.json()
        assert data["channels"] == []
        assert data["total"] == 0
        assert data["enabled"] == 0

    def test_list_channels_with_data(self, test_client, db_session, sample_channel_data):
        """Test listing channels with existing data."""
        # Create test channel
        channel = Channel(**sample_channel_data)
        db_session.add(channel)
        db_session.commit()
        
        response = test_client.get("/api/v1/channels")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["channels"]) == 1
        assert data["total"] == 1
        assert data["enabled"] == 1
        assert data["channels"][0]["name"] == sample_channel_data["name"]

    @patch('app.youtube_service.youtube_service.normalize_channel_url')
    @patch('app.youtube_service.youtube_service.extract_channel_info')
    def test_create_channel_success(self, mock_extract, mock_normalize, test_client):
        """Test successful channel creation with mocked YouTube service."""
        # Mock YouTube service responses
        mock_normalize.return_value = "https://www.youtube.com/@TestChannel"
        mock_extract.return_value = (
            True, 
            {
                "channel_id": "UC12345678901234567890",
                "name": "Test Channel"
            }, 
            None
        )
        
        channel_data = {
            "url": "https://www.youtube.com/@TestChannel",
            "limit": 15,
            "enabled": True,
            "quality_preset": "best"
        }
        
        response = test_client.post("/api/v1/channels", json=channel_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Channel"
        assert data["url"] == "https://www.youtube.com/@TestChannel"
        assert data["limit"] == 15
        assert data["enabled"] is True
        
        # Verify mocks were called correctly
        mock_normalize.assert_called_once()
        mock_extract.assert_called_once()

    @patch('app.youtube_service.youtube_service.normalize_channel_url')
    @patch('app.youtube_service.youtube_service.extract_channel_info')  
    def test_create_channel_with_default_limit(self, mock_extract, mock_normalize, test_client):
        """Test channel creation uses default limit when none specified."""
        # Mock YouTube service responses
        mock_normalize.return_value = "https://www.youtube.com/@TestChannel"
        mock_extract.return_value = (
            True,
            {
                "channel_id": "UC12345678901234567890", 
                "name": "Test Channel"
            },
            None
        )
        
        channel_data = {
            "url": "https://www.youtube.com/@TestChannel",
            # No limit specified - should use default (10)
            "enabled": True,
            "quality_preset": "best"
        }
        
        response = test_client.post("/api/v1/channels", json=channel_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10  # Should use default from ApplicationSettings

    @patch('app.youtube_service.youtube_service.normalize_channel_url')
    @patch('app.youtube_service.youtube_service.extract_channel_info')
    def test_create_channel_youtube_failure(self, mock_extract, mock_normalize, test_client):
        """Test channel creation fails when YouTube extraction fails."""
        # Mock YouTube service failure
        mock_normalize.return_value = "https://www.youtube.com/@TestChannel"
        mock_extract.return_value = (False, None, "Channel not found")
        
        channel_data = {
            "url": "https://www.youtube.com/@TestChannel",
            "limit": 15,
            "enabled": True
        }
        
        response = test_client.post("/api/v1/channels", json=channel_data)
        
        assert response.status_code == 400
        assert "Failed to extract channel information" in response.json()["detail"]

    def test_create_channel_duplicate(self, test_client, db_session, sample_channel_data):
        """Test creating duplicate channel fails."""
        # Create existing channel
        channel = Channel(**sample_channel_data)
        db_session.add(channel)
        db_session.commit()
        
        with patch('app.youtube_service.youtube_service.normalize_channel_url') as mock_normalize, \
             patch('app.youtube_service.youtube_service.extract_channel_info') as mock_extract:
            
            mock_normalize.return_value = "https://www.youtube.com/@TestChannel"
            mock_extract.return_value = (
                True,
                {"channel_id": sample_channel_data["channel_id"], "name": "Test Channel"},
                None
            )
            
            channel_data = {
                "url": "https://www.youtube.com/@TestChannel",
                "limit": 15,
                "enabled": True
            }
            
            response = test_client.post("/api/v1/channels", json=channel_data)
            
            assert response.status_code == 400
            assert "already being monitored" in response.json()["detail"]

    def test_get_channel_success(self, test_client, db_session, sample_channel_data):
        """Test getting specific channel by ID."""
        # Create test channel
        channel = Channel(**sample_channel_data)
        db_session.add(channel)
        db_session.commit()
        
        response = test_client.get(f"/api/v1/channels/{channel.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_channel_data["name"]
        assert data["id"] == channel.id

    def test_get_channel_not_found(self, test_client):
        """Test getting non-existent channel returns 404."""
        response = test_client.get("/api/v1/channels/99999")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Channel not found"

    def test_update_channel_success(self, test_client, db_session, sample_channel_data):
        """Test updating channel limit."""
        # Create test channel
        channel = Channel(**sample_channel_data)
        db_session.add(channel)
        db_session.commit()
        
        update_data = {"limit": 25}
        response = test_client.put(f"/api/v1/channels/{channel.id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 25
        assert data["name"] == sample_channel_data["name"]  # Unchanged

    def test_update_channel_not_found(self, test_client):
        """Test updating non-existent channel returns 404."""
        update_data = {"limit": 25}
        response = test_client.put("/api/v1/channels/99999", json=update_data)
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Channel not found"

    def test_delete_channel_success(self, test_client, db_session, sample_channel_data):
        """Test deleting channel."""
        # Create test channel
        channel = Channel(**sample_channel_data)
        db_session.add(channel)
        db_session.commit()
        channel_id = channel.id
        
        response = test_client.delete(f"/api/v1/channels/{channel_id}")
        
        assert response.status_code == 200
        data = response.json()
        # Structured assertions for stability
        assert data["channel_id"] == channel_id
        assert data["channel_name"] == sample_channel_data["name"]
        assert data["media_deleted"] is False
        assert "deleted successfully" in data["message"]
        
        # Verify channel is deleted
        deleted_channel = db_session.query(Channel).filter(Channel.id == channel_id).first()
        assert deleted_channel is None

    def test_delete_channel_not_found(self, test_client):
        """Test deleting non-existent channel returns 404."""
        response = test_client.delete("/api/v1/channels/99999")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Channel not found"


class TestSettingsAPI:
    """Test application settings API endpoints."""
    
    def test_get_default_video_limit_success(self, test_client, db_session):
        """Test getting default video limit setting."""
        response = test_client.get("/api/v1/settings/default-video-limit")
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10  # From conftest.py fixture
        assert "description" in data
        assert "updated_at" in data

    def test_update_default_video_limit_success(self, test_client, db_session):
        """Test updating default video limit setting."""
        update_data = {"limit": 25}
        response = test_client.put("/api/v1/settings/default-video-limit", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 25
        
        # Verify setting was updated in database
        setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "default_video_limit"
        ).first()
        assert setting.value == "25"

    def test_update_default_video_limit_invalid_range(self, test_client):
        """Test updating with invalid limit range fails validation."""
        # Test limit too low
        response = test_client.put("/api/v1/settings/default-video-limit", json={"limit": 0})
        assert response.status_code == 422
        
        # Test limit too high  
        response = test_client.put("/api/v1/settings/default-video-limit", json={"limit": 101})
        assert response.status_code == 422
