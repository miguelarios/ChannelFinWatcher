"""Integration tests for health check endpoint."""
import pytest


class TestHealthEndpoint:
    """
    Test the system health check endpoint.
    
    The health endpoint is critical for deployment and monitoring systems.
    These tests verify it works correctly and provides useful information.
    """
    
    def test_health_endpoint_returns_200(self, test_client):
        """Test health endpoint returns successful status."""
        response = test_client.get("/health")
        
        assert response.status_code == 200
        
    def test_health_endpoint_returns_json(self, test_client):
        """Test health endpoint returns JSON response."""
        response = test_client.get("/health")
        
        # Should return JSON content type
        assert "application/json" in response.headers.get("content-type", "")
        
        # Should be parseable JSON
        data = response.json()
        assert isinstance(data, dict)
        
    def test_health_response_contains_required_fields(self, test_client):
        """Test health response contains expected fields."""
        response = test_client.get("/health")
        data = response.json()
        
        # Required fields for health check
        assert "status" in data
        assert "service" in data  # Service name field
        assert "database" in data  # Database connection field
        
        # Status should be positive
        assert data["status"] in ["healthy", "ok"]
        
    def test_health_endpoint_database_connectivity(self, test_client):
        """Test health endpoint confirms database connectivity."""
        response = test_client.get("/health")
        data = response.json()
        
        # Database should be accessible in tests
        assert "database" in data
        # Should indicate successful database connection
        assert data["database"] in ["connected", "ok", "healthy"]
        
    def test_health_endpoint_is_fast(self, test_client):
        """Test health endpoint responds quickly."""
        import time
        
        start_time = time.time()
        response = test_client.get("/health")
        end_time = time.time()
        
        # Health check should be very fast (under 1 second)
        response_time = end_time - start_time
        assert response_time < 1.0
        assert response.status_code == 200
        
    def test_health_endpoint_multiple_calls(self, test_client):
        """Test health endpoint handles multiple rapid calls."""
        responses = []
        
        # Make multiple quick requests
        for _ in range(5):
            response = test_client.get("/health")
            responses.append(response)
            
        # All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["healthy", "ok"]