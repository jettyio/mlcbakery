"""add tasks table

Revision ID: e99aa040f905
Revises: 5f64b76e30ce
Create Date: 2025-06-10 16:58:16.774983

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e99aa040f905'
down_revision: Union[str, None] = '5f64b76e30ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tasks",
        sa.Column("id",       sa.Integer, sa.ForeignKey("entities.id"), primary_key=True),
        sa.Column("workflow", sa.JSON,    nullable=False),
        sa.Column("version",  sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("tasks")
