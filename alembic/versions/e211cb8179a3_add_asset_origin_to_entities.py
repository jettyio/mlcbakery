"""add asset_origin to entities

Revision ID: e211cb8179a3
Revises: dbf19ccb0d34
Create Date: 2025-04-27 00:36:45.404804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e211cb8179a3'
down_revision: Union[str, None] = 'dbf19ccb0d34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('entities', sa.Column('asset_origin', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('entities', 'asset_origin')
