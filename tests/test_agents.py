import pytest
from fastapi.testclient import TestClient
import httpx
from mlcbakery.main import app
from conftest import TEST_ADMIN_TOKEN
from mlcbakery.auth.passthrough_strategy import sample_user_token, sample_org_token, authorization_headers

# Define headers globally
AUTH_HEADERS = authorization_headers(sample_org_token())

# TestClient for synchronous tests
client = TestClient(app)


def create_collection(name="test-collection-for-agents"):
    """Helper function to create a collection for testing."""
    collection_data = {
        "name": name,
        "description": "A test collection for agent API testing."
    }
    response = client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response.status_code == 200, f"Failed to create collection: {response.text}"
    return response.json()


@pytest.mark.asyncio
async def test_create_agent_by_collection_name():
    """Test creating an agent using collection name in URL path."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection first
        collection = create_collection("agent-create-test-collection")
        collection_name = collection["name"]
        
        # Create agent using collection name in URL
        agent_data = {
            "name": "Test Agent by Name",
            "type": "human"
        }
        
        response = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 201, f"Failed to create agent: {response.text}"
        
        data = response.json()
        assert data["name"] == agent_data["name"]
        assert data["type"] == agent_data["type"]
        assert data["collection_id"] == collection["id"]
        assert "id" in data
        assert "created_at" in data


@pytest.mark.asyncio
async def test_create_agent_duplicate_name_in_collection():
    """Test that creating an agent with duplicate name in same collection fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection first
        collection = create_collection("agent-duplicate-test-collection")
        collection_name = collection["name"]
        
        # Create first agent
        agent_data = {
            "name": "Duplicate Agent",
            "type": "human"
        }
        
        response1 = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert response1.status_code == 201
        
        # Try to create second agent with same name
        response2 = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_create_agent_nonexistent_collection():
    """Test creating an agent in a nonexistent collection."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        agent_data = {
            "name": "Test Agent",
            "type": "human"
        }
        
        response = await ac.post(
            "/api/v1/agents/nonexistent-collection", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_agents_by_collection():
    """Test listing agents in a specific collection."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-list-test-collection")
        collection_name = collection["name"]
        
        # Create some agents in the collection
        agents_to_create = [
            {"name": "List Agent 1", "type": "human"},
            {"name": "List Agent 2", "type": "system"},
        ]
        
        created_agents = []
        for agent_data in agents_to_create:
            resp = await ac.post(
                f"/api/v1/agents/{collection_name}", 
                json=agent_data, 
                headers=AUTH_HEADERS
            )
            assert resp.status_code == 201
            created_agents.append(resp.json())
        
        # List agents in the collection
        response = await ac.get(f"/api/v1/agents/{collection_name}/", headers=AUTH_HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 3  # Our 2 created agents + 1 automatically created owner agent
        
        # Check that our created agents are in the list
        agent_names = [agent["name"] for agent in data]
        for agent in created_agents:
            assert agent["name"] in agent_names
            
        # Verify that exactly our 2 test agents are present (filtering out owner agent)
        test_agent_names = [agent["name"] for agent in created_agents]
        actual_test_agents = [agent for agent in data if agent["name"] in test_agent_names]
        assert len(actual_test_agents) == 2
            
        # Check that collection_name is included in response
        for agent in data:
            assert agent["collection_name"] == collection_name


@pytest.mark.asyncio
async def test_list_agents_nonexistent_collection():
    """Test listing agents in a nonexistent collection."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/agents/nonexistent-collection/", headers=AUTH_HEADERS)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_agent_by_collection_and_name():
    """Test getting a specific agent by collection and agent name."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-get-test-collection")
        collection_name = collection["name"]
        
        # Create an agent
        agent_data = {
            "name": "Get Agent Test",
            "type": "human"
        }
        
        create_resp = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        created_agent = create_resp.json()
        
        # Get the agent by collection and name
        response = await ac.get(
            f"/api/v1/agents/{collection_name}/{agent_data['name']}", 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == created_agent["id"]
        assert data["name"] == agent_data["name"]
        assert data["type"] == agent_data["type"]
        assert data["collection_id"] == collection["id"]


@pytest.mark.asyncio
async def test_get_agent_nonexistent_collection_or_agent():
    """Test getting agent with nonexistent collection or agent name."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test nonexistent collection
        response1 = await ac.get(
            "/api/v1/agents/nonexistent-collection/some-agent", 
            headers=AUTH_HEADERS
        )
        assert response1.status_code == 404
        assert "not found" in response1.json()["detail"]
        
        # Create a collection but test nonexistent agent
        collection = create_collection("agent-get-missing-test-collection")
        collection_name = collection["name"]
        
        response2 = await ac.get(
            f"/api/v1/agents/{collection_name}/nonexistent-agent", 
            headers=AUTH_HEADERS
        )
        assert response2.status_code == 404
        assert "not found" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_delete_agent_by_collection_and_name():
    """Test deleting an agent by collection and agent name."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-delete-test-collection")
        collection_name = collection["name"]
        
        # Create an agent
        agent_data = {
            "name": "Delete Agent Test",
            "type": "system"
        }
        
        create_resp = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Delete the agent by collection and name
        response = await ac.delete(
            f"/api/v1/agents/{collection_name}/{agent_data['name']}", 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Agent deleted successfully"
        
        # Verify it's deleted by trying to get it
        get_response = await ac.get(
            f"/api/v1/agents/{collection_name}/{agent_data['name']}", 
            headers=AUTH_HEADERS
        )
        assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent_nonexistent():
    """Test deleting a nonexistent agent."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-delete-missing-test-collection")
        collection_name = collection["name"]
        
        # Try to delete nonexistent agent
        response = await ac.delete(
            f"/api/v1/agents/{collection_name}/nonexistent-agent", 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_case_insensitive_agent_names():
    """Test that agent names are handled case-insensitively."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-case-test-collection")
        collection_name = collection["name"]
        
        # Create an agent with lowercase name
        agent_data = {
            "name": "case test agent",
            "type": "human"
        }
        
        create_resp = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Try to get it with different case
        response = await ac.get(
            f"/api/v1/agents/{collection_name}/Case Test Agent", 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == agent_data["name"]  # Original case should be preserved


@pytest.mark.asyncio
async def test_update_agent_by_collection_and_name():
    """Test updating an agent by collection and agent name."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-update-test-collection")
        collection_name = collection["name"]
        
        # Create an agent
        agent_data = {
            "name": "Update Agent Test",
            "type": "human"
        }
        
        create_resp = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        original_agent = create_resp.json()
        
        # Update the agent
        update_data = {
            "name": "Updated Agent Name",
            "type": "system"
        }
        
        response = await ac.put(
            f"/api/v1/agents/{collection_name}/{agent_data['name']}", 
            json=update_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        
        updated_agent = response.json()
        assert updated_agent["id"] == original_agent["id"]
        assert updated_agent["name"] == update_data["name"]
        assert updated_agent["type"] == update_data["type"]
        assert updated_agent["collection_id"] == collection["id"]
        
        # Verify by fetching with new name
        get_response = await ac.get(
            f"/api/v1/agents/{collection_name}/{update_data['name']}", 
            headers=AUTH_HEADERS
        )
        assert get_response.status_code == 200
        fetched_agent = get_response.json()
        assert fetched_agent["name"] == update_data["name"]
        assert fetched_agent["type"] == update_data["type"]


@pytest.mark.asyncio
async def test_update_agent_partial():
    """Test updating only some fields of an agent."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-partial-update-test-collection")
        collection_name = collection["name"]
        
        # Create an agent
        agent_data = {
            "name": "Partial Update Agent",
            "type": "human"
        }
        
        create_resp = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        original_agent = create_resp.json()
        
        # Update only the type
        update_data = {
            "type": "system"
        }
        
        response = await ac.put(
            f"/api/v1/agents/{collection_name}/{agent_data['name']}", 
            json=update_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        
        updated_agent = response.json()
        assert updated_agent["id"] == original_agent["id"]
        assert updated_agent["name"] == agent_data["name"]  # Should remain unchanged
        assert updated_agent["type"] == update_data["type"]  # Should be updated


@pytest.mark.asyncio
async def test_update_agent_duplicate_name():
    """Test that updating an agent to a duplicate name fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-duplicate-update-test-collection")
        collection_name = collection["name"]
        
        # Create two agents
        agent1_data = {
            "name": "Agent One",
            "type": "human"
        }
        agent2_data = {
            "name": "Agent Two",
            "type": "system"
        }
        
        create_resp1 = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent1_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp1.status_code == 201
        
        create_resp2 = await ac.post(
            f"/api/v1/agents/{collection_name}", 
            json=agent2_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp2.status_code == 201
        
        # Try to update agent2 to have the same name as agent1
        update_data = {
            "name": "Agent One"
        }
        
        response = await ac.put(
            f"/api/v1/agents/{collection_name}/{agent2_data['name']}", 
            json=update_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_nonexistent_agent():
    """Test updating a nonexistent agent."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create a collection
        collection = create_collection("agent-update-missing-test-collection")
        collection_name = collection["name"]
        
        # Try to update nonexistent agent
        update_data = {
            "name": "Updated Name",
            "type": "system"
        }
        
        response = await ac.put(
            f"/api/v1/agents/{collection_name}/nonexistent-agent", 
            json=update_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


# Authentication requirement tests for read endpoints
@pytest.mark.asyncio
async def test_list_agents_without_authorization():
    """Test that listing agents requires authentication."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection with proper auth first
        collection = create_collection("auth-required-list-test-collection")
        collection_name = collection["name"]
        
        # Try to list agents without authorization headers
        response = await ac.get(f"/api/v1/agents/{collection_name}/")
        assert response.status_code == 403
        assert response.json()["detail"]  # Verify there's an error detail


@pytest.mark.asyncio
async def test_get_agent_without_authorization():
    """Test that getting a specific agent requires authentication."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and agent with proper auth first
        collection = create_collection("auth-required-get-test-collection")
        collection_name = collection["name"]
        
        agent_data = {
            "name": "Auth Required Test Agent",
            "type": "human"
        }
        
        create_resp = await ac.post(
            f"/api/v1/agents/{collection_name}",
            json=agent_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Try to get agent without authorization headers
        response = await ac.get(f"/api/v1/agents/{collection_name}/{agent_data['name']}")
        assert response.status_code == 403
        assert response.json()["detail"]  # Verify there's an error detail


# Write access restriction tests
@pytest.mark.asyncio
async def test_create_agent_without_write_access():
    """Test that users without write access cannot create agents."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection with admin access first
        collection = create_collection("write-access-test-collection")
        collection_name = collection["name"]
        
        # Try to create agent with read-only access (non-admin role)
        read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
        agent_data = {
            "name": "Unauthorized Agent",
            "type": "human"
        }
        
        response = await ac.post(
            f"/api/v1/agents/{collection_name}",
            json=agent_data,
            headers=read_only_headers
        )
        assert response.status_code == 403
        assert "Access level WRITE required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_agent_without_write_access():
    """Test that users without write access cannot update agents."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and agent with admin access
        collection = create_collection("update-access-test-collection")
        collection_name = collection["name"]
        
        agent_data = {
            "name": "Update Test Agent",
            "type": "human"
        }
        
        create_resp = await ac.post(
            f"/api/v1/agents/{collection_name}",
            json=agent_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Try to update agent with read-only access
        read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
        update_data = {
            "type": "system"
        }
        
        response = await ac.put(
            f"/api/v1/agents/{collection_name}/{agent_data['name']}",
            json=update_data,
            headers=read_only_headers
        )
        assert response.status_code == 403
        assert "Access level WRITE required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_agent_without_write_access():
    """Test that users without write access cannot delete agents."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and agent with admin access
        collection = create_collection("delete-access-test-collection")
        collection_name = collection["name"]
        
        agent_data = {
            "name": "Delete Test Agent",
            "type": "human"
        }
        
        create_resp = await ac.post(
            f"/api/v1/agents/{collection_name}",
            json=agent_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Try to delete agent with read-only access
        read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
        
        response = await ac.delete(
            f"/api/v1/agents/{collection_name}/{agent_data['name']}",
            headers=read_only_headers
        )
        assert response.status_code == 403
        assert "Access level WRITE required" in response.json()["detail"]
