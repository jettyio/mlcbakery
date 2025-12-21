"""add croissant_metadata to entities

Revision ID: f1a2b3c4d5e6
Revises: c30f195dcd11
Create Date: 2024-12-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c30f195dcd11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add croissant_metadata JSONB column to entities table
    op.add_column('entities', sa.Column('croissant_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    
    # Also add to the versioned entities table if it exists
    op.add_column('entities_version', sa.Column('croissant_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Remove croissant_metadata column from entities_version table
    op.drop_column('entities_version', 'croissant_metadata')
    
    # Remove croissant_metadata column from entities table
    op.drop_column('entities', 'croissant_metadata')

