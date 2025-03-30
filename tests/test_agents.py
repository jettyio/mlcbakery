from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pytest

from mlcbakery.main import app
from mlcbakery.models import Base, Agent, Collection
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

        # Create test agents
        test_agents = [
            Agent(
                name="Test Agent 1",
                type="human",
            ),
            Agent(
                name="Test Agent 2",
                type="system",
            ),
        ]
        db.add_all(test_agents)
        db.commit()

        yield db  # Run the tests

    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_create_agent(test_db):
    """Test creating a new agent."""
    agent_data = {
        "name": "New Agent",
        "type": "human",
    }
    response = client.post("/api/v1/agents/", json=agent_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == agent_data["name"]
    assert data["type"] == agent_data["type"]
    assert "id" in data
    assert "created_at" in data


def test_create_agent_without_type(test_db):
    """Test creating an agent without specifying type."""
    agent_data = {
        "name": "New Agent",
    }
    response = client.post("/api/v1/agents/", json=agent_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == agent_data["name"]
    assert data["type"] is None
    assert "id" in data
    assert "created_at" in data


def test_list_agents(test_db):
    """Test getting all agents."""
    response = client.get("/api/v1/agents/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Test Agent 1"
    assert data[0]["type"] == "human"
    assert data[1]["name"] == "Test Agent 2"
    assert data[1]["type"] == "system"


def test_list_agents_pagination(test_db):
    """Test pagination of agents."""
    response = client.get("/api/v1/agents/?skip=1&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Agent 2"
    assert data[0]["type"] == "system"


def test_get_agent(test_db):
    """Test getting a specific agent."""
    # First, get the list to get an ID
    response = client.get("/api/v1/agents/")
    agent_id = response.json()[0]["id"]

    # Then get the specific agent
    response = client.get(f"/api/v1/agents/{agent_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Agent 1"
    assert data["type"] == "human"


def test_get_nonexistent_agent(test_db):
    """Test getting an agent that doesn't exist."""
    response = client.get("/api/v1/agents/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


def test_delete_agent(test_db):
    """Test deleting an agent."""
    # First, get the list to get an ID
    response = client.get("/api/v1/agents/")
    agent_id = response.json()[0]["id"]

    # Delete the agent
    response = client.delete(f"/api/v1/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Agent deleted successfully"

    # Verify it's deleted
    response = client.get(f"/api/v1/agents/{agent_id}")
    assert response.status_code == 404


def test_delete_nonexistent_agent(test_db):
    """Test deleting an agent that doesn't exist."""
    response = client.delete("/api/v1/agents/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


def test_update_agent(test_db):
    """Test updating an agent."""
    # First, get the list to get an ID
    response = client.get("/api/v1/agents/")
    agent_id = response.json()[0]["id"]

    # Update the agent
    update_data = {
        "name": "Updated Agent",
        "type": "system",
    }
    response = client.put(f"/api/v1/agents/{agent_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["type"] == update_data["type"]


def test_update_nonexistent_agent(test_db):
    """Test updating an agent that doesn't exist."""
    update_data = {
        "name": "Updated Agent",
        "type": "system",
    }
    response = client.put("/api/v1/agents/999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"
