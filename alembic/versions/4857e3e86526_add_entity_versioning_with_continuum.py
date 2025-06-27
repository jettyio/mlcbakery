"""add_entity_versioning_with_continuum

Revision ID: 4857e3e86526
Revises: 9b9965a010e9
Create Date: 2025-06-12 23:09:48.203044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4857e3e86526'
down_revision: Union[str, None] = '9b9965a010e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add current_version_hash column to entities table
    op.add_column('entities', sa.Column('current_version_hash', sa.String(64), nullable=True))
    op.create_index('ix_entities_current_version_hash', 'entities', ['current_version_hash'])
        
    # Create SQLAlchemy-Continuum transaction table
    op.create_table('transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('issued_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['agents.id'], name='transaction_user_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='transaction_pkey')
    )
    
    # Create SQLAlchemy-Continuum version tables
    op.create_table('entities_version',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('asset_origin', sa.String(), nullable=True),
        sa.Column('collection_id', sa.Integer(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('end_transaction_id', sa.Integer(), nullable=True),
        sa.Column('operation_type', sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], name='entities_version_collection_id_fkey'),
        sa.ForeignKeyConstraint(['end_transaction_id'], ['transaction.id'], name='entities_version_end_transaction_id_fkey'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], name='entities_version_transaction_id_fkey'),
        sa.PrimaryKeyConstraint('id', 'transaction_id', name='entities_version_pkey')
    )
    
    op.create_table('datasets_version',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('data_path', sa.String(), nullable=False),
        sa.Column('format', sa.String(), nullable=False),
        sa.Column('metadata_version', sa.String(), nullable=True),
        sa.Column('dataset_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('preview', sa.LargeBinary(), nullable=True),
        sa.Column('preview_type', sa.String(), nullable=True),
        sa.Column('long_description', sa.Text(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('end_transaction_id', sa.Integer(), nullable=True),
        sa.Column('operation_type', sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(['end_transaction_id'], ['transaction.id'], name='datasets_version_end_transaction_id_fkey'),
        sa.ForeignKeyConstraint(['id'], ['entities.id'], name='datasets_version_id_fkey'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], name='datasets_version_transaction_id_fkey'),
        sa.PrimaryKeyConstraint('id', 'transaction_id', name='datasets_version_pkey')
    )
    
    op.create_table('trained_models_version',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('model_path', sa.String(), nullable=False),
        sa.Column('metadata_version', sa.String(), nullable=True),
        sa.Column('model_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('long_description', sa.Text(), nullable=True),
        sa.Column('model_attributes', postgresql.JSONB(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('end_transaction_id', sa.Integer(), nullable=True),
        sa.Column('operation_type', sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(['end_transaction_id'], ['transaction.id'], name='trained_models_version_end_transaction_id_fkey'),
        sa.ForeignKeyConstraint(['id'], ['entities.id'], name='trained_models_version_id_fkey'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], name='trained_models_version_transaction_id_fkey'),
        sa.PrimaryKeyConstraint('id', 'transaction_id', name='trained_models_version_pkey')
    )
    
    op.create_table('tasks_version',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('workflow', postgresql.JSONB(), nullable=False),
        sa.Column('version', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('end_transaction_id', sa.Integer(), nullable=True),
        sa.Column('operation_type', sa.SmallInteger(), nullable=False),
        sa.ForeignKeyConstraint(['end_transaction_id'], ['transaction.id'], name='tasks_version_end_transaction_id_fkey'),
        sa.ForeignKeyConstraint(['id'], ['entities.id'], name='tasks_version_id_fkey'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transaction.id'], name='tasks_version_transaction_id_fkey'),
        sa.PrimaryKeyConstraint('id', 'transaction_id', name='tasks_version_pkey')
    )
    
    # Create our custom git-style versioning tables
    op.create_table('entity_version_hashes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], name='entity_version_hashes_entity_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='entity_version_hashes_pkey')
    )
    op.create_index('ix_entity_version_hashes_content_hash', 'entity_version_hashes', ['content_hash'], unique=True)
    
    op.create_table('entity_version_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('version_hash_id', sa.Integer(), nullable=True),
        sa.Column('tag_name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['version_hash_id'], ['entity_version_hashes.id'], name='entity_version_tags_version_hash_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='entity_version_tags_pkey'),
        sa.UniqueConstraint('version_hash_id', 'tag_name', name='uq_version_tag')
    )
    op.create_index('ix_entity_version_tags_tag_name', 'entity_version_tags', ['tag_name'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop custom versioning tables
    op.drop_table('entity_version_tags')
    op.drop_table('entity_version_hashes')
    
    # Drop SQLAlchemy-Continuum version tables
    op.drop_table('tasks_version')
    op.drop_table('trained_models_version')
    op.drop_table('datasets_version')
    op.drop_table('entities_version')
    op.drop_table('transaction')
    
    
    # Remove current_version_hash column
    op.drop_index('ix_entities_current_version_hash')
    op.drop_column('entities', 'current_version_hash')
