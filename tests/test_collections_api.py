import pytest
from httpx import AsyncClient
from typing import Dict, Any
import uuid

from mlcbakery.schemas.collection import CollectionCreate
# Assuming conftest.py provides TEST_ADMIN_TOKEN and async_client fixture
from conftest import TEST_ADMIN_TOKEN 

AUTH_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}

@pytest.mark.asyncio
async def test_create_collection_success(async_client: AsyncClient):
    """Test successful creation of a new collection."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for API testing."
    }
    
    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    
    assert response.status_code == 200 # Collections API uses 200 for create
    response_data = response.json()
    assert response_data["name"] == collection_data["name"]
    assert response_data["description"] == collection_data["description"]
    assert "id" in response_data

@pytest.mark.asyncio
async def test_create_collection_duplicate_name_exact(async_client: AsyncClient):
    """Test creating a collection with an exactly identical name fails."""
    unique_name = f"test-duplicate-{uuid.uuid4().hex[:8]}"
    collection_data = {"name": unique_name, "description": "First collection"}
    
    # Create the first collection
    response1 = await async_client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response1.status_code == 200
    
    # Attempt to create a second collection with the same name
    collection_data_dup = {"name": unique_name, "description": "Second collection with same name"}
    response2 = await async_client.post("/api/v1/collections/", json=collection_data_dup, headers=AUTH_HEADERS)
    
    assert response2.status_code == 400
    assert "already exists" in response2.json().get("detail", "").lower()

@pytest.mark.asyncio
async def test_create_collection_duplicate_name_case_insensitive(async_client: AsyncClient):
    """
    Test that creating a collection with a name differing only by case
    FAILS if the check is case-insensitive (as desired by user).
    NOTE: This test is expected to FAIL with the current endpoint implementation,
    which uses a case-sensitive check.
    """
    base_name = f"TestCiColl-{uuid.uuid4().hex[:8]}" # Mixed case
    collection_name_mixed_case = base_name
    collection_name_lower_case = base_name.lower()

    # Ensure the names are actually different by case but same otherwise
    assert collection_name_mixed_case != collection_name_lower_case
    assert collection_name_mixed_case.lower() == collection_name_lower_case.lower()

    collection_data_mixed = {"name": collection_name_mixed_case, "description": "Mixed case collection"}
    
    # 1. Create the collection with mixed case
    response_mixed = await async_client.post("/api/v1/collections/", json=collection_data_mixed, headers=AUTH_HEADERS)
    assert response_mixed.status_code == 200, f"Failed to create initial mixed-case collection: {response_mixed.text}"
    
    # 2. Attempt to create another collection with the same name but in all lowercase
    collection_data_lower = {"name": collection_name_lower_case, "description": "Lowercase duplicate attempt"}
    response_lower = await async_client.post("/api/v1/collections/", json=collection_data_lower, headers=AUTH_HEADERS)
    
    # This assertion is what the user WANTS. It will fail with current code.
    assert response_lower.status_code == 400, \
        f"Expected 400 (duplicate) but got {response_lower.status_code}. \
        Current endpoint logic is likely case-sensitive. Response: {response_lower.text}"
    
    response_detail = response_lower.json().get("detail", "").lower()
    assert "already exists" in response_detail, \
        f"Expected 'already exists' in detail, but got: {response_detail}. \
        Current endpoint logic is likely case-sensitive."

# TODO: Add tests for other collection endpoints (GET, LIST, PATCH storage, etc.)
# TODO: Add tests for invalid inputs (e.g., missing name) 