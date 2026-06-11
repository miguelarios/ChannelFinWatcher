"""Tests for per-video retry (manual + automatic) and per-channel schedule
overrides (US-013 manual control, US-016 schedule configuration)."""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Channel, Download, ApplicationSettings
from app.scheduled_download_job import get_channels_for_global_run
from app.video_download_service import VideoDownloadService, video_download_service


@pytest.fixture
def channel_with_failed_download(db_session):
    channel = Channel(
        url="https://youtube.com/@retrychannel",
        name="Retry Channel",
        channel_id="UCretryaaaaaaaaaaaaaaa",
        limit=10,
        enabled=True,
        metadata_status="completed",
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)

    download = Download(
        channel_id=channel.id,
        video_id="vid_failed_1",
        title="Failed Video",
        status="failed",
        error_message="Network error",
        retry_count=5,
        file_exists=False,
    )
    db_session.add(download)
    db_session.commit()
    db_session.refresh(download)
    return channel, download


class TestRetryEndpoint:
    """Tests for POST /api/v1/downloads/{id}/retry."""

    def test_retry_not_found(self, test_client: TestClient):
        response = test_client.post("/api/v1/downloads/9999/retry")
        assert response.status_code == 404

    def test_retry_rejects_non_failed_download(
        self, test_client: TestClient, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download
        download.status = "completed"
        db_session.commit()

        response = test_client.post(f"/api/v1/downloads/{download.id}/retry")

        assert response.status_code == 400
        assert "Only failed downloads" in response.json()["detail"]

    def test_retry_rejects_disabled_channel(
        self, test_client: TestClient, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download
        channel.enabled = False
        db_session.commit()

        response = test_client.post(f"/api/v1/downloads/{download.id}/retry")

        assert response.status_code == 400
        assert "disabled" in response.json()["detail"]

    def test_retry_returns_409_while_scheduler_runs(
        self, test_client: TestClient, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download
        db_session.add(ApplicationSettings(key="scheduled_downloads_running", value="true"))
        db_session.commit()

        response = test_client.post(f"/api/v1/downloads/{download.id}/retry")

        assert response.status_code == 409

    def test_retry_resets_budget_and_attempts_download(
        self, test_client: TestClient, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download

        def fake_retry(video_info, ch, db):
            # Simulate what a successful download does to the record
            record = db.query(Download).filter(Download.id == download.id).first()
            record.status = "completed"
            record.file_exists = True
            db.commit()
            return True, None

        with patch.object(video_download_service, "download_video_with_retry", side_effect=fake_retry) as mock_retry:
            response = test_client.post(f"/api/v1/downloads/{download.id}/retry")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["download"]["status"] == "completed"
        mock_retry.assert_called_once()
        # video_info passed through with the stored id/title
        video_info = mock_retry.call_args[0][0]
        assert video_info == {"id": "vid_failed_1", "title": "Failed Video"}

        db_session.refresh(download)
        assert download.retry_count == 0  # Budget reset before the attempt


class TestAutomaticRetryPolicy:
    """Tests for within-run retry and the cross-run auto-retry cap."""

    def test_should_download_skips_video_over_retry_cap(
        self, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download
        download.retry_count = VideoDownloadService.MAX_AUTO_RETRIES
        db_session.commit()

        should, record = video_download_service.should_download_video(
            download.video_id, channel, db_session
        )

        assert should is False
        assert record.id == download.id

    def test_should_download_allows_video_under_retry_cap(
        self, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download
        download.retry_count = VideoDownloadService.MAX_AUTO_RETRIES - 1
        db_session.commit()

        should, _ = video_download_service.should_download_video(
            download.video_id, channel, db_session
        )

        assert should is True

    def test_within_run_retry_on_transient_error(
        self, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download
        download.retry_count = 0
        db_session.commit()
        video_info = {"id": download.video_id, "title": download.title}

        with patch.object(video_download_service, "download_video", return_value=(False, "Connection timeout")) as mock_dl, \
                patch("app.video_download_service.time.sleep") as mock_sleep:
            success, error = video_download_service.download_video_with_retry(video_info, channel, db_session)

        assert success is False
        # Initial attempt + WITHIN_RUN_RETRIES extra attempts
        assert mock_dl.call_count == 1 + VideoDownloadService.WITHIN_RUN_RETRIES
        assert mock_sleep.call_count == VideoDownloadService.WITHIN_RUN_RETRIES
        # One failed run = +1 on the budget (not one per attempt)
        db_session.refresh(download)
        assert download.retry_count == 1

    def test_no_retry_on_permanent_error(
        self, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download
        video_info = {"id": download.video_id, "title": download.title}

        with patch.object(video_download_service, "download_video", return_value=(False, "Video unavailable: private")) as mock_dl, \
                patch("app.video_download_service.time.sleep") as mock_sleep:
            success, _ = video_download_service.download_video_with_retry(video_info, channel, db_session)

        assert success is False
        mock_dl.assert_called_once()
        mock_sleep.assert_not_called()

    def test_success_resets_retry_budget(
        self, db_session: Session, channel_with_failed_download
    ):
        channel, download = channel_with_failed_download
        download.retry_count = 3
        db_session.commit()
        video_info = {"id": download.video_id, "title": download.title}

        with patch.object(video_download_service, "download_video", return_value=(True, None)):
            success, _ = video_download_service.download_video_with_retry(video_info, channel, db_session)

        assert success is True
        db_session.refresh(download)
        assert download.retry_count == 0


class TestGlobalRunChannelSelection:
    """Channels with a schedule_override must be excluded from the global run."""

    def test_excludes_channels_with_override(self, db_session: Session):
        on_global = Channel(
            url="https://youtube.com/@global", name="Global", channel_id="UCglobal111111111111",
            enabled=True,
        )
        blank_override = Channel(
            url="https://youtube.com/@blank", name="Blank", channel_id="UCblank2222222222222",
            enabled=True, schedule_override="",
        )
        custom = Channel(
            url="https://youtube.com/@custom", name="Custom", channel_id="UCcustom333333333333",
            enabled=True, schedule_override="0 */2 * * *",
        )
        disabled = Channel(
            url="https://youtube.com/@off", name="Off", channel_id="UCoff444444444444444",
            enabled=False,
        )
        db_session.add_all([on_global, blank_override, custom, disabled])
        db_session.commit()

        names = {c.name for c in get_channels_for_global_run(db_session)}

        # Blank override means "use global schedule"; disabled and custom excluded
        assert names == {"Global", "Blank"}


class TestScheduleOverrideValidation:
    """Validation and scheduler sync when setting schedule_override via the API."""

    @pytest.fixture
    def channel(self, db_session):
        channel = Channel(
            url="https://youtube.com/@schedchannel",
            name="Sched Channel",
            channel_id="UCschedaaaaaaaaaaaaaa",
            limit=10,
            enabled=True,
            metadata_status="completed",
        )
        db_session.add(channel)
        db_session.commit()
        db_session.refresh(channel)
        return channel

    def test_rejects_invalid_cron(self, test_client: TestClient, channel):
        response = test_client.put(
            f"/api/v1/channels/{channel.id}",
            json={"schedule_override": "not a cron"},
        )

        assert response.status_code == 400
        assert "Invalid schedule_override" in response.json()["detail"]

    def test_rejects_every_minute_schedule(self, test_client: TestClient, channel):
        response = test_client.put(
            f"/api/v1/channels/{channel.id}",
            json={"schedule_override": "* * * * *"},
        )

        assert response.status_code == 400

    def test_accepts_valid_cron_and_syncs_job(self, test_client: TestClient, db_session, channel):
        with patch("app.scheduler_service.scheduler_service") as mock_service:
            response = test_client.put(
                f"/api/v1/channels/{channel.id}",
                json={"schedule_override": "0 */2 * * *"},
            )

        assert response.status_code == 200
        assert response.json()["schedule_override"] == "0 */2 * * *"
        db_session.refresh(channel)
        assert channel.schedule_override == "0 */2 * * *"
        mock_service.sync_channel_schedule.assert_called_once_with(
            channel.id, "0 */2 * * *", True
        )

    def test_blank_override_normalizes_to_none(self, test_client: TestClient, db_session, channel):
        channel.schedule_override = "0 */2 * * *"
        db_session.commit()

        with patch("app.scheduler_service.scheduler_service") as mock_service:
            response = test_client.put(
                f"/api/v1/channels/{channel.id}",
                json={"schedule_override": "   "},
            )

        assert response.status_code == 200
        assert response.json()["schedule_override"] is None
        mock_service.sync_channel_schedule.assert_called_once_with(channel.id, None, True)


class TestSchedulerServiceChannelJobs:
    """Unit tests for per-channel job management in SchedulerService."""

    def _service_with_mock_scheduler(self):
        from app.scheduler_service import SchedulerService

        service = SchedulerService.__new__(SchedulerService)  # Skip real APScheduler setup
        service.scheduler = MagicMock()
        return service

    def test_adds_job_for_valid_override(self):
        service = self._service_with_mock_scheduler()

        service.sync_channel_schedule(42, "0 */2 * * *", enabled=True)

        service.scheduler.add_job.assert_called_once()
        kwargs = service.scheduler.add_job.call_args[1]
        assert kwargs["id"] == "channel_download_job_42"
        assert kwargs["args"] == [42]
        assert kwargs["replace_existing"] is True

    def test_removes_job_when_override_cleared(self):
        service = self._service_with_mock_scheduler()
        service.scheduler.get_job.return_value = MagicMock()

        service.sync_channel_schedule(42, None, enabled=True)

        service.scheduler.remove_job.assert_called_once_with("channel_download_job_42")
        service.scheduler.add_job.assert_not_called()

    def test_removes_job_when_channel_disabled(self):
        service = self._service_with_mock_scheduler()
        service.scheduler.get_job.return_value = MagicMock()

        service.sync_channel_schedule(42, "0 */2 * * *", enabled=False)

        service.scheduler.remove_job.assert_called_once_with("channel_download_job_42")
        service.scheduler.add_job.assert_not_called()

    def test_invalid_cron_raises(self):
        service = self._service_with_mock_scheduler()

        with pytest.raises(ValueError):
            service.sync_channel_schedule(42, "totally invalid", enabled=True)
