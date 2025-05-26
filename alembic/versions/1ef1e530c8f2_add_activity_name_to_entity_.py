"""add_activity_name_to_entity_relationships

Revision ID: 1ef1e530c8f2
Revises: 1083fbe84b7c
Create Date: 2025-05-24 22:54:08.566743

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ef1e530c8f2'
down_revision: Union[str, None] = '1083fbe84b7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('entity_relationships', sa.Column('activity_name', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('entity_relationships', 'activity_name')
