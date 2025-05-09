"""add storage info to collections

Revision ID: 20240508_add_cloud_storage_info
Revises: aa3356eec3d9
Create Date: 2024-05-08 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision: str = "20240508_add_cloud_storage_info"
down_revision: Union[str, None] = "aa3356eec3d9"  # Update this based on the latest migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add storage fields to collections table
    op.add_column("collections", sa.Column("storage_info", JSON, nullable=True))
    op.add_column("collections", sa.Column("storage_provider", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove columns from collections table
    op.drop_column("collections", "storage_provider")
    op.drop_column("collections", "storage_info")