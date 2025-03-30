"""add polymorphic entities and activity datasets

Revision ID: 23a3b6e6f8ce
Revises: ee61cdd5b42a
Create Date: 2025-03-25 15:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "23a3b6e6f8ce"
down_revision: Union[str, None] = "ee61cdd5b42a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add entity_type column to entities table with default value
    op.add_column("entities", sa.Column("entity_type", sa.String(), nullable=True))
    op.execute("UPDATE entities SET entity_type = 'entity'")
    op.alter_column("entities", "entity_type", nullable=False)

    # Create trained_models table
    op.create_table(
        "trained_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("model_path", sa.String(), nullable=False),
        sa.Column("framework", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["id"],
            ["entities.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create activity_datasets table
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

    # Update datasets table to inherit from entities
    # First add columns as nullable
    op.add_column("datasets", sa.Column("data_path", sa.String(), nullable=True))
    op.add_column("datasets", sa.Column("format", sa.String(), nullable=True))

    # Set default values for existing records
    op.execute(
        "UPDATE datasets SET data_path = '/tmp/data', format = 'unknown' WHERE data_path IS NULL"
    )

    # Make columns non-nullable
    op.alter_column("datasets", "data_path", nullable=False)
    op.alter_column("datasets", "format", nullable=False)

    # Create foreign key from datasets to entities
    op.execute(
        "INSERT INTO entities (id, name, entity_type, created_at) SELECT id, name, 'dataset', NOW() FROM datasets WHERE id NOT IN (SELECT id FROM entities)"
    )
    op.create_foreign_key("datasets_id_fkey", "datasets", "entities", ["id"], ["id"])

    # Update activities table
    op.drop_column("activities", "start_time")
    op.drop_column("activities", "end_time")
    op.add_column(
        "activities",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
    )
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

    # Drop old was_generated_by table as it's replaced by activity_datasets
    op.drop_table("was_generated_by")


def downgrade() -> None:
    """Downgrade schema."""
    # Restore was_generated_by table
    op.create_table(
        "was_generated_by",
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("activity_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
        ),
        sa.PrimaryKeyConstraint("entity_id", "activity_id"),
    )

    # Drop new tables
    op.drop_table("activity_datasets")
    op.drop_table("trained_models")

    # Remove entity_type column
    op.drop_column("entities", "entity_type")

    # Restore activities table
    op.drop_constraint(
        "activities_output_model_id_fkey", "activities", type_="foreignkey"
    )
    op.drop_column("activities", "output_model_id")
    op.drop_column("activities", "created_at")
    op.add_column("activities", sa.Column("start_time", sa.DateTime(), nullable=True))
    op.add_column("activities", sa.Column("end_time", sa.DateTime(), nullable=True))

    # Restore datasets table
    op.drop_constraint("datasets_id_fkey", "datasets", type_="foreignkey")
    op.drop_column("datasets", "data_path")
    op.drop_column("datasets", "format")
