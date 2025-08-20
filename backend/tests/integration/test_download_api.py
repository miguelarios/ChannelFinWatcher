"""Integration tests for download API endpoints."""
import json
from datetime import datetime
from unittest.mock import patch, Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Channel, Download, DownloadHistory


@pytest.fixture
def test_channel_with_metadata(db_session):
    """Create a test channel with metadata for download testing."""
    channel = Channel(
        url="https://youtube.com/@testchannel",
        name="Test Channel",
        channel_id="UC123456789",
        limit=10,
        enabled=True,
        metadata_status="completed"
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel


class TestDownloadAPI:
    """Test suite for download-related API endpoints."""

    def test_trigger_channel_download_success(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test successful manual download trigger."""
        # Mock the video download service
        with patch('app.api.video_download_service.process_channel_downloads') as mock_process:
            mock_process.return_value = (True, 3, None)  # Success, 3 videos, no error
            
            response = test_client.post(f"/api/v1/channels/{test_channel_with_metadata.id}/download")
            
            assert response.status_code == 200
            data = response.json()
            
            assert data["success"] is True
            assert data["videos_downloaded"] == 3
            assert data["error_message"] is None
            assert "download_history_id" in data
            
            # Verify the service was called correctly
            mock_process.assert_called_once()

    def test_trigger_channel_download_not_found(self, test_client: TestClient):
        """Test download trigger for non-existent channel."""
        response = test_client.post("/api/v1/channels/999/download")
        
        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

    def test_trigger_channel_download_disabled_channel(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test download trigger for disabled channel."""
        # Disable the channel
        test_channel_with_metadata.enabled = False
        db_session.commit()
        
        response = test_client.post(f"/api/v1/channels/{test_channel_with_metadata.id}/download")
        
        assert response.status_code == 400
        assert "Channel is disabled" in response.json()["detail"]

    def test_trigger_channel_download_service_failure(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test handling of download service failures."""
        with patch('app.api.video_download_service.process_channel_downloads') as mock_process:
            mock_process.return_value = (False, 0, "Network error")
            
            response = test_client.post(f"/api/v1/channels/{test_channel_with_metadata.id}/download")
            
            assert response.status_code == 200  # API doesn't fail, but success=false
            data = response.json()
            
            assert data["success"] is False
            assert data["videos_downloaded"] == 0
            assert data["error_message"] == "Network error"

    def test_get_channel_downloads(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test retrieving download history for a channel."""
        # Create some test downloads
        from datetime import timedelta
        now = datetime.utcnow()
        
        download1 = Download(
            channel_id=test_channel_with_metadata.id,
            video_id="test123",
            title="Test Video 1",
            upload_date="20250120",
            status="completed",
            created_at=now
        )
        download2 = Download(
            channel_id=test_channel_with_metadata.id,
            video_id="test456", 
            title="Test Video 2",
            upload_date="20250119",
            status="failed",
            error_message="Video unavailable",
            created_at=now + timedelta(seconds=1)  # More recent
        )
        
        db_session.add_all([download1, download2])
        db_session.commit()
        
        response = test_client.get(f"/api/v1/channels/{test_channel_with_metadata.id}/downloads")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 2
        assert len(data["downloads"]) == 2
        
        # Verify downloads are ordered by creation date (most recent first)
        downloads = data["downloads"]
        assert downloads[0]["video_id"] == "test456"  # More recent
        assert downloads[1]["video_id"] == "test123"

    def test_get_channel_downloads_with_pagination(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test download history with pagination parameters."""
        # Create multiple downloads
        now = datetime.utcnow()
        for i in range(5):
            download = Download(
                channel_id=test_channel_with_metadata.id,
                video_id=f"test{i}",
                title=f"Test Video {i}",
                upload_date="20250120",
                status="completed",
                created_at=now
            )
            db_session.add(download)
        db_session.commit()
        
        # Test pagination
        response = test_client.get(f"/api/v1/channels/{test_channel_with_metadata.id}/downloads?limit=2&offset=1")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 5
        assert len(data["downloads"]) == 2  # Limited to 2 results

    def test_get_channel_downloads_not_found(self, test_client: TestClient):
        """Test download history for non-existent channel."""
        response = test_client.get("/api/v1/channels/999/downloads")
        
        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

    def test_get_download_details(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test retrieving individual download details."""
        now = datetime.utcnow()
        download = Download(
            channel_id=test_channel_with_metadata.id,
            video_id="test123",
            title="Test Video",
            upload_date="20250120",
            duration="5:00",
            status="completed",
            file_path="/media/test/video.mkv",
            file_size=1024000,
            created_at=now
        )
        db_session.add(download)
        db_session.commit()
        
        response = test_client.get(f"/api/v1/downloads/{download.id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["video_id"] == "test123"
        assert data["title"] == "Test Video"
        assert data["status"] == "completed"
        assert data["file_path"] == "/media/test/video.mkv"
        assert data["file_size"] == 1024000

    def test_get_download_details_not_found(self, test_client: TestClient):
        """Test download details for non-existent download."""
        response = test_client.get("/api/v1/downloads/999")
        
        assert response.status_code == 404
        assert "Download not found" in response.json()["detail"]

    def test_get_channel_download_history(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test retrieving download run history for a channel."""
        # Create some download history records
        history1 = DownloadHistory(
            channel_id=test_channel_with_metadata.id,
            videos_found=5,
            videos_downloaded=3,
            videos_skipped=2,
            status="completed"
        )
        history2 = DownloadHistory(
            channel_id=test_channel_with_metadata.id,
            videos_found=0,
            videos_downloaded=0,
            videos_skipped=0,
            status="completed"
        )
        
        db_session.add_all([history1, history2])
        db_session.commit()
        
        response = test_client.get(f"/api/v1/channels/{test_channel_with_metadata.id}/download-history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2
        
        # Verify history is ordered by run date (most recent first)
        assert data[0]["videos_found"] == 0  # More recent
        assert data[1]["videos_found"] == 5

    def test_get_channel_download_history_with_limit(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test download history with limit parameter."""
        # Create multiple history records
        for i in range(5):
            history = DownloadHistory(
                channel_id=test_channel_with_metadata.id,
                videos_found=i,
                videos_downloaded=i,
                videos_skipped=0,
                status="completed"
            )
            db_session.add(history)
        db_session.commit()
        
        response = test_client.get(f"/api/v1/channels/{test_channel_with_metadata.id}/download-history?limit=2")
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 2  # Limited to 2 results

    def test_get_channel_download_history_not_found(self, test_client: TestClient):
        """Test download history for non-existent channel."""
        response = test_client.get("/api/v1/channels/999/download-history")
        
        assert response.status_code == 404
        assert "Channel not found" in response.json()["detail"]

    def test_download_api_error_responses(self, test_client: TestClient, db_session: Session, test_channel_with_metadata):
        """Test that API endpoints return proper error responses."""
        with patch('app.api.video_download_service.process_channel_downloads') as mock_process:
            # Simulate unexpected exception
            mock_process.side_effect = Exception("Database connection lost")
            
            response = test_client.post(f"/api/v1/channels/{test_channel_with_metadata.id}/download")
            
            assert response.status_code == 500
            assert "Download process failed" in response.json()["detail"]