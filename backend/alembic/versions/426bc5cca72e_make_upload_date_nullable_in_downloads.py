"""make_upload_date_nullable_in_downloads

Revision ID: 426bc5cca72e
Revises: 35ea57b969d7
Create Date: 2025-08-20 12:56:59.341610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '426bc5cca72e'
down_revision: Union[str, None] = '35ea57b969d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
    
    # Create new table with nullable upload_date
    op.create_table('downloads_new',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('channel_id', sa.Integer(), nullable=False),
        sa.Column('video_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('upload_date', sa.String(), nullable=True),  # Changed to nullable
        sa.Column('duration', sa.String(), nullable=True),
        sa.Column('file_path', sa.String(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['channel_id'], ['channels.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Copy data from old table to new table
    op.execute('''
        INSERT INTO downloads_new (id, channel_id, video_id, title, upload_date, duration, file_path, file_size, status, error_message, created_at, completed_at)
        SELECT id, channel_id, video_id, title, upload_date, duration, file_path, file_size, status, error_message, created_at, completed_at
        FROM downloads
    ''')
    
    # Drop old table and rename new table
    op.drop_table('downloads')
    op.rename_table('downloads_new', 'downloads')
    
    # Recreate indexes
    op.create_index('ix_downloads_channel_id', 'downloads', ['channel_id'])
    op.create_index('ix_downloads_id', 'downloads', ['id'])
    op.create_index('ix_downloads_status', 'downloads', ['status'])
    op.create_index('ix_downloads_video_id', 'downloads', ['video_id'])
    op.create_index('idx_downloads_channel_status', 'downloads', ['channel_id', 'status'])


def downgrade() -> None:
    # Reverse the operation - make upload_date NOT NULL again
    # This would require ensuring all upload_date values are not null first
    pass  # Skipping downgrade for now as it's complex