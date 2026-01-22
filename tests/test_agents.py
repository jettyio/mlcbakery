import pytest
import uuid
from httpx import AsyncClient

from mlcbakery.auth.passthrough_strategy import sample_org_token, authorization_headers

# Define headers globally
AUTH_HEADERS = authorization_headers(sample_org_token())


async def create_collection(async_client: AsyncClient, name: str = None):
    """Helper function to create a collection for testing."""
    if name is None:
        name = f"test-collection-{uuid.uuid4().hex[:8]}"
    collection_data = {
        "name": name,
        "description": "A test collection for agent API testing."
    }
    response = await async_client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response.status_code == 200, f"Failed to create collection: {response.text}"
    return response.json()


@pytest.mark.asyncio
async def test_create_agent_by_collection_name(async_client: AsyncClient):
    """Test creating an agent using collection name in URL path."""
    collection = await create_collection(async_client, "agent-create-test-collection")
    collection_name = collection["name"]

    agent_data = {
        "name": "Test Agent by Name",
        "type": "human"
    }

    response = await async_client.post(
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
async def test_create_agent_duplicate_name_in_collection(async_client: AsyncClient):
    """Test that creating an agent with duplicate name in same collection fails."""
    collection = await create_collection(async_client, "agent-duplicate-test-collection")
    collection_name = collection["name"]

    agent_data = {
        "name": "Duplicate Agent",
        "type": "human"
    }

    response1 = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert response1.status_code == 201

    # Try to create second agent with same name
    response2 = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_create_agent_duplicate_name_case_insensitive(async_client: AsyncClient):
    """Test that agent name duplicate check is case-insensitive."""
    collection = await create_collection(async_client, "agent-case-duplicate-test")
    collection_name = collection["name"]

    # Create agent with lowercase name
    agent_data = {
        "name": "my agent",
        "type": "human"
    }
    response1 = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert response1.status_code == 201

    # Try to create agent with same name but different case
    agent_data_upper = {
        "name": "MY AGENT",
        "type": "system"
    }
    response2 = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data_upper,
        headers=AUTH_HEADERS
    )
    assert response2.status_code == 400
    assert "already exists" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_create_agent_nonexistent_collection(async_client: AsyncClient):
    """Test creating an agent in a nonexistent collection."""
    agent_data = {
        "name": "Test Agent",
        "type": "human"
    }

    response = await async_client.post(
        "/api/v1/agents/nonexistent-collection",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_agent_minimal_data(async_client: AsyncClient):
    """Test creating an agent with only required fields."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    # Create agent with only name (type is optional)
    agent_data = {
        "name": "Minimal Agent"
    }

    response = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == agent_data["name"]


@pytest.mark.asyncio
async def test_list_agents_by_collection(async_client: AsyncClient):
    """Test listing agents in a specific collection."""
    collection = await create_collection(async_client, "agent-list-test-collection")
    collection_name = collection["name"]

    # Create some agents in the collection
    agents_to_create = [
        {"name": "List Agent 1", "type": "human"},
        {"name": "List Agent 2", "type": "system"},
    ]

    created_agents = []
    for agent_data in agents_to_create:
        resp = await async_client.post(
            f"/api/v1/agents/{collection_name}",
            json=agent_data,
            headers=AUTH_HEADERS
        )
        assert resp.status_code == 201
        created_agents.append(resp.json())

    # List agents in the collection
    response = await async_client.get(f"/api/v1/agents/{collection_name}/", headers=AUTH_HEADERS)
    assert response.status_code == 200

    data = response.json()
    # Should have our 2 created agents + 1 automatically created owner agent
    assert len(data) >= 2

    # Check that our created agents are in the list
    agent_names = [agent["name"] for agent in data]
    for agent in created_agents:
        assert agent["name"] in agent_names

    # Check that collection_name is included in response
    for agent in data:
        assert agent["collection_name"] == collection_name


@pytest.mark.asyncio
async def test_list_agents_nonexistent_collection(async_client: AsyncClient):
    """Test listing agents in a nonexistent collection."""
    response = await async_client.get("/api/v1/agents/nonexistent-collection/", headers=AUTH_HEADERS)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_agents_by_collection_with_pagination(async_client: AsyncClient):
    """Test listing agents with pagination parameters."""
    collection = await create_collection(async_client, "pagination-test-agents-collection")
    collection_name = collection["name"]

    # Create 5 agents
    for i in range(5):
        agent_data = {
            "name": f"Pagination Agent {i+1}",
            "type": "human"
        }
        create_resp = await async_client.post(
            f"/api/v1/agents/{collection_name}",
            json=agent_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201

    # Test pagination with limit
    response = await async_client.get(
        f"/api/v1/agents/{collection_name}/?limit=2",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Test pagination with skip
    response = await async_client.get(
        f"/api/v1/agents/{collection_name}/?skip=1&limit=2",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_list_agents_empty_collection(async_client: AsyncClient):
    """Test listing agents in an empty collection returns the owner agent."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    # List agents - should have at least owner agent
    response = await async_client.get(f"/api/v1/agents/{collection_name}/", headers=AUTH_HEADERS)
    assert response.status_code == 200
    data = response.json()
    # At least the owner agent should exist
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_agent_by_collection_and_name(async_client: AsyncClient):
    """Test getting a specific agent by collection and agent name."""
    collection = await create_collection(async_client, "agent-get-test-collection")
    collection_name = collection["name"]

    # Create an agent
    agent_data = {
        "name": "Get Agent Test",
        "type": "human"
    }

    create_resp = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert create_resp.status_code == 201
    created_agent = create_resp.json()

    # Get the agent by collection and name
    response = await async_client.get(
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
async def test_get_agent_nonexistent_collection(async_client: AsyncClient):
    """Test getting agent with nonexistent collection."""
    response = await async_client.get(
        "/api/v1/agents/nonexistent-collection/some-agent",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_agent_nonexistent_agent(async_client: AsyncClient):
    """Test getting nonexistent agent in existing collection."""
    collection = await create_collection(async_client, "agent-get-missing-test-collection")
    collection_name = collection["name"]

    response = await async_client.get(
        f"/api/v1/agents/{collection_name}/nonexistent-agent",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_case_insensitive_agent_names(async_client: AsyncClient):
    """Test that agent names are handled case-insensitively for retrieval."""
    collection = await create_collection(async_client, "agent-case-test-collection")
    collection_name = collection["name"]

    # Create an agent with lowercase name
    agent_data = {
        "name": "case test agent",
        "type": "human"
    }

    create_resp = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert create_resp.status_code == 201

    # Try to get it with different case
    response = await async_client.get(
        f"/api/v1/agents/{collection_name}/Case Test Agent",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == agent_data["name"]  # Original case should be preserved


@pytest.mark.asyncio
async def test_update_agent_by_collection_and_name(async_client: AsyncClient):
    """Test updating an agent by collection and agent name."""
    collection = await create_collection(async_client, "agent-update-test-collection")
    collection_name = collection["name"]

    # Create an agent
    agent_data = {
        "name": "Update Agent Test",
        "type": "human"
    }

    create_resp = await async_client.post(
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

    response = await async_client.put(
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
    get_response = await async_client.get(
        f"/api/v1/agents/{collection_name}/{update_data['name']}",
        headers=AUTH_HEADERS
    )
    assert get_response.status_code == 200
    fetched_agent = get_response.json()
    assert fetched_agent["name"] == update_data["name"]
    assert fetched_agent["type"] == update_data["type"]


@pytest.mark.asyncio
async def test_update_agent_partial(async_client: AsyncClient):
    """Test updating only some fields of an agent."""
    collection = await create_collection(async_client, "agent-partial-update-test-collection")
    collection_name = collection["name"]

    # Create an agent
    agent_data = {
        "name": "Partial Update Agent",
        "type": "human"
    }

    create_resp = await async_client.post(
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

    response = await async_client.put(
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
async def test_update_agent_name_same_case(async_client: AsyncClient):
    """Test updating agent name to the same name (same case) should succeed."""
    collection = await create_collection(async_client, "same-name-update-agents-collection")
    collection_name = collection["name"]

    agent_data = {
        "name": "Same Name Agent",
        "type": "human"
    }

    create_resp = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert create_resp.status_code == 201

    # Update with the exact same name should succeed
    update_data = {
        "name": "Same Name Agent",
        "type": "bot"
    }

    response = await async_client.put(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}",
        json=update_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == update_data["name"]
    assert data["type"] == update_data["type"]


@pytest.mark.asyncio
async def test_update_agent_duplicate_name(async_client: AsyncClient):
    """Test that updating an agent to a duplicate name fails."""
    collection = await create_collection(async_client, "agent-duplicate-update-test-collection")
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

    create_resp1 = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent1_data,
        headers=AUTH_HEADERS
    )
    assert create_resp1.status_code == 201

    create_resp2 = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent2_data,
        headers=AUTH_HEADERS
    )
    assert create_resp2.status_code == 201

    # Try to update agent2 to have the same name as agent1
    update_data = {
        "name": "Agent One"
    }

    response = await async_client.put(
        f"/api/v1/agents/{collection_name}/{agent2_data['name']}",
        json=update_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_agent_duplicate_name_case_insensitive(async_client: AsyncClient):
    """Test that updating agent name to case-variant of existing name fails."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    # Create two agents
    agent1_data = {"name": "First Agent", "type": "human"}
    agent2_data = {"name": "Second Agent", "type": "system"}

    await async_client.post(f"/api/v1/agents/{collection_name}", json=agent1_data, headers=AUTH_HEADERS)
    await async_client.post(f"/api/v1/agents/{collection_name}", json=agent2_data, headers=AUTH_HEADERS)

    # Try to update agent2 to have the same name (different case) as agent1
    update_data = {"name": "FIRST AGENT"}

    response = await async_client.put(
        f"/api/v1/agents/{collection_name}/{agent2_data['name']}",
        json=update_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_nonexistent_agent(async_client: AsyncClient):
    """Test updating a nonexistent agent."""
    collection = await create_collection(async_client, "agent-update-missing-test-collection")
    collection_name = collection["name"]

    # Try to update nonexistent agent
    update_data = {
        "name": "Updated Name",
        "type": "system"
    }

    response = await async_client.put(
        f"/api/v1/agents/{collection_name}/nonexistent-agent",
        json=update_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_agent_by_collection_and_name(async_client: AsyncClient):
    """Test deleting an agent by collection and agent name."""
    collection = await create_collection(async_client, "agent-delete-test-collection")
    collection_name = collection["name"]

    # Create an agent
    agent_data = {
        "name": "Delete Agent Test",
        "type": "system"
    }

    create_resp = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert create_resp.status_code == 201

    # Delete the agent by collection and name
    response = await async_client.delete(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Agent deleted successfully"

    # Verify it's deleted by trying to get it
    get_response = await async_client.get(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}",
        headers=AUTH_HEADERS
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_agent_nonexistent(async_client: AsyncClient):
    """Test deleting a nonexistent agent."""
    collection = await create_collection(async_client, "agent-delete-missing-test-collection")
    collection_name = collection["name"]

    # Try to delete nonexistent agent
    response = await async_client.delete(
        f"/api/v1/agents/{collection_name}/nonexistent-agent",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


# Authentication requirement tests for read endpoints
@pytest.mark.asyncio
async def test_list_agents_without_authorization(async_client: AsyncClient):
    """Test that listing agents requires authentication."""
    collection = await create_collection(async_client, "auth-required-list-test-collection")
    collection_name = collection["name"]

    # Try to list agents without authorization headers
    response = await async_client.get(f"/api/v1/agents/{collection_name}/")
    assert response.status_code == 401
    assert response.json()["detail"]  # Verify there's an error detail


@pytest.mark.asyncio
async def test_get_agent_without_authorization(async_client: AsyncClient):
    """Test that getting a specific agent requires authentication."""
    collection = await create_collection(async_client, "auth-required-get-test-collection")
    collection_name = collection["name"]

    agent_data = {
        "name": "Auth Required Test Agent",
        "type": "human"
    }

    create_resp = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert create_resp.status_code == 201

    # Try to get agent without authorization headers
    response = await async_client.get(f"/api/v1/agents/{collection_name}/{agent_data['name']}")
    assert response.status_code == 401
    assert response.json()["detail"]  # Verify there's an error detail


# Write access restriction tests
@pytest.mark.asyncio
async def test_create_agent_without_write_access(async_client: AsyncClient):
    """Test that users without write access cannot create agents."""
    collection = await create_collection(async_client, "write-access-test-collection")
    collection_name = collection["name"]

    # Try to create agent with read-only access (non-admin role)
    read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
    agent_data = {
        "name": "Unauthorized Agent",
        "type": "human"
    }

    response = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=read_only_headers
    )
    assert response.status_code == 403
    assert "Access level WRITE required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_agent_without_write_access(async_client: AsyncClient):
    """Test that users without write access cannot update agents."""
    collection = await create_collection(async_client, "update-access-test-collection")
    collection_name = collection["name"]

    agent_data = {
        "name": "Update Test Agent",
        "type": "human"
    }

    create_resp = await async_client.post(
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

    response = await async_client.put(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}",
        json=update_data,
        headers=read_only_headers
    )
    assert response.status_code == 403
    assert "Access level WRITE required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_agent_without_write_access(async_client: AsyncClient):
    """Test that users without write access cannot delete agents."""
    collection = await create_collection(async_client, "delete-access-test-collection")
    collection_name = collection["name"]

    agent_data = {
        "name": "Delete Test Agent",
        "type": "human"
    }

    create_resp = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert create_resp.status_code == 201

    # Try to delete agent with read-only access
    read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))

    response = await async_client.delete(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}",
        headers=read_only_headers
    )
    assert response.status_code == 403
    assert "Access level WRITE required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_agent_without_any_auth(async_client: AsyncClient):
    """Test that creating an agent without any auth fails."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    agent_data = {
        "name": "No Auth Agent",
        "type": "human"
    }

    response = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_update_agent_without_any_auth(async_client: AsyncClient):
    """Test that updating an agent without any auth fails."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    # First create an agent
    agent_data = {"name": "Auth Test Agent", "type": "human"}
    await async_client.post(f"/api/v1/agents/{collection_name}", json=agent_data, headers=AUTH_HEADERS)

    # Try to update without auth
    update_data = {"type": "system"}
    response = await async_client.put(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}",
        json=update_data
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_agent_without_any_auth(async_client: AsyncClient):
    """Test that deleting an agent without any auth fails."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    # First create an agent
    agent_data = {"name": "Delete Auth Test Agent", "type": "human"}
    await async_client.post(f"/api/v1/agents/{collection_name}", json=agent_data, headers=AUTH_HEADERS)

    # Try to delete without auth
    response = await async_client.delete(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}"
    )
    assert response.status_code == 401


# Test for collection without agents attribute properly loaded
@pytest.mark.asyncio
async def test_list_agents_response_format(async_client: AsyncClient):
    """Test that list agents returns proper response format with all fields."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    # Create an agent
    agent_data = {
        "name": "Format Test Agent",
        "type": "test_type"
    }
    await async_client.post(f"/api/v1/agents/{collection_name}", json=agent_data, headers=AUTH_HEADERS)

    # List agents
    response = await async_client.get(f"/api/v1/agents/{collection_name}/", headers=AUTH_HEADERS)
    assert response.status_code == 200

    data = response.json()
    # Find our test agent
    test_agent = next((a for a in data if a["name"] == agent_data["name"]), None)
    assert test_agent is not None

    # Verify response format
    assert "id" in test_agent
    assert "name" in test_agent
    assert "type" in test_agent
    assert "collection_id" in test_agent
    assert "collection_name" in test_agent
    assert test_agent["collection_name"] == collection_name


@pytest.mark.asyncio
async def test_get_agent_response_format(async_client: AsyncClient):
    """Test that get agent returns proper response format with all fields."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    # Create an agent
    agent_data = {
        "name": "Get Format Test Agent",
        "type": "test_type"
    }
    create_resp = await async_client.post(
        f"/api/v1/agents/{collection_name}",
        json=agent_data,
        headers=AUTH_HEADERS
    )
    assert create_resp.status_code == 201

    # Get the agent
    response = await async_client.get(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}",
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200

    data = response.json()
    # Verify response format - AgentResponse schema
    assert "id" in data
    assert "name" in data
    assert "type" in data
    assert "collection_id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_update_agent_response_format(async_client: AsyncClient):
    """Test that update agent returns proper response format."""
    collection = await create_collection(async_client)
    collection_name = collection["name"]

    # Create an agent
    agent_data = {"name": "Update Format Test", "type": "human"}
    await async_client.post(f"/api/v1/agents/{collection_name}", json=agent_data, headers=AUTH_HEADERS)

    # Update the agent
    update_data = {"type": "system"}
    response = await async_client.put(
        f"/api/v1/agents/{collection_name}/{agent_data['name']}",
        json=update_data,
        headers=AUTH_HEADERS
    )
    assert response.status_code == 200

    data = response.json()
    # Verify response format - AgentResponse schema
    assert "id" in data
    assert "name" in data
    assert "type" in data
    assert data["type"] == "system"
    assert "collection_id" in data
    assert "created_at" in data
