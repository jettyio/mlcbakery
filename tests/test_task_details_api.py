import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from mlcbakery.models import Collection, Task, ApiKey
from conftest import TEST_ADMIN_TOKEN
from mlcbakery.auth.passthrough_strategy import sample_user_token, sample_org_token, authorization_headers

AUTH_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}

@pytest.mark.asyncio
async def test_get_task_details_with_valid_api_key(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting task details with valid API key."""
    # Setup collection
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    
    # Create API key
    plaintext_key = ApiKey.generate_api_key()
    api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection.id,
        name="Test Key"
    )
    db_session.add(api_key)
    await db_session.commit()
    
    # Test API key authentication
    api_headers = {"Authorization": f"Bearer {plaintext_key}"}
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=api_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-task"
    assert data["collection_id"] == collection.id

@pytest.mark.asyncio
async def test_get_task_details_wrong_collection_api_key(async_client: AsyncClient, db_session: AsyncSession):
    """Test that API key from wrong collection is rejected."""
    # Setup two collections
    collection1_name = f"coll1-{uuid.uuid4().hex[:8]}"
    collection2_name = f"coll2-{uuid.uuid4().hex[:8]}"
    collection1 = Collection(name=collection1_name, owner_identifier="test")
    collection2 = Collection(name=collection2_name, owner_identifier="test")
    db_session.add_all([collection1, collection2])
    await db_session.commit()
    await db_session.refresh(collection1)
    await db_session.refresh(collection2)
    
    # Create task in collection1
    task = Task(
        name="test-task",
        collection_id=collection1.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    
    # Create API key for collection2
    plaintext_key = ApiKey.generate_api_key()
    api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection2.id,
        name="Wrong Collection Key"
    )
    db_session.add(api_key)
    await db_session.commit()
    
    # Try to access collection1 task with collection2 API key
    api_headers = {"Authorization": f"Bearer {plaintext_key}"}
    response = await async_client.get(
        f"/api/v1/task-details/{collection1_name}/test-task",
        headers=api_headers
    )
    
    assert response.status_code == 403
    assert "API key not valid for this collection" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_task_details_invalid_api_key(async_client: AsyncClient):
    """Test that invalid API key returns 401."""
    invalid_headers = {"Authorization": "Bearer mlc_invalid_key_12345678901234567890"}
    
    response = await async_client.get(
        "/api/v1/task-details/some-collection/some-task",
        headers=invalid_headers
    )
    
    assert response.status_code == 401
    assert "Invalid or inactive API key" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_task_details_invalid_api_key_format(async_client: AsyncClient):
    """Test that API key with wrong format returns 401."""
    invalid_headers = {"Authorization": "Bearer invalid_format_key"}
    
    response = await async_client.get(
        "/api/v1/task-details/some-collection/some-task",
        headers=invalid_headers
    )
    
    assert response.status_code == 401
    assert "Invalid API key format" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_task_details_inactive_api_key(async_client: AsyncClient, db_session: AsyncSession):
    """Test that inactive API key returns 401."""
    # Setup collection
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    
    # Create inactive API key
    plaintext_key = ApiKey.generate_api_key()
    api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection.id,
        name="Inactive Key"
    )
    api_key.is_active = False  # Deactivate the key
    db_session.add(api_key)
    await db_session.commit()
    
    # Test with inactive API key
    api_headers = {"Authorization": f"Bearer {plaintext_key}"}
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=api_headers
    )
    
    assert response.status_code == 401
    assert "Invalid or inactive API key" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_task_details_task_not_found(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting task details for non-existent task."""
    # Setup collection
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create API key
    plaintext_key = ApiKey.generate_api_key()
    api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection.id,
        name="Test Key"
    )
    db_session.add(api_key)
    await db_session.commit()
    
    # Test with non-existent task
    api_headers = {"Authorization": f"Bearer {plaintext_key}"}
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/non-existent-task",
        headers=api_headers
    )
    
    assert response.status_code == 404
    assert f"Task 'non-existent-task' not found in collection '{collection_name}'" in response.json()["detail"]

@pytest.mark.asyncio
async def test_api_key_authentication_security(async_client: AsyncClient, db_session: AsyncSession):
    """Test that API keys are properly hashed and secured."""
    # Setup collection
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create API key through endpoint
    api_key_data = {"name": "Security Test Key", "collection_name": collection_name}
    create_response = await async_client.post(
        "/api/v1/api-keys/", 
        json=api_key_data, 
        headers=AUTH_HEADERS
    )
    
    assert create_response.status_code == 200
    created_key_data = create_response.json()
    plaintext_key = created_key_data["api_key"]
    
    # Verify that the key in the database is hashed
    from sqlalchemy.future import select
    stmt = select(ApiKey).where(ApiKey.id == created_key_data["id"])
    result = await db_session.execute(stmt)
    db_api_key = result.scalar_one_or_none()
    
    assert db_api_key is not None
    assert db_api_key.key_hash != plaintext_key  # Should be hashed
    assert len(db_api_key.key_hash) == 64  # SHA-256 hash length
    assert db_api_key.key_prefix == plaintext_key[:8]  # Prefix should match
    
    # Verify the hash matches what we expect
    assert db_api_key.key_hash == ApiKey.hash_key(plaintext_key)

@pytest.mark.asyncio
async def test_get_task_details_includes_collection_environment_and_storage(async_client: AsyncClient, db_session: AsyncSession):
    """Test that task details include collection environment variables and storage info."""
    # Setup collection with environment variables and storage info
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(
        name=collection_name, 
        owner_identifier="test",
        environment_variables={
            "API_KEY": "test-key-123",
            "DATABASE_URL": "postgresql://localhost:5432/test",
            "DEBUG": "true"
        },
        storage_info={
            "bucket": "test-bucket",
            "region": "us-west-2",
            "credentials": {"access_key": "test-access"}
        },
        storage_provider="aws"
    )
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1", "step2"]},
        entity_type="task",
        description="Test task with environment variables"
    )
    db_session.add(task)
    
    # Create API key
    plaintext_key = ApiKey.generate_api_key()
    api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection.id,
        name="Environment Test Key"
    )
    db_session.add(api_key)
    await db_session.commit()
    
    # Get task details
    api_headers = {"Authorization": f"Bearer {plaintext_key}"}
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=api_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify basic task information
    assert data["name"] == "test-task"
    assert data["collection_id"] == collection.id
    assert data["workflow"] == {"steps": ["step1", "step2"]}
    assert data["description"] == "Test task with environment variables"
    
    # Verify collection environment variables are included
    assert "environment_variables" in data
    assert data["environment_variables"] is not None
    assert data["environment_variables"]["API_KEY"] == "test-key-123"
    assert data["environment_variables"]["DATABASE_URL"] == "postgresql://localhost:5432/test"
    assert data["environment_variables"]["DEBUG"] == "true"
    
    # Verify collection storage details are included
    assert "storage_info" in data
    assert data["storage_info"] is not None
    assert data["storage_info"]["bucket"] == "test-bucket"
    assert data["storage_info"]["region"] == "us-west-2"
    assert data["storage_info"]["credentials"]["access_key"] == "test-access"
    
    assert "storage_provider" in data
    assert data["storage_provider"] == "aws"

@pytest.mark.asyncio
async def test_get_task_details_null_collection_environment_and_storage(async_client: AsyncClient, db_session: AsyncSession):
    """Test that task details handle null environment variables and storage info gracefully."""
    # Setup collection without environment variables or storage info
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    collection = Collection(
        name=collection_name, 
        owner_identifier="test",
        environment_variables=None,
        storage_info=None,
        storage_provider=None
    )
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    
    # Create API key
    plaintext_key = ApiKey.generate_api_key()
    api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection.id,
        name="Null Test Key"
    )
    db_session.add(api_key)
    await db_session.commit()
    
    # Get task details
    api_headers = {"Authorization": f"Bearer {plaintext_key}"}
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=api_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify basic task information
    assert data["name"] == "test-task"
    assert data["collection_id"] == collection.id
    
    # Verify null values are handled properly
    assert "environment_variables" in data
    assert data["environment_variables"] is None
    
    assert "storage_info" in data
    assert data["storage_info"] is None
    
    assert "storage_provider" in data
    assert data["storage_provider"] is None 


# JWT Authentication Tests

@pytest.mark.asyncio
async def test_get_task_details_with_jwt_user_token_own_collection(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting task details with JWT user token for their own collection."""
    user_identifier = "test_user_123"
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    
    # Setup collection with specific owner
    collection = Collection(name=collection_name, owner_identifier=user_identifier)
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    await db_session.commit()
    
    # Test JWT authentication with user token
    jwt_token = sample_user_token(user_sub=user_identifier)
    jwt_headers = authorization_headers(jwt_token)
    
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=jwt_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-task"
    assert data["collection_id"] == collection.id


@pytest.mark.asyncio
async def test_get_task_details_with_jwt_user_token_other_collection(async_client: AsyncClient, db_session: AsyncSession):
    """Test that JWT user token cannot access other users' collections."""
    user_identifier = "test_user_123"
    other_user_identifier = "other_user_456"
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    
    # Setup collection owned by different user
    collection = Collection(name=collection_name, owner_identifier=other_user_identifier)
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    await db_session.commit()
    
    # Test JWT authentication with user token (different user)
    jwt_token = sample_user_token(user_sub=user_identifier)
    jwt_headers = authorization_headers(jwt_token)
    
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=jwt_headers
    )
    
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]


@pytest.mark.asyncio
async def test_get_task_details_with_jwt_org_admin_token(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting task details with JWT org admin token (should access all collections)."""
    user_identifier = "any_user"
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    
    # Setup collection with any owner
    collection = Collection(name=collection_name, owner_identifier="some_other_user")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    await db_session.commit()
    
    # Test JWT authentication with org admin token
    jwt_token = sample_org_token(user_sub=user_identifier)
    jwt_headers = authorization_headers(jwt_token)
    
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=jwt_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-task"
    assert data["collection_id"] == collection.id


@pytest.mark.asyncio
async def test_get_task_details_with_invalid_jwt_token(async_client: AsyncClient, db_session: AsyncSession):
    """Test getting task details with invalid JWT token."""
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    
    # Setup collection
    collection = Collection(name=collection_name, owner_identifier="test_user")
    db_session.add(collection)
    await db_session.commit()
    
    # Test with invalid JWT token
    invalid_headers = {"Authorization": "Bearer invalid_jwt_token"}
    
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=invalid_headers
    )
    
    assert response.status_code == 401
    data = response.json()
    assert "Invalid API key or JWT token" in data["detail"]


@pytest.mark.asyncio
async def test_get_task_details_jwt_with_collection_environment_and_storage(async_client: AsyncClient, db_session: AsyncSession):
    """Test that JWT auth returns collection environment variables and storage info."""
    user_identifier = "test_user_123"
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    
    # Setup collection with environment and storage info
    collection = Collection(
        name=collection_name,
        owner_identifier=user_identifier,
        environment_variables={"TEST_VAR": "test_value", "API_URL": "https://api.test.com"},
        storage_info={"bucket": "test-bucket", "region": "us-west-2"},
        storage_provider="gcp"
    )
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    await db_session.commit()
    
    # Get task details with JWT token
    jwt_token = sample_user_token(user_sub=user_identifier)
    jwt_headers = authorization_headers(jwt_token)
    
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=jwt_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-task"
    
    # Verify environment variables are included
    assert "environment_variables" in data
    assert data["environment_variables"]["TEST_VAR"] == "test_value"
    assert data["environment_variables"]["API_URL"] == "https://api.test.com"
    
    # Verify storage info is included
    assert "storage_info" in data
    assert data["storage_info"]["bucket"] == "test-bucket"
    assert data["storage_info"]["region"] == "us-west-2"
    
    assert "storage_provider" in data
    assert data["storage_provider"] == "gcp"


@pytest.mark.asyncio
async def test_get_task_details_backward_compatibility_api_key_still_works(async_client: AsyncClient, db_session: AsyncSession):
    """Test that existing API key authentication still works after JWT implementation."""
    collection_name = f"test-coll-{uuid.uuid4().hex[:8]}"
    
    # Setup collection
    collection = Collection(name=collection_name, owner_identifier="test")
    db_session.add(collection)
    await db_session.commit()
    await db_session.refresh(collection)
    
    # Create task
    task = Task(
        name="test-task",
        collection_id=collection.id,
        workflow={"steps": ["step1"]},
        entity_type="task"
    )
    db_session.add(task)
    
    # Create API key
    plaintext_key = ApiKey.generate_api_key()
    api_key = ApiKey.create_from_plaintext(
        api_key=plaintext_key,
        collection_id=collection.id,
        name="Test Key"
    )
    db_session.add(api_key)
    await db_session.commit()
    
    # Test that API key authentication still works
    api_headers = {"Authorization": f"Bearer {plaintext_key}"}
    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/test-task",
        headers=api_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test-task"
    assert data["collection_id"] == collection.id 