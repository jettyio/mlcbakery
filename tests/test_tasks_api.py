import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from typing import Dict, Any
import uuid

from mlcbakery.main import app
from mlcbakery.schemas.collection import CollectionCreate
from mlcbakery.auth.passthrough_strategy import sample_user_token, sample_org_token, authorization_headers

AUTH_HEADERS = authorization_headers(sample_org_token())

# TestClient for synchronous tests (for collection creation)
client = TestClient(app)

async def _create_test_collection(async_client: AsyncClient, collection_name: str) -> Dict[str, Any]:
    collection_data = CollectionCreate(name=collection_name, description="Test Collection for Tasks")
    response = await async_client.post("/api/v1/collections/", json=collection_data.model_dump(), headers=AUTH_HEADERS)
    if response.status_code == 400 and "already exists" in response.json().get("detail", ""):
        get_response = await async_client.get(f"/api/v1/collections/{collection_name}", headers=AUTH_HEADERS)
        if get_response.status_code == 200:
            return get_response.json()
        else:
            pytest.fail(f"Failed to get existing collection {collection_name}: {get_response.text}")
    assert response.status_code == 200, f"Failed to create test collection: {response.text}"
    return response.json()

def create_collection_sync(name: str):
    """Helper function to create a test collection synchronously."""
    collection_data = {
        "name": name,
        "description": "A test collection for task API testing."
    }
    response = client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response.status_code == 200, f"Failed to create collection: {response.text}"
    return response.json()

async def _create_test_task(async_client: AsyncClient, collection_name: str, task_name: str) -> Dict[str, Any]:
    """Create test task using the new collection-based endpoint."""
    task_data = {
        "name": task_name,
        "workflow": {"steps": ["initial_step"]},
    }
    response = await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)
    assert response.status_code == 201, f"Failed to create test task: {response.text}"
    return response.json()

@pytest.mark.asyncio
async def test_create_task_success(async_client: AsyncClient):
    """Test successful creation of a task."""
    unique_collection_name = f"test-coll-tasks-success-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    
    task_data = {
        "name": "My API Test Task",
        "workflow": {"steps": ["step1", "step2"]},
        "version": "1.0.0",
        "description": "A detailed description"
    }
    
    response = await async_client.post(f"/api/v1/tasks/{collection['name']}", json=task_data, headers=AUTH_HEADERS)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["name"] == task_data["name"]
    assert res_data["collection_id"] == collection["id"]
    assert res_data["has_file_uploads"] == False  # Default value
    assert "id" in res_data

@pytest.mark.asyncio
async def test_get_task_by_name_success(async_client: AsyncClient):
    """Test successfully retrieving a task by name."""
    unique_collection_name = f"test-coll-get-task-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"GetMeTask-{uuid.uuid4().hex[:8]}"
    created_task = await _create_test_task(async_client, collection["name"], task_name)

    response = await async_client.get(f"/api/v1/tasks/{collection['name']}/{task_name}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    retrieved_task = response.json()
    assert retrieved_task["id"] == created_task["id"]
    assert retrieved_task["name"] == task_name

@pytest.mark.asyncio
async def test_update_task_success(async_client: AsyncClient):
    """Test successfully updating a task using the new collection-based endpoint."""
    unique_collection_name = f"test-coll-update-task-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"UpdateMeTask-{uuid.uuid4().hex[:8]}"
    created_task = await _create_test_task(async_client, collection["name"], task_name)

    update_data = {
        "description": "An updated description.",
        "workflow": {"steps": ["step1", "step2", "updated_step"]},
        "version": "1.1.0"
    }
    # Use new collection-based update endpoint
    response = await async_client.put(f"/api/v1/tasks/{collection['name']}/{task_name}", json=update_data, headers=AUTH_HEADERS)
    assert response.status_code == 200
    updated_task = response.json()
    assert updated_task["description"] == update_data["description"]
    assert updated_task["workflow"] == update_data["workflow"]
    assert updated_task["version"] == update_data["version"]

@pytest.mark.asyncio
async def test_delete_task_by_name_success(async_client: AsyncClient):
    """Test successfully deleting a task by collection name and task name."""
    unique_collection_name = f"test-coll-delete-task-name-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"DeleteMeByNameTask-{uuid.uuid4().hex[:8]}"
    created_task = await _create_test_task(async_client, collection["name"], task_name)

    # Delete using collection_name/task_name pattern
    del_response = await async_client.delete(f"/api/v1/tasks/{collection['name']}/{task_name}", headers=AUTH_HEADERS)
    assert del_response.status_code == 200
    assert del_response.json()["message"] == "Task deleted successfully"

    # Verify it's deleted
    get_response = await async_client.get(f"/api/v1/tasks/{collection['name']}/{task_name}", headers=AUTH_HEADERS)
    assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_create_task_duplicate_name_fails(async_client: AsyncClient):
    """Test that creating a task with a duplicate name in the same collection fails."""
    unique_collection_name = f"test-coll-task-dup-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"DuplicateTask-{uuid.uuid4().hex[:8]}"
    await _create_test_task(async_client, collection["name"], task_name)

    duplicate_data = {
        "name": task_name,
        "workflow": {"steps": []},
    }
    response = await async_client.post(f"/api/v1/tasks/{collection['name']}", json=duplicate_data, headers=AUTH_HEADERS)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_task_not_found(async_client: AsyncClient):
    """Test that updating a non-existent task returns 404."""
    collection = create_collection_sync(f"test-coll-update-not-found-{uuid.uuid4().hex[:8]}")
    collection_name = collection["name"]
    
    response = await async_client.put(f"/api/v1/tasks/{collection_name}/nonexistent-task", json={"description": "wont work"}, headers=AUTH_HEADERS)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_delete_task_by_name_not_found(async_client: AsyncClient):
    """Test that deleting a non-existent task by name returns 404."""
    response = await async_client.delete("/api/v1/tasks/NonExistentCollection/NonExistentTask", headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"

@pytest.mark.asyncio
async def test_delete_task_by_name_nonexistent_collection(async_client: AsyncClient):
    """Test that deleting a task from a non-existent collection returns 404."""
    response = await async_client.delete("/api/v1/tasks/NonExistentCollection/SomeTask", headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"

@pytest.mark.asyncio
async def test_delete_task_with_entity_relationships(async_client: AsyncClient):
    """Test that deleting a task with entity relationships works correctly (cascade delete)."""
    # Create two collections for testing relationships
    unique_collection_name_1 = f"test-coll-rel-1-{uuid.uuid4().hex[:8]}"
    unique_collection_name_2 = f"test-coll-rel-2-{uuid.uuid4().hex[:8]}"
    collection_1 = await _create_test_collection(async_client, unique_collection_name_1)
    collection_2 = await _create_test_collection(async_client, unique_collection_name_2)
    
    # Create two tasks
    task_name_1 = f"SourceTask-{uuid.uuid4().hex[:8]}"
    task_name_2 = f"TargetTask-{uuid.uuid4().hex[:8]}"
    task_1 = await _create_test_task(async_client, collection_1["name"], task_name_1)
    task_2 = await _create_test_task(async_client, collection_2["name"], task_name_2)
    
    # Create an entity relationship between the tasks
    relationship_data = {
        "source_entity_str": f"task/{collection_1['name']}/{task_name_1}",
        "target_entity_str": f"task/{collection_2['name']}/{task_name_2}",
        "activity_name": "test_relationship"
    }
    rel_response = await async_client.post("/api/v1/entity-relationships/", json=relationship_data, headers=AUTH_HEADERS)
    assert rel_response.status_code == 201
    
    # Delete the source task - this should work with cascade delete
    del_response = await async_client.delete(f"/api/v1/tasks/{collection_1['name']}/{task_name_1}", headers=AUTH_HEADERS)
    assert del_response.status_code == 200
    assert del_response.json()["message"] == "Task deleted successfully"
    
    # Verify the task is deleted
    get_response = await async_client.get(f"/api/v1/tasks/{collection_1['name']}/{task_name_1}", headers=AUTH_HEADERS)
    assert get_response.status_code == 404
    
    # Verify the target task still exists
    get_response_2 = await async_client.get(f"/api/v1/tasks/{collection_2['name']}/{task_name_2}", headers=AUTH_HEADERS)
    assert get_response_2.status_code == 200

@pytest.mark.asyncio
async def test_list_tasks(async_client: AsyncClient):
    """Test listing all tasks."""
    unique_collection_name = f"test-coll-list-tasks-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    await _create_test_task(async_client, collection["name"], "Task1")
    await _create_test_task(async_client, collection["name"], "Task2")

    response = await async_client.get("/api/v1/tasks/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    tasks = response.json()
    assert isinstance(tasks, list)
    # This is a weak assertion, but confirms the endpoint works.
    # A better test would check for the specific tasks created if the DB was clean.
    assert len(tasks) >= 2 

@pytest.mark.asyncio
async def test_create_task_nonexistent_collection(async_client: AsyncClient):
    """Test creating a task in a nonexistent collection fails."""
    task_data = {
        "name": "Task In Missing Collection",
        "workflow": {"steps": ["step1"]}
    }
    
    response = await async_client.post(
        "/api/v1/tasks/nonexistent-collection", 
        json=task_data, 
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_list_tasks_by_collection(async_client: AsyncClient):
    """Test listing tasks in a specific collection."""
    # Create collection
    unique_collection_name = f"test-coll-list-by-collection-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    # Create multiple tasks
    created_tasks = []
    for i in range(2):
        task_name = f"List Test Task {i+1}-{uuid.uuid4().hex[:8]}"
        created_task = await _create_test_task(async_client, collection_name, task_name)
        created_tasks.append(created_task)
    
    # List tasks in the collection
    response = await async_client.get(f"/api/v1/tasks/{collection_name}/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 2  # Our 2 created tasks
    
    # Check that our created tasks are in the list
    task_names = [task["name"] for task in data]
    for task in created_tasks:
        assert task["name"] in task_names

@pytest.mark.asyncio
async def test_list_tasks_nonexistent_collection(async_client: AsyncClient):
    """Test listing tasks in a nonexistent collection fails."""
    response = await async_client.get("/api/v1/tasks/nonexistent-collection/", headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_task_nonexistent_collection_or_task(async_client: AsyncClient):
    """Test getting a task from nonexistent collection or nonexistent task fails."""
    # Test nonexistent collection
    response1 = await async_client.get(
        "/api/v1/tasks/nonexistent-collection/some-task", 
        headers=AUTH_HEADERS
    )
    assert response1.status_code == 404
    assert "not found" in response1.json()["detail"]
    
    # Test existing collection but nonexistent task
    unique_collection_name = f"test-coll-existing-nonexistent-task-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    response2 = await async_client.get(
        f"/api/v1/tasks/{collection_name}/nonexistent-task", 
        headers=AUTH_HEADERS
    )
    assert response2.status_code == 404
    assert "not found" in response2.json()["detail"]

@pytest.mark.asyncio
async def test_case_insensitive_task_names(async_client: AsyncClient):
    """Test that task names are case-insensitive."""
    # Create collection
    unique_collection_name = f"test-coll-case-insensitive-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    # Create task with mixed case name
    task_name = f"Case Test Task-{uuid.uuid4().hex[:8]}"
    await _create_test_task(async_client, collection_name, task_name)
    
    # Get task using different case
    response = await async_client.get(
        f"/api/v1/tasks/{collection_name}/{task_name.lower()}", 
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    
    data = response.json()
    assert data["name"] == task_name  # Original case preserved

@pytest.mark.asyncio
async def test_update_task_partial(async_client: AsyncClient):
    """Test partial update of a task."""
    # Create collection and task
    unique_collection_name = f"test-coll-partial-update-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    task_name = f"Partial Update Task-{uuid.uuid4().hex[:8]}"
    task_data = {
        "name": task_name,
        "workflow": {"steps": ["partial_step"]},
    }
    
    create_resp = await async_client.post(
        f"/api/v1/tasks/{collection_name}", 
        json=task_data, 
        headers=AUTH_HEADERS
    )
    assert create_resp.status_code == 201
    
    # Partial update - only update description
    update_data = {
        "description": "Partially updated description"
    }
    
    response = await async_client.put(
        f"/api/v1/tasks/{collection_name}/{task_name}", 
        json=update_data, 
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    
    data = response.json()
    # Updated field
    assert data["description"] == update_data["description"]
    # Unchanged fields
    assert data["name"] == task_data["name"]
    assert data["workflow"] == task_data["workflow"]

@pytest.mark.asyncio
async def test_update_task_duplicate_name(async_client: AsyncClient):
    """Test that updating a task name to an existing name in the same collection fails."""
    # Create collection
    unique_collection_name = f"test-coll-duplicate-name-update-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    # Create two tasks
    task1_name = f"Task One-{uuid.uuid4().hex[:8]}"
    task2_name = f"Task Two-{uuid.uuid4().hex[:8]}"
    await _create_test_task(async_client, collection_name, task1_name)
    await _create_test_task(async_client, collection_name, task2_name)
    
    # Try to update task2 name to task1's name
    update_data = {
        "name": task1_name  # Same as task1
    }
    
    response = await async_client.put(
        f"/api/v1/tasks/{collection_name}/{task2_name}", 
        json=update_data, 
        headers=AUTH_HEADERS
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

# Authentication requirement tests for read endpoints
@pytest.mark.asyncio
async def test_list_tasks_without_authorization(async_client: AsyncClient):
    """Test that listing tasks requires authentication."""
    # Create collection with proper auth first
    unique_collection_name = f"test-coll-auth-required-list-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    # Try to list tasks without authorization headers
    response = await async_client.get(f"/api/v1/tasks/{collection_name}/")
    assert response.status_code == 403
    assert response.json()["detail"]  # Verify there's an error detail

@pytest.mark.asyncio
async def test_get_task_without_authorization(async_client: AsyncClient):
    """Test that getting a specific task requires authentication."""
    # Create collection and task with proper auth first
    unique_collection_name = f"test-coll-auth-required-get-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    task_name = f"Auth Required Test Task-{uuid.uuid4().hex[:8]}"
    await _create_test_task(async_client, collection_name, task_name)
    
    # Try to get task without authorization headers
    response = await async_client.get(f"/api/v1/tasks/{collection_name}/{task_name}")
    assert response.status_code == 403
    assert response.json()["detail"]  # Verify there's an error detail

# Write access restriction tests
@pytest.mark.asyncio
async def test_create_task_without_write_access(async_client: AsyncClient):
    """Test that users without write access cannot create tasks."""
    # Create collection with admin access first
    unique_collection_name = f"test-coll-write-access-create-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    # Try to create task with read-only access (non-admin role)
    read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
    task_data = {
        "name": f"Unauthorized Task-{uuid.uuid4().hex[:8]}",
        "workflow": {"steps": ["unauthorized_step"]}
    }
    
    response = await async_client.post(
        f"/api/v1/tasks/{collection_name}",
        json=task_data,
        headers=read_only_headers
    )
    assert response.status_code == 403
    assert "Access level WRITE required" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_task_without_write_access(async_client: AsyncClient):
    """Test that users without write access cannot update tasks."""
    # Create collection and task with admin access
    unique_collection_name = f"test-coll-write-access-update-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    task_name = f"Update Test Task-{uuid.uuid4().hex[:8]}"
    await _create_test_task(async_client, collection_name, task_name)
    
    # Try to update task with read-only access
    read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
    update_data = {
        "description": "Updated description"
    }
    
    response = await async_client.put(
        f"/api/v1/tasks/{collection_name}/{task_name}",
        json=update_data,
        headers=read_only_headers
    )
    assert response.status_code == 403
    assert "Access level WRITE required" in response.json()["detail"]

@pytest.mark.asyncio
async def test_delete_task_without_write_access(async_client: AsyncClient):
    """Test that users without write access cannot delete tasks."""
    # Create collection and task with admin access
    unique_collection_name = f"test-coll-write-access-delete-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    collection_name = collection["name"]
    
    task_name = f"Delete Test Task-{uuid.uuid4().hex[:8]}"
    await _create_test_task(async_client, collection_name, task_name)
    
    # Try to delete task with read-only access
    read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
    
    response = await async_client.delete(
        f"/api/v1/tasks/{collection_name}/{task_name}",
        headers=read_only_headers
    )
    assert response.status_code == 403
    assert "Access level WRITE required" in response.json()["detail"]
