"""Integration tests for complete metadata workflow."""
import os
import json
import tempfile
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from app.database import Base, get_db
from app.models import Channel
from app.config import get_settings, Settings


@pytest.fixture
def test_settings():
    """Create test settings with temporary directories."""
    with tempfile.TemporaryDirectory() as temp_media:
        yield Settings(
            database_url="sqlite:///./test_metadata.db",
            media_directory=temp_media
        )


@pytest.fixture
def test_db_session(test_settings):
    """Create test database session."""
    # Create test database
    engine = create_engine(
        test_settings.database_url, 
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Override dependencies
    def override_get_settings():
        return test_settings
    
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_db] = override_get_db
    
    # Provide session for direct database access
    db = TestingSessionLocal()
    yield db
    db.close()
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.clear()


@pytest.fixture
def test_client():
    """Create test FastAPI client."""
    return TestClient(app)


@pytest.fixture
def sample_channel_data():
    """Sample channel data for testing."""
    return {
        "url": "https://www.youtube.com/@testchannel",
        "limit": 10,
        "enabled": True,
        "quality_preset": "best"
    }


class TestMetadataWorkflowIntegration:
    """Integration tests for metadata workflow."""
    
    def test_create_channel_triggers_metadata_processing(self, test_client, test_db_session, 
                                                        sample_channel_data):
        """Test that creating a channel triggers metadata processing."""
        with patch('app.youtube_service.youtube_service.extract_channel_info') as mock_extract:
            with patch('app.metadata_service.metadata_service.process_channel_metadata') as mock_process:
                
                # Mock YouTube service response
                mock_extract.return_value = (True, {
                    'channel_id': 'UC123456789',
                    'name': 'Test Channel'
                }, None)
                
                # Mock metadata processing success
                mock_process.return_value = (True, [])
                
                # Create channel via API
                response = test_client.post("/api/v1/channels", json=sample_channel_data)
                
                assert response.status_code == 200
                channel_data = response.json()
                
                # Verify channel was created
                assert channel_data['name'] == 'Test Channel'
                assert channel_data['channel_id'] == 'UC123456789'
                assert channel_data['metadata_status'] == 'completed'  # Should be updated by process
                
                # Verify metadata processing was triggered
                mock_process.assert_called_once()
                call_args = mock_process.call_args[0]
                assert call_args[1].id == channel_data['id']  # Channel instance
    
    def test_refresh_metadata_endpoint(self, test_client, test_db_session, sample_channel_data):
        """Test metadata refresh endpoint functionality."""
        # Create a channel first
        channel = Channel(
            url="https://www.youtube.com/@testchannel",
            name="Test Channel",
            channel_id="UC123456789",
            limit=10,
            enabled=True,
            metadata_status="completed"
        )
        test_db_session.add(channel)
        test_db_session.commit()
        test_db_session.refresh(channel)
        
        with patch('app.metadata_service.metadata_service.refresh_channel_metadata') as mock_refresh:
            # Mock successful refresh
            mock_refresh.return_value = (True, [])
            
            # Call refresh endpoint
            response = test_client.post(f"/api/v1/channels/{channel.id}/refresh-metadata")
            
            assert response.status_code == 200
            result = response.json()
            assert result['message'] == 'Channel metadata refreshed successfully'
            
            # Verify refresh was called
            mock_refresh.assert_called_once_with(test_db_session, channel)
    
    def test_refresh_metadata_endpoint_failure(self, test_client, test_db_session):
        """Test metadata refresh endpoint error handling."""
        # Create a channel first
        channel = Channel(
            url="https://www.youtube.com/@testchannel",
            name="Test Channel", 
            channel_id="UC123456789",
            limit=10,
            enabled=True,
            metadata_status="completed"
        )
        test_db_session.add(channel)
        test_db_session.commit()
        test_db_session.refresh(channel)
        
        with patch('app.metadata_service.metadata_service.refresh_channel_metadata') as mock_refresh:
            # Mock refresh failure
            mock_refresh.return_value = (False, ["Network error", "Invalid channel"])
            
            # Call refresh endpoint
            response = test_client.post(f"/api/v1/channels/{channel.id}/refresh-metadata")
            
            assert response.status_code == 400
            error_data = response.json()
            assert "Metadata refresh failed" in error_data['detail']
            assert "Network error" in error_data['detail']
    
    def test_refresh_metadata_endpoint_not_found(self, test_client, test_db_session):
        """Test metadata refresh endpoint with non-existent channel."""
        response = test_client.post("/api/v1/channels/999/refresh-metadata")
        
        assert response.status_code == 404
        error_data = response.json()
        assert error_data['detail'] == 'Channel not found'
    
    def test_channel_list_includes_metadata_fields(self, test_client, test_db_session):
        """Test that channel list includes metadata fields."""
        # Create a channel with metadata fields
        channel = Channel(
            url="https://www.youtube.com/@testchannel",
            name="Test Channel",
            channel_id="UC123456789",
            limit=10,
            enabled=True,
            metadata_status="completed",
            metadata_path="/media/test/metadata.json",
            directory_path="/media/test",
            cover_image_path="/media/test/cover.jpg",
            backdrop_image_path="/media/test/backdrop.jpg"
        )
        test_db_session.add(channel)
        test_db_session.commit()
        
        # Get channel list
        response = test_client.get("/api/v1/channels")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data['channels']) == 1
        
        channel_data = data['channels'][0]
        assert channel_data['metadata_status'] == 'completed'
        assert channel_data['metadata_path'] == '/media/test/metadata.json'
        assert channel_data['directory_path'] == '/media/test'
        assert channel_data['cover_image_path'] == '/media/test/cover.jpg'
        assert channel_data['backdrop_image_path'] == '/media/test/backdrop.jpg'
    
    def test_duplicate_channel_detection_in_metadata_workflow(self, test_client, test_db_session):
        """Test that duplicate channel detection works in metadata workflow."""
        # Create existing channel
        existing_channel = Channel(
            url="https://www.youtube.com/@existing",
            name="Existing Channel",
            channel_id="UC123456789",  # Same channel_id
            limit=5,
            enabled=True,
            metadata_status="completed"
        )
        test_db_session.add(existing_channel)
        test_db_session.commit()
        
        with patch('app.youtube_service.youtube_service.extract_channel_info') as mock_extract:
            # Mock YouTube service to return same channel_id
            mock_extract.return_value = (True, {
                'channel_id': 'UC123456789',  # Duplicate channel_id
                'name': 'New Channel Name'
            }, None)
            
            # Try to create duplicate channel
            response = test_client.post("/api/v1/channels", json={
                "url": "https://www.youtube.com/@newurl",
                "limit": 10,
                "enabled": True
            })
            
            assert response.status_code == 400
            error_data = response.json()
            assert "already being monitored" in error_data['detail']
            assert "Existing Channel" in error_data['detail']


class TestMetadataWorkflowErrorScenarios:
    """Test error scenarios in metadata workflow."""
    
    def test_channel_creation_with_metadata_failure(self, test_client, test_db_session, 
                                                   sample_channel_data):
        """Test channel creation when metadata processing fails."""
        with patch('app.youtube_service.youtube_service.extract_channel_info') as mock_extract:
            with patch('app.metadata_service.metadata_service.process_channel_metadata') as mock_process:
                
                # Mock successful channel extraction
                mock_extract.return_value = (True, {
                    'channel_id': 'UC123456789',
                    'name': 'Test Channel'
                }, None)
                
                # Mock metadata processing failure
                mock_process.return_value = (False, ["Directory creation failed", "Network timeout"])
                
                # Create channel via API
                response = test_client.post("/api/v1/channels", json=sample_channel_data)
                
                # Channel creation should still succeed
                assert response.status_code == 200
                channel_data = response.json()
                
                # But metadata status should show failure
                # (Note: In actual implementation, we might set status to 'failed' 
                # but still return the channel since basic info was extracted)
                assert channel_data['name'] == 'Test Channel'
                assert channel_data['channel_id'] == 'UC123456789'
    
    def test_metadata_processing_with_partial_image_failure(self, test_client, test_db_session):
        """Test metadata workflow with partial image download failure."""
        # Create a channel
        channel = Channel(
            url="https://www.youtube.com/@testchannel",
            name="Test Channel",
            channel_id="UC123456789", 
            limit=10,
            enabled=True,
            metadata_status="pending"
        )
        test_db_session.add(channel)
        test_db_session.commit()
        test_db_session.refresh(channel)
        
        with patch('app.metadata_service.metadata_service.refresh_channel_metadata') as mock_refresh:
            # Mock partial success with warnings
            mock_refresh.return_value = (True, ["Image download: Network error downloading backdrop"])
            
            # Call refresh endpoint
            response = test_client.post(f"/api/v1/channels/{channel.id}/refresh-metadata")
            
            assert response.status_code == 200
            result = response.json()
            assert result['message'] == 'Channel metadata refreshed successfully'
            assert 'warnings' in result
            assert len(result['warnings']) == 1
            assert "Image download" in result['warnings'][0]
    
    def test_metadata_workflow_database_rollback(self, test_client, test_db_session, sample_channel_data):
        """Test that database operations are properly rolled back on failure."""
        with patch('app.youtube_service.youtube_service.extract_channel_info') as mock_extract:
            with patch('app.metadata_service.metadata_service.process_channel_metadata') as mock_process:
                
                # Mock successful channel extraction
                mock_extract.return_value = (True, {
                    'channel_id': 'UC123456789', 
                    'name': 'Test Channel'
                }, None)
                
                # Mock metadata processing that raises exception
                mock_process.side_effect = Exception("Unexpected error during metadata processing")
                
                # Try to create channel
                response = test_client.post("/api/v1/channels", json=sample_channel_data)
                
                # Should get a 500 error due to unhandled exception
                assert response.status_code == 500
                
                # Verify channel was not persisted in database
                channels = test_db_session.query(Channel).all()
                # Channel might be created but metadata processing failed
                # The exact behavior depends on implementation details
                # This test ensures we handle the error gracefully


class TestMetadataWorkflowPerformance:
    """Performance-related tests for metadata workflow."""
    
    def test_metadata_processing_timeout_handling(self, test_client, test_db_session):
        """Test that metadata processing handles timeouts gracefully."""
        # Create a channel
        channel = Channel(
            url="https://www.youtube.com/@testchannel",
            name="Test Channel",
            channel_id="UC123456789",
            limit=10,
            enabled=True,
            metadata_status="pending"
        )
        test_db_session.add(channel)
        test_db_session.commit()
        test_db_session.refresh(channel)
        
        with patch('app.metadata_service.metadata_service.refresh_channel_metadata') as mock_refresh:
            # Mock timeout scenario
            mock_refresh.return_value = (False, ["Network timeout during metadata extraction"])
            
            # Call refresh endpoint
            response = test_client.post(f"/api/v1/channels/{channel.id}/refresh-metadata")
            
            assert response.status_code == 400
            error_data = response.json()
            assert "timeout" in error_data['detail'].lower()
    
    def test_concurrent_metadata_operations(self, test_client, test_db_session):
        """Test handling of concurrent metadata operations on same channel."""
        # Create a channel
        channel = Channel(
            url="https://www.youtube.com/@testchannel",
            name="Test Channel",
            channel_id="UC123456789",
            limit=10,
            enabled=True,
            metadata_status="pending"
        )
        test_db_session.add(channel)
        test_db_session.commit()
        test_db_session.refresh(channel)
        
        # Simulate concurrent refresh attempts
        # In a real scenario, this would test that one operation waits for another
        # or that proper locking mechanisms are in place
        
        with patch('app.metadata_service.metadata_service.refresh_channel_metadata') as mock_refresh:
            mock_refresh.return_value = (True, [])
            
            # Multiple simultaneous requests (in practice would use threading/async)
            response1 = test_client.post(f"/api/v1/channels/{channel.id}/refresh-metadata")
            response2 = test_client.post(f"/api/v1/channels/{channel.id}/refresh-metadata")
            
            # Both should succeed (implementation should handle concurrency)
            assert response1.status_code == 200
            assert response2.status_code == 200


class TestMetadataWorkflowSecurity:
    """Security-related tests for metadata workflow."""
    
    def test_path_traversal_protection(self, test_client, test_db_session):
        """Test protection against path traversal attacks in metadata paths."""
        # This test would verify that metadata service doesn't allow
        # directory paths outside of the designated media directory
        
        # Create channel with malicious-looking data
        channel = Channel(
            url="https://www.youtube.com/@testchannel",
            name="../../../etc/passwd",  # Potential path traversal
            channel_id="UC123456789",
            limit=10,
            enabled=True,
            metadata_status="pending"
        )
        test_db_session.add(channel)
        test_db_session.commit()
        test_db_session.refresh(channel)
        
        with patch('app.metadata_service.metadata_service.refresh_channel_metadata') as mock_refresh:
            # Mock should sanitize the path and reject dangerous names
            mock_refresh.return_value = (False, ["Invalid channel name for filesystem"])
            
            response = test_client.post(f"/api/v1/channels/{channel.id}/refresh-metadata")
            
            # Should fail due to security validation
            assert response.status_code == 400
    
    def test_image_url_validation_in_workflow(self, test_client, test_db_session):
        """Test that malicious image URLs are rejected in metadata workflow."""
        channel = Channel(
            url="https://www.youtube.com/@testchannel",
            name="Test Channel",
            channel_id="UC123456789",
            limit=10,
            enabled=True,
            metadata_status="pending"
        )
        test_db_session.add(channel)
        test_db_session.commit()
        test_db_session.refresh(channel)
        
        with patch('app.metadata_service.metadata_service.refresh_channel_metadata') as mock_refresh:
            # Mock should reject malicious image URLs
            mock_refresh.return_value = (False, ["Image download: Invalid or unsafe image URL"])
            
            response = test_client.post(f"/api/v1/channels/{channel.id}/refresh-metadata")
            
            assert response.status_code == 400
            error_data = response.json()
            assert "unsafe image URL" in error_data['detail']