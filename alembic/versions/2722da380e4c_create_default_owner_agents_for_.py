"""create_default_owner_agents_for_collections

Revision ID: 2722da380e4c
Revises: a9466fc7d6f6
Create Date: 2025-05-12 19:55:04.197674

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2722da380e4c'
down_revision: Union[str, None] = 'a9466fc7d6f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()

    # Define minimal table representations using sqlalchemy.sql
    collections_table = sa.table('collections',
                                 sa.column('id', sa.Integer),
                                 sa.column('name', sa.String))
    agents_table = sa.table('agents',
                            sa.column('id', sa.Integer),
                            sa.column('name', sa.String),
                            sa.column('type', sa.String),
                            sa.column('created_at', sa.DateTime),
                            sa.column('collection_id', sa.Integer))

    # Fetch all collections
    collections = conn.execute(sa.select(collections_table.c.id, collections_table.c.name)).fetchall()
    agent_names = set()
    agents_to_insert = []
    for collection_id, collection_name in collections:
        # Define the expected name for the default owner agent
        owner_agent_name = f"{collection_name} Owner"
        if owner_agent_name in agent_names:
            continue
        agent_names.add(owner_agent_name)

        # Check if an agent with the specific name and collection_id already exists
        # We check specifically for the name "{Collection.name} Owner" and the collection_id
        agent_exists_query = sa.select(sa.func.count(agents_table.c.id)).where(
            sa.and_(
                agents_table.c.collection_id == collection_id,
                agents_table.c.name == owner_agent_name
                # Optionally, you could also check type='owner' if that's a strict requirement
                # agents_table.c.type == 'owner'
            )
        )
        agent_count = conn.execute(agent_exists_query).scalar()

        # If no such agent exists, prepare to insert one
        if agent_count == 0:
            agents_to_insert.append(
                {
                    'name': owner_agent_name,
                    'type': 'owner',  # Assuming 'owner' is the correct type string
                    'collection_id': collection_id
                }
            )

    # Bulk insert all the default agents that need to be created
    if agents_to_insert:
        op.bulk_insert(agents_table, agents_to_insert)




def downgrade() -> None:
    """Downgrade schema."""
    pass
