"""merge again

Revision ID: ef9943217125
Revises: a8d17ae79ee1, a1b2c3d4
Create Date: 2025-05-12 19:49:10.027976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ef9943217125'
down_revision: Union[str, None] = ('a8d17ae79ee1', 'a1b2c3d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
