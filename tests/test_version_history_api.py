"""
Tests for version history API endpoints.

These tests verify the version history functionality for tasks (and by extension,
datasets and trained models which share similar implementations).
"""

import pytest
from httpx import AsyncClient
import uuid

from mlcbakery.main import app
from mlcbakery.schemas.collection import CollectionCreate
from mlcbakery.auth.passthrough_strategy import sample_org_token, authorization_headers

AUTH_HEADERS = authorization_headers(sample_org_token())


async def _create_test_collection(async_client: AsyncClient, collection_name: str) -> dict:
    """Create a test collection."""
    collection_data = CollectionCreate(name=collection_name, description="Test Collection for Version History")
    response = await async_client.post("/api/v1/collections/", json=collection_data.model_dump(), headers=AUTH_HEADERS)
    if response.status_code == 400 and "already exists" in response.json().get("detail", ""):
        get_response = await async_client.get(f"/api/v1/collections/{collection_name}", headers=AUTH_HEADERS)
        if get_response.status_code == 200:
            return get_response.json()
        else:
            pytest.fail(f"Failed to get existing collection {collection_name}: {get_response.text}")
    assert response.status_code == 200, f"Failed to create test collection: {response.text}"
    return response.json()


async def _create_test_task(async_client: AsyncClient, collection_name: str, task_name: str) -> dict:
    """Create a test task."""
    task_data = {
        "name": task_name,
        "workflow": {"steps": ["initial_step"]},
        "version": "1.0.0",
        "description": "Initial description",
    }
    response = await async_client.post(f"/api/v1/tasks/{collection_name}", json=task_data, headers=AUTH_HEADERS)
    assert response.status_code == 201, f"Failed to create test task: {response.text}"
    return response.json()


async def _update_test_task(async_client: AsyncClient, collection_name: str, task_name: str, update_data: dict) -> dict:
    """Update an existing task."""
    response = await async_client.put(f"/api/v1/tasks/{collection_name}/{task_name}", json=update_data, headers=AUTH_HEADERS)
    assert response.status_code == 200, f"Failed to update test task: {response.text}"
    return response.json()


# ============================================================================
# Task Version History Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_task_version_history_success(async_client: AsyncClient):
    """Test getting version history for a task."""
    unique_collection_name = f"test-version-history-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"VersionHistoryTask-{uuid.uuid4().hex[:8]}"

    # Create a task
    await _create_test_task(async_client, collection["name"], task_name)

    # Get version history
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/history",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    assert data["entity_name"] == task_name
    assert data["entity_type"] == "task"
    assert data["collection_name"] == collection["name"]
    assert data["total_versions"] >= 1
    assert len(data["versions"]) >= 1

    # Check the first version (should be the creation)
    first_version = data["versions"][0]  # Newest first
    assert "transaction_id" in first_version
    assert "index" in first_version
    # operation_type may be INSERT or None depending on database state
    assert first_version["operation_type"] in ["INSERT", None]


@pytest.mark.asyncio
async def test_get_task_version_history_with_multiple_versions(async_client: AsyncClient):
    """Test getting version history after multiple updates."""
    unique_collection_name = f"test-multi-version-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"MultiVersionTask-{uuid.uuid4().hex[:8]}"

    # Create a task
    await _create_test_task(async_client, collection["name"], task_name)

    # Update it multiple times
    await _update_test_task(async_client, collection["name"], task_name, {
        "description": "First update",
        "version": "1.1.0"
    })

    await _update_test_task(async_client, collection["name"], task_name, {
        "description": "Second update",
        "version": "1.2.0"
    })

    # Get version history
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/history",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    # Should have at least 3 versions (create + 2 updates)
    assert data["total_versions"] >= 3
    assert len(data["versions"]) >= 3

    # Versions should be in reverse chronological order (newest first)
    versions = data["versions"]
    for i in range(len(versions) - 1):
        assert versions[i]["transaction_id"] > versions[i + 1]["transaction_id"]


@pytest.mark.asyncio
async def test_get_task_version_history_with_changeset(async_client: AsyncClient):
    """Test getting version history with changeset information."""
    unique_collection_name = f"test-changeset-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"ChangesetTask-{uuid.uuid4().hex[:8]}"

    # Create a task
    await _create_test_task(async_client, collection["name"], task_name)

    # Update it
    await _update_test_task(async_client, collection["name"], task_name, {
        "description": "Updated description",
        "version": "1.1.0"
    })

    # Get version history with changeset
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/history?include_changeset=true",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    # Check that changeset is included
    for version in data["versions"]:
        assert "changeset" in version
        if version["changeset"]:
            # Changeset should contain field names
            assert isinstance(version["changeset"], dict)


@pytest.mark.asyncio
async def test_get_task_version_history_pagination(async_client: AsyncClient):
    """Test pagination of version history."""
    unique_collection_name = f"test-pagination-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"PaginationTask-{uuid.uuid4().hex[:8]}"

    # Create a task and update it multiple times
    await _create_test_task(async_client, collection["name"], task_name)

    for i in range(5):
        await _update_test_task(async_client, collection["name"], task_name, {
            "description": f"Update {i}",
            "version": f"1.{i}.0"
        })

    # Get first page
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/history?skip=0&limit=3",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    assert len(data["versions"]) == 3
    assert data["total_versions"] >= 6  # 1 create + 5 updates

    # Get second page
    response2 = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/history?skip=3&limit=3",
        headers=AUTH_HEADERS
    )

    assert response2.status_code == 200
    data2 = response2.json()

    assert len(data2["versions"]) == 3

    # Ensure no overlap between pages
    page1_ids = {v["transaction_id"] for v in data["versions"]}
    page2_ids = {v["transaction_id"] for v in data2["versions"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.asyncio
async def test_get_task_version_history_not_found(async_client: AsyncClient):
    """Test version history for non-existent task."""
    unique_collection_name = f"test-not-found-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/NonExistentTask/history",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 404


# ============================================================================
# Task Version Detail Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_task_version_by_index(async_client: AsyncClient):
    """Test getting a specific version by index reference (~0, ~-1)."""
    unique_collection_name = f"test-version-index-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"IndexTask-{uuid.uuid4().hex[:8]}"

    # Create a task
    await _create_test_task(async_client, collection["name"], task_name)

    # Update it
    await _update_test_task(async_client, collection["name"], task_name, {
        "description": "Updated description",
        "version": "2.0.0"
    })

    # Get oldest version (~0)
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/versions/~0",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    assert data["index"] == 0
    assert data["data"]["version"] == "1.0.0"  # Original version
    assert "transaction_id" in data

    # Get latest version (~-1)
    response2 = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/versions/~-1",
        headers=AUTH_HEADERS
    )

    assert response2.status_code == 200
    data2 = response2.json()

    assert data2["index"] > data["index"]  # Latest should have higher index
    assert data2["data"]["version"] == "2.0.0"  # Updated version


@pytest.mark.asyncio
async def test_get_task_version_by_hash(async_client: AsyncClient):
    """Test getting a specific version by content hash."""
    unique_collection_name = f"test-version-hash-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"HashTask-{uuid.uuid4().hex[:8]}"

    # Create a task
    await _create_test_task(async_client, collection["name"], task_name)

    # Get version history to find the hash
    history_response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/history",
        headers=AUTH_HEADERS
    )

    assert history_response.status_code == 200
    history = history_response.json()

    # Find a version with a content hash
    version_with_hash = None
    for v in history["versions"]:
        if v.get("content_hash"):
            version_with_hash = v
            break

    if version_with_hash is None:
        pytest.skip("No version with content hash found")

    content_hash = version_with_hash["content_hash"]

    # Get version by hash
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/versions/{content_hash}",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    data = response.json()

    assert data["content_hash"] == content_hash
    assert "data" in data
    assert data["data"]["name"] == task_name


@pytest.mark.asyncio
async def test_get_task_version_invalid_index(async_client: AsyncClient):
    """Test getting a version with invalid index reference."""
    unique_collection_name = f"test-invalid-index-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"InvalidIndexTask-{uuid.uuid4().hex[:8]}"

    # Create a task
    await _create_test_task(async_client, collection["name"], task_name)

    # Try to get a version with out-of-range index
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/versions/~100",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 404
    assert "out of range" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_task_version_invalid_hash(async_client: AsyncClient):
    """Test getting a version with non-existent hash."""
    unique_collection_name = f"test-invalid-hash-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"InvalidHashTask-{uuid.uuid4().hex[:8]}"

    # Create a task
    await _create_test_task(async_client, collection["name"], task_name)

    # Try to get a version with non-existent hash (64 chars)
    fake_hash = "a" * 64
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/versions/{fake_hash}",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_task_version_task_not_found(async_client: AsyncClient):
    """Test getting a version for non-existent task."""
    unique_collection_name = f"test-task-not-found-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)

    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/NonExistentTask/versions/~0",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_task_version_collection_not_found(async_client: AsyncClient):
    """Test getting a version with non-existent collection."""
    response = await async_client.get(
        "/api/v1/tasks/NonExistentCollection/SomeTask/versions/~0",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_version_data_integrity(async_client: AsyncClient):
    """Test that version data correctly captures the state at that point in time."""
    unique_collection_name = f"test-data-integrity-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"IntegrityTask-{uuid.uuid4().hex[:8]}"

    # Create a task with specific data
    original_workflow = {"steps": ["step1", "step2"]}
    task_data = {
        "name": task_name,
        "workflow": original_workflow,
        "version": "1.0.0",
        "description": "Original description",
        "has_file_uploads": False,
    }
    response = await async_client.post(
        f"/api/v1/tasks/{collection['name']}",
        json=task_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 201

    # Update to new values
    new_workflow = {"steps": ["step1", "step2", "step3"]}
    await _update_test_task(async_client, collection["name"], task_name, {
        "workflow": new_workflow,
        "version": "2.0.0",
        "description": "Updated description",
        "has_file_uploads": True,
    })

    # Get the oldest version (~0) - should have original data
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/versions/~0",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    old_version = response.json()

    assert old_version["data"]["version"] == "1.0.0"
    assert old_version["data"]["description"] == "Original description"
    assert old_version["data"]["workflow"] == original_workflow
    assert old_version["data"]["has_file_uploads"] == False

    # Get the latest version (~-1) - should have updated data
    response2 = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/versions/~-1",
        headers=AUTH_HEADERS
    )

    assert response2.status_code == 200
    new_version = response2.json()

    assert new_version["data"]["version"] == "2.0.0"
    assert new_version["data"]["description"] == "Updated description"
    assert new_version["data"]["workflow"] == new_workflow
    assert new_version["data"]["has_file_uploads"] == True


@pytest.mark.asyncio
async def test_version_history_content_hashes_unique(async_client: AsyncClient):
    """Test that different versions have different content hashes."""
    unique_collection_name = f"test-unique-hashes-{uuid.uuid4().hex[:8]}"
    collection = await _create_test_collection(async_client, unique_collection_name)
    task_name = f"UniqueHashTask-{uuid.uuid4().hex[:8]}"

    # Create a task
    await _create_test_task(async_client, collection["name"], task_name)

    # Update multiple times with different data
    for i in range(3):
        await _update_test_task(async_client, collection["name"], task_name, {
            "description": f"Update {i}",
            "version": f"1.{i + 1}.0"
        })

    # Get version history
    response = await async_client.get(
        f"/api/v1/tasks/{collection['name']}/{task_name}/history",
        headers=AUTH_HEADERS
    )

    assert response.status_code == 200
    history = response.json()

    # Collect all content hashes
    hashes = [v["content_hash"] for v in history["versions"] if v.get("content_hash")]

    # All hashes should be unique
    assert len(hashes) == len(set(hashes)), "Content hashes should be unique for different versions"
