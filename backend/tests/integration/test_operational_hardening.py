"""Tests for operational hardening: deep health checks, cookie status,
notifications, and the recent-logs buffer."""
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.log_buffer import RingBufferHandler
from app.models import ApplicationSettings
from app.notification_service import (
    get_notification_url,
    send_notification,
    validate_notification_url,
)


class TestDeepHealthCheck:
    """Tests for the enriched /health endpoint."""

    def test_healthy_payload_shape(self, test_client: TestClient):
        response = test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("healthy", "degraded")
        assert isinstance(data["problems"], list)
        assert "tools" in data
        assert "yt_dlp_version" in data["tools"]
        assert isinstance(data["tools"]["ffmpeg"], bool)
        assert "scheduler" in data
        assert "database" in data

    def test_scheduler_staleness_flagged(self, test_client: TestClient, db_session):
        db_session.add_all([
            ApplicationSettings(key="scheduler_enabled", value="true"),
            ApplicationSettings(key="scheduled_downloads_last_run",
                                value="2020-01-01T00:00:00"),
        ])
        db_session.commit()

        response = test_client.get("/health")

        data = response.json()
        assert data["scheduler"]["stale"] is True
        assert data["status"] == "degraded"
        assert any("scheduler" in p for p in data["problems"])


class TestCookiesStatus:
    """Tests for GET /api/v1/settings/cookies-status."""

    def test_missing_cookie_file(self, test_client: TestClient):
        with patch("app.api.os.path.exists", return_value=False):
            response = test_client.get("/api/v1/settings/cookies-status")

        assert response.status_code == 200
        data = response.json()
        assert data["present"] is False
        assert data["stale"] is False

    def test_present_cookie_file_reports_age(self, test_client: TestClient, tmp_path):
        cookie_file = tmp_path / "cookies.txt"
        cookie_file.write_text("# Netscape HTTP Cookie File\n")

        with patch("app.api.get_settings") as mock_settings:
            mock_settings.return_value.cookies_file = str(cookie_file)
            response = test_client.get("/api/v1/settings/cookies-status")

        assert response.status_code == 200
        data = response.json()
        assert data["present"] is True
        assert data["size_bytes"] > 0
        assert data["age_days"] == 0
        assert data["stale"] is False


class TestNotificationSettings:
    """Tests for notification configuration and dispatch."""

    def test_get_disabled_by_default(self, test_client: TestClient):
        response = test_client.get("/api/v1/settings/notifications")
        assert response.status_code == 200
        assert response.json() == {"url": "", "enabled": False}

    def test_put_valid_url_persists(self, test_client: TestClient, db_session):
        # json:// is a built-in Apprise scheme that needs no external service
        response = test_client.put(
            "/api/v1/settings/notifications",
            json={"url": "json://localhost/webhook"},
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is True
        assert get_notification_url(db_session) == "json://localhost/webhook"

    def test_put_invalid_url_rejected(self, test_client: TestClient):
        response = test_client.put(
            "/api/v1/settings/notifications",
            json={"url": "not-a-real-scheme-xyz"},
        )
        assert response.status_code == 400

    def test_put_blank_disables(self, test_client: TestClient, db_session):
        db_session.add(ApplicationSettings(key="notification_url", value="json://localhost/x"))
        db_session.commit()

        response = test_client.put("/api/v1/settings/notifications", json={"url": ""})

        assert response.status_code == 200
        assert response.json()["enabled"] is False
        assert get_notification_url(db_session) is None

    def test_test_endpoint_requires_configuration(self, test_client: TestClient):
        response = test_client.post("/api/v1/settings/notifications/test")
        assert response.status_code == 400

    def test_send_notification_noop_when_unconfigured(self, db_session):
        assert send_notification(db_session, "t", "b") is False

    def test_validate_url(self):
        assert validate_notification_url("json://localhost/webhook")[0] is True
        assert validate_notification_url("garbage")[0] is False


class TestRecentLogs:
    """Tests for the in-memory log buffer and endpoint."""

    def test_ring_buffer_captures_and_filters(self):
        handler = RingBufferHandler()
        logger = logging.getLogger("test.ring.buffer")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            logger.info("info message")
            logger.warning("warning message")
            logger.error("error message")
        finally:
            logger.removeHandler(handler)

        all_records = handler.recent(limit=10)
        assert [r["message"] for r in all_records[:3]] == [
            "error message", "warning message", "info message"
        ]

        warnings_up = handler.recent(limit=10, level="WARNING")
        assert all(r["level"] in ("WARNING", "ERROR", "CRITICAL") for r in warnings_up)
        assert len(warnings_up) == 2

    def test_endpoint_returns_records(self, test_client: TestClient):
        # The endpoint reads the global handler; emit through the root logger
        logging.getLogger("app.test_logs").warning("hardening probe message")

        response = test_client.get("/api/v1/logs/recent?limit=50&level=WARNING")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["logs"], list)

    def test_endpoint_rejects_bad_level(self, test_client: TestClient):
        response = test_client.get("/api/v1/logs/recent?level=LOUD")
        assert response.status_code == 400
