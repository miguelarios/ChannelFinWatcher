"""add file_exists column to downloads

Revision ID: 3c738deed2af
Revises: 61c8248141c7
Create Date: 2025-08-30 16:51:36.653958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3c738deed2af'
down_revision: Union[str, None] = '61c8248141c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add file_exists column
    op.add_column('downloads', 
        sa.Column('file_exists', sa.Boolean(), nullable=False, server_default='true')
    )
    
    # Add performance indexes
    op.create_index('idx_download_file_exists', 'downloads', ['file_exists'])


def downgrade() -> None:
    op.drop_index('idx_download_file_exists', 'downloads')
    op.drop_column('downloads', 'file_exists')