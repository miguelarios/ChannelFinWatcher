"""Unit tests for friendly download-error translation (utils).

These cover the logic that turns yt-dlp's raw, technical error output into a
short, actionable message for the UI — the piece that replaces the opaque
"video file not found on disk" symptom users used to see.
"""

import logging

import pytest

from app.utils import YtdlpErrorCapture, friendly_download_error


class TestFriendlyDownloadError:
    """friendly_download_error() maps raw yt-dlp text to human-friendly reasons."""

    def test_returns_none_for_empty_input(self):
        assert friendly_download_error([]) is None
        assert friendly_download_error(None) is None
        assert friendly_download_error(["", "   "]) is None

    def test_bot_check_maps_to_cookies_message(self):
        msg = friendly_download_error([
            'ERROR: [youtube] abc: Sign in to confirm you’re not a bot.'
        ])
        assert msg is not None
        assert "cookies" in msg.lower()

    def test_private_video(self):
        msg = friendly_download_error(["ERROR: [youtube] xyz: Private video"])
        assert "private" in msg.lower()

    def test_unavailable_video(self):
        msg = friendly_download_error(["ERROR: Video unavailable"])
        assert "unavailable" in msg.lower()

    def test_members_only(self):
        msg = friendly_download_error(["ERROR: Join this channel to get access to members-only content"])
        assert "members-only" in msg.lower() or "membership" in msg.lower()

    def test_age_restricted(self):
        msg = friendly_download_error(["ERROR: Sign in to confirm your age. This video may be inappropriate for some users."])
        # Age wording takes priority over the generic bot message
        assert "age" in msg.lower()

    def test_geo_block(self):
        msg = friendly_download_error(["ERROR: The uploader has not made this video available in your country"])
        assert "geo" in msg.lower() or "region" in msg.lower()

    def test_format_unavailable(self):
        msg = friendly_download_error(["ERROR: Requested format is not available"])
        assert "format" in msg.lower() or "quality" in msg.lower()

    def test_stale_player_nsig(self):
        msg = friendly_download_error(["WARNING: [youtube] Some videos may not be available: nsig extraction failed"])
        assert "update" in msg.lower()

    def test_rate_limit(self):
        msg = friendly_download_error(["ERROR: HTTP Error 429: Too Many Requests"])
        assert "429" in msg or "rate" in msg.lower()

    def test_network_error(self):
        msg = friendly_download_error(["ERROR: Unable to download webpage: The read operation timed out"])
        assert "network" in msg.lower() or "temporary" in msg.lower()

    def test_unknown_error_surfaces_trimmed_raw_line(self):
        msg = friendly_download_error(["ERROR: Something totally unexpected happened"])
        assert msg == "Download failed: Something totally unexpected happened"


class TestYtdlpErrorCapture:
    """YtdlpErrorCapture records yt-dlp's error/warning output for inspection."""

    def test_records_errors_and_warnings(self):
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        cap.error("ERROR: boom")
        cap.warning("WARNING: careful")
        cap.info("just info")
        cap.debug("just debug")

        assert cap.errors == ["ERROR: boom"]
        assert cap.warnings == ["WARNING: careful"]
        # messages puts warnings first and errors last, so the fallback (which
        # takes the last line) surfaces the real error, not an incidental warning
        assert cap.messages == ["WARNING: careful", "ERROR: boom"]

    def test_fallback_surfaces_error_not_warning(self):
        # A benign warning alongside an unrecognized fatal error: the friendly
        # fallback must report the error, never the warning.
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        cap.warning("WARNING: Unable to download thumbnail")
        cap.error("ERROR: Some brand-new unrecognized failure")
        assert friendly_download_error(cap.messages) == (
            "Download failed: Some brand-new unrecognized failure"
        )

    def test_capture_feeds_translator(self):
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        cap.error("ERROR: [youtube] abc: Sign in to confirm you're not a bot")
        assert "cookies" in friendly_download_error(cap.messages).lower()
