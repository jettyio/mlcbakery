"""add collection_id foreign key to agents

Revision ID: a9466fc7d6f6
Revises: ef9943217125
Create Date: 2025-05-12 19:54:03.730684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9466fc7d6f6'
down_revision: Union[str, None] = 'ef9943217125'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('agents', sa.Column('collection_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_agents_collection_id',
        'agents', 'collections',
        ['collection_id'], ['id']
    )

def downgrade():
    op.drop_constraint('fk_agents_collection_id', 'agents', type_='foreignkey')
    op.drop_column('agents', 'collection_id')