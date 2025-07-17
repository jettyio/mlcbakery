import pytest
from httpx import AsyncClient
import uuid

from mlcbakery.main import app
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
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org1"))
    )
    assert create_response.status_code == 200

    # Attempt to retrieve storage with a different org's token
    response = await async_client.get(
        f"/api/v1/collections/{unique_name}/storage",
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org2"))
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

@pytest.mark.asyncio
async def test_get_collection_with_admin_token(async_client, admin_token_auth_headers):
    """Test retrieving a collection using the admin token."""
    # First, create a collection
    unique_name = f"test-collection-admin-get-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for admin get."
    }
    create_response = await async_client.post(
        "/api/v1/collections/", json=collection_data, headers=admin_token_auth_headers
    )
    assert create_response.status_code == 200
    # Now, get the collection
    response = await async_client.get(
        f"/api/v1/collections/{unique_name}", headers=admin_token_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == unique_name
    assert data["description"] == collection_data["description"]

@pytest.mark.asyncio
async def test_create_collection_with_admin_token(async_client, admin_token_auth_headers):
    """Test successful creation of a new collection using the admin token."""
    unique_name = f"test-collection-admin-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection created with admin token."
    }
    response = await async_client.post(
        "/api/v1/collections/", json=collection_data, headers=admin_token_auth_headers
    )
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == collection_data["name"]
    assert response_data["description"] == collection_data["description"]
    assert "id" in response_data

@pytest.mark.asyncio
async def test_list_collections_with_admin_token(async_client, admin_token_auth_headers):
    """Test listing all collections using the admin token."""
    # Create a collection to ensure at least one exists
    unique_name = f"test-collection-admin-list-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for admin list."
    }
    await async_client.post(
        "/api/v1/collections/", json=collection_data, headers=admin_token_auth_headers
    )
    response = await async_client.get("/api/v1/list-collections/", headers=admin_token_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(coll["name"] == unique_name for coll in data)

@pytest.mark.asyncio
async def test_get_collection_storage_with_admin_token(async_client, admin_token_auth_headers):
    """Test getting collection storage properties using the admin token."""
    unique_name = f"test-collection-admin-storage-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for admin storage."
    }
    await async_client.post(
        "/api/v1/collections/", json=collection_data, headers=admin_token_auth_headers
    )
    response = await async_client.get(
        f"/api/v1/collections/{unique_name}/storage", headers=admin_token_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == unique_name

@pytest.mark.asyncio
async def test_update_collection_storage_with_admin_token(async_client, admin_token_auth_headers):
    """Test updating collection storage properties using the admin token."""
    unique_name = f"test-collection-admin-update-storage-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for admin update storage."
    }
    await async_client.post(
        "/api/v1/collections/", json=collection_data, headers=admin_token_auth_headers
    )
    update_data = {"storage_info": {"bucket": "admin-bucket"}}
    response = await async_client.patch(
        f"/api/v1/collections/{unique_name}/storage", json=update_data, headers=admin_token_auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["storage_info"] == update_data["storage_info"]

# test delete
# list datasets
# list agents
