from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pytest
import base64

from mlcbakery.main import app
from mlcbakery.models import Base, Dataset, Collection, Activity, Entity
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
    try:
        # Create test collections first
        test_collections = [
            Collection(name="Test Collection 1", description="First test collection"),
            Collection(name="Test Collection 2", description="Second test collection"),
            Collection(name="Test Collection 3", description="Third test collection"),
            Collection(name="Test Collection 4", description="Fourth test collection"),
        ]
        db.add_all(test_collections)
        db.commit()

        # Get the collection IDs after they've been created
        collection_ids = {c.name: c.id for c in test_collections}

        # Then create test datasets
        test_datasets = [
            Dataset(
                name="Test Dataset 1",
                data_path="/path/to/data1",
                format="csv",
                collection_id=collection_ids["Test Collection 1"],
                entity_type="dataset",
                metadata_version="1.0",
                dataset_metadata={
                    "description": "First test dataset",
                    "tags": ["test"],
                },
            ),
            Dataset(
                name="Test Dataset 2",
                data_path="/path/to/data2",
                format="parquet",
                collection_id=collection_ids["Test Collection 2"],
                entity_type="dataset",
                metadata_version="1.0",
                dataset_metadata={
                    "description": "Second test dataset",
                    "tags": ["test"],
                },
            ),
        ]
        db.add_all(test_datasets)
        db.commit()

        yield db  # Run the tests

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_dataset(test_db):
    """Test creating a new dataset."""
    dataset_data = {
        "name": "New Dataset",
        "data_path": "/path/to/data3",
        "format": "json",
        "collection_id": 3,
        "entity_type": "dataset",
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
    assert data["data_path"] == dataset_data["data_path"]
    assert data["format"] == dataset_data["format"]
    assert data["collection_id"] == dataset_data["collection_id"]
    assert data["entity_type"] == dataset_data["entity_type"]
    assert data["metadata_version"] == dataset_data["metadata_version"]
    assert data["dataset_metadata"] == dataset_data["dataset_metadata"]
    assert "id" in data
    assert "created_at" in data


def test_list_datasets(test_db):
    """Test getting all datasets."""
    response = client.get("/api/v1/datasets/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Verify first dataset
    assert data[0]["name"] == "Test Dataset 1"
    assert data[0]["data_path"] == "/path/to/data1"
    assert data[0]["format"] == "csv"
    assert data[0]["collection_id"] == 1
    assert data[0]["entity_type"] == "dataset"
    assert data[0]["metadata_version"] == "1.0"
    assert data[0]["dataset_metadata"]["description"] == "First test dataset"

    # Verify second dataset
    assert data[1]["name"] == "Test Dataset 2"
    assert data[1]["data_path"] == "/path/to/data2"
    assert data[1]["format"] == "parquet"
    assert data[1]["collection_id"] == 2
    assert data[1]["entity_type"] == "dataset"
    assert data[1]["metadata_version"] == "1.0"
    assert data[1]["dataset_metadata"]["description"] == "Second test dataset"


def test_list_datasets_pagination(test_db):
    """Test pagination of datasets."""
    response = client.get("/api/v1/datasets/?skip=1&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Dataset 2"
    assert data[0]["data_path"] == "/path/to/data2"
    assert data[0]["format"] == "parquet"


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
    assert data["data_path"] == "/path/to/data1"
    assert data["format"] == "csv"
    assert data["collection_id"] == 1
    assert data["entity_type"] == "dataset"
    assert data["metadata_version"] == "1.0"
    assert data["dataset_metadata"]["description"] == "First test dataset"


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
        "data_path": "/path/to/updated/data",
        "format": "json",
        "collection_id": 4,
        "entity_type": "dataset",
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
    assert data["data_path"] == update_data["data_path"]
    assert data["format"] == update_data["format"]
    assert data["collection_id"] == update_data["collection_id"]
    assert data["entity_type"] == update_data["entity_type"]
    assert data["metadata_version"] == update_data["metadata_version"]
    assert data["dataset_metadata"] == update_data["dataset_metadata"]


def test_update_nonexistent_dataset(test_db):
    """Test updating a dataset that doesn't exist."""
    update_data = {
        "name": "Updated Dataset",
        "data_path": "/path/to/data",
        "format": "csv",
        "entity_type": "dataset",
    }
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
    # Verify other fields remain unchanged
    assert data["name"] == "Test Dataset 1"
    assert data["data_path"] == "/path/to/data1"
    assert data["format"] == "csv"
    assert data["entity_type"] == "dataset"


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


def test_update_dataset_preview(test_db):
    """Test updating a dataset's preview."""
    # First, get the list to get an ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    # Create a sample preview (a small PNG image as base64)
    sample_preview = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )

    # Create test file
    files = {"preview": ("preview.png", sample_preview, "image/png")}
    response = client.put(f"/api/v1/datasets/{dataset_id}/preview", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["preview_type"] == "image/png"

    # Verify preview can be retrieved
    response = client.get(f"/api/v1/datasets/{dataset_id}/preview")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == sample_preview


def test_update_nonexistent_dataset_preview(test_db):
    """Test updating preview for a dataset that doesn't exist."""
    sample_preview = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    files = {"preview": ("preview.png", sample_preview, "image/png")}
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


def test_get_dataset_upstream_tree(test_db):
    """Test getting the upstream entity tree for a dataset."""
    # Create a test collection with a unique name
    collection = Collection(
        name="Upstream Test Collection", description="Test collection for upstream tree"
    )
    test_db.add(collection)
    test_db.commit()
    test_db.refresh(collection)

    # Create a source dataset
    source_dataset = Dataset(
        name="Source Dataset",
        data_path="/path/to/source",
        format="csv",
        entity_type="dataset",
        collection_id=collection.id,
        metadata_version="1.0",
        dataset_metadata={"description": "Source dataset"},
    )
    test_db.add(source_dataset)
    test_db.commit()
    test_db.refresh(source_dataset)

    # Create an intermediate dataset
    intermediate_dataset = Dataset(
        name="Intermediate Dataset",
        data_path="/path/to/intermediate",
        format="parquet",
        entity_type="dataset",
        collection_id=collection.id,
        metadata_version="1.0",
        dataset_metadata={"description": "Intermediate dataset"},
    )
    test_db.add(intermediate_dataset)
    test_db.commit()
    test_db.refresh(intermediate_dataset)

    # Create a target dataset
    target_dataset = Dataset(
        name="Target Dataset",
        data_path="/path/to/target",
        format="parquet",
        entity_type="dataset",
        collection_id=collection.id,
        metadata_version="1.0",
        dataset_metadata={"description": "Target dataset"},
    )
    test_db.add(target_dataset)
    test_db.commit()
    test_db.refresh(target_dataset)

    # Create activities to link the datasets
    activity1 = Activity(name="First Processing Step")
    activity1.input_entities = [source_dataset]
    activity1.output_entity = intermediate_dataset
    test_db.add(activity1)
    test_db.commit()
    test_db.refresh(activity1)

    activity2 = Activity(name="Second Processing Step")
    activity2.input_entities = [intermediate_dataset]
    activity2.output_entity = target_dataset
    test_db.add(activity2)
    test_db.commit()
    test_db.refresh(activity2)

    # Get the upstream tree
    response = client.get(
        f"/api/v1/datasets/{collection.name}/{target_dataset.name}/upstream"
    )
    assert response.status_code == 200
    tree = response.json()

    # Verify the tree structure
    assert tree["id"] == target_dataset.id
    assert tree["name"] == "Target Dataset"
    assert tree["entity_type"] == "dataset"
    assert tree["activity_id"] == activity2.id
    assert tree["activity_name"] == "Second Processing Step"
    assert len(tree["children"]) == 1

    # Verify intermediate dataset
    intermediate_node = tree["children"][0]
    assert intermediate_node["id"] == intermediate_dataset.id
    assert intermediate_node["name"] == "Intermediate Dataset"
    assert intermediate_node["entity_type"] == "dataset"
    assert intermediate_node["activity_id"] == activity1.id
    assert intermediate_node["activity_name"] == "First Processing Step"
    assert len(intermediate_node["children"]) == 1

    # Verify source dataset
    source_node = intermediate_node["children"][0]
    assert source_node["id"] == source_dataset.id
    assert source_node["name"] == "Source Dataset"
    assert source_node["entity_type"] == "dataset"
    assert source_node["activity_id"] is None
    assert source_node["activity_name"] is None
    assert len(source_node["children"]) == 0

    # Test with non-existent dataset
    response = client.get(
        f"/api/v1/datasets/{collection.name}/NonExistentDataset/upstream"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"

    # Test with non-existent collection
    response = client.get(
        f"/api/v1/datasets/NonExistentCollection/{target_dataset.name}/upstream"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"
