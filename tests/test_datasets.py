from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pytest
import base64

from mlcbakery.main import app
from mlcbakery.models import Base, Dataset, Collection
from mlcbakery.database import get_db

# Create test database
SQLALCHEMY_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/test_db"

engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Test client setup
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function")
def test_db():
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Add test data
    db = TestingSessionLocal()

    # Create test collections first
    test_collections = [
        Collection(id=1, name="Test Collection 1", description="First test collection"),
        Collection(
            id=2, name="Test Collection 2", description="Second test collection"
        ),
        Collection(id=3, name="Test Collection 3", description="Third test collection"),
        Collection(
            id=4, name="Test Collection 4", description="Fourth test collection"
        ),
    ]
    db.add_all(test_collections)
    db.commit()

    # Then create test datasets
    test_datasets = [
        Dataset(
            name="Test Dataset 1",
            collection_id=1,
            generated_by_id=1,
            metadata_version="1.0",
            dataset_metadata={"description": "First test dataset", "tags": ["test"]},
        ),
        Dataset(
            name="Test Dataset 2",
            collection_id=2,
            generated_by_id=2,
            metadata_version="1.0",
            dataset_metadata={"description": "Second test dataset", "tags": ["test"]},
        ),
    ]
    db.add_all(test_datasets)
    db.commit()

    yield db  # Run the tests

    # Cleanup
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_create_dataset(test_db):
    """Test creating a new dataset."""
    dataset_data = {
        "name": "New Dataset",
        "collection_id": 3,
        "generated_by_id": 3,
        "metadata_version": "1.0",
        "dataset_metadata": {
            "description": "New test dataset",
            "tags": ["new", "test"],
        },
    }
    response = client.post("/api/v1/datasets/", json=dataset_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == dataset_data["name"]
    assert data["collection_id"] == dataset_data["collection_id"]
    assert data["dataset_metadata"] == dataset_data["dataset_metadata"]
    assert "id" in data
    assert "created_at" in data


def test_list_datasets(test_db):
    """Test getting all datasets."""
    response = client.get("/api/v1/datasets/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Test Dataset 1"
    assert data[1]["name"] == "Test Dataset 2"


def test_list_datasets_pagination(test_db):
    """Test pagination of datasets."""
    response = client.get("/api/v1/datasets/?skip=1&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Dataset 2"


def test_get_dataset(test_db):
    """Test getting a specific dataset."""
    # First, get the list to get an ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    # Then get the specific dataset
    response = client.get(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Dataset 1"


def test_get_nonexistent_dataset(test_db):
    """Test getting a dataset that doesn't exist."""
    response = client.get("/api/v1/datasets/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


def test_update_dataset(test_db):
    """Test updating a dataset."""
    # First, get the list to get an ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    # Update the dataset
    update_data = {
        "name": "Updated Dataset",
        "collection_id": 4,
        "generated_by_id": 4,
        "metadata_version": "2.0",
        "dataset_metadata": {
            "description": "Updated test dataset",
            "tags": ["updated", "test"],
        },
    }
    response = client.put(f"/api/v1/datasets/{dataset_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["collection_id"] == update_data["collection_id"]
    assert data["dataset_metadata"] == update_data["dataset_metadata"]


def test_update_nonexistent_dataset(test_db):
    """Test updating a dataset that doesn't exist."""
    update_data = {"name": "Updated Dataset"}
    response = client.put("/api/v1/datasets/999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


def test_delete_dataset(test_db):
    """Test deleting a dataset."""
    # First, get the list to get an ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    # Delete the dataset
    response = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Dataset deleted successfully"

    # Verify it's deleted
    response = client.get(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 404


def test_delete_nonexistent_dataset(test_db):
    """Test deleting a dataset that doesn't exist."""
    response = client.delete("/api/v1/datasets/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


def test_update_dataset_metadata(test_db):
    """Test updating just the metadata of a dataset."""
    # First, get the list to get an ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    # Update the metadata
    new_metadata = {
        "description": "Updated metadata",
        "tags": ["updated"],
        "new_field": "value",
    }
    response = client.patch(
        f"/api/v1/datasets/{dataset_id}/metadata", json=new_metadata
    )
    assert response.status_code == 200
    data = response.json()
    assert data["dataset_metadata"] == new_metadata
    assert data["name"] == "Test Dataset 1"  # Other fields should remain unchanged


def test_update_metadata_nonexistent_dataset(test_db):
    """Test updating metadata of a dataset that doesn't exist."""
    new_metadata = {"description": "Updated metadata"}
    response = client.patch("/api/v1/datasets/999/metadata", json=new_metadata)
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


def test_invalid_pagination(test_db):
    """Test invalid pagination parameters."""
    response = client.get("/api/v1/datasets/?skip=-1")
    assert response.status_code == 422  # FastAPI validation error

    response = client.get("/api/v1/datasets/?limit=0")
    assert response.status_code == 422  # FastAPI validation error

    response = client.get("/api/v1/datasets/?limit=101")
    assert response.status_code == 422  # FastAPI validation error


def test_update_dataset_preview(test_db):
    """Test updating a dataset's preview."""
    # First, get the list to get an ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    # Create a sample preview (a small PNG image as base64)
    sample_preview = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

    # Update the dataset with a preview
    files = {
        "preview": ("test.png", sample_preview, "image/png"),
    }
    response = client.put(f"/api/v1/datasets/{dataset_id}/preview", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["preview_type"] == "image/png"
    assert "preview" not in data  # Preview binary data should not be in JSON response

    # Get the dataset and verify preview type
    response = client.get(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["preview_type"] == "image/png"

    # Get the preview directly
    response = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == sample_preview


def test_update_nonexistent_dataset_preview(test_db):
    """Test updating a preview for a dataset that doesn't exist."""
    sample_preview = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    files = {
        "preview": ("test.png", sample_preview, "image/png"),
    }
    response = client.put("/api/v1/datasets/999/preview", files=files)
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


def test_get_nonexistent_dataset_preview(test_db):
    """Test getting a preview for a dataset that doesn't exist."""
    response = client.get("/api/v1/datasets/999/preview")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


def test_get_missing_preview(test_db):
    """Test getting a preview for a dataset that has no preview."""
    # First, get the list to get an ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    response = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset has no preview"
