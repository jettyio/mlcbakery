"""empty message

Revision ID: a8d17ae79ee1
Revises: 20240508_add_cloud_storage_info, e211cb8179a3
Create Date: 2025-05-12 19:47:43.835666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8d17ae79ee1'
down_revision: Union[str, None] = ('20240508_add_cloud_storage_info', 'e211cb8179a3')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
