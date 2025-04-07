from datetime import datetime
import pytest
import asyncio
import httpx

from mlcbakery.main import app
from mlcbakery.models import (
    Base,
    Activity,
    Dataset,
    TrainedModel,
    Agent,
    Collection,
    Entity,
)

# === Async Helper Functions for Creating Entities via API ===
async def create_test_collection(ac: httpx.AsyncClient, name="Test Collection API") -> dict:
    coll_data = {"name": name, "description": f"{name} Desc"}
    coll_resp = await ac.post("/api/v1/collections/", json=coll_data)
    assert coll_resp.status_code == 200, f"Helper failed creating collection: {coll_resp.text}"
    return coll_resp.json()

async def create_test_dataset(ac: httpx.AsyncClient, collection_id: int, name="Test Dataset API") -> dict:
    dataset_data = {
        "name": name,
        "data_path": f"/path/{name.replace(' ', '_')}.csv",
        "format": "csv",
        "collection_id": collection_id,
        "entity_type": "dataset",
        "metadata_version": "1.0",
        "dataset_metadata": {"description": f"{name} Desc via API"},
    }
    dataset_resp = await ac.post("/api/v1/datasets/", json=dataset_data)
    assert dataset_resp.status_code == 200, f"Helper failed creating dataset: {dataset_resp.text}"
    return dataset_resp.json()

async def create_test_model(ac: httpx.AsyncClient, collection_id: int, name="Test Model API") -> dict:
    model_data = {
        "name": name,
        "model_path": f"/path/{name.replace(' ', '_')}.pkl",
        "framework": "scikit-learn",
        "collection_id": collection_id,
        "entity_type": "trained_model",
        "metadata_version": "1.0",
        "model_metadata": {"description": f"{name} Desc via API"},
    }
    model_resp = await ac.post("/api/v1/trained_models/", json=model_data)
    assert model_resp.status_code == 200, f"Helper failed creating model: {model_resp.text}"
    return model_resp.json()

async def create_test_agent(ac: httpx.AsyncClient, name="Test Agent API") -> dict:
    agent_data = {"name": name, "type": "API testing"}
    agent_resp = await ac.post("/api/v1/agents/", json=agent_data)
    assert agent_resp.status_code == 200, f"Helper failed creating agent: {agent_resp.text}"
    return agent_resp.json()

# === Refactored Tests ===

@pytest.mark.asyncio
async def test_create_dataset():
    """Test creating a new dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create prerequisite collection
        collection = await create_test_collection(ac, name="Collection For Create Dataset")
        collection_id = collection["id"]

        # Data for the new dataset
        dataset_data = {
            "name": "New Dataset via API",
            "data_path": "/path/to/new/api_data.csv",
            "format": "csv",
            "collection_id": collection_id,
            "entity_type": "dataset",
            "metadata_version": "1.1",
            "dataset_metadata": {"description": "New test dataset via API"},
        }
        response = await ac.post("/api/v1/datasets/", json=dataset_data)
        assert response.status_code == 200, f"Create dataset failed: {response.text}"
        data = response.json()
        assert data["name"] == dataset_data["name"]
        assert data["data_path"] == dataset_data["data_path"]
        assert data["format"] == dataset_data["format"]
        assert data["collection_id"] == collection_id
        assert data["entity_type"] == "dataset"
        assert data["metadata_version"] == dataset_data["metadata_version"]
        assert data["dataset_metadata"] == dataset_data["dataset_metadata"]
        assert "id" in data
        assert "created_at" in data

@pytest.mark.asyncio
async def test_create_model():
    """Test creating a new model."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # Create prerequisite collection
        collection = await create_test_collection(ac, name="Collection For Create Model")
        collection_id = collection["id"]

        # Data for the new model
        model_data = {
            "name": "New Model via API",
            "model_path": "/path/to/new/api_model.pkl",
            "framework": "pytorch",
            "collection_id": collection_id,
            "entity_type": "trained_model",
            "metadata_version": "1.1",
            "model_metadata": {"description": "New test model via API"},
        }
        response = await ac.post("/api/v1/trained_models/", json=model_data)
        assert response.status_code == 200, f"Create model failed: {response.text}"
        data = response.json()
        assert data["name"] == model_data["name"]
        assert data["model_path"] == model_data["model_path"]
        assert data["framework"] == model_data["framework"]
        assert data["collection_id"] == collection_id
        assert data["entity_type"] == "trained_model"
        assert data["metadata_version"] == model_data["metadata_version"]
        assert data["model_metadata"] == model_data["model_metadata"]
        assert "id" in data
        assert "created_at" in data

@pytest.mark.asyncio
async def test_list_datasets():
    """Test getting all datasets."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        collection = await create_test_collection(ac, name="Collection For List Datasets")
        collection_id = collection["id"]
        ds1 = await create_test_dataset(ac, collection_id, name="List DS 1")
        ds2 = await create_test_dataset(ac, collection_id, name="List DS 2")

        response = await ac.get("/api/v1/datasets/")
        assert response.status_code == 200
        data = response.json()

        # Find the created datasets in the response (order might vary)
        fetched_ids = {item["id"] for item in data}
        expected_ids = {ds1["id"], ds2["id"]}
        assert expected_ids.issubset(fetched_ids), f"Expected {expected_ids}, found {fetched_ids}"

@pytest.mark.asyncio
async def test_list_models():
    """Test getting all models."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        collection = await create_test_collection(ac, name="Collection For List Models")
        collection_id = collection["id"]
        model1 = await create_test_model(ac, collection_id, name="List Model 1")

        response = await ac.get("/api/v1/trained_models/")
        assert response.status_code == 200
        data = response.json()

        fetched_ids = {item["id"] for item in data}
        expected_ids = {model1["id"]}
        assert expected_ids.issubset(fetched_ids)

@pytest.mark.asyncio
async def test_get_dataset():
    """Test getting a specific dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        collection = await create_test_collection(ac, name="Collection For Get Dataset")
        collection_id = collection["id"]
        dataset = await create_test_dataset(ac, collection_id, name="Dataset To Get")
        dataset_id = dataset["id"]

        response = await ac.get(f"/api/v1/datasets/{dataset_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dataset_id
        assert data["name"] == "Dataset To Get"
        assert data["collection_id"] == collection_id

@pytest.mark.asyncio
async def test_get_model():
    """Test getting a specific model."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        collection = await create_test_collection(ac, name="Collection For Get Model")
        collection_id = collection["id"]
        model = await create_test_model(ac, collection_id, name="Model To Get")
        model_id = model["id"]

        response = await ac.get(f"/api/v1/trained_models/{model_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == model_id
        assert data["name"] == "Model To Get"
        assert data["collection_id"] == collection_id

@pytest.mark.asyncio
async def test_get_nonexistent_dataset():
    """Test getting a dataset that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/datasets/99999") # Use a likely non-existent ID
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"

@pytest.mark.asyncio
async def test_get_nonexistent_model():
    """Test getting a model that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/api/v1/trained_models/99999") # Use a likely non-existent ID
        assert response.status_code == 404
        assert response.json()["detail"] == "Trained model not found"

@pytest.mark.asyncio
async def test_delete_dataset():
    """Test deleting a dataset."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        collection = await create_test_collection(ac, name="Collection For Delete Dataset")
        collection_id = collection["id"]
        dataset = await create_test_dataset(ac, collection_id, name="Dataset To Delete")
        dataset_id = dataset["id"]

        # Delete the dataset
        response_del = await ac.delete(f"/api/v1/datasets/{dataset_id}")
        assert response_del.status_code == 200
        assert response_del.json()["message"] == "Dataset deleted successfully"

        # Verify it's deleted
        response_get = await ac.get(f"/api/v1/datasets/{dataset_id}")
        assert response_get.status_code == 404

@pytest.mark.asyncio
async def test_delete_model():
    """Test deleting a model."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        collection = await create_test_collection(ac, name="Collection For Delete Model")
        collection_id = collection["id"]
        model = await create_test_model(ac, collection_id, name="Model To Delete")
        model_id = model["id"]

        # Delete the model
        response_del = await ac.delete(f"/api/v1/trained_models/{model_id}")
        assert response_del.status_code == 200
        assert response_del.json()["message"] == "Trained model deleted successfully"

        # Verify it's deleted
        response_get = await ac.get(f"/api/v1/trained_models/{model_id}")
        assert response_get.status_code == 404

@pytest.mark.asyncio
async def test_delete_nonexistent_dataset():
    """Test deleting a dataset that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.delete("/api/v1/datasets/99999") # Use a likely non-existent ID
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"

@pytest.mark.asyncio
async def test_delete_nonexistent_model():
    """Test deleting a model that doesn't exist."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.delete("/api/v1/trained_models/99999") # Use a likely non-existent ID
        assert response.status_code == 404
        assert response.json()["detail"] == "Trained model not found"

@pytest.mark.asyncio
async def test_entity_activities():
    """Test linking entities to activities."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Setup: Collection, Dataset, Model, Agent
        collection = await create_test_collection(ac, name="Collection For Activity Linking")
        collection_id = collection["id"]
        dataset = await create_test_dataset(ac, collection_id, name="Input Dataset For Activity")
        dataset_id = dataset["id"]
        model = await create_test_model(ac, collection_id, name="Output Model For Activity")
        model_id = model["id"]
        agent = await create_test_agent(ac, name="Agent For Activity")
        agent_id = agent["id"]

        # 2. Create Activity linking them
        activity_data = {
            "name": "Activity Linking Entities",
            "input_entity_ids": [dataset_id],
            "output_entity_id": model_id,
            "agent_ids": [agent_id],
        }
        activity_resp = await ac.post("/api/v1/activities/", json=activity_data)
        assert activity_resp.status_code == 200
        activity_id = activity_resp.json()["id"]

        # 3. Verify links by fetching the activity
        get_activity_resp = await ac.get(f"/api/v1/activities/{activity_id}")
        assert get_activity_resp.status_code == 200
        fetched_activity = get_activity_resp.json()

        assert set(fetched_activity.get("input_entity_ids", [])) == {dataset_id}
        assert fetched_activity.get("output_entity_id") == model_id
        assert set(fetched_activity.get("agent_ids", [])) == {agent_id}

        # 4. Verify links by fetching the entities (if API includes activity links)
        # Fetch Dataset
        # get_dataset_resp = await ac.get(f"/api/v1/datasets/{dataset_id}")
        # fetched_dataset = get_dataset_resp.json()
        # assert activity_id in fetched_dataset.get("input_activity_ids", []) # Check schema/field name

        # Fetch Model
        # get_model_resp = await ac.get(f"/api/v1/trained_models/{model_id}")
        # fetched_model = get_model_resp.json()
        # assert activity_id in fetched_model.get("output_activity_ids", []) # Check schema/field name
