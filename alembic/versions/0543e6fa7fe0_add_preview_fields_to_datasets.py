"""add preview fields to datasets

Revision ID: 0543e6fa7fe0
Revises: ee61cdd5b42a
Create Date: 2024-03-19 12:34:56.789012

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0543e6fa7fe0"
down_revision: Union[str, None] = "ee61cdd5b42a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add preview and preview_type columns to datasets table
    op.add_column("datasets", sa.Column("preview", sa.LargeBinary(), nullable=True))
    op.add_column("datasets", sa.Column("long_description", sa.Text(), nullable=True))
    op.add_column("datasets", sa.Column("preview_type", sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove preview and preview_type columns from datasets table
    op.drop_column("datasets", "preview_type")
    op.drop_column("datasets", "preview")
    op.drop_column("datasets", "long_description")
