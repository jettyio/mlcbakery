from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pytest

from mlcbakery.main import app
from mlcbakery.models import Base, Activity, Dataset, TrainedModel, Agent, Collection
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


def test_create_activity(test_db):
    """Test creating a new activity with relationships."""
    # Get test data IDs
    response = client.get("/api/v1/datasets/")
    dataset_ids = [d["id"] for d in response.json()]

    response = client.get("/api/v1/trained_models/")
    model_id = response.json()[0]["id"]

    # Create an agent first
    agent_data = {"name": "Test Agent", "type": "human"}
    agent_response = client.post("/api/v1/agents/", json=agent_data)
    agent_id = agent_response.json()["id"]

    # Create activity
    activity_data = {
        "name": "Test Activity",
        "input_dataset_ids": dataset_ids,
        "output_model_id": model_id,
        "agent_ids": [agent_id],
    }
    response = client.post("/api/v1/activities/", json=activity_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == activity_data["name"]
    assert data["input_dataset_ids"] == dataset_ids
    assert data["output_model_id"] == model_id
    assert data["agent_ids"] == [agent_id]
    assert "id" in data
    assert "created_at" in data


def test_create_activity_without_optional_relationships(test_db):
    """Test creating an activity without optional relationships."""
    # Get test dataset IDs
    response = client.get("/api/v1/datasets/")
    dataset_ids = [d["id"] for d in response.json()]

    # Create activity without optional relationships
    activity_data = {
        "name": "Test Activity",
        "input_dataset_ids": dataset_ids,
    }
    response = client.post("/api/v1/activities/", json=activity_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == activity_data["name"]
    assert data["input_dataset_ids"] == dataset_ids
    assert data["output_model_id"] is None
    assert data["agent_ids"] == []
    assert "id" in data
    assert "created_at" in data


def test_create_activity_with_nonexistent_entities(test_db):
    """Test creating an activity with nonexistent entities."""
    activity_data = {
        "name": "Test Activity",
        "input_dataset_ids": [999],
        "output_model_id": 999,
        "agent_ids": [999],
    }
    response = client.post("/api/v1/activities/", json=activity_data)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_list_activities(test_db):
    """Test getting all activities."""
    # Create a test activity first
    response = client.get("/api/v1/datasets/")
    dataset_ids = [d["id"] for d in response.json()]

    activity_data = {
        "name": "Test Activity",
        "input_dataset_ids": dataset_ids,
    }
    client.post("/api/v1/activities/", json=activity_data)

    # List activities
    response = client.get("/api/v1/activities/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Activity"
    assert data[0]["input_dataset_ids"] == dataset_ids


def test_list_activities_pagination(test_db):
    """Test pagination of activities."""
    # Create multiple test activities
    response = client.get("/api/v1/datasets/")
    dataset_ids = [d["id"] for d in response.json()]

    for i in range(3):
        activity_data = {
            "name": f"Test Activity {i}",
            "input_dataset_ids": dataset_ids,
        }
        client.post("/api/v1/activities/", json=activity_data)

    # Test pagination
    response = client.get("/api/v1/activities/?skip=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Test Activity 1"
    assert data[1]["name"] == "Test Activity 2"


def test_get_activity(test_db):
    """Test getting a specific activity."""
    # Create a test activity first
    response = client.get("/api/v1/datasets/")
    dataset_ids = [d["id"] for d in response.json()]

    activity_data = {
        "name": "Test Activity",
        "input_dataset_ids": dataset_ids,
    }
    create_response = client.post("/api/v1/activities/", json=activity_data)
    activity_id = create_response.json()["id"]

    # Get the specific activity
    response = client.get(f"/api/v1/activities/{activity_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Activity"
    assert data["input_dataset_ids"] == dataset_ids


def test_get_nonexistent_activity(test_db):
    """Test getting an activity that doesn't exist."""
    response = client.get("/api/v1/activities/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_delete_activity(test_db):
    """Test deleting an activity."""
    # Create a test activity first
    response = client.get("/api/v1/datasets/")
    dataset_ids = [d["id"] for d in response.json()]

    activity_data = {
        "name": "Test Activity",
        "input_dataset_ids": dataset_ids,
    }
    create_response = client.post("/api/v1/activities/", json=activity_data)
    activity_id = create_response.json()["id"]

    # Delete the activity
    response = client.delete(f"/api/v1/activities/{activity_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Activity deleted successfully"

    # Verify it's deleted
    response = client.get(f"/api/v1/activities/{activity_id}")
    assert response.status_code == 404


def test_delete_nonexistent_activity(test_db):
    """Test deleting an activity that doesn't exist."""
    response = client.delete("/api/v1/activities/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"
