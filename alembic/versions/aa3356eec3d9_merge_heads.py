"""merge_heads

Revision ID: aa3356eec3d9
Revises: 0543e6fa7fe0, 23a3b6e6f8ce
Create Date: 2025-03-29 15:38:23.617572

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "aa3356eec3d9"
down_revision: Union[str, None] = ("0543e6fa7fe0", "23a3b6e6f8ce")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
