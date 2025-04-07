from fastapi.testclient import TestClient
# sqlalchemy imports, engine, sessionmaker, override_get_db, and setup_test_db fixture are now handled by conftest.py
# Keep necessary imports:
from datetime import datetime
import pytest
import asyncio # Needed for pytest.mark.asyncio

from mlcbakery.main import app # Keep app import if needed for client
# Model imports might still be needed if tests reference them directly
# from mlcbakery.models import ...

# TestClient remains synchronous, it uses the globally overridden dependency
# Ensure the `app` object used here is the same one modified in conftest.py
client = TestClient(app)

# Remove the setup_test_db fixture definition
# Remove engine, TestingSessionLocal, override_get_db definitions

# Tests remain marked as async
@pytest.mark.asyncio
async def test_create_activity():
    """Test creating a new activity with relationships."""
    # Get seeded data IDs (more robust than calling API again)
    # Assuming seeded dataset IDs are 1 and 2, model ID is 3, agent ID is 1
    # This depends on the order of insertion and potential auto-increment behavior
    # For more robustness, query the seeded data IDs here if necessary.
    # Let's assume we know the IDs based on fixture seeding for simplicity now:
    dataset_ids = [1, 2] # Example: IDs from seeded datasets
    model_id = 3        # Example: ID from seeded model
    agent_id = 1        # Example: ID from seeded agent

    # Create activity
    activity_data = {
        "name": "Test Activity",
        "input_entity_ids": dataset_ids,
        "output_entity_id": model_id,
        "agent_ids": [agent_id],
    }
    response = client.post("/api/v1/activities/", json=activity_data)
    assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
    data = response.json()
    assert data["name"] == activity_data["name"]
    # Order might not be guaranteed in response lists, use set comparison
    assert set(data["input_entity_ids"]) == set(dataset_ids)
    assert data["output_entity_id"] == model_id
    assert set(data["agent_ids"]) == set([agent_id])
    assert "id" in data
    assert "created_at" in data

@pytest.mark.asyncio
async def test_create_activity_without_optional_relationships():
    """Test creating an activity without optional relationships."""
    dataset_ids = [1, 2] # Assuming known IDs from fixture

    # Create activity without optional relationships
    activity_data = {
        "name": "Test Activity No Optional",
        "input_entity_ids": dataset_ids,
    }
    response = client.post("/api/v1/activities/", json=activity_data)
    assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
    data = response.json()
    assert data["name"] == activity_data["name"]
    assert set(data["input_entity_ids"]) == set(dataset_ids)
    assert data["output_entity_id"] is None
    assert data["agent_ids"] == []
    assert "id" in data
    assert "created_at" in data

@pytest.mark.asyncio
async def test_create_activity_with_nonexistent_entities():
    """Test creating an activity with nonexistent entities."""
    activity_data = {
        "name": "Test Activity Bad IDs",
        "input_entity_ids": [99998],
        "output_entity_id": 99999,
        "agent_ids": [99997],
    }
    response = client.post("/api/v1/activities/", json=activity_data)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_list_activities():
    """Test getting all activities."""
    # Create a test activity first
    dataset_ids = [1, 2]
    activity_data = {
        "name": "Activity For Listing",
        "input_entity_ids": dataset_ids,
    }
    create_response = client.post("/api/v1/activities/", json=activity_data)
    assert create_response.status_code == 200
    created_activity_id = create_response.json()["id"]

    # List activities
    response = client.get("/api/v1/activities/")
    assert response.status_code == 200
    data = response.json()
    # Check if the created activity is in the list
    found = any(item["id"] == created_activity_id for item in data)
    assert found, f"Activity {created_activity_id} not found in list"
    # We expect at least 1 activity (the one we just created)
    assert len(data) >= 1

@pytest.mark.asyncio
async def test_list_activities_pagination():
    """Test pagination of activities."""
    # Create multiple test activities (fixture already creates some implicitly)
    dataset_ids = [1, 2]
    initial_activities = client.get("/api/v1/activities/").json()
    initial_count = len(initial_activities)

    for i in range(3):
        activity_data = {
            "name": f"Paginated Activity {i}",
            "input_entity_ids": dataset_ids,
        }
        client.post("/api/v1/activities/", json=activity_data)

    # Test pagination
    # Get total count first
    response_all = client.get("/api/v1/activities/")
    assert response_all.status_code == 200
    total_count = len(response_all.json())
    assert total_count == initial_count + 3

    # Fetch page 2 (skip initial_count + 1, limit 2)
    response_page = client.get(f"/api/v1/activities/?skip={initial_count + 1}&limit=2")
    assert response_page.status_code == 200
    data = response_page.json()
    assert len(data) == 2 # Should get the 2nd and 3rd new activities
    assert data[0]["name"] == "Paginated Activity 1"
    assert data[1]["name"] == "Paginated Activity 2"

@pytest.mark.asyncio
async def test_get_activity():
    """Test getting a specific activity."""
    # Create a test activity first
    dataset_ids = [1, 2]
    activity_data = {
        "name": "Activity To Get",
        "input_entity_ids": dataset_ids,
    }
    create_response = client.post("/api/v1/activities/", json=activity_data)
    assert create_response.status_code == 200
    activity_id = create_response.json()["id"]

    # Get the specific activity
    response = client.get(f"/api/v1/activities/{activity_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Activity To Get"
    assert set(data["input_entity_ids"]) == set(dataset_ids)

@pytest.mark.asyncio
async def test_get_nonexistent_activity():
    """Test getting an activity that doesn't exist."""
    response = client.get("/api/v1/activities/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"

@pytest.mark.asyncio
async def test_delete_activity():
    """Test deleting an activity."""
    # Create a test activity first
    dataset_ids = [1, 2]
    activity_data = {
        "name": "Activity To Delete",
        "input_entity_ids": dataset_ids,
    }
    create_response = client.post("/api/v1/activities/", json=activity_data)
    assert create_response.status_code == 200
    activity_id = create_response.json()["id"]

    # Delete the activity
    delete_response = client.delete(f"/api/v1/activities/{activity_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Activity deleted successfully"

    # Verify it's deleted
    get_response = client.get(f"/api/v1/activities/{activity_id}")
    assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_delete_nonexistent_activity():
    """Test deleting an activity that doesn't exist."""
    response = client.delete("/api/v1/activities/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"
