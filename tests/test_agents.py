from fastapi.testclient import TestClient
# sqlalchemy imports, engine, sessionmaker, override_get_db, and setup_test_db fixture are now handled by conftest.py
# Keep necessary imports:
from datetime import datetime
import pytest
import asyncio # Needed for pytest.mark.asyncio

from mlcbakery.main import app # Keep app import if needed for client
# Model imports might still be needed if tests reference them directly
# from mlcbakery.models import Base, Agent, Collection

# TestClient remains synchronous, it uses the globally overridden dependency
# Ensure the `app` object used here is the same one modified in conftest.py
client = TestClient(app)

# Remove the setup_test_db fixture definition
# Remove engine, TestingSessionLocal, override_get_db definitions

# Tests remain marked as async
@pytest.mark.asyncio
async def test_create_agent():
    """Test creating a new agent."""
    agent_data = {
        "name": "New Agent",
        "type": "human",
    }
    response = client.post("/api/v1/agents/", json=agent_data)
    # Check for the ProgrammingError first
    if response.status_code == 500 and 'NotNullViolationError' in response.text:
         pytest.fail(f"NotNullViolationError encountered: {response.text}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == agent_data["name"]
    assert data["type"] == agent_data["type"]
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_agent_without_type():
    """Test creating an agent without specifying type."""
    agent_data = {
        "name": "New Agent",
    }
    response = client.post("/api/v1/agents/", json=agent_data)
    assert response.status_code == 200 # Expect success, type should default or be nullable
    data = response.json()
    assert data["name"] == agent_data["name"]
    # Check the actual type based on model/schema defaults (might be null or a default string)
    # Assuming nullable based on model:
    assert data["type"] is None
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_agents():
    """Test getting all agents."""
    response = client.get("/api/v1/agents/")
    assert response.status_code == 200
    data = response.json()
    # Check length after test data seeding
    assert len(data) >= 2 # Use >= in case other tests add agents without cleaning up perfectly
    # Find the specific agents we added, order might not be guaranteed
    agent1_found = any(d["name"] == "Test Agent 1" and d["type"] == "human" for d in data)
    agent2_found = any(d["name"] == "Test Agent 2" and d["type"] == "system" for d in data)
    assert agent1_found
    assert agent2_found


@pytest.mark.asyncio
async def test_list_agents_pagination():
    """Test pagination of agents."""
    # Ensure at least 2 agents exist from the fixture
    response_all = client.get("/api/v1/agents/")
    assert response_all.status_code == 200
    all_agents = response_all.json()
    if len(all_agents) < 2:
        pytest.skip("Not enough agents created by fixture for pagination test")

    # Fetch page 2 (skip=1, limit=1)
    response = client.get("/api/v1/agents/?skip=1&limit=1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    # The specific agent depends on default ordering, which might not be guaranteed.
    # Check that the agent returned is one of the seeded agents.
    assert data[0]["name"] in ["Test Agent 1", "Test Agent 2"]


@pytest.mark.asyncio
async def test_get_agent():
    """Test getting a specific agent."""
    # Find the ID of "Test Agent 1"
    response_all = client.get("/api/v1/agents/")
    agents = response_all.json()
    agent_id = next((agent["id"] for agent in agents if agent["name"] == "Test Agent 1"), None)
    assert agent_id is not None, "Test Agent 1 not found"

    # Then get the specific agent
    response = client.get(f"/api/v1/agents/{agent_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Agent 1"
    assert data["type"] == "human"


@pytest.mark.asyncio
async def test_get_nonexistent_agent():
    """Test getting an agent that doesn't exist."""
    response = client.get("/api/v1/agents/99999") # Use a high ID unlikely to exist
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


@pytest.mark.asyncio
async def test_delete_agent():
    """Test deleting an agent."""
    # Find the ID of "Test Agent 1"
    response_all = client.get("/api/v1/agents/")
    agents = response_all.json()
    agent_id = next((agent["id"] for agent in agents if agent["name"] == "Test Agent 1"), None)
    assert agent_id is not None, "Test Agent 1 not found for deletion"


    # Delete the agent
    response = client.delete(f"/api/v1/agents/{agent_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "Agent deleted successfully"

    # Verify it's deleted
    response = client.get(f"/api/v1/agents/{agent_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_agent():
    """Test deleting an agent that doesn't exist."""
    response = client.delete("/api/v1/agents/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


@pytest.mark.asyncio
async def test_update_agent():
    """Test updating an agent."""
    # Find the ID of "Test Agent 1"
    response_all = client.get("/api/v1/agents/")
    agents = response_all.json()
    agent_id = next((agent["id"] for agent in agents if agent["name"] == "Test Agent 1"), None)
    assert agent_id is not None, "Test Agent 1 not found for update"


    # Update the agent
    update_data = {
        "name": "Updated Agent Name", # Changed name
        "type": "system", # Changed type
    }
    response = client.put(f"/api/v1/agents/{agent_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["type"] == update_data["type"]
    assert data["id"] == agent_id # Ensure ID hasn't changed


@pytest.mark.asyncio
async def test_update_nonexistent_agent():
    """Test updating an agent that doesn't exist."""
    update_data = {
        "name": "Updated Agent",
        "type": "system",
    }
    response = client.put("/api/v1/agents/99999", json=update_data)
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"
