"""Tests for privacy-aware search filtering in Typesense.

These tests verify that search results respect user privacy settings:
- Users see their own private entities
- Users see all public entities from any collection
- Users cannot see other collections' private entities
"""

import pytest
import httpx
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any
import uuid

from mlcbakery.main import app
from mlcbakery.auth.passthrough_strategy import (
    sample_org_token,
    authorization_headers,
)
from mlcbakery import search


# Store indexed documents in-memory for testing
_test_search_index: dict[str, dict[str, Any]] = {}

# Flag to track if we've set up the mock
_mock_setup_done = False

# Track org_id per test to ensure consistency
_current_test_org_id: str | None = None


def get_mock_typesense_client():
    """Return a mock Typesense client."""
    mock_client = MagicMock()

    # Mock the upsert method to store documents in our test index
    def mock_upsert(document):
        doc_id = document.get("id")
        if doc_id:
            _test_search_index[doc_id] = document
        return {"success": True}

    # Mock the search method to filter documents based on query
    def mock_search(params):
        q = params.get("q", "")
        filter_by = params.get("filter_by", "")
        per_page = params.get("per_page", 30)

        # Filter documents based on query and filters
        hits = []
        for doc_id, doc in _test_search_index.items():
            # Check if document matches query
            query_match = False
            search_text = str(doc.get("long_description", "")).lower()

            # Also check other searchable fields
            search_text += " " + str(doc.get("collection_name", "")).lower()
            search_text += " " + str(doc.get("entity_name", "")).lower()
            search_text += " " + str(doc.get("full_name", "")).lower()

            if q.lower() in search_text:
                query_match = True

            if not query_match:
                continue

            # Apply entity_type filter
            if "entity_type:dataset" in filter_by and doc.get("entity_type") != "dataset":
                continue
            if "entity_type:trained_model" in filter_by and doc.get("entity_type") != "trained_model":
                continue

            # Apply privacy filter
            if "is_private:false" in filter_by or "is_private:true" in filter_by:
                # Parse privacy filter logic
                is_private = doc.get("is_private", True)
                collection_id = doc.get("collection_id")

                # Extract collection_id(s) from filter if present
                filter_collection_ids = []
                if "collection_id:" in filter_by:
                    # Extract collection_id value from filter
                    parts = filter_by.split("collection_id:")
                    if len(parts) > 1:
                        id_part = parts[1].split(")")[0].split("&")[0].strip()
                        # Check if it's a list syntax: [1,2,3]
                        if id_part.startswith("[") and id_part.endswith("]"):
                            # Parse list of IDs
                            id_part = id_part[1:-1]  # Remove brackets
                            filter_collection_ids = [int(x.strip()) for x in id_part.split(",")]
                        else:
                            # Single ID
                            filter_collection_ids = [int(id_part)]

                # Apply privacy logic: (is_private:false) || (is_private:true && collection_id in filter_ids)
                allow_document = False
                if not is_private:
                    # Public documents are always visible
                    allow_document = True
                elif is_private and filter_collection_ids and collection_id in filter_collection_ids:
                    # Private document from user's collection(s)
                    allow_document = True

                if not allow_document:
                    continue

            hits.append({"document": doc})

            if len(hits) >= per_page:
                break

        return {"hits": hits}

    # Set up mock methods
    mock_client.collections.__getitem__.return_value.documents.upsert = mock_upsert
    mock_client.collections.__getitem__.return_value.documents.search = mock_search

    return mock_client


@pytest.fixture(scope="module", autouse=True)
def mock_typesense_client():
    """Mock Typesense client to avoid requiring actual Typesense instance in tests.

    This fixture uses module scope so the mock is set up once for all tests in this file,
    and uses direct patching rather than monkeypatch to ensure it's applied early enough.
    """
    # Patch the function directly at module import time
    original_func = search.setup_and_get_typesense_client
    search.setup_and_get_typesense_client = get_mock_typesense_client

    # Also override app dependency for the routes
    app.dependency_overrides[original_func] = get_mock_typesense_client

    yield

    # Clean up after all tests in module
    search.setup_and_get_typesense_client = original_func
    if original_func in app.dependency_overrides:
        del app.dependency_overrides[original_func]


@pytest.fixture(autouse=True)
def clear_test_index():
    """Clear the test index and set unique org_id before and after each test."""
    global _current_test_org_id
    _test_search_index.clear()
    # Set a unique org_id for this test
    _current_test_org_id = f"test_org_{uuid.uuid4().hex[:8]}"
    yield
    _test_search_index.clear()
    _current_test_org_id = None


async def create_collection(ac, name: str):
    """Helper to create a collection with unique name using test org_id."""
    # Add unique suffix to avoid collisions across tests
    unique_name = f"{name}_{uuid.uuid4().hex[:8]}"

    resp = await ac.post(
        "/api/v1/collections/",
        json={"name": unique_name, "description": f"Test collection {name}"},
        headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
    )
    assert resp.status_code == 200
    return resp.json()


async def create_dataset(ac, collection_name: str, dataset_name: str, is_private: bool, description: str = ""):
    """Helper to create a dataset with privacy settings using test org_id."""
    resp = await ac.post(
        f"/api/v1/datasets/{collection_name}",
        json={
            "name": dataset_name,
            "data_path": f"/path/{dataset_name}",
            "format": "json",
            "entity_type": "dataset",
            "is_private": is_private,
            "long_description": description or f"Dataset {dataset_name}",
        },
        headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
    )
    assert resp.status_code == 200
    return resp.json()


async def create_model(ac, collection_name: str, model_name: str, is_private: bool, description: str = ""):
    """Helper to create a trained model with privacy settings using test org_id."""
    resp = await ac.post(
        f"/api/v1/models/{collection_name}",
        json={
            "name": model_name,
            "model_path": f"/path/{model_name}",
            "entity_type": "trained_model",
            "is_private": is_private,
            "long_description": description or f"Model {model_name}",
        },
        headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.mark.asyncio
async def test_user_sees_own_private_entities():
    """Test that a user sees their own private entities in search results."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Setup: Create collection and private dataset
        collection = await create_collection(ac, "PrivateCollection")
        dataset = await create_dataset(
            ac,
            collection["name"],
            "PrivateDataset",
            is_private=True,
            description="searchable private content",
        )

        # Search for a term that matches the private entity
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "private"},
            headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
        )

        assert resp.status_code == 200
        results = resp.json()
        assert "hits" in results
        # Should find the private dataset
        hit_ids = [hit["document"]["id"] for hit in results["hits"]]
        dataset_id = f"dataset/{collection['name']}/{dataset['name']}"
        assert dataset_id in hit_ids


@pytest.mark.asyncio
async def test_user_sees_public_entities():
    """Test that a user sees public entities from all collections."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Setup: Create two collections with public entities
        collection1 = await create_collection(ac, "PublicCollection1")
        collection2 = await create_collection(ac, "PublicCollection2")

        dataset1 = await create_dataset(
            ac,
            collection1["name"],
            "PublicDataset1",
            is_private=False,
            description="public searchable content",
        )
        dataset2 = await create_dataset(
            ac,
            collection2["name"],
            "PublicDataset2",
            is_private=False,
            description="public searchable content",
        )

        # Search for public entities
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "public"},
            headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
        )

        assert resp.status_code == 200
        results = resp.json()
        hit_ids = [hit["document"]["id"] for hit in results["hits"]]

        # Should find both public datasets from different collections
        dataset1_id = f"dataset/{collection1['name']}/{dataset1['name']}"
        dataset2_id = f"dataset/{collection2['name']}/{dataset2['name']}"
        assert dataset1_id in hit_ids
        assert dataset2_id in hit_ids


@pytest.mark.asyncio
async def test_user_cannot_see_other_collections_private():
    """Test that a user cannot see other users' private entities."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Setup: Create user's collection with current org_id
        collection1 = await create_collection(ac, "UserCollection")

        # Create private entity in user's collection
        user_dataset = await create_dataset(
            ac,
            collection1["name"],
            "UserPrivateDataset",
            is_private=True,
            description="searchable content",
        )

        # Create another user's collection with different org_id
        other_org_id = f"other_org_{uuid.uuid4().hex[:8]}"
        collection2_resp = await ac.post(
            "/api/v1/collections/",
            json={"name": f"OtherCollection_{uuid.uuid4().hex[:8]}", "description": "Other user's collection"},
            headers=authorization_headers(sample_org_token(org_id=other_org_id)),
        )
        assert collection2_resp.status_code == 200
        collection2 = collection2_resp.json()

        # Create private entity in other user's collection
        other_dataset_resp = await ac.post(
            f"/api/v1/datasets/{collection2['name']}",
            json={
                "name": "OtherPrivateDataset",
                "data_path": "/path/OtherPrivateDataset",
                "format": "json",
                "entity_type": "dataset",
                "is_private": True,
                "long_description": "searchable content",
            },
            headers=authorization_headers(sample_org_token(org_id=other_org_id)),
        )
        assert other_dataset_resp.status_code == 200
        other_dataset = other_dataset_resp.json()

        # Search as the first user
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "searchable"},
            headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
        )

        assert resp.status_code == 200
        results = resp.json()
        hit_ids = [hit["document"]["id"] for hit in results["hits"]]

        # Should find own private dataset
        user_dataset_id = f"dataset/{collection1['name']}/{user_dataset['name']}"
        assert user_dataset_id in hit_ids

        # Should NOT find other user's private dataset
        other_dataset_id = f"dataset/{collection2['name']}/{other_dataset['name']}"
        assert other_dataset_id not in hit_ids


@pytest.mark.asyncio
async def test_both_dataset_and_model_searches_filtered():
    """Test that both dataset and model searches apply privacy filtering."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Setup: Create entities
        collection = await create_collection(ac, "SearchTestCollection")

        # Create private dataset and public model
        private_dataset = await create_dataset(
            ac,
            collection["name"],
            "PrivateDataset",
            is_private=True,
            description="test searchable",
        )
        public_model = await create_model(
            ac,
            collection["name"],
            "PublicModel",
            is_private=False,
            description="test searchable",
        )

        # Search datasets
        ds_resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "test"},
            headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
        )
        assert ds_resp.status_code == 200
        ds_hits = [hit["document"]["id"] for hit in ds_resp.json()["hits"]]
        private_ds_id = f"dataset/{collection['name']}/{private_dataset['name']}"
        assert private_ds_id in ds_hits

        # Search models
        m_resp = await ac.get(
            "/api/v1/models/search",
            params={"q": "test"},
            headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
        )
        assert m_resp.status_code == 200
        m_hits = [hit["document"]["id"] for hit in m_resp.json()["hits"]]
        public_m_id = f"trained_model/{collection['name']}/{public_model['name']}"
        assert public_m_id in m_hits


@pytest.mark.asyncio
async def test_empty_results_when_no_access():
    """Test that search returns empty results (not 403) when user has no access."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Setup: Create another user's collection with private entity
        other_org_id = f"other_org_{uuid.uuid4().hex[:8]}"
        collection1_resp = await ac.post(
            "/api/v1/collections/",
            json={"name": f"RestrictedCollection_{uuid.uuid4().hex[:8]}", "description": "Other user's collection"},
            headers=authorization_headers(sample_org_token(org_id=other_org_id)),
        )
        assert collection1_resp.status_code == 200
        collection1 = collection1_resp.json()

        # Create searchable private entity in other user's collection
        await ac.post(
            f"/api/v1/datasets/{collection1['name']}",
            json={
                "name": "RestrictedDataset",
                "data_path": "/path/RestrictedDataset",
                "format": "json",
                "entity_type": "dataset",
                "is_private": True,
                "long_description": "restricted searchable content",
            },
            headers=authorization_headers(sample_org_token(org_id=other_org_id)),
        )

        # Create our user's collection with a public dataset
        collection2 = await create_collection(ac, "AccessibleCollection")
        await create_dataset(
            ac,
            collection2["name"],
            "PublicDataset",
            is_private=False,
            description="public",
        )

        # Search as our user for term that only matches restricted entity
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "restricted"},
            headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
        )

        # Should return 200 with empty results, not 403
        assert resp.status_code == 200
        results = resp.json()
        assert len(results["hits"]) == 0


@pytest.mark.asyncio
async def test_search_with_pagination_respects_privacy():
    """Test that pagination still respects privacy filtering."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Setup: Create collection with many entities
        collection1 = await create_collection(ac, "PaginatedCollection1")
        collection2 = await create_collection(ac, "PaginatedCollection2")

        # Create multiple public and private entities
        for i in range(5):
            await create_dataset(
                ac,
                collection1["name"],
                f"PrivateDataset{i}",
                is_private=True,
                description="paginated test",
            )
            await create_dataset(
                ac,
                collection2["name"],
                f"PublicDataset{i}",
                is_private=False,
                description="paginated test",
            )

        # Search with limit
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "paginated", "limit": 3},
            headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
        )

        assert resp.status_code == 200
        results = resp.json()

        # Should get results but not more than limit
        assert len(results["hits"]) <= 3

        # All results should be either:
        # - User's private entities, OR
        # - Public entities
        for hit in results["hits"]:
            doc = hit["document"]
            if collection2["name"] in doc["collection_name"]:
                # Public collection, should be public
                assert doc["is_private"] is False
            # If from collection1, will be private (user's collection)


@pytest.mark.asyncio
async def test_search_returns_is_private_field():
    """Test that search results include the is_private field."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Setup: Create collection with mixed privacy entities
        collection = await create_collection(ac, "MixedPrivacyCollection")

        await create_dataset(
            ac,
            collection["name"],
            "PublicDataset",
            is_private=False,
            description="public entity",
        )

        await create_dataset(
            ac,
            collection["name"],
            "PrivateDataset",
            is_private=True,
            description="private entity",
        )

        # Search for entities
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "entity"},
            headers=authorization_headers(sample_org_token(org_id=_current_test_org_id)),
        )

        assert resp.status_code == 200
        results = resp.json()
        assert len(results["hits"]) == 2

        # Verify is_private field is present and correct
        for hit in results["hits"]:
            doc = hit["document"]
            assert "is_private" in doc
            if "Public" in doc["entity_name"]:
                assert doc["is_private"] is False
            else:
                assert doc["is_private"] is True


@pytest.mark.asyncio
async def test_admin_user_sees_all_entities():
    """Test that admin users bypass privacy filtering."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collections for different users
        other_org_id = f"other_org_{uuid.uuid4().hex[:8]}"

        # Create current user's collection with private entity
        collection1 = await create_collection(ac, "UserCollection")
        await create_dataset(
            ac,
            collection1["name"],
            "UserPrivateDataset",
            is_private=True,
            description="admin test searchable",
        )

        # Create other user's collection with private entity
        collection2_resp = await ac.post(
            "/api/v1/collections/",
            json={"name": f"OtherCollection_{uuid.uuid4().hex[:8]}", "description": "Other user's collection"},
            headers=authorization_headers(sample_org_token(org_id=other_org_id)),
        )
        assert collection2_resp.status_code == 200
        collection2 = collection2_resp.json()

        other_dataset_resp = await ac.post(
            f"/api/v1/datasets/{collection2['name']}",
            json={
                "name": "OtherPrivateDataset",
                "data_path": "/path/other",
                "format": "json",
                "entity_type": "dataset",
                "is_private": True,
                "long_description": "admin test searchable",
            },
            headers=authorization_headers(sample_org_token(org_id=other_org_id)),
        )
        assert other_dataset_resp.status_code == 200

        # Search as admin (using TEST_ADMIN_TOKEN from conftest)
        from conftest import TEST_ADMIN_TOKEN
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "admin test"},
            headers={"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"},
        )

        assert resp.status_code == 200
        results = resp.json()

        # Admin should see both private datasets
        hit_ids = [hit["document"]["id"] for hit in results["hits"]]
        assert len(hit_ids) >= 2
