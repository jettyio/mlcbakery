from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime as dt
import pytest

from mlcbakery.main import app
from mlcbakery.models import (
    Base,
    Entity,
    Dataset,
    TrainedModel,
    Activity,
)
from mlcbakery.database import get_db

# Create test database
SQLALCHEMY_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/test_db"
# Alternatively, you could use SQLite for testing:
# SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

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
        # Create test datasets
        dataset1 = Dataset(
            name="Test Dataset 1",
            data_path="/path/to/data1",
            format="csv",
            created_at=dt.datetime.now(dt.UTC),
            entity_type="dataset",
            metadata_version="1.0",
            dataset_metadata={"description": "First test dataset"},
        )
        dataset2 = Dataset(
            name="Test Dataset 2",
            data_path="/path/to/data2",
            format="parquet",
            created_at=dt.datetime.now(dt.UTC),
            entity_type="dataset",
            metadata_version="1.0",
            dataset_metadata={"description": "Second test dataset"},
        )

        # Create test model
        model = TrainedModel(
            name="Test Model 1",
            model_path="/path/to/model1",
            framework="pytorch",
            created_at=dt.datetime.now(dt.UTC),
            entity_type="trained_model",
        )

        db.add_all([dataset1, dataset2, model])
        db.commit()

        yield

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_list_entities(test_db):
    """Test getting all entities"""
    response = client.get("/api/v1/entities/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    # Verify we get all entity types
    entity_types = {entity["entity_type"] for entity in data}
    assert entity_types == {"dataset", "trained_model"}


def test_list_datasets(test_db):
    """Test getting only datasets"""
    response = client.get("/api/v1/datasets/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(entity["entity_type"] == "dataset" for entity in data)
    assert all("data_path" in entity and entity["data_path"] for entity in data)
    assert all(
        "format" in entity and entity["format"] in ["csv", "parquet"] for entity in data
    )
    assert all(
        "metadata_version" in entity and entity["metadata_version"] == "1.0"
        for entity in data
    )
    assert all(
        "dataset_metadata" in entity and isinstance(entity["dataset_metadata"], dict)
        for entity in data
    )


def test_list_trained_models(test_db):
    """Test getting only trained models"""
    response = client.get("/api/v1/trained-models/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert all(entity["entity_type"] == "trained_model" for entity in data)
    assert all("model_path" in entity for entity in data)
    assert all("framework" in entity for entity in data)


def test_polymorphic_entities_and_provenance_many_to_one():
    """Test polymorphic relationships with multiple input datasets"""
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)
    # Create tables
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        # Create multiple datasets
        dataset1 = Dataset(
            name="Training Data",
            data_path="/path/to/data1",
            format="csv",
            created_at=dt.datetime.now(dt.UTC),
            entity_type="dataset",
        )
        dataset2 = Dataset(
            name="Validation Data",
            data_path="/path/to/data2",
            format="csv",
            created_at=dt.datetime.now(dt.UTC),
            entity_type="dataset",
        )
        db.add_all([dataset1, dataset2])
        db.flush()  # Ensure IDs are generated

        # Create a trained model
        model = TrainedModel(
            name="Trained Model A",
            model_path="/path/to/model",
            framework="pytorch",
            created_at=dt.datetime.now(dt.UTC),
            entity_type="trained_model",
        )
        db.add(model)
        db.flush()  # Ensure ID is generated

        # Create an activity linking multiple datasets to one model
        activity = Activity(
            name="Training Run",
            created_at=dt.datetime.now(dt.UTC),
            input_datasets=[dataset1, dataset2],
            output_model=model,
        )
        db.add(activity)
        db.commit()

        # Test polymorphic queries
        entities = db.query(Entity).all()
        assert len(entities) == 3  # 2 datasets + 1 model

        # Test many-to-one relationship
        activity = db.query(Activity).first()
        assert len(activity.input_datasets) == 2
        assert {d.name for d in activity.input_datasets} == {
            "Training Data",
            "Validation Data",
        }
        assert activity.output_model.name == "Trained Model A"

        # Test reverse relationships
        for dataset in [dataset1, dataset2]:
            assert len(dataset.activities) == 1
            assert dataset.activities[0].name == "Training Run"

        # Test that both datasets are used in the same activity
        training_data = db.query(Dataset).filter_by(name="Training Data").first()
        validation_data = db.query(Dataset).filter_by(name="Validation Data").first()
        assert training_data.activities[0] == validation_data.activities[0]

        # Test reverse relationship from model to activity
        assert model.training_activity.name == "Training Run"

    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_list_entities_pagination(test_db):
    """Test pagination of entities"""
    response = client.get("/api/v1/entities/?skip=1&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


def test_empty_entities_list(test_db):
    """Test getting entities when database is empty"""
    # Clear all entities
    db = TestingSessionLocal()
    try:
        # Delete child records first
        db.query(Dataset).delete()
        db.query(TrainedModel).delete()
        db.query(Activity).delete()
        # Then delete parent records
        db.query(Entity).delete()
        db.commit()

        response = client.get("/api/v1/entities/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0
    finally:
        db.close()


def test_invalid_pagination(test_db):
    """Test invalid pagination parameters"""
    response = client.get("/api/v1/entities/?skip=-1")
    assert response.status_code == 422  # FastAPI validation error


def test_large_pagination(test_db):
    """Test pagination beyond available data"""
    response = client.get("/api/v1/entities/?skip=100&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0
