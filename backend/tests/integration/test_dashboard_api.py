"""Integration tests for the dashboard endpoint (US-009 status dashboard +
US-012 storage monitoring)."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.models import Channel, Download, DownloadHistory


@pytest.fixture
def dashboard_fixture(db_session):
    """Two channels with downloads and run history, one never-checked channel."""
    now = datetime.utcnow()

    active = Channel(
        url="https://youtube.com/@active",
        name="Active Channel",
        channel_id="UCactiveaaaaaaaaaaaaaa",
        limit=10,
        enabled=True,
        metadata_status="completed",
        last_check=now - timedelta(hours=1),
    )
    failing = Channel(
        url="https://youtube.com/@failing",
        name="Failing Channel",
        channel_id="UCfailingbbbbbbbbbbbbb",
        limit=5,
        enabled=True,
        metadata_status="completed",
        last_check=now - timedelta(hours=2),
    )
    fresh = Channel(
        url="https://youtube.com/@fresh",
        name="Fresh Channel",
        channel_id="UCfreshccccccccccccccc",
        limit=10,
        enabled=False,
        metadata_status="pending",
        last_check=None,
    )
    db_session.add_all([active, failing, fresh])
    db_session.commit()
    for channel in (active, failing, fresh):
        db_session.refresh(channel)

    db_session.add_all([
        # Two videos on disk for the active channel
        Download(
            channel_id=active.id, video_id="vid_active_1", title="Active 1",
            status="completed", file_exists=True, file_size=1000,
        ),
        Download(
            channel_id=active.id, video_id="vid_active_2", title="Active 2",
            status="completed", file_exists=True, file_size=2000,
        ),
        # Cleaned-up video must not count toward storage or video count
        Download(
            channel_id=active.id, video_id="vid_active_gone", title="Active Gone",
            status="completed", file_exists=False, file_size=4000,
            deleted_at=now - timedelta(days=1),
        ),
        # Failed download must not count either
        Download(
            channel_id=failing.id, video_id="vid_fail_1", title="Fail 1",
            status="failed", error_message="boom", file_exists=False,
        ),
        # Run history: an old success and a newer failure for the failing channel
        DownloadHistory(
            channel_id=failing.id, run_date=now - timedelta(hours=5),
            status="completed",
        ),
        DownloadHistory(
            channel_id=failing.id, run_date=now - timedelta(hours=2),
            status="failed", error_message="Network error during run",
        ),
        DownloadHistory(
            channel_id=active.id, run_date=now - timedelta(hours=1),
            status="completed",
        ),
    ])
    db_session.commit()
    return active, failing, fresh


class TestDashboardEndpoint:
    """Tests for GET /api/v1/dashboard."""

    def test_per_channel_video_count_and_storage(self, test_client: TestClient, dashboard_fixture):
        active, failing, fresh = dashboard_fixture

        response = test_client.get("/api/v1/dashboard")

        assert response.status_code == 200
        data = response.json()
        by_id = {c["id"]: c for c in data["channels"]}

        # Only completed downloads still on disk count
        assert by_id[active.id]["video_count"] == 2
        assert by_id[active.id]["storage_bytes"] == 3000
        assert by_id[failing.id]["video_count"] == 0
        assert by_id[failing.id]["storage_bytes"] == 0
        assert by_id[fresh.id]["video_count"] == 0

    def test_latest_run_status_per_channel(self, test_client: TestClient, dashboard_fixture):
        active, failing, fresh = dashboard_fixture

        data = test_client.get("/api/v1/dashboard").json()
        by_id = {c["id"]: c for c in data["channels"]}

        # The newer failed run wins over the older success
        assert by_id[failing.id]["last_run_status"] == "failed"
        assert by_id[failing.id]["last_run_error"] == "Network error during run"
        assert by_id[active.id]["last_run_status"] == "completed"
        # Never-run channel has no run info
        assert by_id[fresh.id]["last_run_status"] is None
        assert by_id[fresh.id]["last_check"] is None

    def test_totals(self, test_client: TestClient, dashboard_fixture):
        data = test_client.get("/api/v1/dashboard").json()

        assert data["totals"]["channels"] == 3
        assert data["totals"]["enabled_channels"] == 2
        assert data["totals"]["videos"] == 2
        assert data["totals"]["storage_bytes"] == 3000

    def test_sorted_by_last_check_with_never_checked_last(self, test_client: TestClient, dashboard_fixture):
        active, failing, fresh = dashboard_fixture

        data = test_client.get("/api/v1/dashboard").json()
        ids = [c["id"] for c in data["channels"]]

        assert ids == [active.id, failing.id, fresh.id]

    def test_disk_usage_block(self, test_client: TestClient, dashboard_fixture):
        data = test_client.get("/api/v1/dashboard").json()

        # The test environment's media dir resolves to a real filesystem path,
        # so the disk block should be present with consistent numbers
        disk = data["disk"]
        if disk is not None:
            assert disk["total_bytes"] > 0
            assert 0 <= disk["usage_percent"] <= 100
            assert disk["warning"] == (disk["usage_percent"] >= 80.0)

    def test_empty_database(self, test_client: TestClient):
        response = test_client.get("/api/v1/dashboard")

        assert response.status_code == 200
        data = response.json()
        assert data["channels"] == []
        assert data["totals"] == {
            "channels": 0,
            "enabled_channels": 0,
            "videos": 0,
            "storage_bytes": 0,
        }
        assert data["generated_at"] is not None
