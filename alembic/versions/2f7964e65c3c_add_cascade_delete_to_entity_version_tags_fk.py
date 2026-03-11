"""add cascade delete to entity_version_tags FK

Revision ID: 2f7964e65c3c
Revises: c4f5e6d7a8b9, f1a2b3c4d5e6
Create Date: 2026-03-11

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2f7964e65c3c'
down_revision: Union[str, Sequence[str]] = ('c4f5e6d7a8b9', 'f1a2b3c4d5e6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('entity_version_tags_version_hash_id_fkey', 'entity_version_tags', type_='foreignkey')
    op.create_foreign_key(
        'entity_version_tags_version_hash_id_fkey',
        'entity_version_tags',
        'entity_version_hashes',
        ['version_hash_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('entity_version_tags_version_hash_id_fkey', 'entity_version_tags', type_='foreignkey')
    op.create_foreign_key(
        'entity_version_tags_version_hash_id_fkey',
        'entity_version_tags',
        'entity_version_hashes',
        ['version_hash_id'],
        ['id'],
    )
