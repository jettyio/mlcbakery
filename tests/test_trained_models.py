from sqlalchemy import orm
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from mlcbakery import models
from mlcbakery.main import app
from mlcbakery.database import get_async_db, Base

# Create test database
SQLALCHEMY_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/test_db"

engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db):
    """Create a test client that uses the same database session as the test function."""

    def override_get_db():
        yield db

    app.dependency_overrides[get_async_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_trained_model(client, db):
    """Test creating a new trained model."""
    trained_model_data = {
        "name": "test-model",
        "model_path": "/path/to/model.pkl",
        "framework": "scikit-learn",
        "entity_type": "trained_model",
    }

    response = client.post("/api/v1/trained_models/", json=trained_model_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == trained_model_data["name"]
    assert data["model_path"] == trained_model_data["model_path"]
    assert data["framework"] == trained_model_data["framework"]
    assert data["entity_type"] == trained_model_data["entity_type"]
    assert "id" in data
    assert "created_at" in data


def test_get_trained_model(client, db):
    """Test getting a specific trained model."""
    # Create a test model first
    trained_model = models.TrainedModel(
        name="test-model",
        entity_type="trained_model",
        model_path="/path/to/model.pkl",
        framework="scikit-learn",
    )
    db.add(trained_model)
    db.commit()
    db.refresh(trained_model)

    response = client.get(f"/api/v1/trained_models/{trained_model.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == trained_model.id
    assert data["name"] == trained_model.name


def test_list_trained_models(client, db):
    """Test listing all trained models."""
    # Create some test models
    models_list = [
        models.TrainedModel(
            name=f"test-model-{i}",
            entity_type="trained_model",
            model_path=f"/path/to/model_{i}.pkl",
            framework="scikit-learn",
        )
        for i in range(3)
    ]
    for model in models_list:
        db.add(model)
    db.commit()

    response = client.get("/api/v1/trained_models/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3
    assert all(isinstance(item, dict) for item in data)


def test_delete_trained_model(client, db):
    """Test deleting a trained model."""
    # Create a test model first
    trained_model = models.TrainedModel(
        name="test-model",
        entity_type="trained_model",
        model_path="/path/to/model.pkl",
        framework="scikit-learn",
    )
    db.add(trained_model)
    db.commit()
    db.refresh(trained_model)

    response = client.delete(f"/api/v1/trained_models/{trained_model.id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Trained model deleted successfully"

    # Verify the model is deleted
    response = client.get(f"/api/v1/trained_models/{trained_model.id}")
    assert response.status_code == 404


def test_get_nonexistent_trained_model(client, db):
    """Test getting a nonexistent trained model."""
    response = client.get("/api/v1/trained_models/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Trained model not found"
