from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pytest

from mlcbakery.main import app
from mlcbakery.models import (
    Base,
    Activity,
    Dataset,
    TrainedModel,
    Agent,
    Collection,
    Entity,
)
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
        # Create test collection
        test_collection = Collection(
            id=1, name="Test Collection", description="Test collection"
        )
        db.add(test_collection)
        db.commit()

        # Create test datasets
        test_datasets = [
            Dataset(
                name="Test Dataset 1",
                data_path="/path/to/data1",
                format="csv",
                collection_id=1,
                entity_type="dataset",
                metadata_version="1.0",
                dataset_metadata={"description": "First test dataset"},
            ),
            Dataset(
                name="Test Dataset 2",
                data_path="/path/to/data2",
                format="parquet",
                collection_id=1,
                entity_type="dataset",
                metadata_version="1.0",
                dataset_metadata={"description": "Second test dataset"},
            ),
        ]
        db.add_all(test_datasets)
        db.commit()

        # Create test model
        test_model = TrainedModel(
            name="Test Model",
            model_path="/path/to/model",
            framework="scikit-learn",
            collection_id=1,
            entity_type="trained_model",
            metadata_version="1.0",
            model_metadata={"description": "Test model"},
        )
        db.add(test_model)
        db.commit()

        # Create test agent
        test_agent = Agent(
            name="Test Agent",
            type="human",
        )
        db.add(test_agent)
        db.commit()

        yield db  # Run the tests

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_dataset(test_db):
    """Test creating a new dataset."""
    dataset_data = {
        "name": "New Dataset",
        "data_path": "/path/to/new/data",
        "format": "csv",
        "collection_id": 1,
        "entity_type": "dataset",
        "metadata_version": "1.0",
        "dataset_metadata": {"description": "New test dataset"},
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


def test_create_model(test_db):
    """Test creating a new model."""
    model_data = {
        "name": "New Model",
        "model_path": "/path/to/new/model",
        "framework": "scikit-learn",
        "collection_id": 1,
        "entity_type": "trained_model",
        "metadata_version": "1.0",
        "model_metadata": {"description": "New test model"},
    }
    response = client.post("/api/v1/trained_models/", json=model_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == model_data["name"]
    assert data["model_path"] == model_data["model_path"]
    assert data["framework"] == model_data["framework"]
    assert data["collection_id"] == model_data["collection_id"]
    assert data["entity_type"] == model_data["entity_type"]
    assert data["metadata_version"] == model_data["metadata_version"]
    assert data["model_metadata"] == model_data["model_metadata"]
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


def test_list_models(test_db):
    """Test getting all models."""
    response = client.get("/api/v1/trained_models/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Model"


def test_get_dataset(test_db):
    """Test getting a specific dataset."""
    # Get the first dataset's ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    # Get the specific dataset
    response = client.get(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Dataset 1"


def test_get_model(test_db):
    """Test getting a specific model."""
    # Get the first model's ID
    response = client.get("/api/v1/trained_models/")
    model_id = response.json()[0]["id"]

    # Get the specific model
    response = client.get(f"/api/v1/trained_models/{model_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Model"


def test_get_nonexistent_dataset(test_db):
    """Test getting a dataset that doesn't exist."""
    response = client.get("/api/v1/datasets/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


def test_get_nonexistent_model(test_db):
    """Test getting a model that doesn't exist."""
    response = client.get("/api/v1/trained_models/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Trained model not found"


def test_delete_dataset(test_db):
    """Test deleting a dataset."""
    # Get the first dataset's ID
    response = client.get("/api/v1/datasets/")
    dataset_id = response.json()[0]["id"]

    # Delete the dataset
    response = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Dataset deleted successfully"

    # Verify it's deleted
    response = client.get(f"/api/v1/datasets/{dataset_id}")
    assert response.status_code == 404


def test_delete_model(test_db):
    """Test deleting a model."""
    # Get the first model's ID
    response = client.get("/api/v1/trained_models/")
    model_id = response.json()[0]["id"]

    # Delete the model
    response = client.delete(f"/api/v1/trained_models/{model_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Trained model deleted successfully"

    # Verify it's deleted
    response = client.get(f"/api/v1/trained_models/{model_id}")
    assert response.status_code == 404


def test_delete_nonexistent_dataset(test_db):
    """Test deleting a dataset that doesn't exist."""
    response = client.delete("/api/v1/datasets/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found"


def test_delete_nonexistent_model(test_db):
    """Test deleting a model that doesn't exist."""
    response = client.delete("/api/v1/trained_models/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Trained model not found"


def test_entity_activities(test_db):
    """Test entity relationships with activities."""
    # Get test data IDs
    response = client.get("/api/v1/datasets/")
    dataset_ids = [d["id"] for d in response.json()]

    response = client.get("/api/v1/trained_models/")
    model_id = response.json()[0]["id"]

    # Create an agent
    agent_data = {"name": "Test Agent", "type": "human"}
    agent_response = client.post("/api/v1/agents/", json=agent_data)
    agent_id = agent_response.json()["id"]

    # Create an activity linking the dataset and model
    activity_data = {
        "name": "Test Activity",
        "input_entity_ids": dataset_ids,
        "output_entity_id": model_id,
        "agent_ids": [agent_id],
    }
    response = client.post("/api/v1/activities/", json=activity_data)
    assert response.status_code == 200
    activity_id = response.json()["id"]

    # Verify dataset's input activities
    response = client.get(f"/api/v1/datasets/{dataset_ids[0]}")
    assert response.status_code == 200
    dataset_data = response.json()
    assert len(dataset_data["input_activities"]) == 1
    assert dataset_data["input_activities"][0]["id"] == activity_id

    # Verify model's output activities
    response = client.get(f"/api/v1/trained_models/{model_id}")
    assert response.status_code == 200
    model_data = response.json()
    assert len(model_data["output_activities"]) == 1
    assert model_data["output_activities"][0]["id"] == activity_id
