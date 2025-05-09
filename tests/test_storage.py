import os
import pytest
import tempfile
from unittest import mock

from mlcbakery.bakery_client import Client
from mlcbakery.models import Collection, Dataset
from mlcbakery.storage.gcp import create_gcs_client


@pytest.mark.asyncio
async def test_upload_dataset_data(test_client, mocked_gcs, db_session, auth_headers, monkeypatch):
    # Directly patch create_gcs_client to return our mock
    monkeypatch.setattr("mlcbakery.storage.gcp.create_gcs_client", lambda x: mocked_gcs)
    
    # Create a test collection with GCP storage config
    collection = Collection(
        name="test_storage_collection",
        description="Test collection for storage",
        storage_provider="gcp",
        storage_info={
            "bucket": "test-bucket",
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "test-private-key",
            "client_email": "test@example.com", 
            "client_id": "test-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40example.com"
        }
    )
    db_session.add(collection)
    await db_session.commit()
    
    # Create a test dataset
    dataset = Dataset(
        name="test_storage_dataset",
        collection_id=collection.id,
        data_path="",
        format="json"
    )
    db_session.add(dataset)
    await db_session.commit()
    
    # Create a temporary tar.gz file
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_file.write(b"test data content")
        temp_file_path = temp_file.name
    
    try:
        # Test the upload endpoint
        with open(temp_file_path, "rb") as f:
            response = await test_client.post(
                f"/api/v1/datasets/{collection.name}/{dataset.name}/data",
                files={"data_file": ("test.tar.gz", f, "application/gzip")},
                headers=auth_headers
            )
            
        # Assert response
        assert response.status_code == 200
        result = response.json()
        assert result["success"] == True
        assert result["collection_name"] == collection.name
        assert result["dataset_name"] == dataset.name
        assert result["file_number"] == 0  # First file should be 0
        
        # Test the download endpoint
        response = await test_client.get(
            f"/api/v1/datasets/{collection.name}/{dataset.name}/data/0",
            headers=auth_headers
        )
        
        # Assert response
        assert response.status_code == 200
        result = response.json()
        assert "download_url" in result
        assert result["file_number"] == 0
        
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


def test_client_dataset_data_operations(mocker):
    # Create a mock client
    client = Client("http://localhost:8000", token="test_token")
    
    # Mock the internal _request method
    mocker.patch.object(
        client, "_request",
        return_value=mocker.Mock(
            json=lambda: {"success": True, "file_path": "test_path", "file_number": 1},
            headers={"Content-Disposition": 'attachment; filename="data.000001.tar.gz"'},
            content=b"test content",
            iter_content=lambda chunk_size: [b"test", b"content"]
        )
    )
    
    # Test upload_dataset_data
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_file.write(b"test data content")
        temp_file_path = temp_file.name
        
        try:
            result = client.upload_dataset_data("test_collection", "test_dataset", temp_file_path)
            assert result["success"] == True
            assert result["file_path"] == "test_path"
            assert result["file_number"] == 1
            
            # Test update_dataset_data
            # First mock get_dataset_by_name to return a dataset
            mocker.patch.object(
                client, "get_dataset_by_name",
                return_value=mocker.Mock(id=1, name="test_dataset", collection_id=1)
            )
            
            result = client.update_dataset_data("test_collection", "test_dataset", temp_file_path)
            assert result["success"] == True
            
            # Test download_dataset_data
            output_path = client.download_dataset_data("test_collection", "test_dataset")
            assert os.path.exists(output_path)
            
            # Clean up downloaded file
            if os.path.exists(output_path):
                os.unlink(output_path)
                
        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)