"""add metadata management fields to channels

Revision ID: c3d8f2e5a9b4
Revises: b8e7f3d9c1a2
Create Date: 2025-08-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d8f2e5a9b4'
down_revision = 'b8e7f3d9c1a2'
branch_labels = None
depends_on = None


def upgrade():
    """Add metadata management fields to channels table."""
    # Add new columns for metadata management
    op.add_column('channels', sa.Column('metadata_path', sa.String(), nullable=True))
    op.add_column('channels', sa.Column('directory_path', sa.String(), nullable=True))
    op.add_column('channels', sa.Column('last_metadata_update', sa.DateTime(), nullable=True))
    op.add_column('channels', sa.Column('metadata_status', sa.String(), nullable=True))
    op.add_column('channels', sa.Column('cover_image_path', sa.String(), nullable=True))
    op.add_column('channels', sa.Column('backdrop_image_path', sa.String(), nullable=True))
    
    # Set default values for existing records
    op.execute("UPDATE channels SET metadata_status = 'pending' WHERE metadata_status IS NULL")
    
    # Make metadata_status non-nullable with default
    op.alter_column('channels', 'metadata_status', nullable=False, server_default='pending')
    
    # Add indexes for efficient metadata status queries
    op.create_index('idx_channel_metadata_status', 'channels', ['metadata_status'])


def downgrade():
    """Remove metadata management fields from channels table."""
    # Drop indexes
    op.drop_index('idx_channel_metadata_status', table_name='channels')
    
    # Drop columns
    op.drop_column('channels', 'backdrop_image_path')
    op.drop_column('channels', 'cover_image_path')
    op.drop_column('channels', 'metadata_status')
    op.drop_column('channels', 'last_metadata_update')
    op.drop_column('channels', 'directory_path')
    op.drop_column('channels', 'metadata_path')