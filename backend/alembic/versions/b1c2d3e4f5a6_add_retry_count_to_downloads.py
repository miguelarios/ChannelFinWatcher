"""add retry_count to downloads

Revision ID: b1c2d3e4f5a6
Revises: 2obyvozut5uh
Create Date: 2026-06-10

Adds a retry_count column to the downloads table so automatic re-attempts
of failed downloads can be bounded (videos that keep failing stop being
retried after a cap) and surfaced in the UI.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '2obyvozut5uh'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'downloads',
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    op.drop_column('downloads', 'retry_count')
