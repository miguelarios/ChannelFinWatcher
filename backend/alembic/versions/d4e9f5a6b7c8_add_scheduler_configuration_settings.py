"""Add scheduler configuration settings for Story 007: Cron-Scheduled Downloads

This migration adds the 5 required scheduler configuration keys to ApplicationSettings
that provide the data foundation for all scheduler functionality.

Settings Added:
- cron_schedule: Cron expression for automatic downloads (default: "0 0 * * *" - daily at midnight)
- scheduler_enabled: Enable/disable automatic scheduled downloads (default: "true")
- scheduler_running: Flag to prevent overlapping scheduled runs (default: "false")
- scheduler_last_run: ISO timestamp of last successful scheduled download (default: NULL)
- scheduler_next_run: ISO timestamp of next scheduled download (default: NULL)

These settings support the APScheduler implementation without requiring schema changes.
The scheduler uses these flags for coordination and status tracking.

Revision ID: d4e9f5a6b7c8
Revises: 3c738deed2af
Create Date: 2025-10-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'd4e9f5a6b7c8'
down_revision: Union[str, None] = '3c738deed2af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scheduler configuration settings for Story 007."""

    # Get connection to execute raw SQL
    connection = op.get_bind()

    # Define the 5 scheduler configuration keys
    scheduler_settings = [
        {
            'key': 'cron_schedule',
            'value': '0 0 * * *',
            'description': 'Cron expression for automatic downloads (default: daily at midnight UTC). Format: minute hour day month dow'
        },
        {
            'key': 'scheduler_enabled',
            'value': 'true',
            'description': 'Enable/disable automatic scheduled downloads. Set to "false" to pause scheduler without changing schedule.'
        },
        {
            'key': 'scheduler_running',
            'value': 'false',
            'description': 'Internal flag to prevent overlapping scheduled runs. Automatically managed by scheduler service.'
        },
        {
            'key': 'scheduler_last_run',
            'value': None,
            'description': 'ISO 8601 timestamp of last successful scheduled download completion. Used for monitoring and dashboard display.'
        },
        {
            'key': 'scheduler_next_run',
            'value': None,
            'description': 'ISO 8601 timestamp of next scheduled download. Calculated from cron expression for user visibility.'
        }
    ]

    # Insert each setting with proper timestamps
    # Using INSERT OR IGNORE to prevent duplicate key errors on re-run
    for setting in scheduler_settings:
        if setting['value'] is None:
            # Handle NULL values for timestamps
            connection.execute(
                text("""
                    INSERT OR IGNORE INTO application_settings (key, value, description, created_at, updated_at)
                    VALUES (:key, NULL, :description, datetime('now'), datetime('now'))
                """),
                {'key': setting['key'], 'description': setting['description']}
            )
        else:
            connection.execute(
                text("""
                    INSERT OR IGNORE INTO application_settings (key, value, description, created_at, updated_at)
                    VALUES (:key, :value, :description, datetime('now'), datetime('now'))
                """),
                setting
            )


def downgrade() -> None:
    """Remove scheduler configuration settings."""

    # Get connection to execute raw SQL
    connection = op.get_bind()

    # Remove the scheduler settings we added
    scheduler_keys = [
        'cron_schedule',
        'scheduler_enabled',
        'scheduler_running',
        'scheduler_last_run',
        'scheduler_next_run'
    ]

    for key in scheduler_keys:
        connection.execute(
            text("DELETE FROM application_settings WHERE key = :key"),
            {'key': key}
        )
