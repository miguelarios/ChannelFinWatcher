"""Unit tests for friendly download-error translation (utils).

These cover the logic that turns yt-dlp's raw, technical error output into a
short, actionable message for the UI — the piece that replaces the opaque
"video file not found on disk" symptom users used to see.
"""

import logging

import pytest
import yt_dlp

from app.utils import YtdlpErrorCapture, friendly_download_error, is_retryable_error


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

    def test_stale_player_matches_with_player_context(self):
        msg = friendly_download_error(["ERROR: Unable to extract player response"])
        assert "update" in msg.lower()

    def test_unrelated_unable_to_extract_does_not_claim_stale_player(self):
        # A bare "unable to extract" (here for uploader id) must NOT be labeled a
        # stale-player issue, and — critically — must not strip the retry keyword
        # from a line that also carries a transient signal. The stale-player rule
        # is higher priority than the network/rate-limit rules, so this pins that
        # tightening the clause keeps a colliding retryable error retryable.
        msg = friendly_download_error(["ERROR: unable to extract uploader id; HTTP Error 429: Too Many Requests"])
        assert "update yt-dlp" not in msg.lower()
        assert "429" in msg or "rate" in msg.lower()
        assert is_retryable_error(msg) is True

    def test_rate_limit(self):
        msg = friendly_download_error(["ERROR: HTTP Error 429: Too Many Requests"])
        assert "429" in msg or "rate" in msg.lower()

    def test_network_error(self):
        msg = friendly_download_error(["ERROR: Unable to download webpage: The read operation timed out"])
        assert "network" in msg.lower() or "temporary" in msg.lower()

    def test_unknown_error_surfaces_trimmed_raw_line(self):
        msg = friendly_download_error(["ERROR: Something totally unexpected happened"])
        assert msg == "Download failed: Something totally unexpected happened"

    def test_multiple_conflicting_error_lines_follow_branch_priority(self):
        # When more than one error line is passed with conflicting keywords,
        # branch priority (not line order) decides. "private video" outranks the
        # network branch regardless of which line came first. This documents the
        # single-cause-per-video assumption in friendly_download_error.
        msg = friendly_download_error([
            "ERROR: The read operation timed out",
            "ERROR: Private video. Sign in if you've been granted access.",
        ])
        assert "private" in msg.lower()

    def test_no_cross_line_keyword_bleeding(self):
        # A two-keyword rule (geo needs "geo" AND "restrict") must not be
        # satisfied by keywords coming from two *different*, unrelated lines.
        # Here "geo" and "restrict" each appear in a separate line that does not
        # describe a geo-block, so the geo rule must NOT fire.
        msg = friendly_download_error([
            "ERROR: failed to parse geo metadata field",
            "ERROR: could not restrict output template",
        ])
        assert msg is not None
        assert "geo-blocked" not in msg.lower()
        # Falls through to the raw last-line fallback instead
        assert msg.startswith("Download failed:")

    def test_no_bleeding_within_a_single_multiline_message(self):
        # Same guarantee when the two keywords live on separate physical lines
        # *within one* string (e.g. a multi-cause DownloadError). The message is
        # split on newlines internally, so the geo rule must NOT fire.
        msg = friendly_download_error([
            "ERROR: failed to parse geo metadata field\n"
            "ERROR: could not restrict output template"
        ])
        assert msg is not None
        assert "geo-blocked" not in msg.lower()
        # Fallback surfaces the terminal (last) line
        assert "restrict output template" in msg.lower()

    def test_multiline_message_still_classifies_real_cause(self):
        # A genuine cause on one line of a multi-line string is still matched.
        msg = friendly_download_error([
            "ERROR: unable to download video data\n"
            "ERROR: HTTP Error 429: Too Many Requests"
        ])
        assert "429" in msg or "rate" in msg.lower()

    # Guards the load-bearing invariant documented on friendly_download_error:
    # every translated message must round-trip through is_retryable_error() to
    # the correct retryable/non-retryable category. Runs one representative
    # input per branch so a reworded message that drops (or wrongly gains) a
    # retry keyword fails here instead of silently breaking the retry layer.
    @pytest.mark.parametrize("raw,expect_retryable", [
        ("ERROR: Sign in to confirm you're not a bot", False),
        ("ERROR: Sign in to confirm your age", False),
        ("ERROR: Private video", False),
        ("ERROR: Video unavailable", False),
        ("ERROR: Join this channel to get access to members-only content", False),
        ("ERROR: The uploader has not made this video available in your country", False),
        ("ERROR: Requested format is not available", False),
        ("ERROR: nsig extraction failed", False),
        ("ERROR: HTTP Error 429: Too Many Requests", True),
        ("ERROR: Unable to download webpage: The read operation timed out", True),
    ])
    def test_retryability_preserved_per_branch(self, raw, expect_retryable):
        friendly = friendly_download_error([raw])
        assert friendly is not None
        assert is_retryable_error(friendly) is expect_retryable


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
        # messages classifies on the error lines when any exist, so an
        # incidental warning can't outrank the real cause
        assert cap.messages == ["ERROR: boom"]

    def test_messages_falls_back_to_warnings_when_no_error(self):
        # When yt-dlp reports no ERROR (only warnings), classify on the warnings.
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        cap.warning("WARNING: only a warning")
        assert cap.messages == ["WARNING: only a warning"]

    def test_fallback_surfaces_error_not_warning(self):
        # A benign warning alongside an unrecognized fatal error: the friendly
        # fallback must report the error, never the warning.
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        cap.warning("WARNING: Unable to download thumbnail")
        cap.error("ERROR: Some brand-new unrecognized failure")
        assert friendly_download_error(cap.messages) == (
            "Download failed: Some brand-new unrecognized failure"
        )

    def test_colliding_warning_does_not_mask_retryable_error(self):
        # Regression for the blob-matching pitfall: a benign warning whose text
        # collides with an earlier, non-retryable branch ("format is not
        # available") must NOT outrank the real transient error. Both the
        # friendly message AND is_retryable_error must reflect the real cause,
        # or the within-run retry would be silently skipped.
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        cap.warning("WARNING: Requested format is not available. Falling back.")
        cap.error("ERROR: Unable to download webpage: The read operation timed out")

        friendly = friendly_download_error(cap.messages)
        assert "network" in friendly.lower()
        assert "format" not in friendly.lower()
        # The translated message preserves retryability for the retry layer
        assert is_retryable_error(friendly) is True

    def test_capture_feeds_translator(self):
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        cap.error("ERROR: [youtube] abc: Sign in to confirm you're not a bot")
        assert "cookies" in friendly_download_error(cap.messages).lower()


class TestRealYtdlpDispatch:
    """Validate the load-bearing assumption against the *installed* yt-dlp.

    The whole feature relies on yt-dlp routing its error/warning output to our
    custom `logger` even under the production options (`quiet=True`,
    `no_warnings=True`, `ignoreerrors=True`). That dispatch is internal to
    yt-dlp and has shifted across releases, and requirements.txt pins a floating
    `>=` version — so these tests drive a REAL yt_dlp.YoutubeDL (no network:
    they call yt-dlp's own report_error/report_warning, the same methods
    extractors use) and fail loudly if a future version stops calling the
    custom logger, instead of silently degrading to the generic message in
    production while mocked unit tests stay green.
    """

    def _prod_ydl(self, capture):
        # Mirror the quiet/no_warnings/ignoreerrors combo used in
        # VideoDownloadService.download_opts for non-DEBUG operation.
        return yt_dlp.YoutubeDL({
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "logger": capture,
        })

    def test_report_error_reaches_custom_logger_under_prod_opts(self):
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        ydl = self._prod_ydl(cap)
        ydl.report_error("Sign in to confirm you're not a bot")

        # The fatal cause must land in errors (not be swallowed by quiet), and
        # translate to the actionable cookies message.
        assert cap.errors, "yt-dlp did not route report_error() to the custom logger"
        assert "cookies" in friendly_download_error(cap.messages).lower()

    def test_report_warning_reaches_custom_logger_under_prod_opts(self):
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        ydl = self._prod_ydl(cap)
        ydl.report_warning("Unable to download thumbnail")

        # Even with no_warnings=True, the custom logger receives warnings; they
        # are captured for fallback use when no error() line is present.
        assert cap.warnings, "yt-dlp did not route report_warning() to the custom logger"

    def test_error_wins_over_warning_end_to_end_with_real_ydl(self):
        # A benign warning plus a fatal error, both dispatched by a real
        # YoutubeDL: the error must drive classification, not the warning.
        cap = YtdlpErrorCapture(logging.getLogger("test"))
        ydl = self._prod_ydl(cap)
        ydl.report_warning("Unable to download thumbnail")
        ydl.report_error("Sign in to confirm you're not a bot")

        assert "cookies" in friendly_download_error(cap.messages).lower()
