"""add deleted_at to downloads for history tracking

This migration adds a `deleted_at` timestamp column to track when videos
are removed from disk while preserving download history records.

Revision ID: g1h2i3j4k5l6
Revises: f9g8h7i6j5k4
Create Date: 2025-12-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1h2i3j4k5l6'
down_revision = 'f9g8h7i6j5k4'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add deleted_at timestamp to downloads table for history tracking.

    Teaching Moment - Why Track Deletions?
    =======================================
    Instead of deleting download records when files are removed, we mark them
    with a deleted_at timestamp. This provides several benefits:

    1. **Audit Trail**: Know exactly when and what was deleted
    2. **Storage Analytics**: Track historical storage usage patterns
    3. **Download History**: See full download history, not just current state
    4. **Debugging**: Understand why certain videos were removed

    Why NULL default?
    =================
    - NULL means "never deleted" (file still exists)
    - Non-NULL means "deleted at this timestamp"
    - Query: WHERE deleted_at IS NOT NULL → all deleted videos
    - Query: WHERE deleted_at IS NULL → active videos only

    Why index this field?
    =====================
    - Queries filter on this frequently: WHERE deleted_at IS NULL
    - Without index, this becomes a full table scan
    - B-tree index provides fast NULL/NOT NULL checks
    - Critical for cleanup queries that need to count active videos

    Design Pattern:
    ===============
    file_exists + deleted_at work together:
    - file_exists=TRUE,  deleted_at=NULL     → Active video on disk
    - file_exists=FALSE, deleted_at=NULL     → Failed download (never existed)
    - file_exists=FALSE, deleted_at=NOT NULL → Deleted video (was on disk, now removed)

    Migration Safety:
    =================
    - nullable=True allows graceful migration (no default required)
    - Existing records get NULL (meaning "not deleted")
    - Cleanup service sets timestamp when it removes files
    """
    # Add deletion timestamp field
    op.add_column(
        'downloads',
        sa.Column('deleted_at', sa.DateTime(), nullable=True)
    )

    # Add index for efficient cleanup and history queries
    # Why? Queries like "WHERE deleted_at IS NULL" are used in every cleanup run
    op.create_index(
        'idx_download_deleted_at',
        'downloads',
        ['deleted_at']
    )


def downgrade():
    """
    Remove deleted_at tracking from downloads table.

    Warning: This drops all deletion history!
    If you downgrade and then upgrade again, all deletion timestamps will be lost.
    """
    # Drop index first (can't drop column with active indexes)
    op.drop_index('idx_download_deleted_at', table_name='downloads')

    # Drop column
    op.drop_column('downloads', 'deleted_at')
