"""migrate json to jsonb

Revision ID: 9b9965a010e9
Revises: e99aa040f905
Create Date: 2025-06-12 21:16:39.229432

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = '9b9965a010e9'
down_revision: Union[str, None] = 'e99aa040f905'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('datasets', 'dataset_metadata',
               existing_type=sa.JSON(),
               type_=JSONB,
               postgresql_using='dataset_metadata::jsonb')
    op.alter_column('trained_models', 'model_metadata',
               existing_type=sa.JSON(),
               type_=JSONB,
               postgresql_using='model_metadata::jsonb')
    op.alter_column('trained_models', 'model_attributes',
               existing_type=sa.JSON(),
               type_=JSONB,
               postgresql_using='model_attributes::jsonb')
    op.alter_column('tasks', 'workflow',
               existing_type=sa.JSON(),
               type_=JSONB,
               postgresql_using='workflow::jsonb')
    op.alter_column('collections', 'storage_info',
               existing_type=sa.JSON(),
               type_=JSONB,
               postgresql_using='storage_info::jsonb')


def downgrade() -> None:
    """Downgrade schema."""
   
    op.alter_column('datasets', 'dataset_metadata',
               existing_type=JSONB,
               type_=sa.JSON(),
               postgresql_using='dataset_metadata::json')
    op.alter_column('trained_models', 'model_metadata',
               existing_type=JSONB,
               type_=sa.JSON(),
               postgresql_using='model_metadata::json')
    op.alter_column('trained_models', 'model_attributes',
               existing_type=JSONB,
               type_=sa.JSON(),
               postgresql_using='model_attributes::json')
    op.alter_column('tasks', 'workflow',
               existing_type=JSONB,
               type_=sa.JSON(),
               postgresql_using='workflow::json')
    op.alter_column('collections', 'storage_info',
               existing_type=JSONB,
               type_=sa.JSON(),
               postgresql_using='storage_info::json')
    # ### end Alembic commands ###
