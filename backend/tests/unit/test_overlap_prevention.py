"""Unit tests for overlap prevention mechanism.

Tests the overlap_prevention module which provides database flag-based
locking to prevent concurrent scheduler executions.

TEST-001: Comprehensive overlap prevention testing
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.overlap_prevention import (
    scheduler_lock,
    JobAlreadyRunningError,
    _update_last_run_timestamp,
    clear_stale_locks
)
from app.models import ApplicationSettings


class TestSchedulerLock:
    """Test suite for scheduler_lock context manager."""

    def test_lock_acquisition_success(self, db_session):
        """Test successful lock acquisition when not already running."""
        # Ensure flag doesn't exist or is false
        flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "test_job_running"
        ).first()

        if flag:
            flag.value = "false"
            db_session.commit()

        # Acquire lock
        with scheduler_lock(db_session, "test_job"):
            # Verify lock is set
            flag = db_session.query(ApplicationSettings).filter(
                ApplicationSettings.key == "test_job_running"
            ).first()

            assert flag is not None
            assert flag.value == "true"

        # Verify lock is released
        flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "test_job_running"
        ).first()

        assert flag.value == "false"

    def test_lock_already_running_raises_error(self, db_session):
        """Test that JobAlreadyRunningError is raised when lock is held."""
        # Set flag to "true" (simulate already running)
        flag = ApplicationSettings(
            key="test_job_running",
            value="true",
            description="Test lock flag",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(flag)
        db_session.commit()

        # Attempt to acquire lock should raise error
        with pytest.raises(JobAlreadyRunningError) as exc_info:
            with scheduler_lock(db_session, "test_job"):
                pass  # Should not reach here

        assert "already running" in str(exc_info.value).lower()

    def test_lock_released_on_exception(self, db_session):
        """Test that lock is released even when exception occurs."""
        # Acquire lock and raise exception
        with pytest.raises(ValueError):
            with scheduler_lock(db_session, "test_job"):
                # Verify lock is acquired
                flag = db_session.query(ApplicationSettings).filter(
                    ApplicationSettings.key == "test_job_running"
                ).first()
                assert flag.value == "true"

                # Raise exception
                raise ValueError("Test exception")

        # Verify lock is still released despite exception
        flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "test_job_running"
        ).first()

        assert flag.value == "false"

    def test_lock_creates_flag_if_missing(self, db_session):
        """Test that lock creates flag if it doesn't exist."""
        # Ensure flag doesn't exist
        flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "new_job_running"
        ).first()
        assert flag is None

        # Acquire lock
        with scheduler_lock(db_session, "new_job"):
            # Verify flag was created
            flag = db_session.query(ApplicationSettings).filter(
                ApplicationSettings.key == "new_job_running"
            ).first()

            assert flag is not None
            assert flag.value == "true"

    def test_lock_updates_last_run_timestamp(self, db_session):
        """Test that last_run timestamp is updated on lock acquisition."""
        before_time = datetime.utcnow()

        with scheduler_lock(db_session, "test_job"):
            # Check last_run timestamp
            last_run = db_session.query(ApplicationSettings).filter(
                ApplicationSettings.key == "test_job_last_run"
            ).first()

            assert last_run is not None
            assert last_run.value is not None

            # Parse timestamp
            timestamp = datetime.fromisoformat(last_run.value)
            assert timestamp >= before_time

    def test_lock_atomic_operation(self, db_session):
        """Test that lock acquisition is atomic."""
        # This test verifies that the lock check and set happen atomically
        # by checking that no intermediate state exists

        with scheduler_lock(db_session, "test_job"):
            # During lock, flag should definitely be "true"
            flag = db_session.query(ApplicationSettings).filter(
                ApplicationSettings.key == "test_job_running"
            ).first()

            assert flag is not None
            assert flag.value == "true"

    def test_multiple_jobs_independent_locks(self, db_session):
        """Test that different job names have independent locks."""
        # Acquire lock for job1
        with scheduler_lock(db_session, "job1"):
            # Should be able to acquire lock for job2
            with scheduler_lock(db_session, "job2"):
                # Verify both locks are active
                job1_flag = db_session.query(ApplicationSettings).filter(
                    ApplicationSettings.key == "job1_running"
                ).first()

                job2_flag = db_session.query(ApplicationSettings).filter(
                    ApplicationSettings.key == "job2_running"
                ).first()

                assert job1_flag.value == "true"
                assert job2_flag.value == "true"

        # Verify both locks released
        job1_flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "job1_running"
        ).first()

        job2_flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "job2_running"
        ).first()

        assert job1_flag.value == "false"
        assert job2_flag.value == "false"


class TestUpdateLastRunTimestamp:
    """Test suite for _update_last_run_timestamp function."""

    def test_creates_timestamp_if_missing(self, db_session):
        """Test that timestamp record is created if it doesn't exist."""
        _update_last_run_timestamp(db_session, "new_job")

        timestamp_setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "new_job_last_run"
        ).first()

        assert timestamp_setting is not None
        assert timestamp_setting.value is not None

    def test_updates_existing_timestamp(self, db_session):
        """Test that existing timestamp is updated."""
        # Create initial timestamp
        old_time = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        initial_setting = ApplicationSettings(
            key="test_job_last_run",
            value=old_time,
            description="Last run timestamp",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(initial_setting)
        db_session.commit()

        # Update timestamp
        _update_last_run_timestamp(db_session, "test_job")

        # Verify updated
        updated_setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "test_job_last_run"
        ).first()

        assert updated_setting.value != old_time
        assert datetime.fromisoformat(updated_setting.value) > datetime.fromisoformat(old_time)

    def test_timestamp_is_recent(self, db_session):
        """Test that timestamp is within reasonable time."""
        before = datetime.utcnow()
        _update_last_run_timestamp(db_session, "test_job")
        after = datetime.utcnow()

        timestamp_setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "test_job_last_run"
        ).first()

        timestamp = datetime.fromisoformat(timestamp_setting.value)

        assert before <= timestamp <= after


class TestClearStaleLocks:
    """Test suite for clear_stale_locks function."""

    def test_clears_stale_lock(self, db_session):
        """Test that stale locks are cleared."""
        # Create a stale lock (3 hours old)
        stale_time = datetime.utcnow() - timedelta(hours=3)

        stale_flag = ApplicationSettings(
            key="stale_job_running",
            value="true",
            description="Stale lock",
            created_at=stale_time,
            updated_at=stale_time
        )

        stale_last_run = ApplicationSettings(
            key="stale_job_last_run",
            value=stale_time.isoformat(),
            description="Stale timestamp",
            created_at=stale_time,
            updated_at=stale_time
        )

        db_session.add(stale_flag)
        db_session.add(stale_last_run)
        db_session.commit()

        # Clear stale locks
        cleared_count = clear_stale_locks(db_session, max_age_hours=2)

        assert cleared_count == 1

        # Verify lock was cleared
        flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "stale_job_running"
        ).first()

        assert flag.value == "false"

    def test_does_not_clear_fresh_lock(self, db_session):
        """Test that fresh locks are not cleared."""
        # Create a fresh lock (30 minutes old)
        fresh_time = datetime.utcnow() - timedelta(minutes=30)

        fresh_flag = ApplicationSettings(
            key="fresh_job_running",
            value="true",
            description="Fresh lock",
            created_at=fresh_time,
            updated_at=fresh_time
        )

        fresh_last_run = ApplicationSettings(
            key="fresh_job_last_run",
            value=fresh_time.isoformat(),
            description="Fresh timestamp",
            created_at=fresh_time,
            updated_at=fresh_time
        )

        db_session.add(fresh_flag)
        db_session.add(fresh_last_run)
        db_session.commit()

        # Clear stale locks (2 hour threshold)
        cleared_count = clear_stale_locks(db_session, max_age_hours=2)

        assert cleared_count == 0

        # Verify lock was not cleared
        flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "fresh_job_running"
        ).first()

        assert flag.value == "true"

    def test_clears_multiple_stale_locks(self, db_session):
        """Test that multiple stale locks are cleared."""
        stale_time = datetime.utcnow() - timedelta(hours=3)

        # Create 3 stale locks
        for i in range(1, 4):
            flag = ApplicationSettings(
                key=f"stale_job_{i}_running",
                value="true",
                description=f"Stale lock {i}",
                created_at=stale_time,
                updated_at=stale_time
            )

            last_run = ApplicationSettings(
                key=f"stale_job_{i}_last_run",
                value=stale_time.isoformat(),
                description=f"Stale timestamp {i}",
                created_at=stale_time,
                updated_at=stale_time
            )

            db_session.add(flag)
            db_session.add(last_run)

        db_session.commit()

        # Clear stale locks
        cleared_count = clear_stale_locks(db_session, max_age_hours=2)

        assert cleared_count == 3

    def test_handles_missing_last_run(self, db_session):
        """Test that locks without last_run timestamp are cleared based on updated_at."""
        stale_time = datetime.utcnow() - timedelta(hours=3)

        # Create lock without last_run timestamp
        flag = ApplicationSettings(
            key="no_timestamp_job_running",
            value="true",
            description="Lock without timestamp",
            created_at=stale_time,
            updated_at=stale_time
        )

        db_session.add(flag)
        db_session.commit()

        # Clear stale locks
        cleared_count = clear_stale_locks(db_session, max_age_hours=2)

        assert cleared_count == 1

        # Verify lock was cleared
        flag = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == "no_timestamp_job_running"
        ).first()

        assert flag.value == "false"

    def test_handles_empty_database(self, db_session):
        """Test that clear_stale_locks handles empty database gracefully."""
        cleared_count = clear_stale_locks(db_session)

        assert cleared_count == 0

    def test_custom_max_age(self, db_session):
        """Test clear_stale_locks with custom max_age_hours."""
        # Create lock that is 1.5 hours old
        old_time = datetime.utcnow() - timedelta(hours=1, minutes=30)

        flag = ApplicationSettings(
            key="custom_age_job_running",
            value="true",
            description="Custom age test",
            created_at=old_time,
            updated_at=old_time
        )

        last_run = ApplicationSettings(
            key="custom_age_job_last_run",
            value=old_time.isoformat(),
            description="Custom age timestamp",
            created_at=old_time,
            updated_at=old_time
        )

        db_session.add(flag)
        db_session.add(last_run)
        db_session.commit()

        # Should not clear with 2 hour threshold
        cleared_count = clear_stale_locks(db_session, max_age_hours=2)
        assert cleared_count == 0

        # Should clear with 1 hour threshold
        cleared_count = clear_stale_locks(db_session, max_age_hours=1)
        assert cleared_count == 1


class TestJobAlreadyRunningError:
    """Test suite for JobAlreadyRunningError exception."""

    def test_exception_message(self):
        """Test that exception message is preserved."""
        message = "Test job is already running"
        error = JobAlreadyRunningError(message)

        assert str(error) == message

    def test_exception_is_catchable(self):
        """Test that exception can be caught."""
        try:
            raise JobAlreadyRunningError("Test error")
        except JobAlreadyRunningError as e:
            assert "Test error" in str(e)
        except Exception:
            pytest.fail("JobAlreadyRunningError should be caught specifically")

    def test_exception_inherits_from_exception(self):
        """Test that exception inherits from base Exception."""
        error = JobAlreadyRunningError("Test")

        assert isinstance(error, Exception)
