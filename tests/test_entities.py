import pytest
import httpx

from mlcbakery.main import app
from conftest import TEST_ADMIN_TOKEN  # Import the test token

# Define headers globally or pass them around
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}


# === Async Helper Functions for Creating Entities via API ===
async def create_test_collection(
    ac: httpx.AsyncClient, name="Test Collection API"
) -> dict:
    coll_data = {"name": name, "description": f"{name} Desc"}
    # Add headers to the request
    coll_resp = await ac.post(
        "/api/v1/collections/", json=coll_data, headers=AUTH_HEADERS
    )
    assert coll_resp.status_code == 200, (
        f"Helper failed creating collection: {coll_resp.text}"
    )
    return coll_resp.json()


async def create_test_dataset(
    ac: httpx.AsyncClient, collection_id: int, name="Test Dataset API"
) -> dict:
    dataset_data = {
        "name": name,
        "data_path": f"/path/{name.replace(' ', '_')}.csv",
        "format": "csv",
        "collection_id": collection_id,
        "entity_type": "dataset",
        "metadata_version": "1.0",
        "dataset_metadata": {"description": f"{name} Desc via API"},
    }
    # Add headers to the request
    dataset_resp = await ac.post(
        "/api/v1/datasets/", json=dataset_data, headers=AUTH_HEADERS
    )
    assert dataset_resp.status_code == 200, (
        f"Helper failed creating dataset: {dataset_resp.text}"
    )
    return dataset_resp.json()


async def create_test_agent(ac: httpx.AsyncClient, name="Test Agent API") -> dict:
    agent_data = {"name": name, "type": "API testing"}
    # Add headers to the request
    agent_resp = await ac.post("/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS)
    assert agent_resp.status_code == 200, (
        f"Helper failed creating agent: {agent_resp.text}"
    )
    return agent_resp.json()


# === Refactored Tests ===


@pytest.mark.asyncio
async def test_create_dataset():
    """Test creating a new dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create prerequisite collection
        collection = await create_test_collection(
            ac, name="Collection For Create Dataset"
        )
        collection_id = collection["id"]

        # Data for the new dataset
        dataset_data = {
            "name": "New Dataset via API",
            "data_path": "/path/to/new/api_data.csv",
            "format": "csv",
            "collection_id": collection_id,
            "entity_type": "dataset",
            "metadata_version": "1.1",
            "dataset_metadata": {"description": "New test dataset via API"},
        }
        # Add headers
        response = await ac.post(
            "/api/v1/datasets/", json=dataset_data, headers=AUTH_HEADERS
        )
        assert response.status_code == 200, f"Create dataset failed: {response.text}"
        data = response.json()
        assert data["name"] == dataset_data["name"]
        assert data["data_path"] == dataset_data["data_path"]
        assert data["format"] == dataset_data["format"]
        assert data["collection_id"] == collection_id
        assert data["entity_type"] == "dataset"
        assert data["metadata_version"] == dataset_data["metadata_version"]
        assert data["dataset_metadata"] == dataset_data["dataset_metadata"]
        assert "id" in data
        assert "created_at" in data



@pytest.mark.asyncio
async def test_list_datasets():
    """Test getting all datasets."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        collection = await create_test_collection(
            ac, name="Collection For List Datasets"
        )
        collection_id = collection["id"]
        ds1 = await create_test_dataset(ac, collection_id, name="List DS 1")
        ds2 = await create_test_dataset(ac, collection_id, name="List DS 2")

        response = await ac.get("/api/v1/datasets/")
        assert response.status_code == 200
        data = response.json()

        # Find the created datasets in the response (order might vary)
        fetched_ids = {item["id"] for item in data}
        expected_ids = {ds1["id"], ds2["id"]}
        assert expected_ids.issubset(fetched_ids), (
            f"Expected {expected_ids}, found {fetched_ids}"
        )



@pytest.mark.asyncio
async def test_get_dataset():
    """Test getting a specific dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Need collection name for the correct GET endpoint
        collection_name = "Collection For Get Dataset"
        collection = await create_test_collection(ac, name=collection_name)
        collection_id = collection["id"]
        # Need dataset name for the correct GET endpoint
        dataset_name = "Dataset To Get"
        dataset = await create_test_dataset(ac, collection_id, name=dataset_name)
        dataset_id = dataset["id"]

        # Use the name-based GET endpoint
        response = await ac.get(f"/api/v1/datasets/{collection_name}/{dataset_name}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == dataset_id
        assert data["name"] == dataset_name
        assert data["collection_id"] == collection_id


@pytest.mark.asyncio
async def test_get_nonexistent_dataset():
    """Test getting a dataset that doesn't exist."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Use the name-based GET endpoint for a non-existent entity
        response = await ac.get(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset"
        )
        assert response.status_code == 404
        # Check the detail message for "not found"
        assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_dataset():
    """Test deleting a dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Need collection name for the verification GET endpoint
        collection_name = "Collection For Delete Dataset"
        collection = await create_test_collection(ac, name=collection_name)
        collection_id = collection["id"]
        # Need dataset name for the verification GET endpoint
        dataset_name = "Dataset To Delete"
        dataset = await create_test_dataset(ac, collection_id, name=dataset_name)
        dataset_id = dataset["id"]

        # Delete the dataset - Add headers
        response_del = await ac.delete(
            f"/api/v1/datasets/{dataset_id}", headers=AUTH_HEADERS
        )
        assert response_del.status_code == 200
        assert response_del.json()["message"] == "Dataset deleted successfully"

        # Verify it's deleted using the name-based GET endpoint
        response_get = await ac.get(
            f"/api/v1/datasets/{collection_name}/{dataset_name}"
        )
        assert response_get.status_code == 404
        # Check the detail message for "not found"
        assert "not found" in response_get.json()["detail"]



@pytest.mark.asyncio
async def test_delete_nonexistent_dataset():
    """Test deleting a dataset that doesn't exist."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Add headers
        response = await ac.delete(
            "/api/v1/datasets/99999", headers=AUTH_HEADERS
        )  # Use a likely non-existent ID
        assert response.status_code == 404
        # The detail might now be "Dataset not found" instead of auth error
        # assert response.json()["detail"] == "Dataset not found"
