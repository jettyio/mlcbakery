"""
Comprehensive tests for all endpoint files to achieve improved coverage.
Uses the async_client fixture for proper database session handling.
"""

import pytest
import uuid

from mlcbakery.auth.passthrough_strategy import sample_org_token, authorization_headers

AUTH_HEADERS = authorization_headers(sample_org_token())


async def create_test_collection(ac, name: str = None):
    """Helper function to create a test collection with a unique name."""
    if name is None:
        name = f"test-coverage-{uuid.uuid4().hex[:8]}"
    collection_data = {"name": name, "description": "Test collection for coverage"}
    response = await ac.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response.status_code == 200, f"Failed to create collection: {response.text}"
    return response.json()


# ============================================
# Tasks endpoint tests
# ============================================

@pytest.mark.asyncio
async def test_list_all_tasks(async_client):
    """Test listing all tasks across collections."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {
        "name": f"test-task-{uuid.uuid4().hex[:8]}",
        "workflow": {"step": "test"},
        "description": "Test task"
    }
    create_resp = await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)
    assert create_resp.status_code == 201

    response = await async_client.get("/api/v1/tasks/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_all_tasks_with_pagination(async_client):
    """Test listing all tasks with pagination parameters."""
    response = await async_client.get("/api/v1/tasks/?skip=0&limit=10", headers=AUTH_HEADERS)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_tasks_by_collection(async_client):
    """Test listing tasks in a specific collection."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    for i in range(2):
        task_data = {"name": f"list-test-task-{i}-{uuid.uuid4().hex[:6]}", "workflow": {"step": i}}
        await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(f"/api/v1/tasks/{collection_name}/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


@pytest.mark.asyncio
async def test_list_tasks_nonexistent_collection(async_client):
    """Test listing tasks in nonexistent collection returns 404."""
    response = await async_client.get("/api/v1/tasks/nonexistent-collection/", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_by_name(async_client):
    """Test getting a specific task by name."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {
        "name": f"get-task-{uuid.uuid4().hex[:8]}",
        "workflow": {"step": "test"},
        "description": "Task to get"
    }
    await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(f"/api/v1/tasks/{collection_name}/{task_data['name']}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == task_data["name"]


@pytest.mark.asyncio
async def test_get_task_nonexistent(async_client):
    """Test getting nonexistent task returns 404."""
    collection = await create_test_collection(async_client)
    response = await async_client.get(f"/api/v1/tasks/{collection['name']}/nonexistent-task", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_task(async_client):
    """Test creating a task."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {
        "name": f"new-task-{uuid.uuid4().hex[:8]}",
        "workflow": {"step": "create"},
        "version": "1.0.0",
        "description": "New task"
    }
    response = await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == task_data["name"]


@pytest.mark.asyncio
async def test_create_task_duplicate_name(async_client):
    """Test creating task with duplicate name fails."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {"name": f"duplicate-task-{uuid.uuid4().hex[:8]}", "workflow": {"step": "test"}}
    await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_task_nonexistent_collection(async_client):
    """Test creating task in nonexistent collection fails."""
    task_data = {"name": "task", "workflow": {}}
    response = await async_client.post("/api/v1/tasks/nonexistent-collection", json=task_data, headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_task(async_client):
    """Test updating a task."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {
        "name": f"update-task-{uuid.uuid4().hex[:8]}",
        "workflow": {"step": "original"},
        "description": "Original description"
    }
    await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)

    update_data = {"description": "Updated description"}
    response = await async_client.put(
        f"/api/v1/tasks/{collection_name}/{task_data['name']}",
        json=update_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_task_nonexistent(async_client):
    """Test updating nonexistent task fails."""
    collection = await create_test_collection(async_client)
    response = await async_client.put(
        f"/api/v1/tasks/{collection['name']}/nonexistent-task",
        json={"description": "test"},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_task(async_client):
    """Test deleting a task."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {"name": f"delete-task-{uuid.uuid4().hex[:8]}", "workflow": {}}
    await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.delete(f"/api/v1/tasks/{collection_name}/{task_data['name']}", headers=AUTH_HEADERS)
    assert response.status_code == 200

    get_response = await async_client.get(f"/api/v1/tasks/{collection_name}/{task_data['name']}", headers=AUTH_HEADERS)
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_nonexistent(async_client):
    """Test deleting nonexistent task fails."""
    collection = await create_test_collection(async_client)
    response = await async_client.delete(f"/api/v1/tasks/{collection['name']}/nonexistent-task", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_version_history(async_client):
    """Test getting task version history."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {"name": f"versioned-task-{uuid.uuid4().hex[:8]}", "workflow": {"v": 1}}
    await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(
        f"/api/v1/tasks/{collection_name}/{task_data['name']}/history",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_versions" in data
    assert data["total_versions"] >= 1


@pytest.mark.asyncio
async def test_task_version_by_ref(async_client):
    """Test getting task at specific version."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {"name": f"version-ref-task-{uuid.uuid4().hex[:8]}", "workflow": {}}
    await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(
        f"/api/v1/tasks/{collection_name}/{task_data['name']}/versions/~0",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


# ============================================
# Collections endpoint tests
# ============================================

@pytest.mark.asyncio
async def test_list_collections(async_client):
    """Test listing all collections."""
    await create_test_collection(async_client)

    response = await async_client.get("/api/v1/collections/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_collections_with_pagination(async_client):
    """Test listing collections with pagination."""
    response = await async_client.get("/api/v1/collections/?skip=0&limit=10", headers=AUTH_HEADERS)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_collections_invalid_pagination(async_client):
    """Test invalid pagination parameters."""
    response = await async_client.get("/api/v1/collections/?skip=-1&limit=10", headers=AUTH_HEADERS)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_collection(async_client):
    """Test getting a specific collection."""
    collection = await create_test_collection(async_client)

    response = await async_client.get(f"/api/v1/collections/{collection['name']}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == collection["name"]


@pytest.mark.asyncio
async def test_get_collection_nonexistent(async_client):
    """Test getting nonexistent collection returns 404."""
    response = await async_client.get("/api/v1/collections/nonexistent-collection", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_collection(async_client):
    """Test creating a collection."""
    collection_data = {
        "name": f"new-collection-{uuid.uuid4().hex[:8]}",
        "description": "New test collection"
    }
    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == collection_data["name"]


@pytest.mark.asyncio
async def test_create_collection_duplicate(async_client):
    """Test creating duplicate collection fails."""
    collection_data = {"name": f"dup-collection-{uuid.uuid4().hex[:8]}", "description": "Test"}
    await async_client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)

    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_collection_storage_info(async_client):
    """Test getting collection storage info."""
    collection = await create_test_collection(async_client)

    response = await async_client.get(f"/api/v1/collections/{collection['name']}/storage", headers=AUTH_HEADERS)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_collection_storage_info(async_client):
    """Test updating collection storage info."""
    collection = await create_test_collection(async_client)

    storage_data = {
        "storage_info": {"bucket": "test-bucket"},
        "storage_provider": "gcp"
    }
    response = await async_client.patch(
        f"/api/v1/collections/{collection['name']}/storage",
        json=storage_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_collection_storage_info_nonexistent(async_client):
    """Test updating storage info for nonexistent collection."""
    response = await async_client.patch(
        "/api/v1/collections/nonexistent/storage",
        json={"storage_info": {}},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_collection_environment(async_client):
    """Test getting collection environment variables."""
    collection = await create_test_collection(async_client)

    response = await async_client.get(f"/api/v1/collections/{collection['name']}/environment", headers=AUTH_HEADERS)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_collection_environment(async_client):
    """Test updating collection environment variables."""
    collection = await create_test_collection(async_client)

    env_data = {"environment_variables": {"KEY": "value"}}
    response = await async_client.patch(
        f"/api/v1/collections/{collection['name']}/environment",
        json=env_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_collection_owner(async_client):
    """Test updating collection owner."""
    collection = await create_test_collection(async_client)

    owner_data = {"owner_identifier": "new-owner"}
    response = await async_client.patch(
        f"/api/v1/collections/{collection['name']}/owner",
        json=owner_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_agents_by_collection(async_client):
    """Test listing agents in a collection."""
    collection = await create_test_collection(async_client)

    response = await async_client.get(f"/api/v1/collections/{collection['name']}/agents/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


# ============================================
# Agents endpoint tests
# ============================================

@pytest.mark.asyncio
async def test_list_agents(async_client):
    """Test listing agents in a collection."""
    collection = await create_test_collection(async_client)

    response = await async_client.get(f"/api/v1/agents/{collection['name']}/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_agents_nonexistent_collection(async_client):
    """Test listing agents in nonexistent collection."""
    response = await async_client.get("/api/v1/agents/nonexistent-collection/", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_agent(async_client):
    """Test creating an agent."""
    collection = await create_test_collection(async_client)

    agent_data = {"name": f"test-agent-{uuid.uuid4().hex[:8]}", "type": "service"}
    response = await async_client.post(f"/api/v1/agents/{collection['name']}", json=agent_data, headers=AUTH_HEADERS)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == agent_data["name"]


@pytest.mark.asyncio
async def test_create_agent_duplicate(async_client):
    """Test creating duplicate agent fails."""
    collection = await create_test_collection(async_client)

    agent_data = {"name": f"dup-agent-{uuid.uuid4().hex[:8]}", "type": "service"}
    await async_client.post(f"/api/v1/agents/{collection['name']}", json=agent_data, headers=AUTH_HEADERS)

    response = await async_client.post(f"/api/v1/agents/{collection['name']}", json=agent_data, headers=AUTH_HEADERS)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_agent_nonexistent_collection(async_client):
    """Test creating agent in nonexistent collection."""
    agent_data = {"name": "agent", "type": "service"}
    response = await async_client.post("/api/v1/agents/nonexistent-collection", json=agent_data, headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_agent_by_name(async_client):
    """Test getting an agent by name."""
    collection = await create_test_collection(async_client)

    agent_data = {"name": f"get-agent-{uuid.uuid4().hex[:8]}", "type": "service"}
    await async_client.post(f"/api/v1/agents/{collection['name']}", json=agent_data, headers=AUTH_HEADERS)

    response = await async_client.get(f"/api/v1/agents/{collection['name']}/{agent_data['name']}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == agent_data["name"]


@pytest.mark.asyncio
async def test_get_agent_nonexistent(async_client):
    """Test getting nonexistent agent."""
    collection = await create_test_collection(async_client)
    response = await async_client.get(f"/api/v1/agents/{collection['name']}/nonexistent-agent", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_agent(async_client):
    """Test updating an agent."""
    collection = await create_test_collection(async_client)

    agent_data = {"name": f"update-agent-{uuid.uuid4().hex[:8]}", "type": "service"}
    await async_client.post(f"/api/v1/agents/{collection['name']}", json=agent_data, headers=AUTH_HEADERS)

    update_data = {"type": "updated-service"}
    response = await async_client.put(
        f"/api/v1/agents/{collection['name']}/{agent_data['name']}",
        json=update_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_update_agent_nonexistent(async_client):
    """Test updating nonexistent agent."""
    collection = await create_test_collection(async_client)
    response = await async_client.put(
        f"/api/v1/agents/{collection['name']}/nonexistent-agent",
        json={"type": "new"},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent(async_client):
    """Test deleting an agent."""
    collection = await create_test_collection(async_client)

    agent_data = {"name": f"delete-agent-{uuid.uuid4().hex[:8]}", "type": "service"}
    await async_client.post(f"/api/v1/agents/{collection['name']}", json=agent_data, headers=AUTH_HEADERS)

    response = await async_client.delete(
        f"/api/v1/agents/{collection['name']}/{agent_data['name']}",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_agent_nonexistent(async_client):
    """Test deleting nonexistent agent."""
    collection = await create_test_collection(async_client)
    response = await async_client.delete(
        f"/api/v1/agents/{collection['name']}/nonexistent-agent",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


# ============================================
# Task Details endpoint tests
# ============================================

@pytest.mark.asyncio
async def test_get_task_details(async_client):
    """Test getting task details with flexible auth."""
    collection = await create_test_collection(async_client)
    collection_name = collection["name"]

    task_data = {"name": f"details-task-{uuid.uuid4().hex[:8]}", "workflow": {"step": "test"}}
    await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(
        f"/api/v1/task-details/{collection_name}/{task_data['name']}",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_task_details_nonexistent(async_client):
    """Test getting nonexistent task details."""
    collection = await create_test_collection(async_client)

    response = await async_client.get(
        f"/api/v1/task-details/{collection['name']}/nonexistent-task",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


# ============================================
# API Keys endpoint tests
# ============================================

@pytest.mark.asyncio
async def test_create_api_key(async_client):
    """Test creating an API key for a collection."""
    collection = await create_test_collection(async_client)

    api_key_data = {
        "collection_name": collection["name"],
        "name": f"test-api-key-{uuid.uuid4().hex[:8]}"
    }
    response = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert data["name"] == api_key_data["name"]


@pytest.mark.asyncio
async def test_create_api_key_nonexistent_collection(async_client):
    """Test creating API key for nonexistent collection."""
    api_key_data = {
        "collection_name": "nonexistent-collection",
        "name": "test-key"
    }
    response = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_api_key_duplicate_name(async_client):
    """Test creating API key with duplicate name fails."""
    collection = await create_test_collection(async_client)

    api_key_data = {
        "collection_name": collection["name"],
        "name": f"dup-api-key-{uuid.uuid4().hex[:8]}"
    }
    await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)

    response = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_api_keys_for_collection(async_client):
    """Test listing API keys for a collection."""
    collection = await create_test_collection(async_client)

    api_key_data = {
        "collection_name": collection["name"],
        "name": f"list-api-key-{uuid.uuid4().hex[:8]}"
    }
    await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)

    response = await async_client.get(f"/api/v1/api-keys/collection/{collection['name']}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_list_api_keys_nonexistent_collection(async_client):
    """Test listing API keys for nonexistent collection."""
    response = await async_client.get("/api/v1/api-keys/collection/nonexistent", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_api_key(async_client):
    """Test getting a specific API key."""
    collection = await create_test_collection(async_client)

    api_key_data = {
        "collection_name": collection["name"],
        "name": f"get-api-key-{uuid.uuid4().hex[:8]}"
    }
    create_response = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    created_key = create_response.json()

    response = await async_client.get(f"/api/v1/api-keys/{created_key['id']}", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == api_key_data["name"]


@pytest.mark.asyncio
async def test_get_api_key_nonexistent(async_client):
    """Test getting nonexistent API key."""
    response = await async_client.get("/api/v1/api-keys/99999", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_api_key(async_client):
    """Test updating an API key."""
    collection = await create_test_collection(async_client)

    api_key_data = {
        "collection_name": collection["name"],
        "name": f"update-api-key-{uuid.uuid4().hex[:8]}"
    }
    create_response = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    created_key = create_response.json()

    update_data = {"is_active": False}
    response = await async_client.put(f"/api/v1/api-keys/{created_key['id']}", json=update_data, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_update_api_key_name(async_client):
    """Test updating API key name."""
    collection = await create_test_collection(async_client)

    api_key_data = {
        "collection_name": collection["name"],
        "name": f"rename-api-key-{uuid.uuid4().hex[:8]}"
    }
    create_response = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    created_key = create_response.json()

    new_name = f"renamed-key-{uuid.uuid4().hex[:8]}"
    update_data = {"name": new_name}
    response = await async_client.put(f"/api/v1/api-keys/{created_key['id']}", json=update_data, headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == new_name


@pytest.mark.asyncio
async def test_update_api_key_nonexistent(async_client):
    """Test updating nonexistent API key."""
    response = await async_client.put("/api/v1/api-keys/99999", json={"is_active": False}, headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_api_key(async_client):
    """Test deleting an API key."""
    collection = await create_test_collection(async_client)

    api_key_data = {
        "collection_name": collection["name"],
        "name": f"delete-api-key-{uuid.uuid4().hex[:8]}"
    }
    create_response = await async_client.post("/api/v1/api-keys/", json=api_key_data, headers=AUTH_HEADERS)
    created_key = create_response.json()

    response = await async_client.delete(f"/api/v1/api-keys/{created_key['id']}", headers=AUTH_HEADERS)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_delete_api_key_nonexistent(async_client):
    """Test deleting nonexistent API key."""
    response = await async_client.delete("/api/v1/api-keys/99999", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ============================================
# Datasets endpoint tests (simple tests only)
# ============================================

@pytest.mark.asyncio
async def test_create_dataset_nonexistent_collection(async_client):
    """Test creating dataset in nonexistent collection."""
    dataset_data = {"name": "dataset", "data_path": "/data/test.csv"}
    response = await async_client.post("/api/v1/datasets/nonexistent-collection", json=dataset_data, headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_dataset_nonexistent(async_client):
    """Test getting nonexistent dataset."""
    collection = await create_test_collection(async_client)
    response = await async_client.get(f"/api/v1/datasets/{collection['name']}/nonexistent-dataset", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_dataset_nonexistent(async_client):
    """Test updating nonexistent dataset."""
    collection = await create_test_collection(async_client)
    response = await async_client.put(
        f"/api/v1/datasets/{collection['name']}/nonexistent-dataset",
        json={"long_description": "test"},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_dataset_nonexistent(async_client):
    """Test deleting nonexistent dataset."""
    collection = await create_test_collection(async_client)
    response = await async_client.delete(f"/api/v1/datasets/{collection['name']}/nonexistent-dataset", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_dataset_metadata_nonexistent(async_client):
    """Test updating metadata for nonexistent dataset."""
    collection = await create_test_collection(async_client)
    response = await async_client.patch(
        f"/api/v1/datasets/{collection['name']}/nonexistent/metadata",
        json={"key": "value"},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


# ============================================
# Entity Relationships endpoint tests (simple tests only)
# ============================================

@pytest.mark.asyncio
async def test_create_entity_relationship_invalid_format(async_client):
    """Test creating entity relationship with invalid entity format."""
    link_data = {
        "source_entity_str": "invalid-format",
        "target_entity_str": "also-invalid",
        "activity_name": "transform"
    }
    response = await async_client.post("/api/v1/entity-relationships/", json=link_data, headers=AUTH_HEADERS)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_entity_relationship_nonexistent_entity(async_client):
    """Test creating entity relationship with nonexistent entity."""
    link_data = {
        "source_entity_str": "dataset/nonexistent/entity",
        "target_entity_str": "dataset/nonexistent/entity2",
        "activity_name": "transform"
    }
    response = await async_client.post("/api/v1/entity-relationships/", json=link_data, headers=AUTH_HEADERS)
    assert response.status_code == 404


# ============================================
# Additional Collections tests
# ============================================


@pytest.mark.asyncio
async def test_list_datasets_by_collection_nonexistent(async_client):
    """Test listing datasets for nonexistent collection."""
    response = await async_client.get("/api/v1/collections/nonexistent/datasets/", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_collection_environment_nonexistent(async_client):
    """Test getting environment for nonexistent collection."""
    response = await async_client.get("/api/v1/collections/nonexistent/environment", headers=AUTH_HEADERS)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_collection_environment_nonexistent(async_client):
    """Test updating environment for nonexistent collection."""
    response = await async_client.patch(
        "/api/v1/collections/nonexistent/environment",
        json={"environment_variables": {}},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_collection_owner_nonexistent(async_client):
    """Test updating owner for nonexistent collection."""
    response = await async_client.patch(
        "/api/v1/collections/nonexistent/owner",
        json={"owner_identifier": "new-owner"},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_agents_by_collection_nonexistent(async_client):
    """Test listing agents for nonexistent collection from collections endpoint."""
    response = await async_client.get("/api/v1/collections/nonexistent/agents/", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ============================================
# Additional Agents tests
# ============================================

@pytest.mark.asyncio
async def test_update_agent_name_duplicate(async_client):
    """Test updating agent name to an existing name fails."""
    collection = await create_test_collection(async_client)

    # Create two agents
    agent1_data = {"name": f"agent1-{uuid.uuid4().hex[:8]}", "type": "service"}
    await async_client.post(f"/api/v1/agents/{collection['name']}", json=agent1_data, headers=AUTH_HEADERS)

    agent2_data = {"name": f"agent2-{uuid.uuid4().hex[:8]}", "type": "service"}
    await async_client.post(f"/api/v1/agents/{collection['name']}", json=agent2_data, headers=AUTH_HEADERS)

    # Try to rename agent2 to agent1's name
    response = await async_client.put(
        f"/api/v1/agents/{collection['name']}/{agent2_data['name']}",
        json={"name": agent1_data["name"]},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_agent_by_name_nonexistent_collection(async_client):
    """Test getting agent from nonexistent collection."""
    response = await async_client.get("/api/v1/agents/nonexistent-collection/some-agent", headers=AUTH_HEADERS)
    assert response.status_code == 404


# ============================================
# Additional Tasks tests
# ============================================

@pytest.mark.asyncio
async def test_update_task_name_duplicate(async_client):
    """Test updating task name to an existing name fails."""
    collection = await create_test_collection(async_client)

    task1_data = {"name": f"task1-{uuid.uuid4().hex[:8]}", "workflow": {"step": 1}}
    await async_client.post(f"/api/v1/tasks/{collection['name']}", json=task1_data, headers=AUTH_HEADERS)

    task2_data = {"name": f"task2-{uuid.uuid4().hex[:8]}", "workflow": {"step": 2}}
    await async_client.post(f"/api/v1/tasks/{collection['name']}", json=task2_data, headers=AUTH_HEADERS)

    response = await async_client.put(
        f"/api/v1/tasks/{collection['name']}/{task2_data['name']}",
        json={"name": task1_data["name"]},
        headers=AUTH_HEADERS
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_task_version_history_with_changeset(async_client):
    """Test getting task version history with changeset included."""
    collection = await create_test_collection(async_client)

    task_data = {"name": f"changeset-task-{uuid.uuid4().hex[:8]}", "workflow": {"v": 1}}
    await async_client.post(f"/api/v1/tasks/{collection['name']}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_data['name']}/history?include_changeset=true",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    if data["versions"]:
        assert "changeset" in data["versions"][0]


@pytest.mark.asyncio
async def test_task_version_by_negative_index(async_client):
    """Test getting task at specific version by negative index."""
    collection = await create_test_collection(async_client)

    task_data = {"name": f"neg-idx-task-{uuid.uuid4().hex[:8]}", "workflow": {}}
    await async_client.post(f"/api/v1/tasks/{collection['name']}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_data['name']}/versions/~-1",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_task_version_invalid_index(async_client):
    """Test getting task version with invalid index format."""
    collection = await create_test_collection(async_client)

    task_data = {"name": f"invalid-idx-task-{uuid.uuid4().hex[:8]}", "workflow": {}}
    await async_client.post(f"/api/v1/tasks/{collection['name']}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_data['name']}/versions/~abc",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_task_version_out_of_range(async_client):
    """Test getting task version with out-of-range index."""
    collection = await create_test_collection(async_client)

    task_data = {"name": f"oor-task-{uuid.uuid4().hex[:8]}", "workflow": {}}
    await async_client.post(f"/api/v1/tasks/{collection['name']}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_data['name']}/versions/~1000",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_version_nonexistent_tag(async_client):
    """Test getting task version with nonexistent tag."""
    collection = await create_test_collection(async_client)

    task_data = {"name": f"tag-task-{uuid.uuid4().hex[:8]}", "workflow": {}}
    await async_client.post(f"/api/v1/tasks/{collection['name']}", json=task_data, headers=AUTH_HEADERS)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_data['name']}/versions/v99.99.99",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_version_nonexistent_collection(async_client):
    """Test getting task version for nonexistent collection."""
    response = await async_client.get(
        "/api/v1/tasks/nonexistent-collection/some-task/versions/~0",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_version_nonexistent_task(async_client):
    """Test getting task version for nonexistent task."""
    collection = await create_test_collection(async_client)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/nonexistent-task/versions/~0",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_version_history_nonexistent_collection(async_client):
    """Test getting task history for nonexistent collection."""
    response = await async_client.get(
        "/api/v1/tasks/nonexistent-collection/some-task/history",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_version_history_nonexistent_task(async_client):
    """Test getting task history for nonexistent task."""
    collection = await create_test_collection(async_client)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/nonexistent-task/history",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404
