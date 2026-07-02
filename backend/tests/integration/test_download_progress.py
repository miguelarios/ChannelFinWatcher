"""Tests for real-time download progress (US-010: Active Download Progress)."""
import pytest
from fastapi.testclient import TestClient

from app.progress_store import DownloadProgressStore, download_progress_store


class TestProgressStore:
    """Unit tests for the in-memory progress store."""

    def test_start_update_snapshot_finish_lifecycle(self):
        store = DownloadProgressStore()

        store.start("vid1", 1, "Channel A", "Video One")
        store.update("vid1", status="downloading", percent=42.5,
                     downloaded_bytes=425, total_bytes=1000, speed=100.0, eta_seconds=6)

        snapshot = store.snapshot()
        assert len(snapshot) == 1
        entry = snapshot[0]
        assert entry["video_id"] == "vid1"
        assert entry["channel_name"] == "Channel A"
        assert entry["percent"] == 42.5
        assert entry["status"] == "downloading"

        store.finish("vid1")
        assert store.snapshot() == []

    def test_update_unknown_video_is_noop(self):
        store = DownloadProgressStore()
        store.update("ghost", percent=50)  # Must not raise or create entries
        assert store.snapshot() == []

    def test_finish_unknown_video_is_noop(self):
        store = DownloadProgressStore()
        store.finish("ghost")  # Must not raise

    def test_snapshot_is_a_copy(self):
        store = DownloadProgressStore()
        store.start("vid1", 1, "A", "T")
        snapshot = store.snapshot()
        snapshot[0]["percent"] = 99.0
        assert store.snapshot()[0]["percent"] == 0.0

    def test_progress_hook_translates_ytdlp_events(self):
        store = DownloadProgressStore()
        store.start("vid1", 1, "A", "T")
        hook = store.make_progress_hook("vid1")

        hook({"status": "downloading", "downloaded_bytes": 500,
              "total_bytes": 2000, "speed": 250.0, "eta": 6})
        entry = store.snapshot()[0]
        assert entry["status"] == "downloading"
        assert entry["percent"] == 25.0
        assert entry["speed"] == 250.0

        hook({"status": "finished"})
        entry = store.snapshot()[0]
        assert entry["status"] == "processing"
        assert entry["percent"] == 100.0

    def test_progress_hook_handles_missing_totals(self):
        store = DownloadProgressStore()
        store.start("vid1", 1, "A", "T")
        hook = store.make_progress_hook("vid1")

        # Live streams / unknown sizes have no total_bytes at all
        hook({"status": "downloading", "downloaded_bytes": 500})
        entry = store.snapshot()[0]
        assert entry["percent"] == 0.0
        assert entry["total_bytes"] is None

    def test_hook_errors_never_propagate(self):
        store = DownloadProgressStore()
        store.start("vid1", 1, "A", "T")
        hook = store.make_progress_hook("vid1")
        hook({"status": "downloading", "downloaded_bytes": "not-a-number", "total_bytes": 100})
        # No exception raised - download must not be affected by display errors


class TestProgressStream:
    """Tests for the SSE progress event generator."""

    @pytest.mark.asyncio
    async def test_event_generator_emits_snapshots_until_disconnect(self):
        import json
        from app.api import _progress_event_stream

        class FakeRequest:
            """Reports connected for the first check, disconnected after."""
            def __init__(self):
                self.checks = 0

            async def is_disconnected(self):
                self.checks += 1
                return self.checks > 1

        download_progress_store.start("vid_sse_1", 1, "SSE Channel", "SSE Video")
        download_progress_store.update("vid_sse_1", status="downloading", percent=12.5)
        try:
            gen = _progress_event_stream(FakeRequest())

            event = await gen.__anext__()
            assert event.startswith("data: ")
            assert event.endswith("\n\n")
            payload = json.loads(event[len("data: "):])
            assert payload["count"] == 1
            assert payload["active"][0]["video_id"] == "vid_sse_1"
            assert payload["active"][0]["percent"] == 12.5

            # Second iteration sees the disconnect and ends the stream
            with pytest.raises(StopAsyncIteration):
                await gen.__anext__()
        finally:
            download_progress_store.finish("vid_sse_1")


class TestActiveDownloadsEndpoint:
    """Tests for GET /api/v1/downloads/active."""

    def test_empty_when_idle(self, test_client: TestClient):
        response = test_client.get("/api/v1/downloads/active")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["active"] == []

    def test_reflects_global_store(self, test_client: TestClient):
        download_progress_store.start("vid_api_1", 7, "API Channel", "API Video")
        download_progress_store.update("vid_api_1", status="downloading", percent=33.3)
        try:
            response = test_client.get("/api/v1/downloads/active")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["active"][0]["video_id"] == "vid_api_1"
            assert data["active"][0]["percent"] == 33.3
        finally:
            download_progress_store.finish("vid_api_1")
