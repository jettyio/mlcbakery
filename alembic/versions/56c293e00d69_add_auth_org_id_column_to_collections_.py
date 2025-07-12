"""add auth_org_id column to collections table

Revision ID: 56c293e00d69
Revises: e44c37f17887
Create Date: 2025-07-11 23:22:00.569267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56c293e00d69'
down_revision: Union[str, None] = 'e44c37f17887'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the auth_org_id column as a nullable varchar
    op.add_column("collections", sa.Column("auth_org_id", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the auth_org_id column from collections table
    op.drop_column("collections", "auth_org_id")
