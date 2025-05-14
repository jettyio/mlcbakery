import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mlcbakery.models import Dataset, Collection, Activity, EntityRelationship
from mlcbakery.api.endpoints.datasets import build_upstream_tree_async


@pytest.mark.asyncio
async def test_build_upstream_tree_single_parent(db_session: AsyncSession):
    """Test building an upstream tree with a single parent."""
    # Setup mock data using real model instances
    collection = Collection(id=1, name="Test Collection")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)

    parent_ds = Dataset(id=1, name="Parent Dataset", entity_type="dataset", collection_id=collection.id, data_path="/parent", format="csv")
    child_ds = Dataset(id=2, name="Child Dataset", entity_type="dataset", collection_id=collection.id, data_path="/child", format="csv")
    db_session.add(parent_ds)
    db_session.add(child_ds)
    await db_session.commit()
    await db_session.refresh(parent_ds)
    await db_session.refresh(child_ds)

    # Use a real Activity instance
    activity = Activity(name="generated")
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)


    # Create the relationship
    relationship = EntityRelationship(id=1, source_entity_id=parent_ds.id, target_entity_id=child_ds.id, activity_name=activity.name)

    # Add to session and commit
    db_session.add(relationship)
    await db_session.commit()
    await db_session.refresh(relationship)
    await db_session.refresh(parent_ds)
    await db_session.refresh(child_ds)

    # Test the function
    result = await build_upstream_tree_async(child_ds, None, db_session, set())
    assert result is not None
    assert len(result.upstream_entities) == 1
    assert result.upstream_entities[0].id == parent_ds.id
    