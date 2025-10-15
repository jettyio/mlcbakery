"""
Test to verify the bug with SQLAlchemy-Continuum version tables and is_private column.

This test verifies Jon's hypothesis: when is_private is added to entities tables,
the _version tables also need this column, otherwise saving entities multiple times fails.

Expected behavior:
- Creating an entity with is_private should work
- Updating the entity should trigger SQLAlchemy-Continuum to create a version record
- The version record creation should fail because the *_version tables don't have is_private column

To reproduce the bug:
1. Add is_private column to Entity model (entities table) via migration
2. Run this test
3. The test should fail with an error about is_private column missing in entities_version table

This test directly manipulates the database to simulate the bug, since the API
doesn't yet have is_private support in the schemas.
"""

import pytest
from sqlalchemy import text, select
from sqlalchemy.exc import ProgrammingError, DBAPIError

from mlcbakery import models


@pytest.mark.asyncio
async def test_version_table_has_is_private_column(db_session):
    """
    Test that verifies the fix: version tables now have is_private column.

    This test verifies that the migration properly added is_private to all version tables.
    After the fix, creating and updating entities with is_private should work correctly.

    Background: PR#41 added is_private to the Entity model but forgot to add it to the
    version tables. This migration (c30f195dcd11) fixes that by adding is_private to:
    - entities_version
    - datasets_version
    - trained_models_version
    - tasks_version
    """

    # Create a collection and dataset directly via ORM
    collection = models.Collection(
        name="Version Bug Test Collection",
        description="Collection for testing version table bug",
        owner_identifier="test-owner"
    )
    db_session.add(collection)
    await db_session.flush()

    # Create a dataset with is_private=True
    # Since is_private is now in the Entity model, we can set it directly
    dataset = models.Dataset(
        name="Test Dataset",
        data_path="/path/test.csv",
        format="csv",
        entity_type="dataset",
        metadata_version="1.0",
        dataset_metadata={"description": "Test dataset"},
        collection_id=collection.id,
        is_private=True  # This is now supported by the model
    )
    db_session.add(dataset)
    await db_session.commit()

    # Update the dataset multiple times - this should trigger versioning and work correctly
    dataset.data_path = "/path/updated.csv"
    await db_session.commit()

    # Update again to create multiple versions
    dataset.data_path = "/path/updated_v2.csv"
    dataset.is_private = False  # Change is_private value
    await db_session.commit()

    # Update once more
    dataset.data_path = "/path/updated_v3.csv"
    dataset.is_private = True  # Change back to private
    await db_session.commit()

    # Verify the dataset was updated successfully
    assert dataset.data_path == "/path/updated_v3.csv"
    assert dataset.is_private is True

    # Verify that version history was created properly
    # The dataset should have 3 versions (initial + 3 updates = 4 total)
    result = await db_session.execute(
        text("SELECT COUNT(*) FROM entities_version WHERE id = :id"),
        {"id": dataset.id}
    )
    version_count = result.scalar()
    assert version_count == 4, f"Expected 4 versions, got {version_count}"

    # Verify that is_private was captured in the version history
    result = await db_session.execute(
        text("SELECT is_private FROM entities_version WHERE id = :id ORDER BY transaction_id"),
        {"id": dataset.id}
    )
    is_private_values = [row[0] for row in result.fetchall()]
    assert is_private_values == [True, True, False, True], (
        f"Expected is_private history [True, True, False, True], got {is_private_values}"
    )
