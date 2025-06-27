"""add_remote_addr_to_transaction_table

Revision ID: 5a6b7765ddca
Revises: 4857e3e86526
Create Date: 2025-06-27 04:14:08.267522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a6b7765ddca'
down_revision: Union[str, None] = '4857e3e86526'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the missing remote_addr column to the transaction table
    # This is needed for SQLAlchemy-Continuum Flask plugin functionality
    op.add_column('transaction', sa.Column('remote_addr', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the remote_addr column
    op.drop_column('transaction', 'remote_addr')
