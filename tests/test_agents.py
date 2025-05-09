from fastapi.testclient import TestClient

# sqlalchemy imports, engine, sessionmaker, override_get_db, and setup_test_db fixture are now handled by conftest.py
# Keep necessary imports:
import pytest
from mlcbakery.main import app  # Keep app import if needed for client

# Model imports might still be needed if tests reference them directly
# from mlcbakery.models import Base, Agent, Collection
import httpx
from conftest import TEST_ADMIN_TOKEN  # Import the test token

# Define headers globally or pass them around
AUTH_HEADERS = {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}

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
    response = client.post("/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS)
    # Check for the ProgrammingError first
    if response.status_code == 500 and "NotNullViolationError" in response.text:
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
    response = client.post("/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS)
    assert (
        response.status_code == 200
    )  # Expect success, type should default or be nullable
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
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create known agents for this test
        agents_to_create = [
            {"name": "List Agent 1 Async", "type": "human"},
            {"name": "List Agent 2 Async", "type": "system"},
        ]
        created_agents_info = []
        for agent_data in agents_to_create:
            resp = await ac.post(
                "/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS
            )
            assert resp.status_code == 200, (
                f"Failed creating {agent_data['name']}: {resp.text}"
            )
            created_agents_info.append(resp.json())  # Store created agent data

        response = await ac.get("/api/v1/agents/")
        assert response.status_code == 200
        data = response.json()

        # Check that the agents we created are present in the full list
        fetched_agent_map = {item["id"]: item for item in data}
        for created_agent in created_agents_info:
            assert created_agent["id"] in fetched_agent_map
            fetched_agent = fetched_agent_map[created_agent["id"]]
            assert fetched_agent["name"] == created_agent["name"]
            assert fetched_agent["type"] == created_agent["type"]


@pytest.mark.asyncio
async def test_list_agents_pagination():
    """Test pagination of agents."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        base_name = "PaginateAgentAsync"
        agents_to_create = [
            {"name": f"{base_name}_{i}", "type": "human" if i % 2 == 0 else "system"}
            for i in range(5)  # Create 5 agents for pagination check
        ]
        # delete all agents
        response = await ac.get("/api/v1/agents/")
        assert response.status_code == 200
        data = response.json()
        for agent in data:
            await ac.delete(f"/api/v1/agents/{agent['id']}", headers=AUTH_HEADERS)

        created_agents = []
        for agent_data in agents_to_create:
            resp = await ac.post(
                "/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS
            )
            assert resp.status_code == 200, (
                f"Failed creating {agent_data['name']}: {resp.text}"
            )
            created_agents.append(resp.json())

        # Fetch page 2 (skip=2, limit=2) to get 3rd and 4th items
        response = await ac.get("/api/v1/agents/?skip=2&limit=2")
        assert response.status_code == 200
        paginated_data = response.json()
        assert len(paginated_data) == 2

        # Verify IDs match expected slice of agents created in this test (assuming default ID order)
        sorted_created_ids = sorted([a["id"] for a in created_agents])
        if len(sorted_created_ids) >= 4:
            expected_ids = sorted_created_ids[2:4]  # 3rd and 4th created IDs
            fetched_ids = [d["id"] for d in paginated_data]
            assert fetched_ids == expected_ids, (
                f"Expected IDs {expected_ids} but got {fetched_ids}"
            )
        else:
            pytest.fail("Less than 4 agents created for pagination check")


@pytest.mark.asyncio
async def test_get_agent():
    """Test getting a specific agent."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create agent to get
        agent_data = {"name": "GetAgentAsync", "type": "human"}
        create_resp = await ac.post(
            "/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 200, (
            f"Failed creating agent: {create_resp.text}"
        )
        agent_id = create_resp.json()["id"]

        # Get the specific agent
        response = await ac.get(f"/api/v1/agents/{agent_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == agent_id
        assert data["name"] == agent_data["name"]
        assert data["type"] == agent_data["type"]


@pytest.mark.asyncio
async def test_get_nonexistent_agent():
    """Test getting an agent that doesn't exist."""
    response = client.get("/api/v1/agents/99999")  # GET doesn't need auth headers
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


@pytest.mark.asyncio
async def test_delete_agent():
    """Test deleting an agent."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create agent to delete
        agent_data = {"name": "DeleteAgentAsync", "type": "system"}
        create_resp = await ac.post(
            "/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 200, (
            f"Failed creating agent: {create_resp.text}"
        )
        agent_id = create_resp.json()["id"]

        # Delete the agent
        response = await ac.delete(f"/api/v1/agents/{agent_id}", headers=AUTH_HEADERS)
        assert response.status_code == 200
        assert response.json()["message"] == "Agent deleted successfully"

        # Verify it's deleted
        get_response = await ac.get(f"/api/v1/agents/{agent_id}")
        assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_agent():
    """Test deleting an agent that doesn't exist."""
    response = client.delete("/api/v1/agents/99999", headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"


@pytest.mark.asyncio
async def test_update_agent():
    """Test updating an agent."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create agent to update
        agent_data = {"name": "UpdateAgentAsync", "type": "human"}
        create_resp = await ac.post(
            "/api/v1/agents/", json=agent_data, headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 200, (
            f"Failed creating agent: {create_resp.text}"
        )
        agent_id = create_resp.json()["id"]

        # Update the agent
        update_data = {
            "name": "Updated Agent Name Async",  # Changed name
            "type": "system",  # Changed type
        }
        response = await ac.put(
            f"/api/v1/agents/{agent_id}", json=update_data, headers=AUTH_HEADERS
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["type"] == update_data["type"]
        assert data["id"] == agent_id  # Ensure ID hasn't changed

        # Optional: Verify by fetching again
        get_resp = await ac.get(f"/api/v1/agents/{agent_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["name"] == update_data["name"]
        assert get_data["type"] == update_data["type"]


@pytest.mark.asyncio
async def test_update_nonexistent_agent():
    """Test updating an agent that doesn't exist."""
    update_data = {
        "name": "Updated Agent",
        "type": "system",
    }
    response = client.put(
        "/api/v1/agents/99999", json=update_data, headers=AUTH_HEADERS
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Agent not found"
