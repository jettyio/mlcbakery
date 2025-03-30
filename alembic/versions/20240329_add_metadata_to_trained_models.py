"""Add metadata fields to trained_models table

Revision ID: c105d32913f0
Revises: b105c32913f0
Create Date: 2024-03-29 20:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c105d32913f0"
down_revision = "b105c32913f0"
branch_labels = None
depends_on = None


def upgrade():
    # Add metadata fields to trained_models table
    op.add_column(
        "trained_models", sa.Column("metadata_version", sa.String(), nullable=True)
    )
    op.add_column(
        "trained_models", sa.Column("model_metadata", sa.JSON(), nullable=True)
    )


def downgrade():
    # Drop metadata fields from trained_models table
    op.drop_column("trained_models", "model_metadata")
    op.drop_column("trained_models", "metadata_version")
