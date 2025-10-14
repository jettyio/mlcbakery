"""add_is_private_to_version_tables

Revision ID: c30f195dcd11
Revises: 94708fa90b99
Create Date: 2025-10-14 14:57:16.356388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c30f195dcd11'
down_revision: Union[str, None] = '94708fa90b99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Add is_private column to all version tables to fix SQLAlchemy-Continuum versioning bug.

    Background: PR#41 added is_private to the Entity model and entities table, but forgot
    to add it to the version tables (entities_version, datasets_version, trained_models_version,
    tasks_version). This caused errors when updating entities because Continuum tries to INSERT
    the is_private value into the version tables.

    Error without this migration:
        column "is_private" of relation "entities_version" does not exist
    """
    # Add is_private to entities_version table
    op.add_column('entities_version',
                  sa.Column('is_private', sa.Boolean(), nullable=True))

    # Add is_private to datasets_version table
    op.add_column('datasets_version',
                  sa.Column('is_private', sa.Boolean(), nullable=True))

    # Add is_private to trained_models_version table
    op.add_column('trained_models_version',
                  sa.Column('is_private', sa.Boolean(), nullable=True))

    # Add is_private to tasks_version table
    op.add_column('tasks_version',
                  sa.Column('is_private', sa.Boolean(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop is_private from all version tables
    op.drop_column('tasks_version', 'is_private')
    op.drop_column('trained_models_version', 'is_private')
    op.drop_column('datasets_version', 'is_private')
    op.drop_column('entities_version', 'is_private')
