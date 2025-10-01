"""Overlap prevention mechanism for scheduled jobs using database flags.

This module provides a context manager for preventing concurrent execution of
scheduled jobs using ApplicationSettings table as a distributed lock mechanism.
Works across Docker container restarts and includes automatic cleanup.

Key Features:
- Database flag-based locking (works across containers)
- Automatic lock release in finally block (guaranteed cleanup)
- Last run timestamp tracking for monitoring
- Graceful handling of already-running jobs
- Stale lock detection and recovery

Usage:
    from app.overlap_prevention import scheduler_lock, JobAlreadyRunningError

    try:
        with scheduler_lock(db, "scheduled_downloads"):
            # Your job logic here
            process_all_channels()
    except JobAlreadyRunningError:
        logger.warning("Job already running, skipping this execution")
"""

import logging
from datetime import datetime
from contextlib import contextmanager
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models import ApplicationSettings

logger = logging.getLogger(__name__)


class JobAlreadyRunningError(Exception):
    """Raised when attempting to start a job that's already running.

    This is a controlled exception indicating that the job execution
    should be skipped because another instance is already active.
    Not an error condition - just prevents overlap.
    """
    pass


@contextmanager
def scheduler_lock(db: Session, job_name: str = "scheduler"):
    """
    Context manager for preventing overlapping scheduled jobs.

    Uses ApplicationSettings table for distributed locking across containers.
    Includes automatic cleanup and error recovery.

    Args:
        db: Database session (SQLAlchemy Session)
        job_name: Unique identifier for the job type (e.g., "scheduled_downloads")

    Raises:
        JobAlreadyRunningError: If another instance of the job is already running

    Example:
        >>> from app.overlap_prevention import scheduler_lock
        >>> db = SessionLocal()
        >>> try:
        ...     with scheduler_lock(db, "download_job"):
        ...         process_channels()
        ... except JobAlreadyRunningError:
        ...     logger.warning("Job already running, skipped")
        ... finally:
        ...     db.close()

    Implementation:
        1. Checks {job_name}_running flag in database
        2. Raises JobAlreadyRunningError if flag is "true"
        3. Sets flag to "true" atomically with database commit
        4. Updates {job_name}_last_run timestamp
        5. Executes protected code block (yield)
        6. Always clears flag in finally block (even on exceptions)
    """
    lock_key = f"{job_name}_running"
    lock_acquired = False

    try:
        # Check if already running (atomic read)
        running_flag = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == lock_key
        ).first()

        if running_flag and running_flag.value == "true":
            logger.warning(f"Job '{job_name}' already running, skipping execution")
            raise JobAlreadyRunningError(f"Another instance of {job_name} is already running")

        # Acquire lock atomically
        if running_flag:
            running_flag.value = "true"
            running_flag.updated_at = datetime.utcnow()
        else:
            # Create flag if it doesn't exist (shouldn't happen if migration ran)
            running_flag = ApplicationSettings(
                key=lock_key,
                value="true",
                description=f"Lock flag to prevent overlapping {job_name} executions",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(running_flag)

        db.commit()
        lock_acquired = True
        logger.info(f"Acquired lock for job '{job_name}'")

        # Update last run timestamp
        _update_last_run_timestamp(db, job_name)

        yield  # Execute the protected code block

    except JobAlreadyRunningError:
        # Re-raise job overlap errors (not a real error, just skip execution)
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in scheduler lock for '{job_name}': {e}")
        if lock_acquired:
            db.rollback()
        raise
    except Exception as e:
        logger.error(f"Unexpected error in job '{job_name}': {e}")
        raise
    finally:
        # Always clear the lock, even on exceptions
        if lock_acquired:
            try:
                if running_flag:
                    running_flag.value = "false"
                    running_flag.updated_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Released lock for job '{job_name}'")
            except Exception as e:
                logger.error(f"Failed to release lock for '{job_name}': {e}")
                # Force rollback to prevent partial state
                try:
                    db.rollback()
                except:
                    pass


def _update_last_run_timestamp(db: Session, job_name: str):
    """Update last successful run timestamp for monitoring.

    Args:
        db: Database session
        job_name: Job identifier (e.g., "scheduled_downloads")

    Note:
        Timestamp update failures are logged but don't fail the job.
        This is a monitoring feature, not critical for job execution.
    """
    try:
        timestamp_key = f"{job_name}_last_run"
        last_run_setting = db.query(ApplicationSettings).filter(
            ApplicationSettings.key == timestamp_key
        ).first()

        current_time = datetime.utcnow().isoformat()
        if last_run_setting:
            last_run_setting.value = current_time
            last_run_setting.updated_at = datetime.utcnow()
        else:
            # Create timestamp setting if it doesn't exist
            last_run_setting = ApplicationSettings(
                key=timestamp_key,
                value=current_time,
                description=f"Timestamp of last successful {job_name} execution",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(last_run_setting)

        db.commit()

    except Exception as e:
        logger.warning(f"Failed to update last run timestamp for {job_name}: {e}")
        # Don't fail the job for timestamp update errors


def clear_stale_locks(db: Session, max_age_hours: int = 2):
    """
    Clear stale scheduler locks on application startup.

    A lock is considered stale if:
    - The {job}_running flag is "true" AND
    - The last_run timestamp is >2 hours old (or missing)

    This handles crash scenarios where the scheduler was killed and
    the lock wasn't properly released.

    Args:
        db: Database session
        max_age_hours: Maximum age in hours before a lock is considered stale

    Returns:
        Number of stale locks cleared

    Example:
        >>> from app.overlap_prevention import clear_stale_locks
        >>> db = SessionLocal()
        >>> cleared = clear_stale_locks(db, max_age_hours=2)
        >>> logger.info(f"Cleared {cleared} stale locks")
        >>> db.close()
    """
    try:
        # Find all *_running flags that are set to "true"
        running_flags = db.query(ApplicationSettings).filter(
            ApplicationSettings.key.like("%_running"),
            ApplicationSettings.value == "true"
        ).all()

        cleared_count = 0
        now = datetime.utcnow()
        max_age = max_age_hours * 3600  # Convert to seconds

        for flag in running_flags:
            # Extract job name from flag key (e.g., "scheduled_downloads_running" -> "scheduled_downloads")
            job_name = flag.key.replace("_running", "")

            # Check if lock is stale based on last_run timestamp
            last_run_key = f"{job_name}_last_run"
            last_run = db.query(ApplicationSettings).filter(
                ApplicationSettings.key == last_run_key
            ).first()

            is_stale = False
            if last_run and last_run.value:
                try:
                    last_run_time = datetime.fromisoformat(last_run.value.replace('Z', '+00:00'))
                    age_seconds = (now - last_run_time).total_seconds()
                    if age_seconds > max_age:
                        is_stale = True
                except:
                    # If timestamp parsing fails, consider it stale
                    is_stale = True
            else:
                # No last_run timestamp, check updated_at on the flag itself
                if flag.updated_at:
                    age_seconds = (now - flag.updated_at).total_seconds()
                    if age_seconds > max_age:
                        is_stale = True
                else:
                    # No timestamp at all, definitely stale
                    is_stale = True

            if is_stale:
                logger.warning(
                    f"Detected stale scheduler lock for '{job_name}'. "
                    f"Lock age: {age_seconds if 'age_seconds' in locals() else 'unknown'}s. "
                    f"Clearing lock and resuming."
                )
                flag.value = "false"
                flag.updated_at = now
                cleared_count += 1

        if cleared_count > 0:
            db.commit()
            logger.info(f"Cleared {cleared_count} stale scheduler lock(s)")

        return cleared_count

    except Exception as e:
        logger.error(f"Error clearing stale locks: {e}")
        db.rollback()
        return 0
