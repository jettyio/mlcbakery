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
    response = await async_client.get("/api/v1/collections/", headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org1")))

    assert response.status_code == 200
    response_data = response.json()
    assert isinstance(response_data, list)
    assert len(response_data) == 1

@pytest.mark.asyncio
async def test_create_collection_with_storage_info(async_client: AsyncClient):
    """Test successful creation of a collection with storage information."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection with storage info.",
        "storage_info": {
            "bucket": "my-test-bucket",
            "credentials": {"key": "value"},
            "region": "us-west-2"
        },
        "storage_provider": "aws"
    }

    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == collection_data["name"]
    assert response_data["description"] == collection_data["description"]
    assert "id" in response_data


@pytest.mark.asyncio
async def test_create_collection_with_environment_variables(async_client: AsyncClient):
    """Test successful creation of a collection with environment variables."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection with environment variables.",
        "environment_variables": {
            "API_KEY": "test-key-123",
            "DATABASE_URL": "postgresql://localhost:5432/test",
            "DEBUG": "true"
        }
    }

    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == collection_data["name"]
    assert response_data["description"] == collection_data["description"]
    assert "id" in response_data


@pytest.mark.asyncio
async def test_create_collection_with_both_storage_and_environment(async_client: AsyncClient):
    """Test successful creation of a collection with both storage info and environment variables."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection with both storage and environment.",
        "storage_info": {
            "bucket": "my-test-bucket",
            "region": "us-west-2"
        },
        "storage_provider": "aws",
        "environment_variables": {
            "API_KEY": "test-key-123",
            "ENVIRONMENT": "test"
        }
    }

    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == collection_data["name"]
    assert response_data["description"] == collection_data["description"]
    assert "id" in response_data


@pytest.mark.asyncio
async def test_update_collection_storage_success(async_client: AsyncClient):
    """Test successful update of collection storage information."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for storage testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Update storage information
    storage_data = {
        "storage_info": {
            "bucket": "updated-bucket",
            "credentials": {"api_key": "new-key"},
            "region": "eu-west-1"
        },
        "storage_provider": "gcp"
    }

    update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/storage",
        json=storage_data,
        headers=authorization_headers(sample_org_token())
    )
    
    assert update_response.status_code == 200
    response_data = update_response.json()
    assert response_data["id"] == created_collection["id"]
    assert response_data["name"] == unique_name
    assert response_data["storage_info"] == storage_data["storage_info"]
    assert response_data["storage_provider"] == storage_data["storage_provider"]


@pytest.mark.asyncio
async def test_update_collection_storage_partial_update(async_client: AsyncClient):
    """Test partial update of collection storage information."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for storage testing.",
        "storage_info": {"bucket": "original-bucket"},
        "storage_provider": "aws"
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Update only storage_provider
    storage_data = {
        "storage_provider": "azure"
    }

    update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/storage",
        json=storage_data,
        headers=authorization_headers(sample_org_token())
    )
    
    assert update_response.status_code == 200
    response_data = update_response.json()
    assert response_data["storage_provider"] == "azure"
    # storage_info should remain unchanged
    assert "storage_info" in response_data


@pytest.mark.asyncio
async def test_update_collection_storage_mismatched_owner_fails_with_404(async_client: AsyncClient):
    """Test that updating storage for a collection with a mismatched owner returns 404."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for storage testing."
    }

    # Create the collection with one org
    create_response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org1"))
    )
    assert create_response.status_code == 200

    # Attempt to update storage with a different org's token
    storage_data = {
        "storage_info": {"bucket": "updated-bucket"}
    }

    response = await async_client.patch(
        f"/api/v1/collections/{unique_name}/storage",
        json=storage_data,
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org2"))
    )

    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_update_collection_storage_fails_with_member_access_level(async_client: AsyncClient):
    """Test that updating storage fails with member access level."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for storage testing."
    }

    # Create the collection with admin access
    create_response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(sample_org_token())
    )
    assert create_response.status_code == 200

    # Attempt to update storage with member access level
    storage_data = {
        "storage_info": {"bucket": "updated-bucket"}
    }

    response = await async_client.patch(
        f"/api/v1/collections/{unique_name}/storage",
        json=storage_data,
        headers=authorization_headers(sample_org_token("Member"))
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_collection_environment_success(async_client: AsyncClient):
    """Test successful retrieval of collection environment variables."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for environment testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Now retrieve the collection environment variables
    response = await async_client.get(f"/api/v1/collections/{created_collection['name']}/environment", headers=authorization_headers(sample_org_token()))
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["id"] == created_collection["id"]
    assert response_data["name"] == unique_name
    assert response_data["description"] == collection_data["description"]
    assert "environment_variables" in response_data
    assert response_data["environment_variables"] is None  # Should be None initially


@pytest.mark.asyncio
async def test_get_collection_environment_mismatched_owner_fails_with_404(async_client: AsyncClient):
    """Test that retrieving environment variables for a collection with a mismatched owner returns 404."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for environment testing."
    }

    # Create the collection with one org
    create_response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org1"))
    )
    assert create_response.status_code == 200

    # Attempt to retrieve environment variables with a different org's token
    response = await async_client.get(
        f"/api/v1/collections/{unique_name}/environment",
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org2"))
    )

    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_update_collection_environment_success(async_client: AsyncClient):
    """Test successful update of collection environment variables."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for environment testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Update environment variables
    env_data = {
        "environment_variables": {
            "API_KEY": "secret-key-123",
            "DATABASE_URL": "postgresql://localhost:5432/test",
            "DEBUG": "true"
        }
    }

    update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/environment",
        json=env_data,
        headers=authorization_headers(sample_org_token())
    )
    
    assert update_response.status_code == 200
    response_data = update_response.json()
    assert response_data["id"] == created_collection["id"]
    assert response_data["name"] == unique_name
    assert response_data["environment_variables"] == env_data["environment_variables"]


@pytest.mark.asyncio
async def test_update_collection_environment_mismatched_owner_fails_with_404(async_client: AsyncClient):
    """Test that updating environment variables for a collection with a mismatched owner returns 404."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for environment testing."
    }

    # Create the collection with one org
    create_response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org1"))
    )
    assert create_response.status_code == 200

    # Attempt to update environment variables with a different org's token
    env_data = {
        "environment_variables": {
            "API_KEY": "secret-key-123"
        }
    }

    response = await async_client.patch(
        f"/api/v1/collections/{unique_name}/environment",
        json=env_data,
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, "org2"))
    )

    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_update_collection_environment_fails_with_member_access_level(async_client: AsyncClient):
    """Test that updating environment variables fails with member access level."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for environment testing."
    }

    # Create the collection with admin access
    create_response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(sample_org_token())
    )
    assert create_response.status_code == 200

    # Attempt to update environment variables with member access level
    env_data = {
        "environment_variables": {
            "API_KEY": "secret-key-123"
        }
    }

    response = await async_client.patch(
        f"/api/v1/collections/{unique_name}/environment",
        json=env_data,
        headers=authorization_headers(sample_org_token("Member"))
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_collection_environment_empty_variables(async_client: AsyncClient):
    """Test updating collection environment variables with empty dict."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for environment testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Update with empty environment variables
    env_data = {
        "environment_variables": {}
    }

    update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/environment",
        json=env_data,
        headers=authorization_headers(sample_org_token())
    )
    
    assert update_response.status_code == 200
    response_data = update_response.json()
    assert response_data["environment_variables"] == {}


@pytest.mark.asyncio
async def test_update_collection_environment_clear_variables(async_client: AsyncClient):
    """Test clearing collection environment variables by setting to null."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for environment testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # First set some environment variables
    env_data = {
        "environment_variables": {
            "API_KEY": "secret-key-123"
        }
    }

    update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/environment",
        json=env_data,
        headers=authorization_headers(sample_org_token())
    )
    assert update_response.status_code == 200

    # Now clear them by setting to null
    clear_data = {
        "environment_variables": None
    }

    clear_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/environment",
        json=clear_data,
        headers=authorization_headers(sample_org_token())
    )
    
    assert clear_response.status_code == 200
    response_data = clear_response.json()
    assert response_data["environment_variables"] is None


@pytest.mark.asyncio
async def test_environment_variables_with_complex_data_types(async_client: AsyncClient):
    """Test environment variables with various data types."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for complex environment testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Update with complex environment variables
    env_data = {
        "environment_variables": {
            "STRING_VAR": "simple_string",
            "NUMERIC_STRING": "12345",
            "BOOLEAN_STRING": "true",
            "JSON_CONFIG": {"nested": {"key": "value"}, "array": [1, 2, 3]},
            "EMPTY_STRING": "",
            "NULL_VALUE": None,
            "SPECIAL_CHARS": "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        }
    }

    update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/environment",
        json=env_data,
        headers=authorization_headers(sample_org_token())
    )
    
    assert update_response.status_code == 200
    response_data = update_response.json()
    assert response_data["environment_variables"] == env_data["environment_variables"]


@pytest.mark.asyncio
async def test_update_environment_variables_invalid_json_body(async_client: AsyncClient):
    """Test updating environment variables with invalid request body."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for validation testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Update with invalid body (missing environment_variables key)
    invalid_data = {
        "invalid_key": {"VAR": "value"}
    }

    update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/environment",
        json=invalid_data,
        headers=authorization_headers(sample_org_token())
    )
    
    # Should succeed but not update anything since environment_variables key is missing
    assert update_response.status_code == 200
    response_data = update_response.json()
    # environment_variables should still be None since it wasn't updated
    assert response_data["environment_variables"] is None


@pytest.mark.asyncio
async def test_get_environment_variables_nonexistent_collection(async_client: AsyncClient):
    """Test retrieving environment variables for a collection that doesn't exist."""
    nonexistent_name = f"nonexistent-collection-{uuid.uuid4().hex[:8]}"
    
    response = await async_client.get(
        f"/api/v1/collections/{nonexistent_name}/environment",
        headers=authorization_headers(sample_org_token())
    )

    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_update_environment_variables_nonexistent_collection(async_client: AsyncClient):
    """Test updating environment variables for a collection that doesn't exist."""
    nonexistent_name = f"nonexistent-collection-{uuid.uuid4().hex[:8]}"
    
    env_data = {
        "environment_variables": {"TEST": "value"}
    }

    response = await async_client.patch(
        f"/api/v1/collections/{nonexistent_name}/environment",
        json=env_data,
        headers=authorization_headers(sample_org_token())
    )

    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_get_storage_info_nonexistent_collection(async_client: AsyncClient):
    """Test retrieving storage info for a collection that doesn't exist."""
    nonexistent_name = f"nonexistent-collection-{uuid.uuid4().hex[:8]}"
    
    response = await async_client.get(
        f"/api/v1/collections/{nonexistent_name}/storage",
        headers=authorization_headers(sample_org_token())
    )

    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_update_storage_info_nonexistent_collection(async_client: AsyncClient):
    """Test updating storage info for a collection that doesn't exist."""
    nonexistent_name = f"nonexistent-collection-{uuid.uuid4().hex[:8]}"
    
    storage_data = {
        "storage_info": {"bucket": "test-bucket"}
    }

    response = await async_client.patch(
        f"/api/v1/collections/{nonexistent_name}/storage",
        json=storage_data,
        headers=authorization_headers(sample_org_token())
    )

    assert response.status_code == 404
    assert "Collection not found" in response.json().get("detail", "")


@pytest.mark.asyncio
async def test_environment_variables_persistence_after_storage_update(async_client: AsyncClient):
    """Test that environment variables persist when storage info is updated."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for persistence testing.",
        "environment_variables": {
            "PERSISTENT_VAR": "should_remain"
        }
    }

    # Create the collection with environment variables
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Update storage info
    storage_data = {
        "storage_info": {"bucket": "new-bucket"},
        "storage_provider": "aws"
    }

    storage_update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/storage",
        json=storage_data,
        headers=authorization_headers(sample_org_token())
    )
    assert storage_update_response.status_code == 200

    # Check that environment variables are still there
    env_response = await async_client.get(
        f"/api/v1/collections/{created_collection['name']}/environment",
        headers=authorization_headers(sample_org_token())
    )
    
    assert env_response.status_code == 200
    env_data = env_response.json()
    assert env_data["environment_variables"]["PERSISTENT_VAR"] == "should_remain"


@pytest.mark.asyncio
async def test_storage_info_persistence_after_environment_update(async_client: AsyncClient):
    """Test that storage info persists when environment variables are updated."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for persistence testing.",
        "storage_info": {"bucket": "persistent-bucket"},
        "storage_provider": "gcp"
    }

    # Create the collection with storage info
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()

    # Update environment variables
    env_data = {
        "environment_variables": {
            "NEW_VAR": "new_value"
        }
    }

    env_update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/environment",
        json=env_data,
        headers=authorization_headers(sample_org_token())
    )
    assert env_update_response.status_code == 200

    # Check that storage info is still there
    storage_response = await async_client.get(
        f"/api/v1/collections/{created_collection['name']}/storage",
        headers=authorization_headers(sample_org_token())
    )
    
    assert storage_response.status_code == 200
    storage_data = storage_response.json()
    assert storage_data["storage_info"]["bucket"] == "persistent-bucket"
    assert storage_data["storage_provider"] == "gcp"


@pytest.mark.asyncio
async def test_create_collection_fails_without_auth(async_client: AsyncClient):
    """Test that collection creation fails without authentication."""
    unique_name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "Should fail without auth."
    }

    response = await async_client.post("/api/v1/collections/", json=collection_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_environment_fails_without_auth(async_client: AsyncClient):
    """Test that getting environment variables fails without authentication."""
    response = await async_client.get("/api/v1/collections/some-collection/environment")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_environment_fails_without_auth(async_client: AsyncClient):
    """Test that updating environment variables fails without authentication."""
    env_data = {"environment_variables": {"TEST": "value"}}
    response = await async_client.patch("/api/v1/collections/some-collection/environment", json=env_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_storage_fails_without_auth(async_client: AsyncClient):
    """Test that getting storage info fails without authentication."""
    response = await async_client.get("/api/v1/collections/some-collection/storage")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_storage_fails_without_auth(async_client: AsyncClient):
    """Test that updating storage info fails without authentication."""
    storage_data = {"storage_info": {"bucket": "test"}}
    response = await async_client.patch("/api/v1/collections/some-collection/storage", json=storage_data)
    assert response.status_code == 401


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
    response = await async_client.get("/api/v1/collections/", headers=admin_token_auth_headers)
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

@pytest.mark.asyncio
async def test_update_collection_owner_success(async_client: AsyncClient):
    """Test successful update of collection owner identifier."""
    unique_name = f"test-collection-owner-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection for owner update testing."
    }

    # Create the collection first
    create_response = await async_client.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
    assert create_response.status_code == 200
    created_collection = create_response.json()
    
    # Verify initial owner identifier
    assert created_collection["owner_identifier"] is not None
    original_owner = created_collection["owner_identifier"]

    # Update owner identifier
    owner_data = {
        "owner_identifier": "new-owner-123"
    }

    update_response = await async_client.patch(
        f"/api/v1/collections/{created_collection['name']}/owner",
        json=owner_data,
        headers=authorization_headers(sample_org_token())
    )
    
    assert update_response.status_code == 200
    response_data = update_response.json()
    assert response_data["id"] == created_collection["id"]
    assert response_data["name"] == unique_name
    assert response_data["owner_identifier"] == owner_data["owner_identifier"]
    assert response_data["owner_identifier"] != original_owner


@pytest.mark.asyncio
async def test_admin_can_specify_owner_identifier(async_client, admin_token_auth_headers):
    """Test that admins can specify any owner_identifier when creating collections."""
    unique_name = f"test-admin-owner-{uuid.uuid4().hex[:8]}"
    custom_owner = "custom-owner-12345"
    collection_data = {
        "name": unique_name,
        "description": "A test collection with custom owner.",
        "owner_identifier": custom_owner
    }

    response = await async_client.post(
        "/api/v1/collections/", 
        json=collection_data, 
        headers=admin_token_auth_headers
    )
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == unique_name
    assert response_data["owner_identifier"] == custom_owner


@pytest.mark.asyncio
async def test_regular_user_cannot_specify_different_owner_identifier(async_client: AsyncClient):
    """Test that org admins cannot specify a different owner_identifier - it gets ignored."""
    unique_name = f"test-user-owner-{uuid.uuid4().hex[:8]}"
    attempted_owner = "malicious-owner-12345"
    collection_data = {
        "name": unique_name,
        "description": "A test collection with attempted custom owner.",
        "owner_identifier": attempted_owner  # This should be ignored
    }

    # Use an org admin token (has write access but not system admin privileges)
    response = await async_client.post(
        "/api/v1/collections/", 
        json=collection_data, 
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME))  # Org admin role
    )
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == unique_name
    # Should be set to the actual auth identifier, not the attempted one
    assert response_data["owner_identifier"] != attempted_owner
    assert response_data["owner_identifier"] == "org_12345"  # The actual org_id from the token


@pytest.mark.asyncio 
async def test_admin_owner_identifier_defaults_to_admin_when_not_specified(async_client, admin_token_auth_headers):
    """Test that when system admin doesn't specify owner_identifier, it defaults to admin identifier."""
    unique_name = f"test-admin-default-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": unique_name,
        "description": "A test collection without explicit owner."
        # No owner_identifier specified
    }

    response = await async_client.post(
        "/api/v1/collections/", 
        json=collection_data, 
        headers=admin_token_auth_headers
    )
    
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == unique_name
    assert response_data["owner_identifier"] == "admin"  # Should default to admin identifier


@pytest.mark.asyncio
async def test_only_system_admin_can_specify_custom_owner_identifier(async_client, admin_token_auth_headers):
    """Test that only system admins can specify custom owner_identifier, org admins cannot."""
    
    # Test 1: System admin can specify custom owner
    unique_name_1 = f"test-system-admin-{uuid.uuid4().hex[:8]}"
    custom_owner_1 = "custom-owner-system-admin"
    collection_data_1 = {
        "name": unique_name_1,
        "description": "System admin with custom owner.",
        "owner_identifier": custom_owner_1
    }

    response_1 = await async_client.post(
        "/api/v1/collections/", 
        json=collection_data_1, 
        headers=admin_token_auth_headers  # System admin
    )
    
    assert response_1.status_code == 200
    response_data_1 = response_1.json()
    assert response_data_1["owner_identifier"] == custom_owner_1
    
    # Test 2: Org admin cannot specify custom owner
    unique_name_2 = f"test-org-admin-{uuid.uuid4().hex[:8]}"
    attempted_custom_owner = "attempted-custom-owner"
    collection_data_2 = {
        "name": unique_name_2,
        "description": "Org admin attempting custom owner.",
        "owner_identifier": attempted_custom_owner  # This should be ignored
    }

    response_2 = await async_client.post(
        "/api/v1/collections/", 
        json=collection_data_2, 
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME))  # Org admin
    )
    
    assert response_2.status_code == 200
    response_data_2 = response_2.json()
    assert response_data_2["owner_identifier"] != attempted_custom_owner
    assert response_data_2["owner_identifier"] == "org_12345"  # Should be org identifier

# TODO: Add tests for other collection endpoints (GET, LIST, PATCH storage, etc.)
# TODO: Add tests for invalid inputs (e.g., missing name) 
# test delete
# list datasets
# list agents
