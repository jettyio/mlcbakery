"""Add owner to collections

Revision ID: e44c37f17887
Revises: 5a6b7765ddca
Create Date: 2025-07-04 08:04:40.882039

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e44c37f17887'
down_revision: Union[str, None] = '5a6b7765ddca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ADMIN_USER_ID = "user_2zZTlvr3v8yXqYUZcyk432lBUGk"

def upgrade() -> None:
    """Upgrade schema."""
    # Add the owner_identifier column
    op.add_column("collections", sa.Column("owner_identifier", sa.String(), nullable=True))
    
    # Pre-populate existing collections with the specified owner identifier
    op.execute(f"UPDATE collections SET owner_identifier = '{_ADMIN_USER_ID}' WHERE owner_identifier IS NULL")

    # now make it not nullable
    op.alter_column("collections", "owner_identifier", nullable=False)

def downgrade() -> None:
    """Downgrade schema."""
    # Drop the owner_identifier column from collections table
    op.drop_column("collections", "owner_identifier")
