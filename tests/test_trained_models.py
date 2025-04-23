from fastapi.testclient import TestClient
# sqlalchemy sync imports, engine, sessionmaker, override_get_db, and fixture are now handled by conftest.py
# Keep necessary imports:
from datetime import datetime
import pytest
import base64
import asyncio # Needed for pytest.mark.asyncio
import httpx
import python_multipart

from mlcbakery.main import app
from mlcbakery.models import Base, Dataset, Collection, Activity, Entity

# Refactored tests using local async client pattern (Relying on global setup now)
@pytest.mark.asyncio
async def test_create_trained_model():
    """Test creating a new trained model."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create the prerequisite collection within the test
        collection_data = {"name": "Model Test Collection Create", "description": "For model create test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200, f"Failed to create prerequisite collection: {coll_resp.text}"
        collection_id = coll_resp.json()["id"]

        trained_model_data = {
            "name": "test-model-async",
            "model_path": "/path/to/model-async.pkl",
            "framework": "scikit-learn",
            "entity_type": "trained_model", # Ensure this matches your model
            "collection_id": collection_id,
        }

        response = await ac.post("/api/v1/trained_models/", json=trained_model_data)
        assert response.status_code == 200, f"Create failed: {response.text}"
        data = response.json()
        assert data["name"] == trained_model_data["name"]
        assert data["model_path"] == trained_model_data["model_path"]
        assert data["framework"] == trained_model_data["framework"]
        assert data["entity_type"] == "trained_model"
        assert data["collection_id"] == collection_id
        assert "id" in data
        assert "created_at" in data

@pytest.mark.asyncio
async def test_get_trained_model():
    """Test getting a specific trained model."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create the prerequisite collection within the test
        collection_data = {"name": "Model Test Collection Get", "description": "For model get test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200, f"Failed to create prerequisite collection: {coll_resp.text}"
        collection_id = coll_resp.json()["id"]

        # Create a test model first
        model_data = {
            "name":"get-model-async",
            "entity_type":"trained_model",
            "model_path":"/path/get.pkl",
            "framework":"pytorch",
            "collection_id": collection_id,
        }
        create_resp = await ac.post("/api/v1/trained_models/", json=model_data)
        assert create_resp.status_code == 200
        model_id = create_resp.json()["id"]

        # Get the model
        response = await ac.get(f"/api/v1/trained_models/{model_id}")
        assert response.status_code == 200, f"Get failed: {response.text}"
        data = response.json()
        assert data["id"] == model_id
        assert data["name"] == model_data["name"]
        assert data["framework"] == model_data["framework"]
        assert data["collection_id"] == collection_id

@pytest.mark.asyncio
async def test_list_trained_models():
    """Test listing all trained models."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create the prerequisite collection within the test
        collection_data = {"name": "Model Test Collection List", "description": "For model list test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200, f"Failed to create prerequisite collection: {coll_resp.text}"
        collection_id = coll_resp.json()["id"]

        # Create some test models
        created_ids = []
        for i in range(3):
            model_data = {
                "name":f"list-model-async-{i}",
                "entity_type":"trained_model",
                "model_path":f"/path/list_{i}.pkl",
                "framework":"tensorflow",
                "collection_id": collection_id,
            }
            resp = await ac.post("/api/v1/trained_models/", json=model_data)
            assert resp.status_code == 200
            created_ids.append(resp.json()["id"])

        # List models
        response = await ac.get("/api/v1/trained_models/")
        assert response.status_code == 200, f"List failed: {response.text}"
        data = response.json()

        # Check that created models are in the list
        fetched_ids = {item["id"] for item in data}
        assert set(created_ids).issubset(fetched_ids)

@pytest.mark.asyncio
async def test_delete_trained_model():
    """Test deleting a trained model."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create the prerequisite collection within the test
        collection_data = {"name": "Model Test Collection Delete", "description": "For model delete test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data)
        assert coll_resp.status_code == 200, f"Failed to create prerequisite collection: {coll_resp.text}"
        collection_id = coll_resp.json()["id"]

        # Create a test model first
        model_data = {
            "name":"delete-model-async",
            "entity_type":"trained_model",
            "model_path":"/path/delete.pkl",
            "framework":"jax",
            "collection_id": collection_id,
        }
        create_resp = await ac.post("/api/v1/trained_models/", json=model_data)
        assert create_resp.status_code == 200
        model_id = create_resp.json()["id"]

        # Delete the model
        response = await ac.delete(f"/api/v1/trained_models/{model_id}")
        assert response.status_code == 200, f"Delete failed: {response.text}"
        assert response.json()["message"] == "Trained model deleted successfully"

        # Verify the model is deleted
        get_response = await ac.get(f"/api/v1/trained_models/{model_id}")
        assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_get_nonexistent_trained_model():
    """Test getting a nonexistent trained model."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/trained_models/99999")
        assert response.status_code == 404
        assert response.json()["detail"] == "Trained model not found"
