"""add is_private field to entities

Revision ID: c4f5e6d7a8b9
Revises: 94708fa90b99
Create Date: 2025-10-09 21:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f5e6d7a8b9'
down_revision: Union[str, None] = '94708fa90b99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_private column to entities table."""
    # Add column as nullable initially for safe migration
    op.add_column('entities', sa.Column('is_private', sa.Boolean(), nullable=True))

    # Set default value True (private) for all existing rows
    op.execute('UPDATE entities SET is_private = TRUE WHERE is_private IS NULL')

    # Alter column to have server default for new rows
    op.alter_column('entities', 'is_private',
                    existing_type=sa.Boolean(),
                    server_default='true',
                    nullable=True)


def downgrade() -> None:
    """Remove is_private column from entities table."""
    op.drop_column('entities', 'is_private')
