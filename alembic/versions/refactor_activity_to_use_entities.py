"""refactor activity to use entities

Revision ID: a1b2c3d4
Revises: 23a3b6e6f8ce
Create Date: 2025-03-26 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4"
down_revision: Union[str, None] = "23a3b6e6f8ce"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create activity_entities table for input entities
    op.create_table(
        "activity_entities",
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
        ),
        sa.PrimaryKeyConstraint("activity_id", "entity_id"),
    )

    # Add output_entity_id to activities table
    op.add_column(
        "activities",
        sa.Column("output_entity_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "activities_output_entity_id_fkey",
        "activities",
        "entities",
        ["output_entity_id"],
        ["id"],
    )

    # Migrate existing data
    # First, migrate input datasets to activity_entities
    op.execute(
        """
        INSERT INTO activity_entities (activity_id, entity_id)
        SELECT activity_id, dataset_id
        FROM activity_datasets
        """
    )

    # Then, migrate output models to output_entity_id
    op.execute(
        """
        UPDATE activities
        SET output_entity_id = output_model_id
        WHERE output_model_id IS NOT NULL
        """
    )

    # Drop old tables and columns
    op.drop_constraint(
        "activities_output_model_id_fkey", "activities", type_="foreignkey"
    )
    op.drop_column("activities", "output_model_id")
    op.drop_table("activity_datasets")


def downgrade() -> None:
    """Downgrade schema."""
    # Recreate activity_datasets table
    op.create_table(
        "activity_datasets",
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["datasets.id"],
        ),
        sa.PrimaryKeyConstraint("activity_id", "dataset_id"),
    )

    # Migrate data back
    op.execute(
        """
        INSERT INTO activity_datasets (activity_id, dataset_id)
        SELECT activity_id, entity_id
        FROM activity_entities
        WHERE entity_id IN (SELECT id FROM datasets)
        """
    )

    # Add back output_model_id
    op.add_column(
        "activities",
        sa.Column("output_model_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "activities_output_model_id_fkey",
        "activities",
        "trained_models",
        ["output_model_id"],
        ["id"],
    )

    # Migrate output_entity_id back to output_model_id
    op.execute(
        """
        UPDATE activities
        SET output_model_id = output_entity_id
        WHERE output_entity_id IN (SELECT id FROM trained_models)
        """
    )

    # Drop new tables and columns
    op.drop_constraint(
        "activities_output_entity_id_fkey", "activities", type_="foreignkey"
    )
    op.drop_column("activities", "output_entity_id")
    op.drop_table("activity_entities")
