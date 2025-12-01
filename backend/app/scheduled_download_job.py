"""Scheduled download job with three-tier error handling.

This module implements the main scheduled job that processes all enabled channels
and downloads new videos. It integrates with the existing video_download_service
and uses the overlap prevention mechanism to prevent concurrent executions.

Three-Tier Error Handling:
1. Job Level: Prevent overlaps, continue on individual channel failures
2. Channel Level: Log errors, update history, continue with next channel
3. Video Level: Log errors, continue with next video (handled in video_download_service)

Key Features:
- Sequential channel processing (prevents system overload)
- Individual channel error isolation
- Retry logic for transient errors
- Comprehensive job statistics
- Integration with overlap prevention
- DownloadHistory tracking for all runs

Usage:
    This job is scheduled by SchedulerService and runs automatically
    based on the cron schedule in ApplicationSettings.
"""

import logging
import asyncio
import shutil
import os
from datetime import datetime
from typing import Tuple
from pathlib import Path
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Channel, ApplicationSettings, DownloadHistory, Download
from app.video_download_service import video_download_service
from app.overlap_prevention import scheduler_lock, JobAlreadyRunningError

logger = logging.getLogger(__name__)


async def scheduled_download_job():
    """
    Main scheduled download job with three-tier error handling.

    This job:
    1. Acquires lock to prevent overlapping executions
    2. Queries all enabled channels
    3. Processes each channel sequentially
    4. Retries transient errors
    5. Tracks statistics for monitoring
    6. Always releases lock (even on exceptions)

    Error Handling Strategy:
    - Job Level: Catches all exceptions to prevent scheduler disruption
    - Channel Level: Individual failures don't stop processing
    - Video Level: Handled by video_download_service

    The job is designed to be resilient and continue processing even
    when individual channels fail.
    """
    logger.info("Starting scheduled download job")

    db = SessionLocal()
    downloaded_summary = {
        "total_channels": 0,
        "successful_channels": 0,
        "failed_channels": 0,
        "total_videos": 0,
        "total_videos_deleted": 0,
        "start_time": datetime.utcnow()
    }

    try:
        # Job-level overlap prevention
        with scheduler_lock(db, "scheduled_downloads"):

            # Get all enabled channels
            channels = db.query(Channel).filter(Channel.enabled == True).all()
            downloaded_summary["total_channels"] = len(channels)

            if not channels:
                logger.info("No enabled channels found for scheduled downloads")
                return

            logger.info(f"Processing {len(channels)} enabled channels")

            # Process each channel with individual error handling
            for channel in channels:
                channel_start_time = datetime.utcnow()

                try:
                    logger.info(f"Processing channel: {channel.name} (ID: {channel.id})")

                    # Channel-level processing with error isolation
                    success, videos_downloaded, error_message = await _process_channel_with_recovery(
                        channel, db
                    )

                    if success:
                        downloaded_summary["successful_channels"] += 1
                        downloaded_summary["total_videos"] += videos_downloaded

                        # === BE-004B: AUTOMATIC VIDEO CLEANUP ===
                        # Clean up old videos if channel exceeds configured limit
                        # This runs after downloads complete to maintain storage limits
                        try:
                            deleted_count = await cleanup_old_videos(channel, db)
                            downloaded_summary["total_videos_deleted"] += deleted_count
                            if deleted_count > 0:
                                logger.info(
                                    f"Cleaned up {deleted_count} old video(s) for channel '{channel.name}' "
                                    f"(limit: {channel.limit})"
                                )
                        except Exception as e:
                            # Cleanup errors shouldn't stop the job
                            logger.error(f"Cleanup failed for channel '{channel.name}': {e}")

                        processing_time = (datetime.utcnow() - channel_start_time).total_seconds()
                        logger.info(
                            f"Channel '{channel.name}' completed successfully: "
                            f"{videos_downloaded} videos in {processing_time:.1f}s"
                        )
                    else:
                        downloaded_summary["failed_channels"] += 1
                        logger.error(f"Channel '{channel.name}' failed: {error_message}")

                except Exception as e:
                    # Individual channel failure shouldn't stop the entire job
                    downloaded_summary["failed_channels"] += 1
                    logger.error(f"Unexpected error processing channel '{channel.name}': {e}")

                    # Create failed history record for monitoring
                    _create_failed_history_record(channel.id, str(e), db)

                    continue  # Continue with next channel

            # Log final summary
            total_time = (datetime.utcnow() - downloaded_summary["start_time"]).total_seconds()
            logger.info(
                f"Scheduled download job completed in {total_time:.1f}s: "
                f"{downloaded_summary['successful_channels']}/{downloaded_summary['total_channels']} channels successful, "
                f"{downloaded_summary['total_videos']} total videos downloaded"
            )

            # === BE-007: PROCESS MANUAL TRIGGER QUEUE ===
            # Process any queued manual download requests after scheduled channels
            logger.info("Checking for queued manual download requests")
            try:
                from app.manual_trigger_queue import process_queue

                queue_successful, queue_failed = await process_queue(db)
                if queue_successful > 0 or queue_failed > 0:
                    logger.info(
                        f"Processed manual trigger queue: {queue_successful} successful, {queue_failed} failed"
                    )
                    # Update summary to include queued requests
                    downloaded_summary["manual_queue_successful"] = queue_successful
                    downloaded_summary["manual_queue_failed"] = queue_failed

            except Exception as e:
                logger.error(f"Error processing manual trigger queue: {e}")
                # Don't fail the entire job if queue processing fails

            # Update global job statistics
            _update_job_statistics(downloaded_summary, db)

    except JobAlreadyRunningError:
        logger.warning("Scheduled download job skipped - another instance already running")
        return
    except Exception as e:
        logger.error(f"Critical error in scheduled download job: {e}")
        # Don't re-raise - let scheduler continue with next scheduled run
    finally:
        db.close()


async def _process_channel_with_recovery(channel: Channel, db: Session) -> Tuple[bool, int, str]:
    """
    Process single channel with comprehensive error recovery.

    Implements retry logic for transient errors (network issues, rate limits).
    Non-retryable errors (channel deleted, invalid URL) fail immediately.

    Args:
        channel: Channel database model
        db: Database session

    Returns:
        Tuple of (success, videos_downloaded, error_message)

    Retry Strategy:
        - Maximum 2 retries
        - 30 second delay between retries
        - Only retry transient/network errors
        - Fail fast on permanent errors
    """
    max_retries = 2
    retry_count = 0

    while retry_count < max_retries:
        try:
            # Use existing video download service
            # This returns (success, videos_downloaded, error_message)
            success, videos_downloaded, error_message = video_download_service.process_channel_downloads(
                channel, db
            )

            # If successful or non-retryable error, return immediately
            if success or not _is_retryable_error(error_message):
                return success, videos_downloaded, error_message

            # Retryable error - log and try again
            retry_count += 1
            if retry_count < max_retries:
                logger.warning(
                    f"Retryable error for channel '{channel.name}' (attempt {retry_count}/{max_retries}): "
                    f"{error_message}"
                )
                await asyncio.sleep(30)  # Wait before retry

        except Exception as e:
            error_message = str(e)
            retry_count += 1

            if retry_count < max_retries:
                logger.warning(f"Exception in channel processing, retrying: {error_message}")
                await asyncio.sleep(30)
            else:
                logger.error(f"Max retries exceeded for channel '{channel.name}': {error_message}")
                return False, 0, error_message

    return False, 0, error_message


def _is_retryable_error(error_message: str) -> bool:
    """
    Determine if an error is worth retrying.

    Retryable errors include:
    - Network timeouts and connection issues
    - Rate limiting (HTTP 429, 503)
    - Temporary service unavailability

    Non-retryable errors include:
    - Channel deleted or private
    - Invalid URL format
    - Disk space exhausted
    - Authentication issues

    Args:
        error_message: Error message string from failed operation

    Returns:
        True if error should be retried, False otherwise
    """
    if not error_message:
        return False

    # Network-related errors are retryable
    retryable_keywords = [
        "network", "timeout", "connection", "temporary",
        "rate limit", "quota", "503", "502", "504",
        "429"  # Too Many Requests
    ]

    error_lower = error_message.lower()
    return any(keyword in error_lower for keyword in retryable_keywords)


def _create_failed_history_record(channel_id: int, error_message: str, db: Session):
    """
    Create history record for failed channel processing.

    This ensures all job runs are tracked, even failures, for monitoring
    and debugging purposes.

    Args:
        channel_id: Channel database ID
        error_message: Error description
        db: Database session
    """
    try:
        history = DownloadHistory(
            channel_id=channel_id,
            run_date=datetime.utcnow(),
            videos_found=0,
            videos_downloaded=0,
            videos_skipped=0,
            status='failed',
            error_message=error_message[:500],  # Truncate long errors
            completed_at=datetime.utcnow()
        )
        db.add(history)
        db.commit()
    except Exception as e:
        logger.error(f"Failed to create history record for channel {channel_id}: {e}")


def _update_job_statistics(summary: dict, db: Session):
    """
    Update global job statistics for monitoring dashboard.

    Stores comprehensive job statistics in ApplicationSettings for display
    in the UI dashboard and monitoring endpoints.

    Args:
        summary: Dictionary with job execution statistics
        db: Database session

    Statistics Stored:
        - scheduler_last_run_summary: Full summary dict as string
        - scheduler_last_successful_run: ISO timestamp
        - scheduler_total_channels_last_run: Channel count
        - scheduler_successful_channels_last_run: Success count
        - scheduler_total_videos_last_run: Video count
    """
    try:
        stats_keys = [
            ("scheduler_last_run_summary", str(summary)),
            ("scheduler_last_successful_run", summary["start_time"].isoformat()),
            ("scheduler_total_channels_last_run", str(summary["total_channels"])),
            ("scheduler_successful_channels_last_run", str(summary["successful_channels"])),
            ("scheduler_total_videos_last_run", str(summary["total_videos"])),
            ("scheduler_total_videos_deleted_last_run", str(summary.get("total_videos_deleted", 0)))
        ]

        for key, value in stats_keys:
            setting = db.query(ApplicationSettings).filter(
                ApplicationSettings.key == key
            ).first()

            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = ApplicationSettings(
                    key=key,
                    value=value,
                    description=f"Scheduler statistic: {key}",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(setting)

        db.commit()

    except Exception as e:
        logger.error(f"Failed to update job statistics: {e}")


async def cleanup_old_videos(channel: Channel, db: Session) -> int:
    """
    Delete oldest videos when channel exceeds configured limit.

    This function maintains the video count at the channel's configured limit
    by deleting the oldest videos (by upload_date). It handles both database
    records and physical files on disk.

    Process:
    1. Query all completed downloads for the channel
    2. Sort by upload_date (newest first)
    3. Calculate how many videos exceed the limit
    4. Delete oldest videos (both DB records and files)
    5. Return count of deleted videos

    Args:
        channel: Channel database model with configured limit
        db: Database session

    Returns:
        Number of videos deleted

    Error Handling:
        - Missing files are logged but don't stop deletion
        - Individual file deletion errors don't prevent DB cleanup
        - All errors logged with context for debugging

    Example:
        Channel has limit=10, currently has 13 videos
        → Deletes 3 oldest videos
        → Returns 3
    """
    try:
        # Query all completed downloads with existing files, sorted to put NULLs first, then oldest to newest
        # This ensures videos without upload_date metadata are deleted first, followed by oldest videos
        downloads = db.query(Download).filter(
            Download.channel_id == channel.id,
            Download.status == "completed",
            Download.file_exists == True
        ).order_by(
            Download.upload_date.is_(None).desc(),  # NULLs first (they're old videos without metadata)
            Download.upload_date.asc()               # Then oldest to newest by actual date
        ).all()

        current_count = len(downloads)

        # If we're at or under the limit, no cleanup needed
        if current_count <= channel.limit:
            logger.debug(f"Channel '{channel.name}' has {current_count} videos (limit: {channel.limit}), no cleanup needed")
            return 0

        # Calculate how many videos to delete (oldest ones)
        excess_count = current_count - channel.limit
        videos_to_delete = downloads[:excess_count]  # Get the oldest videos (at the start of list)

        logger.info(
            f"Channel '{channel.name}' has {current_count} videos (limit: {channel.limit}), "
            f"deleting {excess_count} oldest video(s)"
        )

        deleted_count = 0
        deleted_video_names = []  # Track deleted video names for logging

        for download in videos_to_delete:
            try:
                # Delete physical file/directory if it exists
                if download.file_path and download.file_exists:
                    file_path = Path(download.file_path)

                    # Try to delete the parent directory (contains video + metadata + thumbnails)
                    video_dir = file_path.parent

                    if video_dir.exists():
                        shutil.rmtree(video_dir)
                        logger.debug(f"Deleted video directory: {video_dir}")
                    else:
                        logger.warning(f"Video directory not found (already deleted?): {video_dir}")

                # Mark database record as deleted (preserve history)
                # Don't delete the record - just mark when it was removed from disk
                download.file_exists = False
                download.deleted_at = datetime.utcnow()
                deleted_count += 1
                deleted_video_names.append(download.title)  # Track for summary log

                logger.debug(
                    f"Marked video as deleted '{download.title}' (ID: {download.video_id}, "
                    f"uploaded: {download.upload_date})"
                )

            except Exception as e:
                # Log error but continue with other deletions
                logger.error(
                    f"Failed to delete video '{download.title}' (ID: {download.video_id}): {e}"
                )
                # Still try to mark the DB record as deleted
                try:
                    download.file_exists = False
                    download.deleted_at = datetime.utcnow()
                    deleted_count += 1
                    deleted_video_names.append(download.title)  # Track even if file deletion failed
                except Exception as db_error:
                    logger.error(f"Failed to mark database record as deleted for video {download.video_id}: {db_error}")

        # Commit all deletions
        db.commit()

        # Build detailed log message with video names
        if deleted_video_names:
            video_list = "\n  - ".join(deleted_video_names)
            logger.info(
                f"Cleanup completed for channel '{channel.name}': "
                f"deleted {deleted_count}/{excess_count} video(s), "
                f"now has {current_count - deleted_count} videos (limit: {channel.limit})\n"
                f"  Deleted videos:\n  - {video_list}"
            )
        else:
            logger.info(
                f"Cleanup completed for channel '{channel.name}': "
                f"deleted {deleted_count}/{excess_count} video(s), "
                f"now has {current_count - deleted_count} videos (limit: {channel.limit})"
            )

        return deleted_count

    except Exception as e:
        logger.error(f"Error during cleanup for channel '{channel.name}': {e}")
        db.rollback()
        return 0
