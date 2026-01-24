# sqlalchemy sync imports, engine, sessionmaker, override_get_db, and fixture are now handled by conftest.py
# Keep necessary imports:
import pytest
import base64
import httpx
import uuid
from unittest.mock import MagicMock

from mlcbakery.main import app  # Keep app import if needed for client
from mlcbakery.auth.passthrough_strategy import sample_org_token, sample_user_token, authorization_headers, ADMIN_ROLE_NAME
from mlcbakery import search

# Tests start here, marked as async and using local async client
# Helper for creating a dataset using the new API
async def create_dataset_v2(ac, collection_name, dataset_data):
    return await ac.post(
        f"/api/v1/datasets/{collection_name}", json=dataset_data, headers=authorization_headers(sample_org_token())
    )


@pytest.mark.asyncio
async def test_create_dataset():
    """Test creating a new dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create prerequisite collection for isolation
        collection_data = {
            "name": "Create DS Collection Async",
            "description": "For create_dataset test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200, (
            f"Failed to create prerequisite collection: {coll_resp.text}"
        )
        collection_name_to_use = coll_resp.json()["name"]

        dataset_data = {
            "name": "New Dataset Async",
            "data_path": "/path/to/data3/async",
            "format": "json",
            "entity_type": "dataset",
            "metadata_version": "1.0",
            "dataset_metadata": {
                "description": "New async test dataset",
                "tags": ["new", "async"],
            },
        }
        response = await create_dataset_v2(ac, collection_name_to_use, dataset_data)
        assert response.status_code == 200, (
            f"Failed with {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["name"] == dataset_data["name"]
        assert data["data_path"] == dataset_data["data_path"]
        assert data["format"] == dataset_data["format"]
        assert data["entity_type"] == dataset_data["entity_type"]
        assert data["metadata_version"] == dataset_data["metadata_version"]
        assert data["dataset_metadata"] == dataset_data["dataset_metadata"]
        assert "id" in data
        assert "created_at" in data


@pytest.mark.asyncio
async def test_list_datasets():
    """Test getting all datasets."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a known collection first
        collection_data = {
            "name": "List DS Collection",
            "description": "For list ds test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name_to_use = coll_resp.json()["name"]

        # Create some known datasets first to ensure test isolation
        datasets_to_create = [
            {
                "name": "List Dataset 1",
                "data_path": "/list/1",
                "format": "csv",
                "entity_type": "dataset",
            },
            {
                "name": "List Dataset 2",
                "data_path": "/list/2",
                "format": "parquet",
                "entity_type": "dataset",
            },
        ]
        created_ids = []
        for ds_data in datasets_to_create:
            resp = await create_dataset_v2(ac, collection_name_to_use, ds_data)
            assert resp.status_code == 200
            created_ids.append(resp.json()["id"])

        response = await ac.get(f"/api/v1/datasets/{collection_name_to_use}", headers=authorization_headers(sample_org_token()))
        assert response.status_code == 200
        data = response.json()
        # Check that *at least* the datasets we created are present
        fetched_ids = {item["id"] for item in data}
        assert set(created_ids).issubset(fetched_ids)

        # Optional: Verify specific data points if needed, comparing against datasets_to_create


@pytest.mark.asyncio
async def test_list_datasets_pagination():
    """Test pagination of datasets."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a known collection first
        collection_data = {
            "name": "Paginate DS Collection Async",
            "description": "For paginate_datasets test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name_to_use = coll_resp.json()["name"]

        # Create known datasets for pagination test
        base_name = "PaginateDSAsync"
        datasets_to_create = [
            {
                "name": f"{base_name}_{i}",
                "data_path": f"/paginate/a{i}",
                "format": "csv",
                "entity_type": "dataset",
            }
            for i in range(5)  # Create 5 datasets
        ]
        # start by deleting any existing datasets with this base name
        response = await ac.get(f"/api/v1/datasets/{collection_name_to_use}?name={base_name}", headers=authorization_headers(sample_org_token()))
        assert response.status_code == 200
        existing_datasets = response.json()
        for ds in existing_datasets:
            delete_resp = await ac.delete(
                f"/api/v1/datasets/{collection_name_to_use}/{ds['name']}", headers=authorization_headers(sample_org_token())
            )
            assert delete_resp.status_code == 200

        created_ids = []
        for ds_data in datasets_to_create:
            resp = await create_dataset_v2(ac, collection_name_to_use, ds_data)
            assert resp.status_code == 200, (
                f"Failed creating {ds_data['name']}: {resp.text}"
            )
            created_ids.append(resp.json()["id"])

        # Fetch with skip and limit
        response = await ac.get(f"/api/v1/datasets/{collection_name_to_use}?skip=2&limit=2", headers=authorization_headers(sample_org_token()))
        assert response.status_code == 200
        paginated_data = response.json()
        assert len(paginated_data) == 2

        # Verify the *IDs* returned match the expected slice of IDs created *in this test*
        sorted_created_ids = sorted(created_ids)
        if len(sorted_created_ids) >= 4:
            expected_ids = sorted_created_ids[2:4]  # 3rd and 4th created IDs
            fetched_ids = [d["id"] for d in paginated_data]
            assert fetched_ids == expected_ids, (
                f"Expected IDs {expected_ids} but got {fetched_ids}"
            )
        else:
            pytest.fail("Less than 4 datasets created for pagination check")

        # Optional: Verify names if IDs match (more robust check)
        # fetched_names = [d["name"] for d in paginated_data]
        # expected_names = [f"{base_name}_{i}" for i in [2, 3]] # Assuming IDs correspond to indices 2, 3
        # assert fetched_names == expected_names


@pytest.mark.asyncio
async def test_get_dataset():
    """Test getting a specific dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": "Get DS Collection",
            "description": "For get ds test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name_to_use = collection_data["name"]  # Get collection name
        # Create a dataset to get
        ds_data = {
            "name": "GetMeDS",
            "data_path": "/get/me",
            "format": "json",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name_to_use, ds_data)
        assert create_resp.status_code == 200
        dataset_name = ds_data["name"]  # Get dataset name

        # Then get the specific dataset by name (canonical endpoint)
        response = await ac.get(
            f"/api/v1/datasets/{collection_name_to_use}/{dataset_name}",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == ds_data["name"]
        assert data["data_path"] == ds_data["data_path"]
        assert data["format"] == ds_data["format"]
        assert data["entity_type"] == ds_data["entity_type"]


@pytest.mark.asyncio
async def test_get_nonexistent_dataset():
    """Test getting a dataset that doesn't exist."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Use the name-based GET for a nonexistent dataset/collection
        response = await ac.get(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 404
        # The error message might differ slightly, check for "not found"
        assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_dataset():
    """Test updating a dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": "Update DS Collection",
            "description": "For update ds test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name_to_use = collection_data["name"]  # Get collection name
        # Create a dataset to update
        ds_data = {
            "name": "UpdateMeDS",
            "data_path": "/update/me",
            "format": "csv",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name_to_use, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"] # Get dataset name

        # Update the dataset
        update_data = {
            "name": "Updated Dataset Async",
            "data_path": "/path/to/updated/data_async",
            "format": "json",
            "entity_type": "dataset",  # Should remain dataset
            "metadata_version": "2.0",
            "dataset_metadata": {
                "description": "Updated async test dataset",
                "tags": ["updated", "async"],
            },
        }
        response = await ac.put(
            f"/api/v1/datasets/{collection_name_to_use}/{dataset_name}", json=update_data, headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 200, (
            f"Failed with {response.status_code}: {response.text}"
        )
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["data_path"] == update_data["data_path"]
        assert data["format"] == update_data["format"]
        assert data["entity_type"] == update_data["entity_type"]
        assert data["metadata_version"] == update_data["metadata_version"]
        assert data["dataset_metadata"] == update_data["dataset_metadata"]


@pytest.mark.asyncio
async def test_update_nonexistent_dataset():
    """Test updating a dataset that doesn't exist."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        update_data = {
            "name": "Updated Dataset Fail",
            "data_path": "/update/fail",
            "format": "csv",
            "entity_type": "dataset",
        }
        response = await ac.put(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset", json=update_data, headers=authorization_headers(sample_org_token())
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"


@pytest.mark.asyncio
async def test_delete_dataset():
    """Test deleting a dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": "Delete DS Collection",
            "description": "For delete ds test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name_to_use = collection_data["name"]  # Get collection name
        # Create a dataset to delete
        ds_data = {
            "name": "DeleteMeDS",
            "data_path": "/delete/me",
            "format": "txt",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name_to_use, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"] # Get dataset name

        # Delete the dataset (still uses ID)
        delete_response = await ac.delete(
            f"/api/v1/datasets/{collection_name_to_use}/{dataset_name}", headers=authorization_headers(sample_org_token())
        )
        assert delete_response.status_code == 200
        assert delete_response.json()["message"] == "Dataset deleted successfully"

        # Verify it's deleted using the name-based GET
        get_response = await ac.get(
            f"/api/v1/datasets/{collection_name_to_use}/{dataset_name}",
            headers=authorization_headers(sample_org_token())
        )  # Use name-based GET
        assert get_response.status_code == 404
        # Check for "not found" in the detail message
        assert "not found" in get_response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_nonexistent_dataset():
    """Test deleting a dataset that doesn't exist."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.delete("/api/v1/datasets/NonExistentCollection/NonExistentDataset", headers=authorization_headers(sample_org_token()))
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"


@pytest.mark.asyncio
async def test_update_dataset_metadata():
    """Test updating only the metadata of a dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": "Meta Update DS Collection",
            "description": "For meta update ds test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name_to_use = collection_data["name"]  # Get collection name
        # Create a dataset
        ds_data = {
            "name": "MetadataUpdateDS",
            "data_path": "/metadata/update",
            "format": "csv",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name_to_use, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"] # Get dataset name

        # Update only metadata
        metadata_update = {
            "metadata_version": "1.1",
            "dataset_metadata": {"author": "Test Author", "license": "MIT"},
        }
        response = await ac.patch(
            f"/api/v1/datasets/{collection_name_to_use}/{dataset_name}/metadata",
            json=metadata_update,
            headers=authorization_headers(sample_org_token()),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == ds_data["name"]  # Name should be unchanged
        assert (
            data["dataset_metadata"]["dataset_metadata"]
            == metadata_update["dataset_metadata"]
        )


@pytest.mark.asyncio
async def test_update_metadata_nonexistent_dataset():
    """Test updating metadata of a nonexistent dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        metadata_update = {
            "metadata_version": "1.1",
            "dataset_metadata": {"author": "Test Author"},
        }
        response = await ac.patch(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset/metadata",
            json=metadata_update,
            headers=authorization_headers(sample_org_token()),
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Dataset not found"


@pytest.mark.asyncio
async def test_invalid_pagination():
    """Test invalid pagination parameters (negative skip/limit)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection first since the endpoint now requires a collection name
        collection_data = {
            "name": "Invalid Pagination Collection",
            "description": "For invalid pagination test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = collection_data["name"]

        response_skip = await ac.get(
            f"/api/v1/datasets/{collection_name}?skip=-1&limit=10",
            headers=authorization_headers(sample_org_token())
        )
        assert response_skip.status_code == 400  # FastAPI validation error

        response_limit = await ac.get(
            f"/api/v1/datasets/{collection_name}?skip=0&limit=-1",
            headers=authorization_headers(sample_org_token())
        )
        assert response_limit.status_code == 400  # FastAPI validation error


@pytest.mark.asyncio
async def test_update_dataset_preview():
    """Test updating the preview of a dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection and dataset first
        collection_data = {
            "name": "Preview Update DS Collection Async",
            "description": "For update_preview test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name_to_use = collection_data["name"]  # Get collection name
        ds_data = {
            "name": "PreviewUpdateDSAsync",
            "data_path": "/preview/updatea",
            "format": "csv",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name_to_use, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"] # Get dataset name

        # 1. Prepare file details
        preview_content = b"Sample preview content async"
        preview_type = "text/plain"
        file_name = "preview.txt"  # Can be anything reasonable
        preview_update_body = base64.b64encode(preview_content).decode("utf-8")
        # 2. Create the 'files' dictionary
        #    The key 'preview_update' MUST match the endpoint parameter name
        files_data = {"preview_update": (file_name, preview_update_body, preview_type)}

        # 3. Make the PUT request using the 'files' parameter
        response = await ac.put(
            f"/api/v1/datasets/{collection_name_to_use}/{dataset_name}/preview",
            files=files_data,
            headers=authorization_headers(sample_org_token()),
        )

        # 4. Assertions...
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["preview_type"] == preview_type
        assert data["name"] == ds_data["name"]


@pytest.mark.asyncio
async def test_update_nonexistent_dataset_preview():
    """Test updating preview of a nonexistent dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        preview_content = b"Sample preview content"
        preview_base64 = base64.b64encode(preview_content).decode("utf-8")
        preview_type = "text/plain"
        preview_data = {"preview": preview_base64, "preview_type": preview_type}
        response = await ac.patch(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset/preview", json=preview_data, headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 405


@pytest.mark.asyncio
async def test_get_nonexistent_dataset_preview():
    """Test getting preview of a nonexistent dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset/preview",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_missing_preview():
    """Test getting preview for a dataset that has none."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": "Missing Preview DS Collection",
            "description": "For missing preview ds test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name_to_use = collection_data["name"]
        # Create a dataset without a preview
        ds_data = {
            "name": "NoPreviewDS",
            "data_path": "/no/preview",
            "format": "csv",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name_to_use, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"] # Get dataset name

        response = await ac.get(
            f"/api/v1/datasets/{collection_name_to_use}/{dataset_name}/preview",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_dataset_duplicate_name_case_insensitive():
    """
    Test that creating a dataset with a name differing only by case within the same collection
    FAILS if the check is case-insensitive.
    NOTE: This test is expected to FAIL with the current endpoint implementation.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Create a unique collection for this test
        collection_name = f"TestCiDsColl-{uuid.uuid4().hex[:8]}"
        collection_data = {"name": collection_name, "description": "Collection for CI dataset name test"}
        coll_resp = await ac.post("/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token()))
        assert coll_resp.status_code == 200, f"Failed to create prerequisite collection: {coll_resp.text}"
        collection_name = collection_data["name"]

        # 2. Create the first dataset with a mixed-case name
        base_name = f"TestCiDs-{uuid.uuid4().hex[:8]}"
        dataset_name_mixed_case = base_name
        dataset_data_mixed = {
            "name": dataset_name_mixed_case,
            "data_path": "/path/to/ci_ds_mixed",
            "format": "json",
            "entity_type": "dataset",
        }
        response_mixed = await create_dataset_v2(ac, collection_name, dataset_data_mixed)
        assert response_mixed.status_code == 200, f"Failed to create initial mixed-case dataset: {response_mixed.text}"

        # 3. Attempt to create another dataset in the same collection with the same name but all lowercase
        dataset_name_lower_case = base_name.lower()
        assert dataset_name_mixed_case != dataset_name_lower_case # Ensure names differ only by case
        
        dataset_data_lower = {
            "name": dataset_name_lower_case,
            "data_path": "/path/to/ci_ds_lower",
            "format": "json",
            "entity_type": "dataset",
        }
        response_lower = await create_dataset_v2(ac, collection_name, dataset_data_lower)

        # This assertion is what is desired. It will likely fail with current code.
        assert response_lower.status_code == 400, \
            f"Expected 400 (duplicate) but got {response_lower.status_code}. \
            Current dataset name check is likely case-sensitive. Response: {response_lower.text}"
        
        response_detail = response_lower.json().get("detail", "").lower()
        assert "already exists" in response_detail, \
            f"Expected 'dataset already exists' in detail, but got: {response_detail}. \
            Current dataset name check is likely case-sensitive."


@pytest.mark.asyncio
async def test_get_dataset_upstream_tree():
    """Test getting the upstream tree of a dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": f"Upstream Tree Collection-{uuid.uuid4().hex[:8]}",
            "description": "For upstream tree test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create a dataset
        ds_data = {
            "name": "UpstreamTreeDS",
            "data_path": "/upstream/tree",
            "format": "csv",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"]

        # Get upstream tree
        response = await ac.get(
            f"/api/v1/datasets/{collection_name}/{dataset_name}/upstream",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == dataset_name
        assert data["entity_type"] == "dataset"
        assert "upstream_entities" in data
        assert "downstream_entities" in data


@pytest.mark.asyncio
async def test_get_dataset_upstream_tree_not_found():
    """Test getting upstream tree of a nonexistent dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset/upstream",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_dataset_mlcroissant():
    """Test getting a dataset's Croissant metadata."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": f"Croissant Collection-{uuid.uuid4().hex[:8]}",
            "description": "For croissant test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create a dataset with croissant metadata
        ds_data = {
            "name": "CroissantDS",
            "data_path": "/croissant/test",
            "format": "json",
            "entity_type": "dataset",
            "dataset_metadata": {
                "@context": "https://schema.org/",
                "@type": "Dataset",
                "name": "Test Croissant Dataset",
            },
        }
        create_resp = await create_dataset_v2(ac, collection_name, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"]

        # Get Croissant metadata
        response = await ac.get(
            f"/api/v1/datasets/{collection_name}/{dataset_name}/mlcroissant",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 200
        data = response.json()
        assert data["@type"] == "Dataset"


@pytest.mark.asyncio
async def test_get_dataset_mlcroissant_not_found():
    """Test getting Croissant metadata for nonexistent dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset/mlcroissant",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_dataset_mlcroissant_no_metadata():
    """Test getting Croissant metadata when dataset has none."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": f"No Croissant Collection-{uuid.uuid4().hex[:8]}",
            "description": "For no croissant test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create a dataset without metadata
        ds_data = {
            "name": "NoCroissantDS",
            "data_path": "/no/croissant",
            "format": "csv",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"]

        # Get Croissant metadata - should return 404
        response = await ac.get(
            f"/api/v1/datasets/{collection_name}/{dataset_name}/mlcroissant",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 404
        assert "no Croissant metadata" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_dataset_version_history():
    """Test getting the version history of a dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection_data = {
            "name": f"Version History Collection-{uuid.uuid4().hex[:8]}",
            "description": "For version history test",
        }
        coll_resp = await ac.post(
            "/api/v1/collections/", json=collection_data, headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200
        collection_name = coll_resp.json()["name"]

        # Create a dataset
        ds_data = {
            "name": "VersionHistoryDS",
            "data_path": "/version/history",
            "format": "csv",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name, ds_data)
        assert create_resp.status_code == 200
        dataset_name = create_resp.json()["name"]

        # Update the dataset to create a version
        update_data = {
            "name": "VersionHistoryDS",
            "data_path": "/version/history/updated",
            "format": "json",
            "entity_type": "dataset",
        }
        await ac.put(
            f"/api/v1/datasets/{collection_name}/{dataset_name}",
            json=update_data,
            headers=authorization_headers(sample_org_token())
        )

        # Get version history
        response = await ac.get(
            f"/api/v1/datasets/{collection_name}/{dataset_name}/history",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 200
        data = response.json()
        assert data["entity_name"] == dataset_name
        assert data["entity_type"] == "dataset"
        assert "total_versions" in data
        assert "versions" in data


@pytest.mark.asyncio
async def test_get_dataset_version_history_not_found():
    """Test getting version history for nonexistent dataset."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/datasets/NonExistentCollection/NonExistentDataset/history",
            headers=authorization_headers(sample_org_token())
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_validate_mlcroissant_file_invalid_json():
    """Test validating an invalid JSON file returns 422 Unprocessable Entity."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create invalid JSON content
        invalid_json = b"{ invalid json content"

        response = await ac.post(
            "/api/v1/datasets/mlcroissant-validation",
            files={"file": ("test.json", invalid_json, "application/json")},
            headers=authorization_headers(sample_org_token())
        )
        # Invalid JSON returns 422 Unprocessable Entity
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_validate_mlcroissant_file_with_valid_json():
    """Test validating a JSON file that is valid JSON but may not pass Croissant schema validation."""
    import json
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a minimal JSON that is valid JSON (will pass JSON validation step)
        # but may not pass full Croissant schema validation
        valid_json = json.dumps({
            "@context": {
                "sc": "http://schema.org/",
                "ml": "http://mlcommons.org/schema/"
            },
            "@type": "sc:Dataset",
            "name": "Test Dataset",
            "description": "A test dataset for validation"
        }).encode()

        response = await ac.post(
            "/api/v1/datasets/mlcroissant-validation",
            files={"file": ("test.json", valid_json, "application/json")},
            headers=authorization_headers(sample_org_token())
        )
        # The endpoint should return either:
        # - 200 with validation results (JSON is valid but may fail Croissant validation)
        # - 422 if the JSON fails schema validation
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            # Should have a results key with validation info
            assert "results" in data


@pytest.mark.asyncio
async def test_create_dataset_to_nonexistent_collection():
    """Test creating a dataset in a nonexistent collection."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        ds_data = {
            "name": "TestDS",
            "data_path": "/test/path",
            "format": "csv",
            "entity_type": "dataset",
        }
        response = await create_dataset_v2(ac, "NonExistentCollection", ds_data)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# Search tests with mocked Typesense

def _create_mock_typesense_client():
    """Create a mock Typesense client."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_documents = MagicMock()

    # Setup the mock chain: client.collections[name].documents.search()
    mock_client.collections.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.documents = mock_documents

    return mock_client, mock_documents


@pytest.mark.asyncio
async def test_search_datasets_success():
    """Test searching datasets with mocked Typesense."""
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock search results
    mock_documents.search.return_value = {
        "hits": [
            {
                "document": {
                    "entity_name": "test-dataset",
                    "collection_name": "test-collection",
                    "entity_type": "dataset",
                    "full_name": "test-collection/test-dataset"
                }
            }
        ]
    }

    # Override the dependency
    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/datasets/search?q=test",
                headers=authorization_headers(sample_org_token())
            )

            assert response.status_code == 200
            data = response.json()
            assert "hits" in data
            assert len(data["hits"]) == 1
            assert data["hits"][0]["document"]["entity_type"] == "dataset"
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_datasets_empty_results():
    """Test searching datasets with no results."""
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock with empty results
    mock_documents.search.return_value = {"hits": []}

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/datasets/search?q=nonexistent",
                headers=authorization_headers(sample_org_token())
            )

            assert response.status_code == 200
            data = response.json()
            assert "hits" in data
            assert len(data["hits"]) == 0
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_datasets_with_limit():
    """Test searching datasets with limit parameter."""
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock search results
    mock_documents.search.return_value = {
        "hits": [
            {"document": {"entity_name": f"dataset-{i}", "entity_type": "dataset"}}
            for i in range(5)
        ]
    }

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/datasets/search?q=dataset&limit=5",
                headers=authorization_headers(sample_org_token())
            )

            assert response.status_code == 200
            data = response.json()
            assert "hits" in data

            # Verify the search was called with the correct limit
            mock_documents.search.assert_called_once()
            call_args = mock_documents.search.call_args[0][0]
            assert call_args["per_page"] == 5
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_datasets_collection_not_found():
    """Test searching datasets when Typesense collection doesn't exist."""
    import typesense
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock to raise ObjectNotFound
    mock_documents.search.side_effect = typesense.exceptions.ObjectNotFound("Collection not found")

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/datasets/search?q=test",
                headers=authorization_headers(sample_org_token())
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_datasets_typesense_error():
    """Test searching datasets when Typesense returns an error."""
    import typesense
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock to raise TypesenseClientError
    mock_documents.search.side_effect = typesense.exceptions.TypesenseClientError("API error")

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/datasets/search?q=test",
                headers=authorization_headers(sample_org_token())
            )

            assert response.status_code == 500
            assert "failed" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_datasets_missing_query():
    """Test searching datasets without query parameter returns 422."""
    mock_client, mock_documents = _create_mock_typesense_client()

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/datasets/search",
                headers=authorization_headers(sample_org_token())
            )

            assert response.status_code == 422  # Validation error for missing required param
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_datasets_unauthenticated():
    """Test searching datasets without authentication (should work for public datasets)."""
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock search results
    mock_documents.search.return_value = {
        "hits": [
            {
                "document": {
                    "entity_name": "public-dataset",
                    "entity_type": "dataset",
                    "is_private": False
                }
            }
        ]
    }

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            # Search without auth header - should still work for public datasets
            response = await ac.get("/api/v1/datasets/search?q=public")

            assert response.status_code == 200
            data = response.json()
            assert "hits" in data
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


# ============================================================================
# TIMESTAMP TESTS - Tests for updated_at functionality
# ============================================================================

@pytest.mark.asyncio
async def test_get_dataset_returns_updated_at():
    """Test that GET dataset endpoint returns updated_at timestamp."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_name = f"updated-at-ds-{uuid.uuid4().hex[:8]}"
        coll_resp = await ac.post(
            "/api/v1/collections/",
            json={"name": collection_name, "description": "For updated_at test"},
            headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200

        # Create dataset
        dataset_name = f"UpdatedAtDataset-{uuid.uuid4().hex[:8]}"
        dataset_data = {
            "name": dataset_name,
            "data_path": "/test/updated_at",
            "format": "csv",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name, dataset_data)
        assert create_resp.status_code == 200

        # Get the dataset
        response = await ac.get(
            f"/api/v1/datasets/{collection_name}/{dataset_name}",
            headers=authorization_headers(sample_org_token())
        )

        assert response.status_code == 200
        data = response.json()

        # Should have both created_at and updated_at
        assert "created_at" in data, "Dataset response should include created_at"
        assert "updated_at" in data, "Dataset response should include updated_at"
        assert data["updated_at"] is not None, "updated_at should not be None"


@pytest.mark.asyncio
async def test_dataset_version_history_includes_created_at():
    """Test that dataset version history includes created_at timestamps."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection_name = f"version-ts-ds-{uuid.uuid4().hex[:8]}"
        coll_resp = await ac.post(
            "/api/v1/collections/",
            json={"name": collection_name, "description": "For version timestamp test"},
            headers=authorization_headers(sample_org_token())
        )
        assert coll_resp.status_code == 200

        # Create dataset
        dataset_name = f"VersionTsDataset-{uuid.uuid4().hex[:8]}"
        dataset_data = {
            "name": dataset_name,
            "data_path": "/test/version_ts",
            "format": "parquet",
            "entity_type": "dataset",
        }
        create_resp = await create_dataset_v2(ac, collection_name, dataset_data)
        assert create_resp.status_code == 200

        # Update to create another version
        update_resp = await ac.put(
            f"/api/v1/datasets/{collection_name}/{dataset_name}",
            json={"data_path": "/test/version_ts/updated"},
            headers=authorization_headers(sample_org_token())
        )
        assert update_resp.status_code == 200

        # Get version history
        history_resp = await ac.get(
            f"/api/v1/datasets/{collection_name}/{dataset_name}/history",
            headers=authorization_headers(sample_org_token())
        )

        assert history_resp.status_code == 200
        history = history_resp.json()

        # Should have at least 2 versions
        assert history["total_versions"] >= 2

        # All versions should have created_at timestamps
        for version in history["versions"]:
            assert version.get("created_at") is not None, \
                f"Version {version.get('index')} should have a created_at timestamp"
