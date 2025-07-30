"""add has_file_uploads to tasks_version table

Revision ID: 94708fa90b99
Revises: 8d98d7b90f62
Create Date: 2025-07-30 12:45:38.944637

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94708fa90b99'
down_revision: Union[str, None] = '8d98d7b90f62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add has_file_uploads column to tasks_version table."""
    op.add_column('tasks_version', sa.Column('has_file_uploads', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove has_file_uploads column from tasks_version table."""
    op.drop_column('tasks_version', 'has_file_uploads')
