"""add environment variables to collections

Revision ID: b58ad412267d
Revises: ad22ca157966
Create Date: 2025-07-19 23:52:44.989248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'b58ad412267d'
down_revision: Union[str, None] = 'ad22ca157966'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add environment_variables field to collections table
    op.add_column("collections", sa.Column("environment_variables", JSONB, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove environment_variables column from collections table
    op.drop_column("collections", "environment_variables")
