# sqlalchemy imports, engine, sessionmaker, override_get_db, and setup_test_db fixture are now handled by conftest.py
# Keep necessary imports:
import pytest
import httpx  # Add httpx

from mlcbakery.main import app  # Keep app import if needed for client
from conftest import TEST_ADMIN_TOKEN  # Import the test token
# Model imports might still be needed if tests reference them directly
# from mlcbakery.models import ...

# Define headers globally or pass them around
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}


# Helper function to create prerequisites consistently
async def create_test_prerequisites(ac: httpx.AsyncClient, prefix: str):
    """Creates a collection, two datasets, a model, and an agent."""
    # Collection
    coll_data = {"name": f"{prefix} Collection", "description": f"{prefix} Desc"}
    coll_resp = await ac.post(
        "/api/v1/collections/", json=coll_data, headers=AUTH_HEADERS
    )
    assert coll_resp.status_code == 200
    collection_id = coll_resp.json()["id"]

    # Datasets
    ds1_data = {
        "name": f"{prefix} Dataset 1",
        "data_path": "/path/ds1.csv",
        "format": "csv",
        "collection_id": collection_id,
        "entity_type": "dataset",
    }
    ds2_data = {
        "name": f"{prefix} Dataset 2",
        "data_path": "/path/ds2.csv",
        "format": "csv",
        "collection_id": collection_id,
        "entity_type": "dataset",
    }
    ds1_resp = await ac.post("/api/v1/datasets/", json=ds1_data, headers=AUTH_HEADERS)
    ds2_resp = await ac.post("/api/v1/datasets/", json=ds2_data, headers=AUTH_HEADERS)
    assert ds1_resp.status_code == 200
    assert ds2_resp.status_code == 200
    dataset_ids = [ds1_resp.json()["id"], ds2_resp.json()["id"]]

    # Agent
    agent_data = {"name": f"{prefix} Agent", "type": "user"}
    agent_resp = await ac.post("/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS)
    assert agent_resp.status_code == 200
    agent_id = agent_resp.json()["id"]

    return {"dataset_ids": dataset_ids, "agent_id": agent_id}



@pytest.mark.asyncio
async def test_delete_nonexistent_activity():
    """Test deleting an activity that doesn't exist."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.delete("/api/v1/activities/99999", headers=AUTH_HEADERS)
        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"
