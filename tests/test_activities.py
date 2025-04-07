# sqlalchemy imports, engine, sessionmaker, override_get_db, and setup_test_db fixture are now handled by conftest.py
# Keep necessary imports:
from datetime import datetime
import pytest
import asyncio # Needed for pytest.mark.asyncio
import httpx # Add httpx

from mlcbakery.main import app # Keep app import if needed for client
# Model imports might still be needed if tests reference them directly
# from mlcbakery.models import ...

# REMOVED: client = TestClient(app)

# Helper function to create prerequisites consistently
async def create_test_prerequisites(ac: httpx.AsyncClient, prefix: str):
    """Creates a collection, two datasets, a model, and an agent."""
    # Collection
    coll_data = {"name": f"{prefix} Collection", "description": f"{prefix} Desc"}
    coll_resp = await ac.post("/api/v1/collections/", json=coll_data)
    assert coll_resp.status_code == 200
    collection_id = coll_resp.json()["id"]

    # Datasets
    ds1_data = {"name": f"{prefix} Dataset 1", "data_path": "/path/ds1.csv", "format": "csv", "collection_id": collection_id, "entity_type": "dataset"}
    ds2_data = {"name": f"{prefix} Dataset 2", "data_path": "/path/ds2.csv", "format": "csv", "collection_id": collection_id, "entity_type": "dataset"}
    ds1_resp = await ac.post("/api/v1/datasets/", json=ds1_data)
    ds2_resp = await ac.post("/api/v1/datasets/", json=ds2_data)
    assert ds1_resp.status_code == 200
    assert ds2_resp.status_code == 200
    dataset_ids = [ds1_resp.json()["id"], ds2_resp.json()["id"]]

    # Model
    model_data = {"name": f"{prefix} Model", "model_path": "/path/model.pkl", "framework": "sklearn", "collection_id": collection_id, "entity_type": "trained_model"}
    model_resp = await ac.post("/api/v1/trained_models/", json=model_data)
    assert model_resp.status_code == 200
    model_id = model_resp.json()["id"]

    # Agent
    agent_data = {"name": f"{prefix} Agent", "type": "user"}
    agent_resp = await ac.post("/api/v1/agents/", json=agent_data)
    assert agent_resp.status_code == 200
    agent_id = agent_resp.json()["id"]

    return {"dataset_ids": dataset_ids, "model_id": model_id, "agent_id": agent_id}

# Tests remain marked as async
@pytest.mark.asyncio
async def test_create_activity():
    """Test creating a new activity with relationships."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        prereqs = await create_test_prerequisites(ac, "CreateAct")
        dataset_ids = prereqs["dataset_ids"]
        model_id = prereqs["model_id"]
        agent_id = prereqs["agent_id"]

        # Create activity
        activity_data = {
            "name": "Test Activity Create",
            "input_entity_ids": dataset_ids,
            "output_entity_id": model_id,
            "agent_ids": [agent_id],
        }
        response = await ac.post("/api/v1/activities/", json=activity_data)
        assert response.status_code == 200, f"Failed with {response.status_code}: {response.text}"
        data = response.json()
        assert data["name"] == activity_data["name"]
        assert set(data["input_entity_ids"]) == set(dataset_ids)
        assert data["output_entity_id"] == model_id
        assert set(data["agent_ids"]) == set([agent_id])
        assert "id" in data
        assert "created_at" in data

@pytest.mark.asyncio
async def test_create_activity_without_optional_relationships():
    """Test creating an activity without optional relationships."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        prereqs = await create_test_prerequisites(ac, "CreateActNoOpt")
        dataset_ids = prereqs["dataset_ids"]

        # Create activity without optional relationships
        activity_data = {
            "name": "Test Activity No Optional",
            "input_entity_ids": dataset_ids,
            # output_entity_id and agent_ids omitted
        }
        response = await ac.post("/api/v1/activities/", json=activity_data)
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
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Don't need real prerequisites, just testing invalid IDs
        activity_data = {
            "name": "Test Activity Bad IDs",
            "input_entity_ids": [99998],
            "output_entity_id": 99999,
            "agent_ids": [99997],
        }
        response = await ac.post("/api/v1/activities/", json=activity_data)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_list_activities():
    """Test getting all activities."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        prereqs = await create_test_prerequisites(ac, "ListAct")
        dataset_ids = prereqs["dataset_ids"]

        # Create a test activity first
        activity_data = {
            "name": "Activity For Listing",
            "input_entity_ids": dataset_ids,
        }
        create_response = await ac.post("/api/v1/activities/", json=activity_data)
        assert create_response.status_code == 200
        created_activity_id = create_response.json()["id"]

        # List activities
        response = await ac.get("/api/v1/activities/")
        assert response.status_code == 200
        data = response.json()
        found = any(item["id"] == created_activity_id for item in data)
        assert found, f"Activity {created_activity_id} not found in list"
        assert len(data) >= 1

@pytest.mark.asyncio
async def test_list_activities_pagination():
    """Test pagination of activities."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        prereqs = await create_test_prerequisites(ac, "PaginateAct")
        dataset_ids = prereqs["dataset_ids"]

        # Get initial count (might include activities from other tests if run together, ideally run isolated)
        response_initial = await ac.get("/api/v1/activities/")
        assert response_initial.status_code == 200
        initial_count = len(response_initial.json())

        # Create multiple test activities
        created_ids = []
        activity_names = {}
        for i in range(5): # Create 5 activities for pagination test
            name = f"Paginated Activity {i}"
            activity_data = {"name": name, "input_entity_ids": dataset_ids}
            resp = await ac.post("/api/v1/activities/", json=activity_data)
            assert resp.status_code == 200
            activity_id = resp.json()["id"]
            created_ids.append(activity_id)
            activity_names[activity_id] = name

        # Test pagination
        # Get total count
        response_all = await ac.get("/api/v1/activities/")
        assert response_all.status_code == 200
        total_count = len(response_all.json())
        assert total_count >= initial_count + 5 # Check it increased by at least 5

        # Fetch page 2 (e.g., skip 2, limit 2)
        response_page = await ac.get(f"/api/v1/activities/?skip={initial_count + 2}&limit=2")
        assert response_page.status_code == 200
        data = response_page.json()
        assert len(data) == 2

        # Assert the correct activities are on page 2 (the 3rd and 4th we created)
        # This relies on default ordering (likely by ID or creation time)
        # More robust tests might check IDs against created_ids[2:4]
        page_ids = {item["id"] for item in data}
        expected_ids_on_page = set(created_ids[2:4])
        assert page_ids == expected_ids_on_page, f"Expected IDs {expected_ids_on_page}, got {page_ids}"
        assert data[0]["name"] == activity_names[created_ids[2]]
        assert data[1]["name"] == activity_names[created_ids[3]]

@pytest.mark.asyncio
async def test_get_activity():
    """Test getting a specific activity."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        prereqs = await create_test_prerequisites(ac, "GetAct")
        dataset_ids = prereqs["dataset_ids"]

        # Create a test activity first
        activity_data = {
            "name": "Activity To Get",
            "input_entity_ids": dataset_ids,
        }
        create_response = await ac.post("/api/v1/activities/", json=activity_data)
        assert create_response.status_code == 200
        activity_id = create_response.json()["id"]

        # Get the specific activity
        response = await ac.get(f"/api/v1/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == activity_id
        assert data["name"] == "Activity To Get"
        assert set(data["input_entity_ids"]) == set(dataset_ids)

@pytest.mark.asyncio
async def test_get_nonexistent_activity():
    """Test getting an activity that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/activities/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"

@pytest.mark.asyncio
async def test_delete_activity():
    """Test deleting an activity."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        prereqs = await create_test_prerequisites(ac, "DeleteAct")
        dataset_ids = prereqs["dataset_ids"]

        # Create a test activity first
        activity_data = {
            "name": "Activity To Delete",
            "input_entity_ids": dataset_ids,
        }
        create_response = await ac.post("/api/v1/activities/", json=activity_data)
        assert create_response.status_code == 200
        activity_id = create_response.json()["id"]

        # Delete the activity
        delete_response = await ac.delete(f"/api/v1/activities/{activity_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Activity deleted successfully"

        # Verify it's deleted
        get_response = await ac.get(f"/api/v1/activities/{activity_id}")
        assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_delete_nonexistent_activity():
    """Test deleting an activity that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.delete("/api/v1/activities/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
