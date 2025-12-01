"""merge deleted_at and backfill branches

This is a merge migration that combines two divergent branches:
- Branch 1: deleted_at field for history tracking (g1h2i3j4k5l6)
- Branch 2: Upload date backfill migration (a1b2c3d4e5f6)

Both branches diverged from f9g8h7i6j5k4 (merge NFO and scheduler).
This merge brings them back together into a single migration head.

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6, a1b2c3d4e5f6
Create Date: 2025-12-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h2i3j4k5l6m7'
down_revision: Union[str, Sequence[str], None] = ('g1h2i3j4k5l6', 'a1b2c3d4e5f6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Merge migration - no schema changes needed.

    Both branches made independent changes to different parts of the schema:
    - deleted_at branch: Added deleted_at timestamp to downloads table
    - Backfill branch: Backfilled upload_date values from .info.json files

    No conflicts exist, so this merge migration is empty.
    """
    pass


def downgrade() -> None:
    """
    Downgrade splits back into two heads.

    This is the reverse of a merge - it recreates the branch point.
    """
    pass
