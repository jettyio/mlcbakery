"""add_created_at_to_agents

Revision ID: dbf19ccb0d34
Revises: c105d32913f0
Create Date: 2025-03-30 00:11:19.667473

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = "dbf19ccb0d34"
down_revision: Union[str, None] = "c105d32913f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add created_at column to agents table
    op.add_column(
        "agents",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove created_at column from agents table
    op.drop_column("agents", "created_at")
