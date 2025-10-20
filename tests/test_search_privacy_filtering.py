"""
Integration tests for privacy-filtered search functionality.

These tests define the expected behavior of privacy-aware search where:
- Users see their own private entities (within their collection)
- Users see all public entities (from any collection)
- Users cannot see other collections' private entities
- Search results respect user permissions

Tests are initially failing (red phase of TDD) to establish the contract
that the privacy-filtering implementation must satisfy.
"""

import pytest
import uuid
from mlcbakery.auth.passthrough_strategy import sample_org_token, authorization_headers
from mlcbakery.main import app
import httpx


# --- Test Fixtures ---

@pytest.fixture
async def user_a_token():
    """Token for User A (organization A)."""
    return sample_org_token(org_id="org_user_a", user_sub="user_a")


@pytest.fixture
async def user_b_token():
    """Token for User B (organization B)."""
    return sample_org_token(org_id="org_user_b", user_sub="user_b")


@pytest.fixture
async def user_c_token():
    """Token for User C (organization C)."""
    return sample_org_token(org_id="org_user_c", user_sub="user_c")


@pytest.fixture
async def async_client():
    """Async HTTP client for testing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def collection_x(async_client, user_a_token):
    """Create Collection X owned by User A."""
    collection_data = {
        "name": f"collection-x-{uuid.uuid4().hex[:8]}",
        "description": "Collection X for privacy testing",
    }
    response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(user_a_token),
    )
    assert response.status_code == 200
    return response.json()["name"]


@pytest.fixture
async def collection_y(async_client, user_b_token):
    """Create Collection Y owned by User B."""
    collection_data = {
        "name": f"collection-y-{uuid.uuid4().hex[:8]}",
        "description": "Collection Y for privacy testing",
    }
    response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(user_b_token),
    )
    assert response.status_code == 200
    return response.json()["name"]


@pytest.fixture
async def collection_z(async_client, user_c_token):
    """Create Collection Z owned by User C."""
    collection_data = {
        "name": f"collection-z-{uuid.uuid4().hex[:8]}",
        "description": "Collection Z for privacy testing",
    }
    response = await async_client.post(
        "/api/v1/collections/",
        json=collection_data,
        headers=authorization_headers(user_c_token),
    )
    assert response.status_code == 200
    return response.json()["name"]


# --- Test 1: User sees own private entities in search results ---


@pytest.mark.asyncio
async def test_user_sees_own_private_dataset(
    async_client, collection_x, user_a_token
):
    """
    Test: User A creates private dataset in Collection X
    - User A searches and finds own private dataset
    - Assertion: search result includes the entity
    """
    dataset_name = f"private-dataset-{uuid.uuid4().hex[:8]}"
    dataset_data = {
        "name": dataset_name,
        "data_path": "/path/to/private/dataset",
        "format": "json",
        "entity_type": "dataset",
        "is_private": True,
    }

    # Create private dataset
    create_response = await async_client.post(
        f"/api/v1/datasets/{collection_x}",
        json=dataset_data,
        headers=authorization_headers(user_a_token),
    )
    assert create_response.status_code == 200
    assert create_response.json()["is_private"] is True

    # Search for the dataset
    search_response = await async_client.get(
        "/api/v1/datasets/search",
        params={"q": dataset_name},
        headers=authorization_headers(user_a_token),
    )
    assert search_response.status_code == 200
    results = search_response.json()

    # Verify dataset appears in results
    found_dataset = any(
        r["entity_name"] == dataset_name for r in results.get("hits", [])
    )
    assert found_dataset, f"User A should see their own private dataset '{dataset_name}'"


# --- Test 2: User sees public entities in search results ---


@pytest.mark.asyncio
async def test_user_sees_public_entities_from_different_collections(
    async_client, collection_x, collection_y, user_a_token, user_b_token
):
    """
    Test: User A creates public dataset in Collection X
         User B creates public model in Collection Y
    - User A searches and sees both public entities
    - Assertion: search results include both entities from different collections
    """
    dataset_name = f"public-dataset-{uuid.uuid4().hex[:8]}"
    dataset_data = {
        "name": dataset_name,
        "data_path": "/path/to/public/dataset",
        "format": "json",
        "entity_type": "dataset",
        "is_private": False,
    }

    # User A creates public dataset in Collection X
    create_ds_response = await async_client.post(
        f"/api/v1/datasets/{collection_x}",
        json=dataset_data,
        headers=authorization_headers(user_a_token),
    )
    assert create_ds_response.status_code == 200
    assert create_ds_response.json()["is_private"] is False

    # User B creates public model in Collection Y
    model_name = f"public-model-{uuid.uuid4().hex[:8]}"
    model_data = {
        "name": model_name,
        "model_path": "/path/to/public/model",
        "entity_type": "trained_model",
        "is_private": False,
    }
    create_model_response = await async_client.post(
        f"/api/v1/models/{collection_y}",
        json=model_data,
        headers=authorization_headers(user_b_token),
    )
    assert create_model_response.status_code == 201
    assert create_model_response.json()["is_private"] is False

    # User A searches for public dataset
    search_ds_response = await async_client.get(
        "/api/v1/datasets/search",
        params={"q": dataset_name},
        headers=authorization_headers(user_a_token),
    )
    assert search_ds_response.status_code == 200
    ds_results = search_ds_response.json()

    # User A searches for public model
    search_model_response = await async_client.get(
        "/api/v1/models/search",
        params={"q": model_name},
        headers=authorization_headers(user_a_token),
    )
    assert search_model_response.status_code == 200
    model_results = search_model_response.json()

    # Verify both public entities appear
    found_dataset = any(
        r["entity_name"] == dataset_name for r in ds_results.get("hits", [])
    )
    found_model = any(
        r["entity_name"] == model_name for r in model_results.get("hits", [])
    )
    assert found_dataset, "User A should see public dataset"
    assert found_model, "User A should see public model from different collection"


# --- Test 3: User cannot see other collections' private entities ---


@pytest.mark.asyncio
async def test_user_cannot_see_other_collections_private_entities(
    async_client, collection_x, collection_y, user_a_token, user_b_token
):
    """
    Test: User A creates private dataset in Collection X
         User B creates private dataset in Collection Y
    - User A searches and does NOT see User B's private entity
    - Assertion: search results exclude other collections' private entities
    """
    # User A creates private dataset in Collection X
    dataset_x_name = f"private-dataset-a-{uuid.uuid4().hex[:8]}"
    dataset_x_data = {
        "name": dataset_x_name,
        "data_path": "/path/to/private/dataset/a",
        "format": "json",
        "entity_type": "dataset",
        "is_private": True,
    }
    create_x_response = await async_client.post(
        f"/api/v1/datasets/{collection_x}",
        json=dataset_x_data,
        headers=authorization_headers(user_a_token),
    )
    assert create_x_response.status_code == 200

    # User B creates private dataset in Collection Y with similar name for search
    dataset_y_name = f"private-dataset-b-{uuid.uuid4().hex[:8]}"
    dataset_y_data = {
        "name": dataset_y_name,
        "data_path": "/path/to/private/dataset/b",
        "format": "json",
        "entity_type": "dataset",
        "is_private": True,
    }
    create_y_response = await async_client.post(
        f"/api/v1/datasets/{collection_y}",
        json=dataset_y_data,
        headers=authorization_headers(user_b_token),
    )
    assert create_y_response.status_code == 200

    # User A searches for "private-dataset" - should only find their own
    search_response = await async_client.get(
        "/api/v1/datasets/search",
        params={"q": "private-dataset"},
        headers=authorization_headers(user_a_token),
    )
    assert search_response.status_code == 200
    results = search_response.json()

    # User A should find their own private dataset
    found_own = any(
        r["entity_name"] == dataset_x_name for r in results.get("hits", [])
    )
    assert found_own, "User A should find their own private dataset"

    # User A should NOT find User B's private dataset
    found_other = any(
        r["entity_name"] == dataset_y_name for r in results.get("hits", [])
    )
    assert (
        not found_other
    ), "User A should NOT see User B's private dataset from different collection"


# --- Test 4: Admin/no-auth sees all entities (baseline test) ---


@pytest.mark.asyncio
async def test_admin_token_sees_all_entities(
    async_client, collection_x, collection_y, user_a_token, user_b_token, admin_token_auth_headers
):
    """
    Test: Create mixed public/private entities across collections
    - Search without auth filter (using admin token)
    - Assertion: all entities appear (for comparison with filtered results)
    """
    # User A creates private dataset in Collection X
    dataset_x_name = f"admin-test-private-{uuid.uuid4().hex[:8]}"
    dataset_x_data = {
        "name": dataset_x_name,
        "data_path": "/path/to/admin/test/private",
        "format": "json",
        "entity_type": "dataset",
        "is_private": True,
    }
    create_x_response = await async_client.post(
        f"/api/v1/datasets/{collection_x}",
        json=dataset_x_data,
        headers=authorization_headers(user_a_token),
    )
    assert create_x_response.status_code == 200

    # User B creates public dataset in Collection Y
    dataset_y_name = f"admin-test-public-{uuid.uuid4().hex[:8]}"
    dataset_y_data = {
        "name": dataset_y_name,
        "data_path": "/path/to/admin/test/public",
        "format": "json",
        "entity_type": "dataset",
        "is_private": False,
    }
    create_y_response = await async_client.post(
        f"/api/v1/datasets/{collection_y}",
        json=dataset_y_data,
        headers=authorization_headers(user_b_token),
    )
    assert create_y_response.status_code == 200

    # Admin searches and sees both public and private entities
    search_response = await async_client.get(
        "/api/v1/datasets/search",
        params={"q": "admin-test"},
        headers=admin_token_auth_headers,
    )
    assert search_response.status_code == 200
    results = search_response.json()

    # Admin should see both private and public datasets
    found_private = any(
        r["entity_name"] == dataset_x_name for r in results.get("hits", [])
    )
    found_public = any(
        r["entity_name"] == dataset_y_name for r in results.get("hits", [])
    )
    assert found_private, "Admin should see private entities"
    assert found_public, "Admin should see public entities"


# --- Test 5: Search pagination works with privacy filtering ---


@pytest.mark.asyncio
async def test_search_pagination_respects_privacy_filtering(
    async_client, collection_x, collection_y, user_a_token, user_b_token
):
    """
    Test: Create many entities (public and private)
    - Query with pagination parameters
    - Assertion: privacy filter still applies across pages
    """
    # Create 5 private datasets in Collection X (User A)
    private_datasets = []
    for i in range(5):
        dataset_name = f"pagination-private-{i}-{uuid.uuid4().hex[:8]}"
        dataset_data = {
            "name": dataset_name,
            "data_path": f"/path/to/pagination/private/{i}",
            "format": "json",
            "entity_type": "dataset",
            "is_private": True,
        }
        response = await async_client.post(
            f"/api/v1/datasets/{collection_x}",
            json=dataset_data,
            headers=authorization_headers(user_a_token),
        )
        assert response.status_code == 200
        private_datasets.append(dataset_name)

    # Create 5 public datasets in Collection Y (User B)
    public_datasets = []
    for i in range(5):
        dataset_name = f"pagination-public-{i}-{uuid.uuid4().hex[:8]}"
        dataset_data = {
            "name": dataset_name,
            "data_path": f"/path/to/pagination/public/{i}",
            "format": "json",
            "entity_type": "dataset",
            "is_private": False,
        }
        response = await async_client.post(
            f"/api/v1/datasets/{collection_y}",
            json=dataset_data,
            headers=authorization_headers(user_b_token),
        )
        assert response.status_code == 200
        public_datasets.append(dataset_name)

    # User A searches with limit=3 (should see 3 private + 3 public if available)
    search_response = await async_client.get(
        "/api/v1/datasets/search",
        params={"q": "pagination", "limit": 3},
        headers=authorization_headers(user_a_token),
    )
    assert search_response.status_code == 200
    results = search_response.json()
    first_page = results.get("hits", [])

    # Should get some results
    assert len(first_page) > 0, "Should get results from first page"

    # Verify no private datasets from Collection Y appear
    for result in first_page:
        assert result["entity_name"] not in [\n            f"pagination-public-{i}-*" for i in range(5)\n        ] or any(\n            pub_name in result["entity_name"] for pub_name in public_datasets\n        ), "Results should only contain own private or public entities"


# --- Test 6: Both dataset and trained model searches are filtered ---


@pytest.mark.asyncio
async def test_both_dataset_and_model_searches_are_filtered(
    async_client, collection_x, collection_y, user_a_token, user_b_token
):
    """
    Test: Create private/public datasets and models
    - Query both endpoints
    - Assertion: both endpoints apply privacy filtering
    """
    # User A creates private dataset
    dataset_name = f"model-test-dataset-{uuid.uuid4().hex[:8]}"
    dataset_data = {
        "name": dataset_name,
        "data_path": "/path/to/model/test/dataset",
        "format": "json",
        "entity_type": "dataset",
        "is_private": True,
    }
    dataset_response = await async_client.post(
        f"/api/v1/datasets/{collection_x}",
        json=dataset_data,
        headers=authorization_headers(user_a_token),
    )
    assert dataset_response.status_code == 200

    # User B creates private model in Collection Y
    model_name = f"model-test-model-{uuid.uuid4().hex[:8]}"
    model_data = {
        "name": model_name,
        "model_path": "/path/to/model/test/model",
        "entity_type": "trained_model",
        "is_private": True,
    }
    model_response = await async_client.post(
        f"/api/v1/models/{collection_y}",
        json=model_data,
        headers=authorization_headers(user_b_token),
    )
    assert model_response.status_code == 201

    # User A searches datasets - should find own private dataset
    dataset_search = await async_client.get(
        "/api/v1/datasets/search",
        params={"q": "model-test-dataset"},
        headers=authorization_headers(user_a_token),
    )
    assert dataset_search.status_code == 200
    ds_results = dataset_search.json().get("hits", [])
    found_dataset = any(r["entity_name"] == dataset_name for r in ds_results)
    assert found_dataset, "User A should find their own private dataset"

    # User A searches models - should NOT find User B's private model
    model_search = await async_client.get(
        "/api/v1/models/search",
        params={"q": "model-test-model"},
        headers=authorization_headers(user_a_token),
    )
    assert model_search.status_code == 200
    model_results = model_search.json().get("hits", [])
    found_model = any(r["entity_name"] == model_name for r in model_results)
    assert (
        not found_model
    ), "User A should NOT find User B's private model from different collection"


# --- Test 7: Empty results when user has no access ---


@pytest.mark.asyncio
async def test_empty_results_when_user_has_no_access(
    async_client, collection_y, user_a_token, user_b_token
):
    """
    Test: Create only other collections' private entities (matching query term)
    - User searches
    - Assertion: search returns empty results (not 403)
    """
    # User B creates private dataset in Collection Y
    dataset_name = f"no-access-{uuid.uuid4().hex[:8]}"
    dataset_data = {
        "name": dataset_name,
        "data_path": "/path/to/no/access",
        "format": "json",
        "entity_type": "dataset",
        "is_private": True,
    }
    create_response = await async_client.post(
        f"/api/v1/datasets/{collection_y}",
        json=dataset_data,
        headers=authorization_headers(user_b_token),
    )
    assert create_response.status_code == 200

    # User A searches for the dataset that they don't have access to
    search_response = await async_client.get(
        "/api/v1/datasets/search",
        params={"q": dataset_name},
        headers=authorization_headers(user_a_token),
    )
    # Should return 200 OK (not 403 Forbidden)
    assert search_response.status_code == 200

    # Results should be empty
    results = search_response.json()
    assert (
        len(results.get("hits", [])) == 0
    ), "User A should get empty results (not 403) when searching for inaccessible private entities"
