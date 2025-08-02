"""Add default application settings for User Story 3: Set Global Default Video Limit

This migration initializes the application_settings table with default values
required for User Story 3. It ensures that the system has sensible defaults
on first run while allowing users to customize them later.

Settings Added:
- default_video_limit: Controls how many recent videos to keep per channel (default: 10)
- default_quality_preset: Default video quality for new channels (default: "best")  
- default_schedule: Default cron schedule for new channels (default: "0 2 * * *")

These settings provide a foundation for user customization while ensuring
the system works out-of-the-box with reasonable defaults.

Revision ID: b8e7f3d9c1a2
Revises: a5dc5e4ba46b
Create Date: 2025-08-02 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'b8e7f3d9c1a2'
down_revision: Union[str, None] = 'a5dc5e4ba46b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add default application settings for User Story 3: Set Global Default Video Limit."""
    
    # Get connection to execute raw SQL
    connection = op.get_bind()
    
    # Insert default settings
    # This supports User Story 3 by providing initial default video limit configuration
    default_settings = [
        {
            'key': 'default_video_limit',
            'value': '10',
            'description': 'Default number of videos to keep per channel (1-100). Applied to new channels automatically.'
        },
        {
            'key': 'default_quality_preset', 
            'value': 'best',
            'description': 'Default video quality preset for new channels (best, 1080p, 720p, 480p).'
        },
        {
            'key': 'default_schedule',
            'value': '0 */6 * * *',
            'description': 'Default cron schedule for channel monitoring (every 6 hours).'
        }
    ]
    
    # Insert each setting with proper timestamps
    for setting in default_settings:
        connection.execute(
            text("""
                INSERT INTO application_settings (key, value, description, created_at, updated_at)
                VALUES (:key, :value, :description, datetime('now'), datetime('now'))
            """),
            setting
        )


def downgrade() -> None:
    """Remove default application settings."""
    
    # Get connection to execute raw SQL
    connection = op.get_bind()
    
    # Remove the default settings we added
    setting_keys = ['default_video_limit', 'default_quality_preset', 'default_schedule']
    
    for key in setting_keys:
        connection.execute(
            text("DELETE FROM application_settings WHERE key = :key"),
            {'key': key}
        )