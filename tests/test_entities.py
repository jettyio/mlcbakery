from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import datetime as dt
import pytest

from mlcbakery.main import app
from mlcbakery.models import Base, Entity
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
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Add test data
    db = TestingSessionLocal()
    test_entities = [
        Entity(
            name="Test Entity 1", type="test_type", created_at=dt.datetime.now(dt.UTC)
        ),
        Entity(
            name="Test Entity 2", type="test_type", created_at=dt.datetime.now(dt.UTC)
        ),
    ]
    db.add_all(test_entities)
    db.commit()

    yield  # Run the tests

    # Cleanup
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_list_entities(test_db):
    """Test getting all entities"""
    response = client.get("/api/v1/entities/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Test Entity 1"
    assert data[1]["name"] == "Test Entity 2"


def test_list_entities_pagination(test_db):
    """Test pagination of entities"""
    response = client.get("/api/v1/entities/?skip=1&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Entity 2"


def test_empty_entities_list(test_db):
    """Test getting entities when database is empty"""
    # Clear all entities
    db = TestingSessionLocal()
    db.query(Entity).delete()
    db.commit()

    response = client.get("/api/v1/entities/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0


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
