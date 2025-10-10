"""Tests for is_private field functionality across all entity types."""

import pytest
import httpx

from mlcbakery.main import app
from mlcbakery.auth.passthrough_strategy import sample_org_token, authorization_headers


@pytest.mark.asyncio
async def test_dataset_create_with_is_private_true():
    """Test creating a dataset with is_private=True."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_data = {"name": "Private DS Test Collection", "description": "Test collection"}
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create dataset with is_private=True
        dataset_data = {
            "name": "Private Dataset",
            "data_path": "/path/to/private",
            "format": "json",
            "entity_type": "dataset",
            "is_private": True,
        }
        response = await ac.post(
            f"/api/v1/datasets/{collection_name}", json=dataset_data, headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_private"] is True


@pytest.mark.asyncio
async def test_dataset_create_with_is_private_false():
    """Test creating a dataset with is_private=False."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_data = {"name": "Public DS Test Collection", "description": "Test collection"}
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create dataset with is_private=False
        dataset_data = {
            "name": "Public Dataset",
            "data_path": "/path/to/public",
            "format": "json",
            "entity_type": "dataset",
            "is_private": False,
        }
        response = await ac.post(
            f"/api/v1/datasets/{collection_name}", json=dataset_data, headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_private"] is False


@pytest.mark.asyncio
async def test_dataset_create_without_is_private_defaults_to_true():
    """Test that is_private defaults to True (private) when not provided."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_data = {"name": "Default DS Test Collection", "description": "Test collection"}
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create dataset without is_private field
        dataset_data = {
            "name": "Default Dataset",
            "data_path": "/path/to/default",
            "format": "json",
            "entity_type": "dataset",
        }
        response = await ac.post(
            f"/api/v1/datasets/{collection_name}", json=dataset_data, headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_private"] is True


@pytest.mark.asyncio
async def test_dataset_update_is_private():
    """Test updating is_private field on an existing dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_data = {"name": "Update DS Test Collection", "description": "Test collection"}
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create dataset with is_private=False
        dataset_data = {
            "name": "Update Dataset",
            "data_path": "/path/to/update",
            "format": "json",
            "entity_type": "dataset",
            "is_private": False,
        }
        create_resp = await ac.post(
            f"/api/v1/datasets/{collection_name}", json=dataset_data, headers=authorization_headers(sample_org_token())
        )
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"]

        # Update is_private to True
        update_data = {"is_private": True}
        update_resp = await ac.put(
            f"/api/v1/datasets/{collection_name}/{dataset_name}",
            json=update_data,
            headers=authorization_headers(sample_org_token())
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["is_private"] is True


@pytest.mark.asyncio
async def test_dataset_get_returns_is_private():
    """Test that GET endpoint returns is_private field."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_data = {"name": "Get DS Test Collection", "description": "Test collection"}
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create dataset
        dataset_data = {
            "name": "Get Dataset",
            "data_path": "/path/to/get",
            "format": "json",
            "entity_type": "dataset",
            "is_private": True,
        }
        create_resp = await ac.post(
            f"/api/v1/datasets/{collection_name}", json=dataset_data, headers=authorization_headers(sample_org_token())
        )
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"]

        # Get dataset
        get_resp = await ac.get(
            f"/api/v1/datasets/{collection_name}/{dataset_name}",
            headers=authorization_headers(sample_org_token())
        )
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert "is_private" in data
        assert data["is_private"] is True


@pytest.mark.asyncio
async def test_trained_model_create_with_is_private():
    """Test creating a trained model with is_private field."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_data = {"name": "Model Test Collection", "description": "Test collection"}
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create trained model with is_private=True
        model_data = {
            "name": "Private Model",
            "model_path": "/path/to/model",
            "entity_type": "trained_model",
            "is_private": True,
        }
        response = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_private"] is True


@pytest.mark.asyncio
async def test_task_create_with_is_private():
    """Test creating a task with is_private field."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_data = {"name": "Task Test Collection", "description": "Test collection"}
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create task with is_private=True
        task_data = {
            "name": "Private Task",
            "workflow": {"steps": ["step1", "step2"]},
            "entity_type": "task",
            "is_private": True,
        }
        response = await ac.post(
            f"/api/v1/tasks/{collection_name}",
            json=task_data,
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_private"] is True


@pytest.mark.asyncio
async def test_invalid_is_private_type_rejected():
    """Test that invalid is_private values are rejected."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_data = {"name": "Invalid Test Collection", "description": "Test collection"}
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Try to create dataset with invalid is_private value
        dataset_data = {
            "name": "Invalid Dataset",
            "data_path": "/path/to/invalid",
            "format": "json",
            "entity_type": "dataset",
            "is_private": "not_a_boolean",
        }
        response = await ac.post(
            f"/api/v1/datasets/{collection_name}",
            json=dataset_data,
            headers=authorization_headers(sample_org_token())
        )
        # Pydantic should reject this with 422 Unprocessable Entity
        assert response.status_code == 422
