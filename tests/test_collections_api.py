import pytest
from httpx import AsyncClient
from typing import Dict, Any
import uuid
import json

from mlcbakery.main import app
from mlcbakery.schemas.collection import CollectionCreate
from mlcbakery.auth.passthrough_strategy import sample_org_token, sample_user_token, authorization_headers, ADMIN_ROLE_NAME
# Assuming conftest.py provides async_client fixture

@pytest.mark.asyncio
async def test_create_collection_success(async_client: AsyncClient):
    """Test successful creation of a new collection."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for API testing."
    }

    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    
    assert response.status_code == 200 # Collections API uses 200 for create
    response_data = response.json()
    assert response_data["name"] == collection_data["name"]
    assert response_data["description"] == collection_data["description"]
    assert "id" in response_data

@pytest.mark.asyncio
async def test_create_collection_success_for_user(async_client: AsyncClient):
    """Test successful creation of a new collection as admin."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for API testing."
    }

    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    
    assert response.status_code == 200 # Collections API uses 200 for create
    response_data = response.json()
    assert response_data["name"] == collection_data["name"]
    assert response_data["description"] == collection_data["description"]
    assert "id" in response_data

@pytest.mark.asyncio
async def test_create_collection_fails_with_member_access_level(async_client: AsyncClient):
    """Test unauthorized creation of a new collection."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for API testing."
    }

    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token("Member")))

    assert response.status_code == 403

@pytest.mark.asyncio
async def test_create_collection_duplicate_name_exact(async_client: AsyncClient):
    """Test creating a collection with an exactly identical name fails."""
    unique_name = f"test-duplicate-{uuid.uuid4().hex[:8]}"
    collection_data = {"name": unique_name, "description": "First collection"}
    
    # Create the first collection
    response1 = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert response1.status_code == 200
    
    # Attempt to create a second collection with the same name
    collection_data_dup = {"name": unique_name, "description": "Second collection with same name"}
    response2 = await async_client.post("/api/v1/collections/", json=collection_data_dup, headers=authorization_headers(sample_org_token()))
    
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
    response_mixed = await async_client.post("/api/v1/collections/", json=collection_data_mixed, headers=authorization_headers(sample_org_token()))
    assert response_mixed.status_code == 200, f"Failed to create initial mixed-case collection: {response_mixed.text}"
    
    # 2. Attempt to create another collection with the same name but in all lowercase
    collection_data_lower = {"name": collection_name_lower_case, "description": "Lowercase duplicate attempt"}
    response_lower = await async_client.post("/api/v1/collections/", json=collection_data_lower, headers=authorization_headers(sample_org_token()))
    
    # This assertion is what the user WANTS. It will fail with current code.
    assert response_lower.status_code == 400, \
        f"Expected 400 (duplicate) but got {response_lower.status_code}. \
        Current endpoint logic is likely case-sensitive. Response: {response_lower.text}"
    
    response_detail = response_lower.json().get("detail", "").lower()
    assert "already exists" in response_detail, \
        f"Expected 'already exists' in detail, but got: {response_detail}. \
        Current endpoint logic is likely case-sensitive."

@pytest.mark.asyncio
async def test_get_collection_success(async_client: AsyncClient):
    """Test successful retrieval of a collection."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for API testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Now retrieve the collection by ID
    response = await async_client.get(f"/api/v1/collections/{created_collection['name']}", headers=authorization_headers(sample_org_token()))
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == created_collection["id"]
    assert response_data["name"] == unique_name
    assert response_data["description"] == collection_data["description"]

@pytest.mark.asyncio
async def test_get_collection_storage_mismatched_owner_fails_with_404(async_client: AsyncClient):
    """Test that retrieving storage for a collection with a mismatched owner returns 404."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for API testing."
    }

    # Create the collection with one org
    create_response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(sample_org_token("Admin", "org1"))
    )
    assert create_response.status_code == 200

    # Attempt to retrieve storage with a different org's token
    response = await async_client.get(
        f"/api/v1/collections/{unique_name}/storage",
        headers=authorization_headers(sample_org_token("Admin", "org2"))
    )

    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")



@pytest.mark.asyncio
async def test_get_collection_storage_success(async_client: AsyncClient):
    """Test successful retrieval of a collection."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for API testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Now retrieve the collection by ID
    response = await async_client.get(f"/api/v1/collections/{created_collection['name']}/storage", headers=authorization_headers(sample_org_token()))
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == created_collection["id"]
    assert response_data["name"] == unique_name
    assert response_data["description"] == collection_data["description"]

@pytest.mark.asyncio
async def test_get_collection_mismatched_owner_fails_with_404(async_client: AsyncClient):
    """Test failure to retrieve a collection with an invalid token."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for API testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200

    # Now try to retrieve it with an invalid token
    response = await async_client.get(f"/api/v1/collections/{unique_name}", headers=authorization_headers(sample_user_token("user 0987")))
    
    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")

@pytest.mark.asyncio
async def test_list_collections(async_client: AsyncClient):
    """Test listing all collections."""
    # Create a couple of collections
    org1_collection_name = f"test-collection-org1"
    collection_data = {
        "name": org1_collection_name,
        "description": f"A test collection for API testing."
    }
    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org1")))

    org2_collection_name = f"test-collection-org2"
    collection_data = {
        "name": org2_collection_name,
        "description": f"A test collection for API testing."
    }
    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org2")))

    # Now list all collections
    response = await async_client.get("/api/v1/list-collections/", headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org1")))

    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 1

# TODO: Add tests for other collection endpoints (GET, LIST, PATCH storage, etc.)
# TODO: Add tests for invalid inputs (e.g., missing name) 