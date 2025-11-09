"""add nfo tracking to channels

Revision ID: e8f7g6h5i4j3
Revises: c3d8f2e5a9b4
Create Date: 2025-11-08 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8f7g6h5i4j3'
down_revision = 'c3d8f2e5a9b4'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add NFO file generation tracking to channels table.

    Teaching Moment - Why NULL default?
    ========================
    Setting nfo_last_generated = NULL for existing channels is intentional:
    - NULL indicates "NFO files never generated for this channel"
    - This enables automatic backfill detection in the UI
    - Query: WHERE nfo_last_generated IS NULL → channels needing backfill
    - After backfill completes, we set it to current timestamp

    Why index this field?
    =====================
    - Backfill queries need fast lookup: WHERE nfo_last_generated IS NULL
    - Without index, this becomes a full table scan (slow for many channels)
    - B-tree index makes NULL checks O(log n) instead of O(n)
    - Small storage cost (<1% overhead) for significant query performance gain

    Migration Safety:
    =================
    - nullable=True allows graceful migration (no default value required)
    - Existing channels get NULL (meaning "not generated yet")
    - New channels after migration also get NULL initially
    - NFO generation service sets timestamp when it runs
    """
    # Add NFO generation tracking field
    op.add_column(
        'channels',
        sa.Column('nfo_last_generated', sa.DateTime(), nullable=True)
    )

    # Add index for efficient backfill queries
    # Why this index? Queries like "WHERE nfo_last_generated IS NULL" are common
    op.create_index(
        'idx_channel_nfo_last_generated',
        'channels',
        ['nfo_last_generated']
    )


def downgrade():
    """
    Remove NFO tracking from channels table.

    Warning: This drops all NFO generation history!
    If you downgrade and then upgrade again, all channels will show as
    needing backfill (since nfo_last_generated resets to NULL).
    """
    # Drop index first (can't drop column with active indexes)
    op.drop_index('idx_channel_nfo_last_generated', table_name='channels')

    # Drop column
    op.drop_column('channels', 'nfo_last_generated')
