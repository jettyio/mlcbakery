import pytest
from httpx import AsyncClient
from typing import Dict, Any
import uuid


from mlcbakery.schemas.collection import CollectionCreate
from mlcbakery.auth.passthrough_strategy import sample_user_token, sample_org_token, authorization_headers

AUTH_HEADERS = authorization_headers(sample_org_token())

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

async def _create_test_task(async_client: AsyncClient, collection_name: str, task_name: str) -> Dict[str, Any]:
    task_data = {
        "name": task_name,
        "workflow": {"steps": ["initial_step"]},
        "collection_name": collection_name,
    }
    response = await async_client.post("/api/v1/tasks", json=task_data, headers=AUTH_HEADERS)
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
        "collection_name": collection["name"],
        "version": "1.0.0",
        "description": "A detailed description"
    }
    
    response = await async_client.post("/api/v1/tasks", json=task_data, headers=AUTH_HEADERS)
    assert response.status_code == 201
    res_data = response.json()
    assert res_data["name"] == task_data["name"]
    assert res_data["collection_id"] == collection["id"]
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
    """Test successfully updating a task."""
    unique_collection_name = f"test-coll-update-task-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"UpdateMeTask-{uuid.uuid4().hex[:8]}"
    created_task = await _create_test_task(async_client, collection["name"], task_name)

    update_data = {
        "description": "An updated description.",
        "workflow": {"steps": ["step1", "step2", "updated_step"]},
        "version": "1.1.0"
    }
    response = await async_client.put(f"/api/v1/tasks/{created_task['id']}", json=update_data, headers=AUTH_HEADERS)
    assert response.status_code == 200
    updated_task = response.json()
    assert updated_task["description"] == update_data["description"]
    assert updated_task["workflow"] == update_data["workflow"]
    assert updated_task["version"] == update_data["version"]

@pytest.mark.asyncio
async def test_delete_task_success(async_client: AsyncClient):
    """Test successfully deleting a task."""
    unique_collection_name = f"test-coll-delete-task-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"DeleteMeTask-{uuid.uuid4().hex[:8]}"
    created_task = await _create_test_task(async_client, collection["name"], task_name)

    del_response = await async_client.delete(f"/api/v1/tasks/{created_task['id']}", headers=AUTH_HEADERS)
    assert del_response.status_code == 204

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
        "collection_name": collection["name"]
    }
    response = await async_client.post("/api/v1/tasks", json=duplicate_data, headers=AUTH_HEADERS)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_task_not_found(async_client: AsyncClient):
    """Test that updating a non-existent task returns 404."""
    response = await async_client.put("/api/v1/tasks/999999", json={"description": "wont work"}, headers=AUTH_HEADERS)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_delete_task_not_found(async_client: AsyncClient):
    """Test that deleting a non-existent task returns 404."""
    response = await async_client.delete("/api/v1/tasks/999999", headers=AUTH_HEADERS)
    assert response.status_code == 404

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