import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from mlcbakery.models import ApiKey, Collection
from conftest import TEST_ADMIN_TOKEN

AUTH_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}

@pytest.mark.asyncio
async def test_create_api_key_with_collection_name(async_client: AsyncClient, db_session: AsyncSession):
    """Test creating an API key using collection name."""
    # Create a test collection
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create API key using collection name
    api_key_data = {
        "name": "Test API Key",
        "collection_name": collection_name
    }
    
    response = await async_client.post(
        "/api/v1/api-keys/", 
        json=api_key_data, 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test API Key"
    assert data["collection_name"] == collection_name
    assert data["collection_id"] == collection.id
    assert data["api_key"].startswith("mlc_")
    assert len(data["api_key"]) == 36  # mlc_ + 32 chars
    assert data["key_prefix"] == data["api_key"][:8]

@pytest.mark.asyncio
async def test_create_api_key_collection_not_found(async_client: AsyncClient):
    """Test creating API key for non-existent collection."""
    api_key_data = {
        "name": "Test API Key",
        "collection_name": "non-existent-collection"
    }
    
    response = await async_client.post(
        "/api/v1/api-keys/", 
        json=api_key_data, 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 404
    assert "Collection 'non-existent-collection' not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_list_api_keys_by_collection_name(async_client: AsyncClient, db_session: AsyncSession):
    """Test listing API keys using collection name."""
    # Create collection
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create API key via endpoint
    api_key_data = {"name": "Test Key", "collection_name": collection_name}
    await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    
    # List API keys by collection name
    response = await async_client.get(
        f"/api/v1/api-keys/collection/{collection_name}", 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 200
    keys = response.json()
    assert len(keys) == 1
    assert keys[0]["name"] == "Test Key"
    assert keys[0]["collection_name"] == collection_name
    assert "api_key" not in keys[0]  # Should not include actual key

@pytest.mark.asyncio
async def test_duplicate_api_key_name_in_collection(async_client: AsyncClient, db_session: AsyncSession):
    """Test that duplicate API key names in the same collection are not allowed."""
    # Create collection
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    
    # Create first API key
    api_key_data = {"name": "Duplicate Name", "collection_name": collection_name}
    response1 = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    assert response1.status_code == 200
    
    # Try to create second API key with same name
    response2 = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    assert response2.status_code == 400
    assert "already exists in collection" in response2.json()["detail"]

@pytest.mark.asyncio
async def test_case_insensitive_collection_lookup(async_client: AsyncClient, db_session: AsyncSession):
    """Test that collection name lookup is case-insensitive."""
    # Create collection with mixed case
    collection_name = f"Test-Coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    
    # Create API key using lowercase collection name
    api_key_data = {
        "name": "Test Key",
        "collection_name": collection_name.lower()
    }
    
    response = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["collection_name"] == collection_name  # Should return original case

@pytest.mark.asyncio
async def test_update_api_key(async_client: AsyncClient, db_session: AsyncSession):
    """Test updating an API key name."""
    # Setup
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    
    # Create API key
    create_response = await async_client.post(
        "/api/v1/api-keys/", 
        json={"name": "Original Name", "collection_name": collection_name}, 
        headers=AUTH_HEADERS
    )
    key_id = create_response.json()["id"]
    
    # Update API key
    update_data = {"name": "Updated Name"}
    response = await async_client.put(
        f"/api/v1/api-keys/{key_id}", 
        json=update_data, 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"

@pytest.mark.asyncio
async def test_deactivate_api_key(async_client: AsyncClient, db_session: AsyncSession):
    """Test deactivating an API key."""
    # Setup
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    
    # Create API key
    create_response = await async_client.post(
        "/api/v1/api-keys/", 
        json={"name": "Test Key", "collection_name": collection_name}, 
        headers=AUTH_HEADERS
    )
    key_id = create_response.json()["id"]
    
    # Deactivate API key
    update_data = {"is_active": False}
    response = await async_client.put(
        f"/api/v1/api-keys/{key_id}", 
        json=update_data, 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] == False

@pytest.mark.asyncio
async def test_delete_api_key(async_client: AsyncClient, db_session: AsyncSession):
    """Test deleting an API key."""
    # Setup
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create API key
    create_response = await async_client.post(
        "/api/v1/api-keys/", 
        json={"name": "Test Key", "collection_name": collection_name}, 
        headers=AUTH_HEADERS
    )
    key_id = create_response.json()["id"]
    
    # Delete API key
    response = await async_client.delete(
        f"/api/v1/api-keys/{key_id}", 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "API key deleted successfully"
    
    # Verify key is deleted
    get_response = await async_client.get(
        f"/api/v1/api-keys/{key_id}", 
        headers=AUTH_HEADERS
    )
    assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_get_api_key_details(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting details of a specific API key."""
    # Setup
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    
    # Create API key
    create_response = await async_client.post(
        "/api/v1/api-keys/", 
        json={"name": "Test Key", "collection_name": collection_name}, 
        headers=AUTH_HEADERS
    )
    key_id = create_response.json()["id"]
    
    # Get API key details
    response = await async_client.get(
        f"/api/v1/api-keys/{key_id}", 
        headers=AUTH_HEADERS
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Key"
    assert data["collection_name"] == collection_name
    assert "api_key" not in data  # Should not include actual key

@pytest.mark.asyncio
async def test_write_access_required(async_client: AsyncClient):
    """Test that non-write access users cannot access API key endpoints."""
    # Try to create API key without proper credentials 
    api_key_data = {
        "name": "Test API Key",
        "collection_name": "some-collection"
    }
    
    response = await async_client.post(
        "/api/v1/api-keys/", 
        json=api_key_data, 
        headers={"Authorization": "Bearer invalid-token"}
    )
    
    # Should be unauthorized due to invalid token
    assert response.status_code == 401
    
    # Check if response has content before trying to parse JSON
    if response.content and len(response.content) > 0:
        try:
            response_data = response.json()
            detail = response_data.get("detail", "").lower()
            assert any(keyword in detail for keyword in ["token", "unauthorized", "invalid", "missing"])
        except Exception:
            # If JSON parsing fails, just check that we got 401
            pass 