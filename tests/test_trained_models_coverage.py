"""
Additional tests for trained_models.py to achieve 90%+ coverage.
Uses the async_client fixture for proper database session handling.
"""

import pytest
import uuid
from unittest.mock import MagicMock

from mlcbakery.auth.passthrough_strategy import sample_org_token, authorization_headers

AUTH_HEADERS = authorization_headers(sample_org_token())


async def create_test_collection(ac, name: str = None):
    """Helper function to create a test collection with a unique name."""
    if name is None:
        name = f"test-models-coverage-{uuid.uuid4().hex[:8]}"
    collection_data = {"name": name, "description": "Test collection for models coverage"}
    response = await ac.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response.status_code == 200, f"Failed to create collection: {response.text}"
    return response.json()


async def create_test_model(ac, collection_name: str, model_name: str = None):
    """Helper function to create a test model."""
    if model_name is None:
        model_name = f"test-model-{uuid.uuid4().hex[:8]}"
    model_data = {
        "name": model_name,
        "model_path": f"/models/{model_name}.pt",
        "metadata_version": "1.0.0",
        "model_metadata": {"accuracy": 0.95},
        "long_description": "Test model for coverage",
    }
    response = await ac.post(f"/api/v1/models/{collection_name}", json=model_data, headers=AUTH_HEADERS)
    assert response.status_code == 201, f"Failed to create model: {response.text}"
    return response.json()


# ============================================
# Tests for list_trained_models (list all)
# ============================================

@pytest.mark.asyncio
async def test_list_all_trained_models(async_client):
    """Test listing all trained models."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    for i in range(2):
        model_data = {
            "name": f"List All Model {i+1} {uuid.uuid4().hex[:6]}",
            "model_path": f"/models/list_all_{i+1}.pt"
        }
        resp = await async_client.post(f"/api/v1/models/{collection_name}", json=model_data, headers=AUTH_HEADERS)
        assert resp.status_code == 201

    response = await async_client.get("/api/v1/models/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_list_all_trained_models_with_pagination(async_client):
    """Test listing all trained models with pagination parameters."""
    response = await async_client.get("/api/v1/models/?skip=0&limit=10", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_all_trained_models_without_auth(async_client):
    """Test listing all trained models without authentication fails."""
    response = await async_client.get("/api/v1/models/")
    assert response.status_code == 403


# Note: Search tests require Typesense which may not be available in test environment


# ============================================
# Tests for version history endpoints
# ============================================

@pytest.mark.asyncio
async def test_get_trained_model_version_history(async_client):
    """Test getting version history for a trained model."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/history",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert "entity_name" in data
    assert "entity_type" in data
    assert data["entity_type"] == "trained_model"
    assert "total_versions" in data
    assert "versions" in data
    assert data["total_versions"] >= 1


@pytest.mark.asyncio
async def test_get_trained_model_version_history_with_pagination(async_client):
    """Test version history with pagination."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/history?skip=0&limit=10",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_trained_model_version_history_with_changeset(async_client):
    """Test version history with changeset included."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/history?include_changeset=true",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    if data["versions"]:
        assert "changeset" in data["versions"][0]


@pytest.mark.asyncio
async def test_get_trained_model_version_history_nonexistent_collection(async_client):
    """Test version history for nonexistent collection returns 404."""
    response = await async_client.get(
        "/api/v1/models/nonexistent-collection/some-model/history",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_version_history_nonexistent_model(async_client):
    """Test version history for nonexistent model returns 404."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/nonexistent-model/history",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_version_by_index(async_client):
    """Test getting a specific model version by index (~0, ~1, etc.)."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/versions/~0",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert "index" in data
    assert "transaction_id" in data
    assert "data" in data
    assert data["data"]["name"] == model_name


@pytest.mark.asyncio
async def test_get_trained_model_version_by_negative_index(async_client):
    """Test getting model version by negative index (~-1 for latest)."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/versions/~-1",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_get_trained_model_version_invalid_index(async_client):
    """Test getting model version with invalid index format."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/versions/~abc",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_trained_model_version_out_of_range_index(async_client):
    """Test getting model version with out-of-range index."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/versions/~1000",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_version_by_hash(async_client):
    """Test getting model version by content hash."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    history_response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/history",
        headers=AUTH_HEADERS
    )
    assert history_response.status_code == 200
    history = history_response.json()

    if history["versions"] and history["versions"][0].get("content_hash"):
        content_hash = history["versions"][0]["content_hash"]

        response = await async_client.get(
            f"/api/v1/models/{collection_name}/{model_name}/versions/{content_hash}",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_trained_model_version_nonexistent_hash(async_client):
    """Test getting model version with nonexistent hash."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    fake_hash = "a" * 64
    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/versions/{fake_hash}",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_version_nonexistent_tag(async_client):
    """Test getting model version with nonexistent tag."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)
    model_name = model["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/{model_name}/versions/v99.99.99",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_version_nonexistent_collection(async_client):
    """Test getting model version for nonexistent collection."""
    response = await async_client.get(
        "/api/v1/models/nonexistent-collection/some-model/versions/~0",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_version_nonexistent_model(async_client):
    """Test getting model version for nonexistent model."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    response = await async_client.get(
        f"/api/v1/models/{collection_name}/nonexistent-model/versions/~0",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


# ============================================
# Additional CRUD tests
# ============================================

@pytest.mark.asyncio
async def test_trained_model_response_includes_entity_type(async_client):
    """Test that trained model responses include entity_type field."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    model_data = {
        "name": f"entity-type-test-{uuid.uuid4().hex[:8]}",
        "model_path": "/models/entity_type_test.pt"
    }

    response = await async_client.post(f"/api/v1/models/{collection_name}", json=model_data, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["entity_type"] == "trained_model"


@pytest.mark.asyncio
async def test_list_trained_models_by_collection(async_client):
    """Test listing models in a specific collection."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    await create_test_model(async_client, collection_name)

    response = await async_client.get(f"/api/v1/models/{collection_name}/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    if len(data) > 0:
        assert "collection_name" in data[0]
        assert data[0]["collection_name"] == collection_name


@pytest.mark.asyncio
async def test_list_trained_models_nonexistent_collection(async_client):
    """Test listing models in nonexistent collection."""
    response = await async_client.get("/api/v1/models/nonexistent-collection/", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_by_name(async_client):
    """Test getting a specific model by name."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)

    response = await async_client.get(f"/api/v1/models/{collection_name}/{model['name']}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == model["name"]


@pytest.mark.asyncio
async def test_get_trained_model_nonexistent(async_client):
    """Test getting nonexistent model."""
    collection = await create_test_collection(async_client)
    response = await async_client.get(f"/api/v1/models/{collection['name']}/nonexistent-model", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_trained_model(async_client):
    """Test creating a trained model."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    model_data = {
        "name": f"new-model-{uuid.uuid4().hex[:8]}",
        "model_path": "/models/new.pt",
        "metadata_version": "1.0.0"
    }
    response = await async_client.post(f"/api/v1/models/{collection_name}", json=model_data, headers=AUTH_HEADERS)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_create_trained_model_duplicate(async_client):
    """Test creating duplicate model fails."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    model_data = {
        "name": f"dup-model-{uuid.uuid4().hex[:8]}",
        "model_path": "/models/dup.pt"
    }
    await async_client.post(f"/api/v1/models/{collection_name}", json=model_data, headers=AUTH_HEADERS)

    response = await async_client.post(f"/api/v1/models/{collection_name}", json=model_data, headers=AUTH_HEADERS)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_trained_model_nonexistent_collection(async_client):
    """Test creating model in nonexistent collection."""
    model_data = {"name": "model", "model_path": "/models/test.pt"}
    response = await async_client.post("/api/v1/models/nonexistent-collection", json=model_data, headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_trained_model(async_client):
    """Test updating a trained model."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)

    update_data = {"long_description": "Updated description"}
    response = await async_client.put(
        f"/api/v1/models/{collection_name}/{model['name']}",
        json=update_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_trained_model_nonexistent(async_client):
    """Test updating nonexistent model."""
    collection = await create_test_collection(async_client)
    response = await async_client.put(
        f"/api/v1/models/{collection['name']}/nonexistent-model",
        json={"long_description": "test"},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_trained_model(async_client):
    """Test deleting a trained model."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]
    model = await create_test_model(async_client, collection_name)

    response = await async_client.delete(f"/api/v1/models/{collection_name}/{model['name']}", headers=AUTH_HEADERS)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_trained_model_nonexistent(async_client):
    """Test deleting nonexistent model."""
    collection = await create_test_collection(async_client)
    response = await async_client.delete(f"/api/v1/models/{collection['name']}/nonexistent-model", headers=AUTH_HEADERS)
    assert response.status_code == 404
