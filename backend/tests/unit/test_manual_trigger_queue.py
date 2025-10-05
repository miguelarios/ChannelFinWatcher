"""Unit tests for manual trigger queue (BE-007).

Tests the manual_trigger_queue module which manages queueing
of manual download triggers when the scheduler is running.

TEST-001: Manual trigger queue testing
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from app.manual_trigger_queue import (
    add_to_queue,
    get_queue,
    clear_queue,
    remove_stale_entries,
    process_queue,
    QUEUE_KEY,
    TIMEOUT_MINUTES
)
from app.models import ApplicationSettings, Channel


class TestAddToQueue:
    """Test suite for add_to_queue function."""

    def test_adds_entry_to_empty_queue(self, db_session):
        """Test adding entry to empty queue."""
        position = add_to_queue(db_session, 123)

        assert position == 1

        # Verify queue in database
        queue_setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == QUEUE_KEY
        ).first()

        assert queue_setting is not None
        queue = json.loads(queue_setting.value)
        assert len(queue) == 1
        assert queue[0]["channel_id"] == 123
        assert queue[0]["user"] == "manual"

    def test_adds_entry_to_existing_queue(self, db_session):
        """Test adding entry to existing queue."""
        # Create initial queue
        initial_queue = [{"channel_id": 111, "user": "manual", "timestamp": datetime.utcnow().isoformat()}]
        queue_setting = ApplicationSettings(
            key=QUEUE_KEY,
            value=json.dumps(initial_queue),
            description="Queue",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(queue_setting)
        db_session.commit()

        # Add new entry
        position = add_to_queue(db_session, 222)

        assert position == 2

        # Verify queue
        updated_setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == QUEUE_KEY
        ).first()

        queue = json.loads(updated_setting.value)
        assert len(queue) == 2
        assert queue[1]["channel_id"] == 222


class TestGetQueue:
    """Test suite for get_queue function."""

    def test_returns_empty_list_when_no_queue(self, db_session):
        """Test returns empty list when queue doesn't exist."""
        queue = get_queue(db_session)

        assert queue == []

    def test_returns_queue_entries(self, db_session):
        """Test returns queue entries."""
        entries = [
            {"channel_id": 111, "user": "manual", "timestamp": datetime.utcnow().isoformat()},
            {"channel_id": 222, "user": "manual", "timestamp": datetime.utcnow().isoformat()}
        ]

        queue_setting = ApplicationSettings(
            key=QUEUE_KEY,
            value=json.dumps(entries),
            description="Queue",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(queue_setting)
        db_session.commit()

        queue = get_queue(db_session)

        assert len(queue) == 2
        assert queue[0]["channel_id"] == 111
        assert queue[1]["channel_id"] == 222


class TestClearQueue:
    """Test suite for clear_queue function."""

    def test_clears_existing_queue(self, db_session):
        """Test clears existing queue."""
        # Create queue
        entries = [{"channel_id": 111, "user": "manual", "timestamp": datetime.utcnow().isoformat()}]
        queue_setting = ApplicationSettings(
            key=QUEUE_KEY,
            value=json.dumps(entries),
            description="Queue",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(queue_setting)
        db_session.commit()

        # Clear queue
        clear_queue(db_session)

        # Verify cleared
        updated_setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == QUEUE_KEY
        ).first()

        assert updated_setting.value == "[]"


class TestRemoveStaleEntries:
    """Test suite for remove_stale_entries function."""

    def test_removes_stale_entries(self, db_session):
        """Test removes entries older than timeout."""
        stale_time = (datetime.utcnow() - timedelta(minutes=TIMEOUT_MINUTES + 1)).isoformat()
        fresh_time = datetime.utcnow().isoformat()

        entries = [
            {"channel_id": 111, "user": "manual", "timestamp": stale_time},
            {"channel_id": 222, "user": "manual", "timestamp": fresh_time}
        ]

        queue_setting = ApplicationSettings(
            key=QUEUE_KEY,
            value=json.dumps(entries),
            description="Queue",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(queue_setting)
        db_session.commit()

        removed = remove_stale_entries(db_session)

        assert removed == 1

        # Verify only fresh entry remains
        updated_setting = db_session.query(ApplicationSettings).filter(
            ApplicationSettings.key == QUEUE_KEY
        ).first()

        queue = json.loads(updated_setting.value)
        assert len(queue) == 1
        assert queue[0]["channel_id"] == 222

    def test_keeps_fresh_entries(self, db_session):
        """Test keeps entries within timeout."""
        fresh_time = datetime.utcnow().isoformat()

        entries = [
            {"channel_id": 111, "user": "manual", "timestamp": fresh_time},
            {"channel_id": 222, "user": "manual", "timestamp": fresh_time}
        ]

        queue_setting = ApplicationSettings(
            key=QUEUE_KEY,
            value=json.dumps(entries),
            description="Queue",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(queue_setting)
        db_session.commit()

        removed = remove_stale_entries(db_session)

        assert removed == 0

        # Verify both entries remain
        queue = get_queue(db_session)
        assert len(queue) == 2


class TestProcessQueue:
    """Test suite for process_queue function."""

    @pytest.mark.asyncio
    @patch('app.manual_trigger_queue.video_download_service')
    async def test_processes_queued_entries(self, mock_service, db_session):
        """Test processes all queued entries."""
        # Create channels
        channel1 = Channel(
            url="http://example.com/1",
            channel_id="ch1",
            name="Channel 1",
            enabled=True,
            limit=10
        )
        channel2 = Channel(
            url="http://example.com/2",
            channel_id="ch2",
            name="Channel 2",
            enabled=True,
            limit=10
        )
        db_session.add(channel1)
        db_session.add(channel2)
        db_session.commit()

        # Create queue
        entries = [
            {"channel_id": channel1.id, "user": "manual", "timestamp": datetime.utcnow().isoformat()},
            {"channel_id": channel2.id, "user": "manual", "timestamp": datetime.utcnow().isoformat()}
        ]

        queue_setting = ApplicationSettings(
            key=QUEUE_KEY,
            value=json.dumps(entries),
            description="Queue",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(queue_setting)
        db_session.commit()

        # Mock successful processing
        mock_service.process_channel_downloads.return_value = (True, 5, None)

        successful, failed = await process_queue(db_session)

        assert successful == 2
        assert failed == 0

        # Verify queue was cleared
        queue = get_queue(db_session)
        assert len(queue) == 0

    @pytest.mark.asyncio
    async def test_handles_empty_queue(self, db_session):
        """Test handles empty queue gracefully."""
        successful, failed = await process_queue(db_session)

        assert successful == 0
        assert failed == 0

    @pytest.mark.asyncio
    @patch('app.manual_trigger_queue.video_download_service')
    async def test_continues_on_channel_failure(self, mock_service, db_session):
        """Test continues processing when individual channel fails."""
        # Create channels
        channel1 = Channel(
            url="http://example.com/1",
            channel_id="ch1",
            name="Channel 1",
            enabled=True,
            limit=10
        )
        channel2 = Channel(
            url="http://example.com/2",
            channel_id="ch2",
            name="Channel 2",
            enabled=True,
            limit=10
        )
        db_session.add(channel1)
        db_session.add(channel2)
        db_session.commit()

        # Create queue
        entries = [
            {"channel_id": channel1.id, "user": "manual", "timestamp": datetime.utcnow().isoformat()},
            {"channel_id": channel2.id, "user": "manual", "timestamp": datetime.utcnow().isoformat()}
        ]

        queue_setting = ApplicationSettings(
            key=QUEUE_KEY,
            value=json.dumps(entries),
            description="Queue",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(queue_setting)
        db_session.commit()

        # First fails, second succeeds
        mock_service.process_channel_downloads.side_effect = [
            (False, 0, "Channel error"),
            (True, 3, None)
        ]

        successful, failed = await process_queue(db_session)

        assert successful == 1
        assert failed == 1

    @pytest.mark.asyncio
    @patch('app.manual_trigger_queue.video_download_service')
    async def test_removes_stale_entries_before_processing(self, mock_service, db_session):
        """Test removes stale entries before processing."""
        stale_time = (datetime.utcnow() - timedelta(minutes=TIMEOUT_MINUTES + 1)).isoformat()

        # Create channel
        channel = Channel(
            url="http://example.com/1",
            channel_id="ch1",
            name="Channel 1",
            enabled=True,
            limit=10
        )
        db_session.add(channel)
        db_session.commit()

        # Create queue with stale entry
        entries = [
            {"channel_id": 999, "user": "manual", "timestamp": stale_time},  # Stale, non-existent channel
            {"channel_id": channel.id, "user": "manual", "timestamp": datetime.utcnow().isoformat()}
        ]

        queue_setting = ApplicationSettings(
            key=QUEUE_KEY,
            value=json.dumps(entries),
            description="Queue",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db_session.add(queue_setting)
        db_session.commit()

        mock_service.process_channel_downloads.return_value = (True, 2, None)

        successful, failed = await process_queue(db_session)

        # Only fresh entry should be processed
        assert successful == 1
        assert failed == 0
