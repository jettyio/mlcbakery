"""add has_file_uploads field to tasks

Revision ID: 8d98d7b90f62
Revises: b58ad412267d
Create Date: 2025-07-29 22:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d98d7b90f62'
down_revision: Union[str, None] = 'b58ad412267d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add has_file_uploads column to tasks table."""
    op.add_column('tasks', sa.Column('has_file_uploads', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove has_file_uploads column from tasks table."""
    op.drop_column('tasks', 'has_file_uploads') 