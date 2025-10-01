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
from datetime import datetime
from typing import Tuple
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Channel, ApplicationSettings, DownloadHistory
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
            ("scheduler_total_videos_last_run", str(summary["total_videos"]))
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
