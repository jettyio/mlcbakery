"""add collections table and update datasets relationship

Revision ID: ee61cdd5b42a
Revises: da6221ce34cb
Create Date: 2025-03-25 14:49:54.298812

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ee61cdd5b42a"
down_revision: Union[str, None] = "da6221ce34cb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create collections table
    op.create_table(
        "collections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Drop the old foreign key from datasets to entities
    op.drop_constraint("datasets_collection_id_fkey", "datasets", type_="foreignkey")

    # Add new foreign key to collections
    op.create_foreign_key(
        "datasets_collection_id_fkey",
        "datasets",
        "collections",
        ["collection_id"],
        ["id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the foreign key to collections
    op.drop_constraint("datasets_collection_id_fkey", "datasets", type_="foreignkey")

    # Restore the foreign key to entities
    op.create_foreign_key(
        "datasets_collection_id_fkey", "datasets", "entities", ["collection_id"], ["id"]
    )

    # Drop collections table
    op.drop_table("collections")
