"""Tests for video quality presets (US-015: Download Quality Configuration)."""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Channel, ApplicationSettings
from app.video_download_service import VideoDownloadService, video_download_service


@pytest.fixture
def channel(db_session):
    channel = Channel(
        url="https://youtube.com/@qualitychannel",
        name="Quality Channel",
        channel_id="UCqualityaaaaaaaaaaaaa",
        limit=10,
        enabled=True,
        quality_preset="720p",
        metadata_status="completed",
    )
    db_session.add(channel)
    db_session.commit()
    db_session.refresh(channel)
    return channel


class TestQualityFormatMapping:
    """format_for_quality resolves presets to yt-dlp format strings."""

    @pytest.mark.parametrize("preset", ["best", "2160p", "1080p", "720p", "480p"])
    def test_known_presets_resolve(self, preset):
        fmt = video_download_service.format_for_quality(preset)
        assert fmt == VideoDownloadService.QUALITY_FORMATS[preset]

    def test_capped_presets_fall_back_to_best_available(self):
        # Each capped preset must end with the unconditional best-available
        # alternative so downloads degrade gracefully (US-015 acceptance)
        for preset, fmt in VideoDownloadService.QUALITY_FORMATS.items():
            if preset != "best":
                assert fmt.endswith("/bv*+ba/b"), f"{preset} lacks best-available fallback"

    def test_unknown_preset_falls_back_to_best(self):
        assert video_download_service.format_for_quality("potato") == VideoDownloadService.QUALITY_FORMATS["best"]

    def test_none_preset_falls_back_to_best(self):
        assert video_download_service.format_for_quality(None) == VideoDownloadService.QUALITY_FORMATS["best"]


class TestDownloadUsesChannelPreset:
    """download_video must pass the channel's preset format to yt-dlp."""

    def test_download_opts_use_channel_quality(self, db_session: Session, channel):
        captured_opts = {}

        class FakeYoutubeDL:
            def __init__(self, opts):
                captured_opts.update(opts)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def download(self, urls):
                pass

        video_info = {"id": "vid_quality_1", "title": "Quality Test"}
        with patch("app.video_download_service.yt_dlp.YoutubeDL", FakeYoutubeDL):
            video_download_service.download_video(video_info, channel, db_session)

        assert captured_opts["format"] == VideoDownloadService.QUALITY_FORMATS["720p"]


class TestChannelQualityValidation:
    """Channel create/update must reject unsupported presets."""

    def test_update_rejects_unknown_preset(self, test_client: TestClient, channel):
        response = test_client.put(
            f"/api/v1/channels/{channel.id}",
            json={"quality_preset": "4k-ultra"},
        )
        assert response.status_code == 422

    def test_update_accepts_supported_preset(self, test_client: TestClient, db_session, channel):
        response = test_client.put(
            f"/api/v1/channels/{channel.id}",
            json={"quality_preset": "1080p"},
        )
        assert response.status_code == 200
        db_session.refresh(channel)
        assert channel.quality_preset == "1080p"


class TestCreateChannelRace:
    """Regression test for the create-channel TOCTOU race.

    With blocking work moved to worker threads, two requests for the same
    channel can both pass the duplicate check before either commits. The
    unique constraint must then surface as a friendly 400, not a 500.
    """

    def test_concurrent_duplicate_creation_returns_400(self, test_client: TestClient, db_session: Session):
        channel_info = {"channel_id": "UCraceaaaaaaaaaaaaaaaa", "name": "Race Channel"}

        def insert_conflicting_channel(db):
            # Simulates the concurrent request winning the race in the window
            # between the duplicate check and this request's commit
            db_session.add(Channel(
                url="https://youtube.com/@race-winner",
                name="Race Channel",
                channel_id=channel_info["channel_id"],
                limit=10,
                enabled=True,
            ))
            db_session.commit()
            return 'best'

        with patch("app.api.youtube_service.normalize_channel_url",
                   return_value="https://youtube.com/@race-loser"), \
                patch("app.api.youtube_service.extract_channel_info",
                      return_value=(True, channel_info, None)), \
                patch("app.api.get_default_quality_preset",
                      side_effect=insert_conflicting_channel):
            response = test_client.post(
                "/api/v1/channels",
                json={"url": "https://youtube.com/@race-loser"},
            )

        assert response.status_code == 400
        assert "already being monitored" in response.json()["detail"]


class TestDefaultQualitySetting:
    """GET/PUT /settings/default-quality (global default for new channels)."""

    def test_get_returns_best_when_unset(self, test_client: TestClient):
        response = test_client.get("/api/v1/settings/default-quality")
        assert response.status_code == 200
        assert response.json()["quality"] == "best"

    def test_put_persists_and_get_reflects(self, test_client: TestClient, db_session):
        response = test_client.put(
            "/api/v1/settings/default-quality",
            json={"quality": "1080p"},
        )
        assert response.status_code == 200
        assert response.json()["quality"] == "1080p"

        response = test_client.get("/api/v1/settings/default-quality")
        assert response.json()["quality"] == "1080p"

        setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "default_quality_preset"
        ).first()
        assert setting.value == "1080p"

    def test_put_rejects_unknown_preset(self, test_client: TestClient):
        response = test_client.put(
            "/api/v1/settings/default-quality",
            json={"quality": "potato"},
        )
        assert response.status_code == 422
