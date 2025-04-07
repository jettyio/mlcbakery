import pytest
from datetime import datetime
import asyncio
import httpx

from mlcbakery.models import Base, Dataset, Activity, Entity
from mlcbakery.main import app

@pytest.mark.asyncio
async def test_dataset_generation_from_another_dataset():
    """Test that a dataset can be generated from another dataset through an activity (API based)."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as ac:
        # 1. Create source dataset
        source_dataset_data = {
            "name": "Source Dataset API",
            "data_path": "/path/to/source/api.csv",
            "format": "csv",
            "entity_type": "dataset",
            "metadata_version": "1.0",
            "dataset_metadata": {"description": "Original source dataset via API"},
        }
        source_resp = await ac.post("/api/v1/datasets/", json=source_dataset_data)
        assert source_resp.status_code == 200, f"Failed to create source dataset: {source_resp.text}"
        source_dataset = source_resp.json()
        source_dataset_id = source_dataset["id"]

        # 2. Create activity linking source dataset as input
        activity_data = {
            "name": "Data Preprocessing API",
            "input_entity_ids": [source_dataset_id],
        }
        activity_resp = await ac.post("/api/v1/activities/", json=activity_data)
        assert activity_resp.status_code == 200, f"Failed to create activity: {activity_resp.text}"
        activity = activity_resp.json()
        activity_id = activity["id"]

        # 3. Create derived dataset
        derived_dataset_data = {
            "name": "Preprocessed Dataset API",
            "data_path": "/path/to/preprocessed/api.parquet",
            "format": "parquet",
            "entity_type": "dataset",
            "metadata_version": "1.0",
            "dataset_metadata": {
                "description": "Preprocessed version via API",
                "source_dataset_id": source_dataset_id,
                "preprocessing_steps": ["normalization", "api-based generation"],
            },
        }
        derived_resp = await ac.post("/api/v1/datasets/", json=derived_dataset_data)
        assert derived_resp.status_code == 200, f"Failed to create derived dataset: {derived_resp.text}"
        derived_dataset = derived_resp.json()
        derived_dataset_id = derived_dataset["id"]

        # 5. Verify relationships by fetching data via GET requests
        get_activity_resp = await ac.get(f"/api/v1/activities/{activity_id}")
        assert get_activity_resp.status_code == 200
        updated_activity = get_activity_resp.json()

        get_source_resp = await ac.get(f"/api/v1/datasets/{source_dataset_id}")
        assert get_source_resp.status_code == 200
        updated_source_dataset = get_source_resp.json()

        get_derived_resp = await ac.get(f"/api/v1/datasets/{derived_dataset_id}")
        assert get_derived_resp.status_code == 200
        updated_derived_dataset = get_derived_resp.json()

        assert source_dataset_id in updated_activity.get("input_entity_ids", [])

        assert (
            updated_derived_dataset["dataset_metadata"].get("source_dataset_id") == source_dataset_id
        )
