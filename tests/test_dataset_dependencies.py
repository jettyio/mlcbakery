import pytest
import httpx

from mlcbakery.main import app
from conftest import TEST_ADMIN_TOKEN  # Import the test token

# Define headers globally or pass them around
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}


@pytest.mark.asyncio
async def test_dataset_generation_from_another_dataset():
    """Test that a dataset can be generated from another dataset through an activity (API based)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # 0. Create a Collection first
        collection_name = "Dataset Dependency Collection"
        collection_data = {
            "name": collection_name,
            "description": "For dataset dependency test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS
        )
        assert coll_resp.status_code == 200, (
            f"Failed to create collection: {coll_resp.text}"
        )
        collection_id = coll_resp.json()["id"]

        # 1. Create source dataset (add collection_id)
        source_dataset_name = "Source Dataset API"
        source_dataset_data = {
            "name": source_dataset_name,
            "data_path": "/path/to/source/api.csv",
            "format": "csv",
            "entity_type": "dataset",
            "collection_id": collection_id,
            "metadata_version": "1.0",
            "dataset_metadata": {"description": "Original source dataset via API"},
        }
        source_resp = await ac.post(
            "/api/v1/datasets/", json=source_dataset_data, headers=AUTH_HEADERS
        )
        assert source_resp.status_code == 200, (
            f"Failed to create source dataset: {source_resp.text}"
        )
        source_dataset = source_resp.json()
        source_dataset_id = source_dataset["id"]

        # 2. Create activity linking source dataset as input
        activity_data = {
            "name": "Data Preprocessing API",
            "input_entity_ids": [source_dataset_id],
        }
        activity_resp = await ac.post(
            "/api/v1/activities/", json=activity_data, headers=AUTH_HEADERS
        )
        assert activity_resp.status_code == 200, (
            f"Failed to create activity: {activity_resp.text}"
        )
        activity = activity_resp.json()
        activity_id = activity["id"]

        # 3. Create derived dataset (add collection_id)
        derived_dataset_name = "Preprocessed Dataset API"
        derived_dataset_data = {
            "name": derived_dataset_name,
            "data_path": "/path/to/preprocessed/api.parquet",
            "format": "parquet",
            "entity_type": "dataset",
            "collection_id": collection_id,
            "metadata_version": "1.0",
            "dataset_metadata": {
                "description": "Preprocessed version via API",
                "source_dataset_id": source_dataset_id,
                "preprocessing_steps": ["normalization", "api-based generation"],
            },
        }
        derived_resp = await ac.post(
            "/api/v1/datasets/", json=derived_dataset_data, headers=AUTH_HEADERS
        )
        assert derived_resp.status_code == 200, (
            f"Failed to create derived dataset: {derived_resp.text}"
        )
        derived_dataset = derived_resp.json()
        derived_dataset["id"]

        # 5. Verify relationships by fetching data via GET requests
        get_activity_resp = await ac.get(f"/api/v1/activities/{activity_id}")
        assert get_activity_resp.status_code == 200
        updated_activity = get_activity_resp.json()

        get_source_resp = await ac.get(
            f"/api/v1/datasets/{collection_name}/{source_dataset_name}"
        )
        assert get_source_resp.status_code == 200
        get_source_resp.json()

        get_derived_resp = await ac.get(
            f"/api/v1/datasets/{collection_name}/{derived_dataset_name}"
        )
        assert get_derived_resp.status_code == 200
        updated_derived_dataset = get_derived_resp.json()

        assert source_dataset_id in updated_activity.get("input_entity_ids", [])

        assert (
            updated_derived_dataset["dataset_metadata"].get("source_dataset_id")
            == source_dataset_id
        )
