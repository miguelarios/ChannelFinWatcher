"""Unit tests for main.py logging filters."""
import logging
from unittest.mock import Mock
import pytest

from main import AccessLogFilter


class MockLogRecord:
    """Mock logging.LogRecord for testing filters."""
    def __init__(self, message):
        self.message = message

    def getMessage(self):
        return self.message


class TestAccessLogFilter:
    """Test suite for AccessLogFilter functionality."""

    def test_filter_suppresses_health_endpoint(self):
        """Test that /health endpoint logs are filtered."""
        log_filter = AccessLogFilter()

        # Should suppress successful health checks
        record = MockLogRecord('INFO:     127.0.0.1:47194 - "GET /health HTTP/1.1" 200 OK')
        assert log_filter.filter(record) is False

    def test_filter_suppresses_scheduler_status_endpoint(self):
        """Test that /api/v1/scheduler/status endpoint logs are filtered."""
        log_filter = AccessLogFilter()

        # Should suppress successful scheduler status polls
        record = MockLogRecord('INFO:     127.0.0.1:58052 - "GET /api/v1/scheduler/status HTTP/1.1" 200 OK')
        assert log_filter.filter(record) is False

    def test_filter_suppresses_channels_endpoint(self):
        """Test that /api/v1/channels endpoint logs are filtered."""
        log_filter = AccessLogFilter()

        # Should suppress successful channels polls
        record = MockLogRecord('INFO:     127.0.0.1:58064 - "GET /api/v1/channels HTTP/1.1" 200 OK')
        assert log_filter.filter(record) is False

    def test_filter_allows_error_responses(self):
        """Test that error responses are NOT filtered (remain visible)."""
        log_filter = AccessLogFilter()

        # Should NOT suppress errors (500, 404, etc.)
        error_responses = [
            'INFO:     127.0.0.1:58052 - "GET /api/v1/scheduler/status HTTP/1.1" 500 Internal Server Error',
            'INFO:     127.0.0.1:58052 - "GET /health HTTP/1.1" 503 Service Unavailable',
            'INFO:     127.0.0.1:58052 - "GET /api/v1/channels HTTP/1.1" 404 Not Found'
        ]

        for error_msg in error_responses:
            record = MockLogRecord(error_msg)
            assert log_filter.filter(record) is True, f"Should allow error: {error_msg}"

    def test_filter_allows_post_requests(self):
        """Test that POST requests are NOT filtered (only GET requests are filtered)."""
        log_filter = AccessLogFilter()

        # Should NOT suppress POST requests
        record = MockLogRecord('INFO:     127.0.0.1:58052 - "POST /api/v1/channels HTTP/1.1" 200 OK')
        assert log_filter.filter(record) is True

    def test_filter_allows_other_endpoints(self):
        """Test that non-filtered endpoints remain visible."""
        log_filter = AccessLogFilter()

        # Should NOT suppress other endpoints
        other_endpoints = [
            'INFO:     127.0.0.1:58052 - "GET /api/v1/downloads HTTP/1.1" 200 OK',
            'INFO:     127.0.0.1:58052 - "POST /api/v1/trigger-download HTTP/1.1" 200 OK',
            'INFO:     127.0.0.1:58052 - "GET /api/v1/settings HTTP/1.1" 200 OK'
        ]

        for endpoint_msg in other_endpoints:
            record = MockLogRecord(endpoint_msg)
            assert log_filter.filter(record) is True, f"Should allow: {endpoint_msg}"

    def test_filter_endpoints_list_is_complete(self):
        """Test that FILTERED_ENDPOINTS contains expected values."""
        log_filter = AccessLogFilter()

        expected_endpoints = {'/health', '/api/v1/scheduler/status', '/api/v1/channels'}
        actual_endpoints = set(log_filter.FILTERED_ENDPOINTS)

        assert actual_endpoints == expected_endpoints, \
            f"Expected {expected_endpoints}, got {actual_endpoints}"

    def test_filter_with_non_uvicorn_log(self):
        """Test that non-Uvicorn logs pass through unchanged."""
        log_filter = AccessLogFilter()

        # Regular application logs should pass through
        app_logs = [
            'INFO  [app.video_download_service] Starting download...',
            'WARNING  [app.scheduler_service] Job overlap detected',
            'ERROR  [app.database] Connection failed'
        ]

        for log_msg in app_logs:
            record = MockLogRecord(log_msg)
            assert log_filter.filter(record) is True, f"Should allow app log: {log_msg}"

    def test_filter_suppresses_endpoints_with_query_parameters(self):
        """Test that endpoints with query parameters are also filtered."""
        log_filter = AccessLogFilter()

        # Should suppress endpoints even with query parameters
        with_params = [
            'INFO:     127.0.0.1:58064 - "GET /api/v1/channels?page=1 HTTP/1.1" 200 OK',
            'INFO:     127.0.0.1:58064 - "GET /api/v1/channels?limit=50&offset=10 HTTP/1.1" 200 OK',
            'INFO:     127.0.0.1:58052 - "GET /api/v1/scheduler/status?verbose=true HTTP/1.1" 200 OK'
        ]

        for log_msg in with_params:
            record = MockLogRecord(log_msg)
            assert log_filter.filter(record) is False, f"Should suppress: {log_msg}"
