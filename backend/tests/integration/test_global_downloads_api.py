"""Integration tests for the global download history endpoint (US-011)
and related quick fixes (reindex locking, NFO settings validation)."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Channel, Download, ApplicationSettings


@pytest.fixture
def two_channels_with_downloads(db_session):
    """Create two channels with a mix of download records."""
    channel_a = Channel(
        url="https://youtube.com/@channela",
        name="Channel A",
        channel_id="UCaaaaaaaaaaaaaaaaaaaa",
        limit=10,
        enabled=True,
        metadata_status="completed"
    )
    channel_b = Channel(
        url="https://youtube.com/@channelb",
        name="Channel B",
        channel_id="UCbbbbbbbbbbbbbbbbbbbb",
        limit=10,
        enabled=True,
        metadata_status="completed"
    )
    db_session.add_all([channel_a, channel_b])
    db_session.commit()
    db_session.refresh(channel_a)
    db_session.refresh(channel_b)

    now = datetime.utcnow()
    downloads = [
        Download(
            channel_id=channel_a.id,
            video_id="vid_a_done_1",
            title="A Completed 1",
            status="completed",
            file_size=1024,
            created_at=now - timedelta(hours=3)
        ),
        Download(
            channel_id=channel_a.id,
            video_id="vid_a_fail_1",
            title="A Failed 1",
            status="failed",
            error_message="Network error",
            created_at=now - timedelta(hours=2)
        ),
        Download(
            channel_id=channel_b.id,
            video_id="vid_b_done_1",
            title="B Completed 1",
            status="completed",
            file_size=2048,
            created_at=now - timedelta(hours=1)
        ),
    ]
    db_session.add_all(downloads)
    db_session.commit()
    return channel_a, channel_b


class TestGlobalDownloadsList:
    """Tests for GET /api/v1/downloads."""

    def test_lists_downloads_across_channels(self, test_client: TestClient, two_channels_with_downloads):
        response = test_client.get("/api/v1/downloads")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["downloads"]) == 3

        # Ordered most recent first
        video_ids = [d["video_id"] for d in data["downloads"]]
        assert video_ids == ["vid_b_done_1", "vid_a_fail_1", "vid_a_done_1"]

        # Channel name is included for UI display
        assert data["downloads"][0]["channel_name"] == "Channel B"
        assert data["downloads"][1]["channel_name"] == "Channel A"

    def test_filters_by_channel(self, test_client: TestClient, two_channels_with_downloads):
        channel_a, _ = two_channels_with_downloads

        response = test_client.get(f"/api/v1/downloads?channel_id={channel_a.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert all(d["channel_id"] == channel_a.id for d in data["downloads"])

    def test_filters_by_status(self, test_client: TestClient, two_channels_with_downloads):
        response = test_client.get("/api/v1/downloads?status=failed")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["downloads"][0]["video_id"] == "vid_a_fail_1"
        assert data["downloads"][0]["error_message"] == "Network error"

    def test_rejects_invalid_status(self, test_client: TestClient, two_channels_with_downloads):
        response = test_client.get("/api/v1/downloads?status=bogus")

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_pagination(self, test_client: TestClient, two_channels_with_downloads):
        response = test_client.get("/api/v1/downloads?limit=2&offset=2")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3  # Total reflects all matches, not the page size
        assert len(data["downloads"]) == 1
        assert data["downloads"][0]["video_id"] == "vid_a_done_1"

    def test_file_state_fields_come_from_database(
        self, test_client: TestClient, db_session: Session, two_channels_with_downloads
    ):
        """file_exists/deleted_at must reflect the ORM row, not schema defaults,
        so the UI can show cleaned-up videos correctly."""
        channel_a, _ = two_channels_with_downloads
        cleanup_time = datetime.utcnow() - timedelta(minutes=30)
        db_session.add(Download(
            channel_id=channel_a.id,
            video_id="vid_a_cleaned",
            title="A Cleaned Up",
            status="completed",
            file_exists=False,
            deleted_at=cleanup_time,
            created_at=datetime.utcnow()
        ))
        db_session.commit()

        response = test_client.get("/api/v1/downloads")

        assert response.status_code == 200
        by_video_id = {d["video_id"]: d for d in response.json()["downloads"]}

        cleaned = by_video_id["vid_a_cleaned"]
        assert cleaned["file_exists"] is False
        assert cleaned["deleted_at"] is not None

        intact = by_video_id["vid_a_done_1"]
        assert intact["file_exists"] is True
        assert intact["deleted_at"] is None

    def test_nonexistent_channel_filter_returns_empty_list(
        self, test_client: TestClient, two_channels_with_downloads
    ):
        """Filtering by an unknown channel is a filter miss, not a lookup:
        the endpoint intentionally returns an empty list rather than 404."""
        response = test_client.get("/api/v1/downloads?channel_id=9999")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["downloads"] == []

    def test_empty_database(self, test_client: TestClient):
        response = test_client.get("/api/v1/downloads")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["downloads"] == []


class TestReindexLocking:
    """Tests for concurrent-execution protection on the reindex endpoint."""

    def test_reindex_returns_409_when_already_running(
        self, test_client: TestClient, db_session: Session, two_channels_with_downloads
    ):
        channel_a, _ = two_channels_with_downloads

        # Simulate another reindex holding the lock
        db_session.add(ApplicationSettings(key="reindex_running", value="true"))
        db_session.commit()

        response = test_client.post(f"/api/v1/channels/{channel_a.id}/reindex")

        assert response.status_code == 409
        assert "already in progress" in response.json()["detail"]

    def test_reindex_releases_lock_after_run(
        self, test_client: TestClient, db_session: Session, two_channels_with_downloads
    ):
        channel_a, _ = two_channels_with_downloads

        response = test_client.post(f"/api/v1/channels/{channel_a.id}/reindex")
        assert response.status_code == 200

        lock = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "reindex_running"
        ).first()
        assert lock is not None
        assert lock.value == "false"

        # Lock released, so a second reindex must succeed
        response = test_client.post(f"/api/v1/channels/{channel_a.id}/reindex")
        assert response.status_code == 200


class TestNfoSettingsValidation:
    """Tests for Pydantic validation on PUT /api/v1/settings/nfo."""

    def test_rejects_empty_payload(self, test_client: TestClient):
        response = test_client.put("/api/v1/settings/nfo", json={})

        assert response.status_code == 400
        assert "At least one setting" in response.json()["detail"]

    def test_rejects_non_boolean_values(self, test_client: TestClient):
        response = test_client.put("/api/v1/settings/nfo", json={"enabled": "not-a-bool"})

        assert response.status_code == 422

    def test_updates_single_setting(self, test_client: TestClient):
        response = test_client.put("/api/v1/settings/nfo", json={"enabled": False})

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        # Unchanged setting keeps its default
        assert data["overwrite_existing"] is False

        # Persisted value visible via GET
        response = test_client.get("/api/v1/settings/nfo")
        assert response.status_code == 200
        assert response.json()["enabled"] is False
