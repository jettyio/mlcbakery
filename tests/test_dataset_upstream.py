import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy import inspect
from sqlalchemy.orm.attributes import set_attribute

from mlcbakery.models import Dataset, Collection, Activity, Entity
from mlcbakery.api.endpoints.datasets import build_upstream_tree_async
from mlcbakery.schemas.dataset import UpstreamEntityNode


@pytest.mark.asyncio
async def test_build_upstream_tree_single_parent():
    """Test building an upstream tree with a single parent."""
    # Setup mock data using real model instances
    mock_collection = Collection(id=1, name="Test Collection")
    mock_parent_dataset = Dataset(id=1, name="Parent Dataset", entity_type="dataset", collection_id=1, data_path="/parent", format="csv")
    mock_child_dataset = Dataset(id=2, name="Child Dataset", entity_type="dataset", collection_id=1, data_path="/child", format="csv")
    # Use a real Activity instance
    mock_activity = Activity(id=100, name="Test Activity", output_entity_id=mock_child_dataset.id)

    # --- Link objects together directly BEFORE mocking ---
    # Set relationships on the instances themselves
    mock_child_dataset.collection = mock_collection
    mock_parent_dataset.collection = mock_collection
    
    # Link child -> activity -> parent
    # Use simple attribute assignment, hoping SQLAlchemy handles it if instances are 'clean'
    mock_child_dataset.input_activities = [mock_activity]
    mock_parent_dataset.output_activities = [mock_activity] 
    mock_activity.input_entities = [mock_parent_dataset]
    mock_activity.output_entity = mock_child_dataset
    mock_activity.agents = [] # Ensure agents list exists

    # --- Configure Mock DB ---
    mock_db = AsyncMock(spec=AsyncSession)

    # Side effect simply returns the pre-configured object by ID
    async def mock_execute_side_effect(*args, **kwargs):
        stmt = args[0]
        requested_id = None
        # Basic logic to extract ID from where clause (adapt if necessary)
        if hasattr(stmt, 'whereclause') and hasattr(stmt.whereclause, 'right') and hasattr(stmt.whereclause.right, 'value'):
            requested_id = stmt.whereclause.right.value
        elif hasattr(stmt, 'whereclause') and hasattr(stmt.whereclause, 'clauses'): 
             for clause in stmt.whereclause.clauses:
                  if hasattr(clause, 'right') and hasattr(clause.right, 'value'):
                       requested_id = clause.right.value
                       break

        entity_to_return = None
        if requested_id == mock_child_dataset.id:
            entity_to_return = mock_child_dataset
            # Ensure relationships needed by the function are set (redundant but safe)
            # entity_to_return.collection = mock_collection # Already set
            # entity_to_return.input_activities = [mock_activity] # Already set
            # mock_activity.input_entities = [mock_parent_dataset] # Already set
            # mock_activity.agents = [] # Already set
        elif requested_id == mock_parent_dataset.id:
            entity_to_return = mock_parent_dataset
            # Ensure relationships needed by the function are set (redundant but safe)
            # entity_to_return.collection = mock_collection # Already set
            # entity_to_return.output_activities = [mock_activity] # Already set
            # entity_to_return.input_activities = [] # Already set implicitly?
            # mock_activity.input_entities = [mock_parent_dataset] # Already set
            
        # Create a mock result proxy that behaves like SQLAlchemy's AsyncResult
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = AsyncMock(return_value=entity_to_return)
        return mock_result

    mock_db.execute.side_effect = mock_execute_side_effect
    # No mock_db.add needed if we aren't simulating adding to session state this way

    # --- Call Function Under Test ---
    visited = set()
    result_tree = await build_upstream_tree_async(mock_child_dataset.id, mock_db, visited)

    # --- Assertions ---
    assert result_tree is not None
    assert result_tree.id == mock_child_dataset.id
    assert result_tree.name == "Child Dataset"
    assert result_tree.collection_name == "Test Collection"
    assert result_tree.entity_type == "dataset"

    # Check activity details - THIS IS THE FAILING ASSERTION
    assert result_tree.activity_id == mock_activity.id  # Should be 100

    # Check parent node details
    assert len(result_tree.children) == 1
    parent_node = result_tree.children[0]
    assert parent_node.id == mock_parent_dataset.id
    assert parent_node.name == "Parent Dataset"
    assert parent_node.collection_name == "Test Collection"
    assert parent_node.entity_type == "dataset"
    assert parent_node.activity_id is None # Parent was source, no activity led to it
    assert len(parent_node.children) == 0 # Should be the root of this branch


# TODO: Add tests for multiple parents, no parents, deeper trees, different entity types etc.

# Add more tests for edge cases: no parents, multiple parents, deeper trees, cycles (handled by visited) 