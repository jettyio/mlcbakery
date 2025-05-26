import pytest
from httpx import AsyncClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import uuid # For unique collection names

from mlcbakery.main import app # Import your FastAPI app
from conftest import TEST_ADMIN_TOKEN # Import the test token
from mlcbakery.schemas.collection import CollectionCreate # Added

# Define headers globally or pass them around
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}


# Helper to create a test collection
async def _create_test_collection(async_client: AsyncClient, collection_name: str) -> Dict[str, Any]: # Returns dict with name and id
    collection_data = CollectionCreate(name=collection_name, description="Test Collection for Models")
    response = await async_client.post("/api/v1/collections/", json=collection_data.model_dump(), headers=AUTH_HEADERS)
    if response.status_code == 400 and "already exists" in response.json().get("detail", ""):
        get_response = await async_client.get(f"/api/v1/collections/{collection_name}", headers=AUTH_HEADERS)
        if get_response.status_code == 200:
            existing_coll_data = get_response.json()
            return {"id": existing_coll_data["id"], "name": existing_coll_data["name"]}
        else:
            pytest.fail(f"Failed to get existing collection {collection_name}: {get_response.text}")

    assert response.status_code == 200, f"Failed to create test collection: {response.text}"
    created_coll_data = response.json()
    return {"id": created_coll_data["id"], "name": created_coll_data["name"]}

@pytest.mark.asyncio
async def test_create_trained_model_success(async_client: AsyncClient):
    """
    Test successful creation of a trained model.
    Assumes async_client fixture is set up with your FastAPI app.
    """
    unique_collection_name = f"test-coll-models-success-{uuid.uuid4().hex[:8]}"
    collection_info = await _create_test_collection(async_client, unique_collection_name)

    model_data: Dict[str, Any] = {
        "name": "My API Test Model",
        "model_path": "/test/api/model.pt",
        "collection_name": collection_info["name"], # Use collection_name
        "metadata_version": "1.0.0",
        "model_metadata": {"accuracy": 0.95, "layers": 5},
        "asset_origin": "s3://my-bucket/models/model.pt",
        "long_description": "A detailed description of the test model.",
        "model_attributes": {"input_shape": [None, 224, 224, 3], "output_classes": 1000}
    }
    
    response = await async_client.post("/api/v1/models", json=model_data, headers=AUTH_HEADERS)
    
    assert response.status_code == 201
    response_data = response.json()

    assert response_data["name"] == model_data["name"]
    assert response_data["model_path"] == model_data["model_path"]
    assert response_data["asset_origin"] == model_data["asset_origin"]
    assert response_data["long_description"] == model_data["long_description"]
    assert response_data["model_attributes"] == model_data["model_attributes"]
    assert response_data["model_metadata"] == model_data["model_metadata"]
    assert response_data["collection_id"] == collection_info["id"]
    assert response_data["entity_type"] == "trained_model"
    assert "id" in response_data
    assert "created_at" in response_data

@pytest.mark.asyncio
async def test_create_trained_model_missing_required_fields(async_client: AsyncClient):
    """
    Test creating a trained model with missing required fields (name, model_path).
    NOTE: This test does not strictly need a collection to exist, as it should fail before DB interaction for missing fields.
    However, if the endpoint logic changes, or for consistency, one might still be created.
    For now, we assume Pydantic validation catches it first.
    """
    
    incomplete_data: Dict[str, Any] = {
        "long_description": "A model missing vital info.",
    }
    response = await async_client.post("/api/v1/models", json=incomplete_data, headers=AUTH_HEADERS)
    
    assert response.status_code == 422 # FastAPI's validation error
    response_data = response.json()
    assert "detail" in response_data
    # Check for specific error messages related to missing fields
    errors = response_data["detail"]
    assert any(e['type'] == 'missing' and "name" in e['loc'] for e in errors)
    assert any(e['type'] == 'missing' and "model_path" in e['loc'] for e in errors)

@pytest.mark.asyncio
async def test_create_trained_model_optional_fields_omitted(async_client: AsyncClient):
    """
    Test successful creation when optional fields are omitted.
    The placeholder endpoint will return them as None or default if schema defines.
    """
    unique_collection_name = f"test-coll-models-optional-{uuid.uuid4().hex[:8]}"
    collection_info = await _create_test_collection(async_client, unique_collection_name)

    minimal_data: Dict[str, Any] = {
        "name": "Minimal API Model",
        "model_path": "/test/api/minimal_model.dat",
        "collection_name": collection_info["name"] # Use collection_name
    }
    
    response = await async_client.post("/api/v1/models", json=minimal_data, headers=AUTH_HEADERS)
    assert response.status_code == 201
    response_data = response.json()

    assert response_data["name"] == minimal_data["name"]
    assert response_data["model_path"] == minimal_data["model_path"]
    assert response_data["collection_id"] == collection_info["id"]
    assert response_data["entity_type"] == "trained_model"
    assert response_data["asset_origin"] is None
    assert response_data["long_description"] is None
    assert response_data["model_attributes"] is None
    assert response_data["model_metadata"] is None
    assert response_data["metadata_version"] is None

@pytest.mark.asyncio
async def test_create_trained_model_duplicate_name_exact(async_client: AsyncClient):
    """Test creating a trained model with an exactly identical name in the same collection fails."""
    unique_collection_name = f"test-coll-tm-dup-exact-{uuid.uuid4().hex[:8]}"
    collection_info = await _create_test_collection(async_client, unique_collection_name)

    model_name = f"ExactDupModel-{uuid.uuid4().hex[:8]}"
    model_data_1 = {
        "name": model_name,
        "model_path": "/test/exact_dup1.pt",
        "collection_name": collection_info["name"],
    }
    response1 = await async_client.post("/api/v1/models", json=model_data_1, headers=AUTH_HEADERS)
    assert response1.status_code == 201, f"Failed to create first model: {response1.text}"

    model_data_2 = {
        "name": model_name, # Same name
        "model_path": "/test/exact_dup2.pt",
        "collection_name": collection_info["name"], # Same collection
    }
    response2 = await async_client.post("/api/v1/models", json=model_data_2, headers=AUTH_HEADERS)
    assert response2.status_code == 400
    response_detail = response2.json().get("detail", "").lower()
    assert "already exists" in response_detail, f"Expected 'already exists' in detail, but got: {response_detail}"

@pytest.mark.asyncio
async def test_create_trained_model_duplicate_name_case_insensitive(async_client: AsyncClient):
    """
    Test that creating a trained model with a name differing only by case within the same collection
    FAILS if the check is case-insensitive.
    NOTE: This test is expected to FAIL with the current endpoint implementation.
    """
    unique_collection_name = f"test-coll-tm-dup-ci-{uuid.uuid4().hex[:8]}"
    collection_info = await _create_test_collection(async_client, unique_collection_name)
    
    base_name = f"TestCiModel-{uuid.uuid4().hex[:8]}" # Mixed case
    model_name_mixed_case = base_name
    model_name_lower_case = base_name.lower()

    assert model_name_mixed_case != model_name_lower_case
    assert model_name_mixed_case.lower() == model_name_lower_case.lower()

    model_data_mixed = {
        "name": model_name_mixed_case,
        "model_path": "/test/ci_model_mixed.pt",
        "collection_name": collection_info["name"],
    }
    response_mixed = await async_client.post("/api/v1/models", json=model_data_mixed, headers=AUTH_HEADERS)
    assert response_mixed.status_code == 201, f"Failed to create initial mixed-case model: {response_mixed.text}"

    model_data_lower = {
        "name": model_name_lower_case,
        "model_path": "/test/ci_model_lower.pt",
        "collection_name": collection_info["name"], # Same collection
    }
    response_lower = await async_client.post("/api/v1/models", json=model_data_lower, headers=AUTH_HEADERS)

    assert response_lower.status_code == 400, \
        f"Expected 400 (duplicate) but got {response_lower.status_code}. \
        Current model name check is likely case-sensitive. Response: {response_lower.text}"
    
    response_detail = response_lower.json().get("detail", "").lower()
    assert "already exists" in response_detail, \
        f"Expected 'trained model with name ... already exists' in detail, but got: {response_detail}. \
        Current model name check is likely case-sensitive."

# Note: To make these tests fully runnable, you'll need:
# 1. A conftest.py (or similar test setup) that:
#    - Provides the `async_client` fixture, configured with your FastAPI app.
#    - Provides the `db_session` fixture if your actual endpoint interacts with the DB.
# 2. Your actual FastAPI application (`mlcbakery.main.app` or equivalent) to be importable.
# 3. The CRUD layer for `TrainedModel` to be implemented in the endpoint if you move
#    beyond testing the placeholder. 