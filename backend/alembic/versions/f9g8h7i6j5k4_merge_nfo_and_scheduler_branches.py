"""merge NFO and scheduler branches

This is a merge migration that combines two divergent branches:
- Branch 1: NFO file generation tracking (e8f7g6h5i4j3)
- Branch 2: File tracking and scheduler configuration (d4e9f5a6b7c8)

Both branches diverged from c3d8f2e5a9b4 (metadata management).
This merge brings them back together into a single migration head.

Revision ID: f9g8h7i6j5k4
Revises: d4e9f5a6b7c8, e8f7g6h5i4j3
Create Date: 2025-11-09 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9g8h7i6j5k4'
down_revision: Union[str, Sequence[str], None] = ('d4e9f5a6b7c8', 'e8f7g6h5i4j3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Merge migration - no schema changes needed.

    Both branches made independent changes to different parts of the schema:
    - NFO branch: Added nfo_last_generated to channels table
    - Scheduler branch: Added scheduler settings and file tracking

    No conflicts exist, so this merge migration is empty.
    """
    pass


def downgrade() -> None:
    """
    Downgrade splits back into two heads.

    This is the reverse of a merge - it recreates the branch point.
    """
    pass
