"""Move collection_id to entities table

Revision ID: b105c32913f0
Revises: aa3356eec3d9
Create Date: 2024-03-29 19:50:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = "b105c32913f0"
down_revision = "aa3356eec3d9"
branch_labels = None
depends_on = None


def get_fk_constraint_name(table_name, column_name):
    """Get the actual foreign key constraint name from the database."""
    conn = op.get_bind()
    insp = Inspector.from_engine(conn)
    for fk in insp.get_foreign_keys(table_name):
        if column_name in fk["constrained_columns"]:
            return fk["name"]
    return None


def upgrade():
    # Add collection_id to entities table
    op.add_column("entities", sa.Column("collection_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_entities_collection_id",
        "entities",
        "collections",
        ["collection_id"],
        ["id"],
    )

    # Copy collection_id from datasets to entities
    op.execute("""
        UPDATE entities e
        SET collection_id = d.collection_id
        FROM datasets d
        WHERE e.id = d.id
    """)

    # Drop collection_id from datasets
    fk_name = get_fk_constraint_name("datasets", "collection_id")
    if fk_name:
        op.drop_constraint(fk_name, "datasets", type_="foreignkey")
    op.drop_column("datasets", "collection_id")


def downgrade():
    # Add collection_id back to datasets
    op.add_column("datasets", sa.Column("collection_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_datasets_collection_id",
        "datasets",
        "collections",
        ["collection_id"],
        ["id"],
    )

    # Copy collection_id from entities back to datasets
    op.execute("""
        UPDATE datasets d
        SET collection_id = e.collection_id
        FROM entities e
        WHERE d.id = e.id
    """)

    # Drop collection_id from entities
    op.drop_constraint("fk_entities_collection_id", "entities", type_="foreignkey")
    op.drop_column("entities", "collection_id")
