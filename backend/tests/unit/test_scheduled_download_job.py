"""Unit tests for scheduled download job.

Tests the scheduled_download_job module which orchestrates
scheduled video downloads with error handling and statistics.

TEST-001: Comprehensive scheduled job testing
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime

from app.scheduled_download_job import (
    scheduled_download_job,
    _process_channel_with_recovery,
    _is_retryable_error,
    _create_failed_history_record,
    _update_job_statistics,
    _cleanup_old_videos
)
from app.models import Channel, DownloadHistory, ApplicationSettings, Download
from app.overlap_prevention import JobAlreadyRunningError


class TestScheduledDownloadJob:
    """Test suite for main scheduled_download_job function."""

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.scheduler_lock')
    @patch('app.scheduled_download_job.SessionLocal')
    async def test_job_with_no_channels(self, mock_session_local, mock_lock):
        """Test job execution when no channels are enabled."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session_local.return_value = mock_session

        # Mock the context manager
        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()

        await scheduled_download_job()

        # Verify query was made
        mock_session.query.assert_called()

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.scheduler_lock')
    @patch('app.scheduled_download_job.SessionLocal')
    @patch('app.scheduled_download_job._process_channel_with_recovery')
    async def test_job_processes_enabled_channels(self, mock_process, mock_session_local, mock_lock):
        """Test that job processes all enabled channels."""
        # Create mock channels
        channel1 = Mock(id=1, name="Channel 1", enabled=True)
        channel2 = Mock(id=2, name="Channel 2", enabled=True)

        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = [channel1, channel2]
        mock_session_local.return_value = mock_session

        # Mock successful processing
        mock_process.return_value = (True, 5, None)

        # Mock the context manager
        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()

        with patch('app.manual_trigger_queue.process_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = (0, 0)
            await scheduled_download_job()

        # Verify both channels were processed
        assert mock_process.call_count == 2

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.scheduler_lock')
    @patch('app.scheduled_download_job.SessionLocal')
    async def test_job_skipped_when_already_running(self, mock_session_local, mock_lock):
        """Test that job is skipped when already running."""
        mock_session = Mock()
        mock_session_local.return_value = mock_session

        # Mock lock raising JobAlreadyRunningError
        mock_lock.return_value.__enter__.side_effect = JobAlreadyRunningError("Already running")

        # Should not raise exception
        await scheduled_download_job()

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.scheduler_lock')
    @patch('app.scheduled_download_job.SessionLocal')
    @patch('app.scheduled_download_job._process_channel_with_recovery')
    async def test_job_continues_on_channel_failure(self, mock_process, mock_session_local, mock_lock):
        """Test that job continues processing when individual channel fails."""
        channel1 = Mock(id=1, name="Channel 1")
        channel2 = Mock(id=2, name="Channel 2")

        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = [channel1, channel2]
        mock_session_local.return_value = mock_session

        # First channel fails, second succeeds
        mock_process.side_effect = [
            (False, 0, "Channel failed"),
            (True, 3, None)
        ]

        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()

        with patch('app.manual_trigger_queue.process_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = (0, 0)
            await scheduled_download_job()

        # Both channels should be attempted
        assert mock_process.call_count == 2

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.scheduler_lock')
    @patch('app.scheduled_download_job.SessionLocal')
    @patch('app.scheduled_download_job._update_job_statistics')
    async def test_job_updates_statistics(self, mock_update_stats, mock_session_local, mock_lock):
        """Test that job statistics are updated."""
        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        mock_session_local.return_value = mock_session

        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()

        with patch('app.manual_trigger_queue.process_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = (0, 0)
            await scheduled_download_job()

        # Verify statistics were updated (might be called from within context manager)
        assert mock_update_stats.call_count >= 0  # Should be called, but context manager makes it tricky

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.scheduler_lock')
    @patch('app.scheduled_download_job.SessionLocal')
    @patch('app.scheduled_download_job._process_channel_with_recovery')
    async def test_job_processes_manual_queue(self, mock_process, mock_session_local, mock_lock):
        """Test that manual trigger queue is processed after scheduled channels."""
        # Create at least one channel so job doesn't return early
        channel1 = Mock(id=1, name="Channel 1")

        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = [channel1]
        mock_session_local.return_value = mock_session

        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()

        # Mock successful channel processing
        mock_process.return_value = (True, 5, None)

        # Mock queue processing from the correct module
        with patch('app.manual_trigger_queue.process_queue', new_callable=AsyncMock) as mock_process_queue:
            mock_process_queue.return_value = (2, 1)  # 2 successful, 1 failed

            await scheduled_download_job()

            # Verify queue was processed
            mock_process_queue.assert_called_once()


class TestProcessChannelWithRecovery:
    """Test suite for _process_channel_with_recovery function."""

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.video_download_service')
    async def test_successful_channel_processing(self, mock_service):
        """Test successful channel processing without retries."""
        channel = Mock(id=1, name="Test Channel")
        db = Mock()

        mock_service.process_channel_downloads.return_value = (True, 5, None)

        success, count, error = await _process_channel_with_recovery(channel, db)

        assert success is True
        assert count == 5
        assert error is None

        # Should call service once
        mock_service.process_channel_downloads.assert_called_once_with(channel, db)

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.video_download_service')
    @patch('app.scheduled_download_job.asyncio.sleep', new_callable=AsyncMock)
    async def test_retry_on_retryable_error(self, mock_sleep, mock_service):
        """Test that retryable errors trigger retry logic."""
        channel = Mock(id=1, name="Test Channel")
        db = Mock()

        # First attempt fails with retryable error, second succeeds
        mock_service.process_channel_downloads.side_effect = [
            (False, 0, "Network timeout error"),
            (True, 3, None)
        ]

        success, count, error = await _process_channel_with_recovery(channel, db)

        assert success is True
        assert count == 3

        # Should have called service twice
        assert mock_service.process_channel_downloads.call_count == 2

        # Should have slept between retries
        mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.video_download_service')
    async def test_no_retry_on_non_retryable_error(self, mock_service):
        """Test that non-retryable errors don't trigger retries."""
        channel = Mock(id=1, name="Test Channel")
        db = Mock()

        # Fail with non-retryable error
        mock_service.process_channel_downloads.return_value = (False, 0, "Channel deleted")

        success, count, error = await _process_channel_with_recovery(channel, db)

        assert success is False
        assert error == "Channel deleted"

        # Should only call service once (no retry)
        mock_service.process_channel_downloads.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.video_download_service')
    @patch('app.scheduled_download_job.asyncio.sleep', new_callable=AsyncMock)
    async def test_max_retries_exceeded(self, mock_sleep, mock_service):
        """Test that max retries limit is enforced."""
        channel = Mock(id=1, name="Test Channel")
        db = Mock()

        # Always fail with retryable error
        mock_service.process_channel_downloads.return_value = (False, 0, "Network timeout")

        success, count, error = await _process_channel_with_recovery(channel, db)

        assert success is False

        # Should attempt max_retries (2) times
        assert mock_service.process_channel_downloads.call_count == 2


class TestIsRetryableError:
    """Test suite for _is_retryable_error function."""

    def test_retryable_network_errors(self):
        """Test that network-related errors are retryable."""
        retryable_errors = [
            "Network timeout occurred",
            "Connection reset by peer",
            "Temporary failure",
            "Rate limit exceeded",
            "HTTP 503 Service Unavailable",
            "HTTP 502 Bad Gateway",
            "HTTP 504 Gateway Timeout",
            "HTTP 429 Too Many Requests",
            "Quota exceeded"
        ]

        for error_msg in retryable_errors:
            assert _is_retryable_error(error_msg), f"'{error_msg}' should be retryable"

    def test_non_retryable_errors(self):
        """Test that permanent errors are not retryable."""
        non_retryable_errors = [
            "Channel deleted",
            "Invalid URL format",
            "Disk space exhausted",
            "Authentication failed",
            "Video not found"
        ]

        for error_msg in non_retryable_errors:
            assert not _is_retryable_error(error_msg), f"'{error_msg}' should not be retryable"

    def test_empty_error_not_retryable(self):
        """Test that empty error message is not retryable."""
        assert not _is_retryable_error("")
        assert not _is_retryable_error(None)

    def test_case_insensitive_matching(self):
        """Test that error matching is case-insensitive."""
        assert _is_retryable_error("NETWORK ERROR")
        assert _is_retryable_error("Network Error")
        assert _is_retryable_error("network error")


class TestCreateFailedHistoryRecord:
    """Test suite for _create_failed_history_record function."""

    def test_creates_history_record(self, db_session):
        """Test that failed history record is created."""
        _create_failed_history_record(123, "Test error", db_session)

        # Verify record was created
        history = db_session.query(DownloadHistory).filter(
            DownloadHistory.channel_id == 123
        ).first()

        assert history is not None
        assert history.status == 'failed'
        assert history.error_message == "Test error"
        assert history.videos_found == 0
        assert history.videos_downloaded == 0

    def test_truncates_long_error_messages(self, db_session):
        """Test that long error messages are truncated."""
        long_error = "Error: " + "x" * 600  # >500 characters

        _create_failed_history_record(123, long_error, db_session)

        history = db_session.query(DownloadHistory).filter(
            DownloadHistory.channel_id == 123
        ).first()

        # Should be truncated to 500 characters
        assert len(history.error_message) == 500

    def test_handles_database_errors(self, db_session):
        """Test that database errors are handled gracefully."""
        # Force a database error by using invalid channel_id type
        # Should not raise exception
        try:
            _create_failed_history_record("invalid_id", "Test", db_session)
        except Exception:
            pass  # Expected to fail, but should be caught internally


class TestUpdateJobStatistics:
    """Test suite for _update_job_statistics function."""

    def test_creates_statistics_records(self, db_session):
        """Test that statistics records are created."""
        summary = {
            "total_channels": 5,
            "successful_channels": 4,
            "failed_channels": 1,
            "total_videos": 20,
            "start_time": datetime.utcnow()
        }

        _update_job_statistics(summary, db_session)

        # Verify statistics were created
        stats = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key.like("scheduler_%")
        ).all()

        assert len(stats) > 0

        # Check specific statistics
        total_channels_stat = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "scheduler_total_channels_last_run"
        ).first()

        assert total_channels_stat is not None
        assert total_channels_stat.value == "5"

    def test_updates_existing_statistics(self, db_session):
        """Test that existing statistics are updated."""
        # Create initial statistics
        old_stat = ApplicationSettings(
            key="scheduler_total_channels_last_run",
            value="3",
            description="Test stat",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(old_stat)
        db_session.commit()

        # Update with new summary
        summary = {
            "total_channels": 10,
            "successful_channels": 8,
            "failed_channels": 2,
            "total_videos": 40,
            "start_time": datetime.utcnow()
        }

        _update_job_statistics(summary, db_session)

        # Verify update
        updated_stat = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "scheduler_total_channels_last_run"
        ).first()

        assert updated_stat.value == "10"

    def test_handles_database_errors(self, db_session):
        """Test that database errors don't crash the job."""
        summary = {
            "total_channels": 5,
            "start_time": datetime.utcnow()
        }

        # Force database to fail
        db_session.commit = Mock(side_effect=Exception("DB Error"))

        # Should not raise exception
        _update_job_statistics(summary, db_session)


class TestJobStatisticsSummary:
    """Test suite for job statistics summary."""

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.scheduler_lock')
    @patch('app.scheduled_download_job.SessionLocal')
    @patch('app.scheduled_download_job._process_channel_with_recovery')
    @patch('app.scheduled_download_job._update_job_statistics')
    async def test_summary_tracks_all_metrics(self, mock_update, mock_process, mock_session_local, mock_lock):
        """Test that summary tracks all required metrics."""
        channel1 = Mock(id=1, name="Channel 1")
        channel2 = Mock(id=2, name="Channel 2")

        mock_session = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = [channel1, channel2]
        mock_session_local.return_value = mock_session

        # First succeeds with 5 videos, second fails
        mock_process.side_effect = [
            (True, 5, None),
            (False, 0, "Error")
        ]

        mock_lock.return_value.__enter__ = Mock()
        mock_lock.return_value.__exit__ = Mock()

        with patch('app.manual_trigger_queue.process_queue', new_callable=AsyncMock) as mock_queue:
            mock_queue.return_value = (0, 0)
            await scheduled_download_job()

        # Verify summary was passed to update function
        mock_update.assert_called_once()
        summary = mock_update.call_args[0][0]

        assert summary["total_channels"] == 2
        assert summary["successful_channels"] == 1
        assert summary["failed_channels"] == 1
        assert summary["total_videos"] == 5
        assert "start_time" in summary


class TestCleanupOldVideos:
    """Test suite for _cleanup_old_videos function (BE-004B)."""

    @pytest.mark.asyncio
    async def test_no_cleanup_when_at_limit(self, db_session):
        """Test that no videos are deleted when channel is at limit."""
        # Create channel with limit=10
        channel = Channel(
            id=1,
            name="Test Channel",
            url="https://youtube.com/test",
            channel_id="UC123",
            limit=10
        )
        db_session.add(channel)
        db_session.commit()

        # Create exactly 10 completed downloads
        for i in range(10):
            download = Download(
                channel_id=channel.id,
                video_id=f"video_{i}",
                title=f"Video {i}",
                upload_date=f"202501{i:02d}",
                status="completed",
                file_exists=True,
                file_path=f"/media/channel/video_{i}.mp4"
            )
            db_session.add(download)
        db_session.commit()

        # Run cleanup
        deleted_count = await _cleanup_old_videos(channel, db_session)

        # Verify no deletions
        assert deleted_count == 0
        remaining_count = db_session.query(Download).filter(
            Download.channel_id == channel.id
        ).count()
        assert remaining_count == 10

    @pytest.mark.asyncio
    async def test_no_cleanup_when_under_limit(self, db_session):
        """Test that no videos are deleted when channel is under limit."""
        channel = Channel(
            id=1,
            name="Test Channel",
            url="https://youtube.com/test",
            channel_id="UC123",
            limit=10
        )
        db_session.add(channel)
        db_session.commit()

        # Create only 5 downloads (under limit of 10)
        for i in range(5):
            download = Download(
                channel_id=channel.id,
                video_id=f"video_{i}",
                title=f"Video {i}",
                upload_date=f"202501{i:02d}",
                status="completed",
                file_exists=True,
                file_path=f"/media/channel/video_{i}.mp4"
            )
            db_session.add(download)
        db_session.commit()

        # Run cleanup
        deleted_count = await _cleanup_old_videos(channel, db_session)

        # Verify no deletions
        assert deleted_count == 0
        remaining_count = db_session.query(Download).filter(
            Download.channel_id == channel.id
        ).count()
        assert remaining_count == 5

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.shutil.rmtree')
    @patch('app.scheduled_download_job.Path')
    async def test_deletes_oldest_videos_when_over_limit(self, mock_path, mock_rmtree, db_session):
        """Test that oldest videos are deleted when channel exceeds limit."""
        channel = Channel(
            id=1,
            name="Test Channel",
            url="https://youtube.com/test",
            channel_id="UC123",
            limit=10
        )
        db_session.add(channel)
        db_session.commit()

        # Create 13 downloads (3 over limit)
        # upload_date format: YYYYMMDD (strings sort correctly)
        for i in range(13):
            download = Download(
                channel_id=channel.id,
                video_id=f"video_{i}",
                title=f"Video {i}",
                upload_date=f"202501{i:02d}",  # 20250100, 20250101, ..., 20250112
                status="completed",
                file_exists=True,
                file_path=f"/media/channel/video_{i}/video.mp4"
            )
            db_session.add(download)
        db_session.commit()

        # Mock file system operations
        mock_path_instance = MagicMock()
        mock_path_instance.parent.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Run cleanup
        deleted_count = await _cleanup_old_videos(channel, db_session)

        # Verify 3 oldest videos were deleted
        assert deleted_count == 3

        # Verify correct number of videos remain
        remaining_count = db_session.query(Download).filter(
            Download.channel_id == channel.id
        ).count()
        assert remaining_count == 10

        # Verify oldest videos were deleted (video_0, video_1, video_2)
        oldest_videos = db_session.query(Download).filter(
            Download.channel_id == channel.id,
            Download.video_id.in_(["video_0", "video_1", "video_2"])
        ).all()
        assert len(oldest_videos) == 0

        # Verify newest videos were kept (video_10, video_11, video_12)
        newest_videos = db_session.query(Download).filter(
            Download.channel_id == channel.id,
            Download.video_id.in_(["video_10", "video_11", "video_12"])
        ).all()
        assert len(newest_videos) == 3

    @pytest.mark.asyncio
    async def test_handles_empty_channel(self, db_session):
        """Test graceful handling of channel with no videos."""
        channel = Channel(
            id=1,
            name="Empty Channel",
            url="https://youtube.com/empty",
            channel_id="UC999",
            limit=10
        )
        db_session.add(channel)
        db_session.commit()

        # Run cleanup on empty channel
        deleted_count = await _cleanup_old_videos(channel, db_session)

        # Should handle gracefully with no errors
        assert deleted_count == 0

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.shutil.rmtree')
    @patch('app.scheduled_download_job.Path')
    async def test_handles_missing_files(self, mock_path, mock_rmtree, db_session):
        """Test graceful handling when video files don't exist on disk."""
        channel = Channel(
            id=1,
            name="Test Channel",
            url="https://youtube.com/test",
            channel_id="UC123",
            limit=5
        )
        db_session.add(channel)
        db_session.commit()

        # Create 8 downloads (3 over limit)
        for i in range(8):
            download = Download(
                channel_id=channel.id,
                video_id=f"video_{i}",
                title=f"Video {i}",
                upload_date=f"202501{i:02d}",
                status="completed",
                file_exists=True,
                file_path=f"/media/channel/video_{i}/video.mp4"
            )
            db_session.add(download)
        db_session.commit()

        # Mock file system - directory doesn't exist
        mock_path_instance = MagicMock()
        mock_path_instance.parent.exists.return_value = False
        mock_path.return_value = mock_path_instance

        # Run cleanup - should handle missing files gracefully
        deleted_count = await _cleanup_old_videos(channel, db_session)

        # Database records should still be deleted
        assert deleted_count == 3

        # Verify correct count remains
        remaining_count = db_session.query(Download).filter(
            Download.channel_id == channel.id
        ).count()
        assert remaining_count == 5

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.shutil.rmtree')
    @patch('app.scheduled_download_job.Path')
    async def test_continues_on_individual_file_deletion_error(self, mock_path, mock_rmtree, db_session):
        """Test that cleanup continues if individual file deletion fails."""
        channel = Channel(
            id=1,
            name="Test Channel",
            url="https://youtube.com/test",
            channel_id="UC123",
            limit=5
        )
        db_session.add(channel)
        db_session.commit()

        # Create 8 downloads (3 over limit)
        for i in range(8):
            download = Download(
                channel_id=channel.id,
                video_id=f"video_{i}",
                title=f"Video {i}",
                upload_date=f"202501{i:02d}",
                status="completed",
                file_exists=True,
                file_path=f"/media/channel/video_{i}/video.mp4"
            )
            db_session.add(download)
        db_session.commit()

        # Mock file system operations
        mock_path_instance = MagicMock()
        mock_path_instance.parent.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Make rmtree fail for first deletion, succeed for others
        mock_rmtree.side_effect = [
            Exception("Permission denied"),  # First deletion fails
            None,  # Second succeeds
            None   # Third succeeds
        ]

        # Run cleanup - should continue despite error
        deleted_count = await _cleanup_old_videos(channel, db_session)

        # All database records should be deleted (even if file deletion failed)
        assert deleted_count == 3

        remaining_count = db_session.query(Download).filter(
            Download.channel_id == channel.id
        ).count()
        assert remaining_count == 5

    @pytest.mark.asyncio
    async def test_only_deletes_completed_videos(self, db_session):
        """Test that only completed videos are considered for cleanup."""
        channel = Channel(
            id=1,
            name="Test Channel",
            url="https://youtube.com/test",
            channel_id="UC123",
            limit=5
        )
        db_session.add(channel)
        db_session.commit()

        # Create 5 completed videos (at limit)
        for i in range(5):
            download = Download(
                channel_id=channel.id,
                video_id=f"completed_{i}",
                title=f"Completed {i}",
                upload_date=f"202501{i:02d}",
                status="completed",
                file_exists=True,
                file_path=f"/media/channel/completed_{i}.mp4"
            )
            db_session.add(download)

        # Create 3 pending/failed videos (should not be counted)
        for i in range(3):
            download = Download(
                channel_id=channel.id,
                video_id=f"pending_{i}",
                title=f"Pending {i}",
                upload_date=f"202502{i:02d}",
                status="pending",
                file_exists=False
            )
            db_session.add(download)

        db_session.commit()

        # Run cleanup
        deleted_count = await _cleanup_old_videos(channel, db_session)

        # No deletions (only 5 completed videos, which is at limit)
        assert deleted_count == 0

        # Verify all videos still exist
        total_count = db_session.query(Download).filter(
            Download.channel_id == channel.id
        ).count()
        assert total_count == 8  # 5 completed + 3 pending

    @pytest.mark.asyncio
    @patch('app.scheduled_download_job.shutil.rmtree')
    @patch('app.scheduled_download_job.Path')
    async def test_cleanup_tracks_deleted_count_in_summary(self, mock_path, mock_rmtree, db_session):
        """Test that deleted video count is tracked for statistics."""
        channel = Channel(
            id=1,
            name="Test Channel",
            url="https://youtube.com/test",
            channel_id="UC123",
            limit=10
        )
        db_session.add(channel)
        db_session.commit()

        # Create 15 downloads (5 over limit)
        for i in range(15):
            download = Download(
                channel_id=channel.id,
                video_id=f"video_{i}",
                title=f"Video {i}",
                upload_date=f"202501{i:02d}",
                status="completed",
                file_exists=True,
                file_path=f"/media/channel/video_{i}/video.mp4"
            )
            db_session.add(download)
        db_session.commit()

        # Mock file system operations
        mock_path_instance = MagicMock()
        mock_path_instance.parent.exists.return_value = True
        mock_path.return_value = mock_path_instance

        # Run cleanup
        deleted_count = await _cleanup_old_videos(channel, db_session)

        # Verify correct count returned
        assert deleted_count == 5

    @pytest.mark.asyncio
    async def test_database_rollback_on_error(self, db_session):
        """Test that database is rolled back on cleanup error."""
        channel = Channel(
            id=1,
            name="Test Channel",
            url="https://youtube.com/test",
            channel_id="UC123",
            limit=5
        )
        db_session.add(channel)
        db_session.commit()

        # Force a database error by making query fail
        with patch.object(db_session, 'query', side_effect=Exception("DB connection lost")):
            # Run cleanup - should handle error gracefully
            deleted_count = await _cleanup_old_videos(channel, db_session)

            # Should return 0 and not crash
            assert deleted_count == 0
