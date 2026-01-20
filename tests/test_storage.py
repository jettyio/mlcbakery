import os
import pytest
import tempfile

from mlcbakery.bakery_client import Client
from mlcbakery.models import Collection, Dataset
from mlcbakery.auth.passthrough_strategy import sample_org_token, authorization_headers, ADMIN_ROLE_NAME

# Add a constant for the test owner identifier
_TEST_OWNER_IDENTIFIER = "test-owner"


@pytest.mark.asyncio
async def test_upload_dataset_data(
    test_client, mocked_gcs, db_session, monkeypatch
):
    # Directly patch create_gcs_client to return our mock
    monkeypatch.setattr("mlcbakery.storage.gcp.create_gcs_client", lambda x: mocked_gcs)

    # Create a test collection with GCP storage config
    collection = Collection(
        name="test_storage_collection",
        description="Test collection for storage",
        storage_provider="gcp",
        owner_identifier=_TEST_OWNER_IDENTIFIER,
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
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/test%40example.com",
        },
    )
    db_session.add(collection)
    await db_session.commit()

    # Create a test dataset
    dataset = Dataset(
        name="test_storage_dataset",
        collection_id=collection.id,
        data_path="",
        format="json",
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
                headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
            )

        # Assert response
        assert response.status_code == 200
        result = response.json()
        assert result["success"]
        assert result["collection_name"] == collection.name
        assert result["dataset_name"] == dataset.name
        assert result["file_number"] == 0  # First file should be 0

        # Test the download endpoint
        response = await test_client.get(
            f"/api/v1/datasets/{collection.name}/{dataset.name}/data/0",
            headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
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
        client,
        "_request",
        return_value=mocker.Mock(
            json=lambda: {"success": True, "file_path": "test_path", "file_number": 1},
            headers={
                "Content-Disposition": 'attachment; filename="data.000001.tar.gz"'
            },
            content=b"test content",
            iter_content=lambda chunk_size: [b"test", b"content"],
        ),
    )

    # Test upload_dataset_data
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_file.write(b"test data content")
        temp_file_path = temp_file.name

        try:
            result = client.upload_dataset_data(
                "test_collection", "test_dataset", temp_file_path
            )
            assert result["success"]
            assert result["file_path"] == "test_path"
            assert result["file_number"] == 1

            # Test update_dataset_data
            # First mock get_dataset_by_name to return a dataset
            mocker.patch.object(
                client,
                "get_dataset_by_name",
                return_value=mocker.Mock(id=1, name="test_dataset", collection_id=1),
            )

            result = client.update_dataset_data(
                "test_collection", "test_dataset", temp_file_path
            )
            assert result["success"]

            # Test download_dataset_data
            output_path = client.download_dataset_data(
                "test_collection", "test_dataset"
            )
            assert os.path.exists(output_path)

            # Clean up downloaded file
            if os.path.exists(output_path):
                os.unlink(output_path)

        finally:
            # Clean up temp file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

@pytest.mark.asyncio
async def test_upload_dataset_data_collection_not_found(
    test_client, db_session
):
    """Test uploading data to non-existent collection returns 404."""
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_file.write(b"test data content")
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as f:
            response = await test_client.post(
                "/api/v1/datasets/nonexistent_collection/test_dataset/data",
                files={"data_file": ("test.tar.gz", f, "application/gzip")},
                headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
            )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@pytest.mark.asyncio
async def test_upload_dataset_data_dataset_not_found(
    test_client, db_session
):
    """Test uploading data to non-existent dataset returns 404."""
    import tempfile

    # Create a collection without storage config
    collection = Collection(
        name="test_upload_no_dataset_collection",
        description="Test collection",
        owner_identifier=_TEST_OWNER_IDENTIFIER,
    )
    db_session.add(collection)
    await db_session.commit()

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_file.write(b"test data content")
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as f:
            response = await test_client.post(
                f"/api/v1/datasets/{collection.name}/nonexistent_dataset/data",
                files={"data_file": ("test.tar.gz", f, "application/gzip")},
                headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
            )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@pytest.mark.asyncio
async def test_upload_dataset_data_no_storage_configured(
    test_client, db_session
):
    """Test uploading data when collection has no storage configured returns 400."""
    import tempfile

    # Create collection without storage provider
    collection = Collection(
        name="test_no_storage_collection",
        description="Test collection without storage",
        owner_identifier=_TEST_OWNER_IDENTIFIER,
    )
    db_session.add(collection)
    await db_session.commit()

    # Create dataset
    dataset = Dataset(
        name="test_no_storage_dataset",
        collection_id=collection.id,
        data_path="",
        format="json",
    )
    db_session.add(dataset)
    await db_session.commit()

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_file.write(b"test data content")
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as f:
            response = await test_client.post(
                f"/api/v1/datasets/{collection.name}/{dataset.name}/data",
                files={"data_file": ("test.tar.gz", f, "application/gzip")},
                headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
            )
        assert response.status_code == 400
        assert "storage_provider" in response.json()["detail"].lower() or "storage_info" in response.json()["detail"].lower()
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@pytest.mark.asyncio
async def test_upload_dataset_data_unsupported_provider(
    test_client, db_session
):
    """Test uploading data with unsupported storage provider returns 400."""
    import tempfile

    # Create collection with unsupported storage provider
    collection = Collection(
        name="test_unsupported_provider_collection",
        description="Test collection with unsupported provider",
        storage_provider="aws",  # Unsupported provider
        storage_info={"bucket": "test"},
        owner_identifier=_TEST_OWNER_IDENTIFIER,
    )
    db_session.add(collection)
    await db_session.commit()

    # Create dataset
    dataset = Dataset(
        name="test_unsupported_provider_dataset",
        collection_id=collection.id,
        data_path="",
        format="json",
    )
    db_session.add(dataset)
    await db_session.commit()

    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as temp_file:
        temp_file.write(b"test data content")
        temp_file_path = temp_file.name

    try:
        with open(temp_file_path, "rb") as f:
            response = await test_client.post(
                f"/api/v1/datasets/{collection.name}/{dataset.name}/data",
                files={"data_file": ("test.tar.gz", f, "application/gzip")},
                headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
            )
        assert response.status_code == 400
        assert "gcp" in response.json()["detail"].lower()
    finally:
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)


@pytest.mark.asyncio
async def test_get_download_url_collection_not_found(test_client, db_session):
    """Test getting download URL for non-existent collection returns 404."""
    response = await test_client.get(
        "/api/v1/datasets/nonexistent_collection/test_dataset/data/0",
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_download_url_dataset_not_found(test_client, db_session):
    """Test getting download URL for non-existent dataset returns 404."""
    # Create a collection
    collection = Collection(
        name="test_download_no_dataset_collection",
        description="Test collection",
        owner_identifier=_TEST_OWNER_IDENTIFIER,
    )
    db_session.add(collection)
    await db_session.commit()

    response = await test_client.get(
        f"/api/v1/datasets/{collection.name}/nonexistent_dataset/data/0",
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_download_url_no_storage_configured(test_client, db_session):
    """Test getting download URL when collection has no storage configured returns 400."""
    # Create collection without storage provider
    collection = Collection(
        name="test_download_no_storage_collection",
        description="Test collection without storage",
        owner_identifier=_TEST_OWNER_IDENTIFIER,
    )
    db_session.add(collection)
    await db_session.commit()

    # Create dataset
    dataset = Dataset(
        name="test_download_no_storage_dataset",
        collection_id=collection.id,
        data_path="",
        format="json",
    )
    db_session.add(dataset)
    await db_session.commit()

    response = await test_client.get(
        f"/api/v1/datasets/{collection.name}/{dataset.name}/data/0",
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
    )
    assert response.status_code == 400
    assert "storage_provider" in response.json()["detail"].lower() or "storage_info" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_download_latest_dataset_not_found(test_client, db_session):
    """Test downloading latest data for non-existent dataset returns 404."""
    response = await test_client.get(
        "/api/v1/datasets/data/latest/nonexistent_collection/nonexistent_dataset",
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_download_latest_unsupported_provider(test_client, db_session):
    """Test downloading latest data with unsupported storage provider returns 400."""
    # Create collection with unsupported storage provider
    collection = Collection(
        name="test_latest_unsupported_collection",
        description="Test collection with unsupported provider",
        storage_provider="azure",  # Unsupported provider
        storage_info={"bucket": "test"},
        owner_identifier=_TEST_OWNER_IDENTIFIER,
    )
    db_session.add(collection)
    await db_session.commit()

    # Create dataset
    dataset = Dataset(
        name="test_latest_unsupported_dataset",
        collection_id=collection.id,
        data_path="",
        format="json",
    )
    db_session.add(dataset)
    await db_session.commit()

    response = await test_client.get(
        f"/api/v1/datasets/data/latest/{collection.name}/{dataset.name}",
        headers=authorization_headers(sample_org_token(ADMIN_ROLE_NAME, _TEST_OWNER_IDENTIFIER)),
    )
    assert response.status_code == 400
    assert "gcp" in response.json()["detail"].lower()
