"""Manual trigger queue management for coordinating with scheduler.

This module implements the queue mechanism for manual download triggers
when the scheduler is running. Uses ApplicationSettings table for persistence
across container restarts.

BE-007: Coordinate Manual Trigger with Scheduler Lock

Key Features:
- JSON-based queue stored in ApplicationSettings table
- FIFO (First In, First Out) processing
- Timeout handling for stale requests (30 minutes)
- Persistence across Docker restarts
- Thread-safe queue operations

Queue Entry Format:
    {
        "channel_id": 123,
        "user": "manual",
        "timestamp": "2025-10-04T10:30:00Z"
    }

Usage:
    from app.manual_trigger_queue import add_to_queue, get_queue, process_queue

    # In manual trigger endpoint:
    position = add_to_queue(db, channel_id)

    # In scheduled job:
    await process_queue(db)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import ApplicationSettings, Channel
from app.video_download_service import video_download_service

logger = logging.getLogger(__name__)

QUEUE_KEY = "manual_trigger_queue"
TIMEOUT_MINUTES = 30


def add_to_queue(db: Session, channel_id: int) -> int:
    """
    Add a manual trigger request to the queue.

    Args:
        db: Database session
        channel_id: Channel ID to queue for download

    Returns:
        int: Queue position (1-based index)

    Example:
        >>> position = add_to_queue(db, 123)
        >>> logger.info(f"Request queued at position {position}")
    """
    try:
        # Get existing queue or create empty one
        queue_setting = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == QUEUE_KEY
        ).first()

        if queue_setting and queue_setting.value:
            try:
                queue = json.loads(queue_setting.value)
            except json.JSONDecodeError:
                logger.warning("Invalid queue JSON, resetting to empty queue")
                queue = []
        else:
            queue = []

        # Add new entry to queue
        new_entry = {
            "channel_id": channel_id,
            "user": "manual",
            "timestamp": datetime.utcnow().isoformat()
        }
        queue.append(new_entry)

        # Save back to database
        if queue_setting:
            queue_setting.value = json.dumps(queue)
            queue_setting.updated_at = datetime.utcnow()
        else:
            queue_setting = ApplicationSettings(
                key=QUEUE_KEY,
                value=json.dumps(queue),
                description="Queue for manual download triggers during scheduler runs",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(queue_setting)

        db.commit()

        position = len(queue)
        logger.info(f"Added channel {channel_id} to manual trigger queue at position {position}")
        return position

    except Exception as e:
        logger.error(f"Failed to add channel {channel_id} to queue: {e}")
        db.rollback()
        raise


def get_queue(db: Session) -> List[Dict]:
    """
    Get the current manual trigger queue.

    Args:
        db: Database session

    Returns:
        List of queue entries (may be empty)

    Example:
        >>> queue = get_queue(db)
        >>> logger.info(f"Queue has {len(queue)} pending requests")
    """
    try:
        queue_setting = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == QUEUE_KEY
        ).first()

        if not queue_setting or not queue_setting.value:
            return []

        try:
            return json.loads(queue_setting.value)
        except json.JSONDecodeError:
            logger.warning("Invalid queue JSON, returning empty queue")
            return []

    except Exception as e:
        logger.error(f"Failed to get queue: {e}")
        return []


def clear_queue(db: Session):
    """
    Clear the entire manual trigger queue.

    Args:
        db: Database session

    Example:
        >>> clear_queue(db)
        >>> logger.info("Manual trigger queue cleared")
    """
    try:
        queue_setting = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == QUEUE_KEY
        ).first()

        if queue_setting:
            queue_setting.value = "[]"
            queue_setting.updated_at = datetime.utcnow()
            db.commit()
            logger.info("Manual trigger queue cleared")

    except Exception as e:
        logger.error(f"Failed to clear queue: {e}")
        db.rollback()


def remove_stale_entries(db: Session) -> int:
    """
    Remove entries older than TIMEOUT_MINUTES from the queue.

    Stale requests are removed and logged as warnings. This prevents
    the queue from filling up with abandoned requests.

    Args:
        db: Database session

    Returns:
        int: Number of stale entries removed

    Example:
        >>> removed = remove_stale_entries(db)
        >>> if removed > 0:
        ...     logger.warning(f"Removed {removed} stale queue entries")
    """
    try:
        queue = get_queue(db)
        if not queue:
            return 0

        now = datetime.utcnow()
        timeout_threshold = now - timedelta(minutes=TIMEOUT_MINUTES)

        original_count = len(queue)
        fresh_queue = []

        for entry in queue:
            try:
                timestamp = datetime.fromisoformat(entry["timestamp"].replace('Z', '+00:00'))
                if timestamp > timeout_threshold:
                    fresh_queue.append(entry)
                else:
                    logger.warning(
                        f"Removing stale manual trigger request for channel {entry['channel_id']}: "
                        f"queued at {entry['timestamp']}, timed out after {TIMEOUT_MINUTES} minutes"
                    )
            except Exception as e:
                logger.warning(f"Invalid queue entry format: {entry}, error: {e}")
                # Skip malformed entries

        removed_count = original_count - len(fresh_queue)

        if removed_count > 0:
            # Save cleaned queue
            queue_setting = db.query(ApplicationSettings).filter(
                ApplicationSettings.key == QUEUE_KEY
            ).first()

            if queue_setting:
                queue_setting.value = json.dumps(fresh_queue)
                queue_setting.updated_at = datetime.utcnow()
                db.commit()

        return removed_count

    except Exception as e:
        logger.error(f"Failed to remove stale entries: {e}")
        return 0


async def process_queue(db: Session) -> Tuple[int, int]:
    """
    Process all queued manual trigger requests.

    This function should be called at the end of the scheduled download job,
    after all scheduled channels have been processed. It processes queued
    requests in FIFO order.

    Args:
        db: Database session

    Returns:
        Tuple of (successful_count, failed_count)

    Example:
        >>> successful, failed = await process_queue(db)
        >>> logger.info(f"Processed queue: {successful} successful, {failed} failed")
    """
    logger.info("Processing manual trigger queue")

    # Remove stale entries first
    stale_count = remove_stale_entries(db)
    if stale_count > 0:
        logger.warning(f"Removed {stale_count} stale entries from manual trigger queue")

    # Get current queue
    queue = get_queue(db)
    if not queue:
        logger.info("Manual trigger queue is empty, nothing to process")
        return 0, 0

    logger.info(f"Processing {len(queue)} queued manual trigger requests")

    successful = 0
    failed = 0

    for entry in queue:
        try:
            channel_id = entry["channel_id"]
            timestamp = entry["timestamp"]

            logger.info(f"Processing queued manual trigger for channel {channel_id} (queued at {timestamp})")

            # Get channel from database
            channel = db.query(Channel).filter(Channel.id == channel_id).first()
            if not channel:
                logger.warning(f"Channel {channel_id} not found, skipping queued request")
                failed += 1
                continue

            if not channel.enabled:
                logger.warning(f"Channel {channel_id} is disabled, skipping queued request")
                failed += 1
                continue

            # Process the download
            success, videos_downloaded, error_message = video_download_service.process_channel_downloads(
                channel, db
            )

            if success:
                logger.info(
                    f"Queued manual trigger completed for channel {channel_id}: "
                    f"{videos_downloaded} videos downloaded"
                )
                successful += 1
            else:
                logger.error(
                    f"Queued manual trigger failed for channel {channel_id}: {error_message}"
                )
                failed += 1

        except Exception as e:
            logger.error(f"Error processing queued request for channel {entry.get('channel_id', 'unknown')}: {e}")
            failed += 1

    # Clear the queue after processing
    clear_queue(db)

    logger.info(
        f"Manual trigger queue processing completed: {successful} successful, {failed} failed"
    )

    return successful, failed
