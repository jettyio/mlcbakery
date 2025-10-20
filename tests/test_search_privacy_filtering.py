"""Tests for privacy-aware search filtering in Typesense.

These tests verify that search results respect user privacy settings:
- Users see their own private entities
- Users see all public entities from any collection
- Users cannot see other collections' private entities
"""

import pytest
import httpx

from mlcbakery.main import app
from mlcbakery.auth.passthrough_strategy import (
    sample_org_token,
    authorization_headers,
)


async def create_collection(ac, name: str):
    """Helper to create a collection."""
    resp = await ac.post(
        "/api/v1/collections/",
        json={"name": name, "description": f"Test collection {name}"},
        headers=authorization_headers(sample_org_token()),
    )
    assert resp.status_code == 200
    return resp.json()


async def create_dataset(ac, collection_name: str, dataset_name: str, is_private: bool, description: str = ""):
    """Helper to create a dataset with privacy settings."""
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
        headers=authorization_headers(sample_org_token()),
    )
    assert resp.status_code == 200
    return resp.json()


async def create_model(ac, collection_name: str, model_name: str, is_private: bool, description: str = ""):
    """Helper to create a trained model with privacy settings."""
    resp = await ac.post(
        f"/api/v1/models/{collection_name}",
        json={
            "name": model_name,
            "model_path": f"/path/{model_name}",
            "entity_type": "trained_model",
            "is_private": is_private,
            "long_description": description or f"Model {model_name}",
        },
        headers=authorization_headers(sample_org_token()),
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
            headers=authorization_headers(sample_org_token()),
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
            headers=authorization_headers(sample_org_token()),
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
    """Test that a user cannot see other collections' private entities."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Setup: Create two collections
        collection1 = await create_collection(ac, "UserCollection")
        collection2 = await create_collection(ac, "OtherCollection")

        # Create private entity in user's collection
        user_dataset = await create_dataset(
            ac,
            collection1["name"],
            "UserPrivateDataset",
            is_private=True,
            description="searchable content",
        )

        # Create private entity in other collection
        other_dataset = await create_dataset(
            ac,
            collection2["name"],
            "OtherPrivateDataset",
            is_private=True,
            description="searchable content",
        )

        # Search for content
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "private"},
            headers=authorization_headers(sample_org_token()),
        )

        assert resp.status_code == 200
        results = resp.json()
        hit_ids = [hit["document"]["id"] for hit in results["hits"]]

        # Should find own private dataset
        user_dataset_id = f"dataset/{collection1['name']}/{user_dataset['name']}"
        assert user_dataset_id in hit_ids

        # Should NOT find other collection's private dataset
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
            headers=authorization_headers(sample_org_token()),
        )
        assert ds_resp.status_code == 200
        ds_hits = [hit["document"]["id"] for hit in ds_resp.json()["hits"]]
        private_ds_id = f"dataset/{collection['name']}/{private_dataset['name']}"
        assert private_ds_id in ds_hits

        # Search models
        m_resp = await ac.get(
            "/api/v1/models/search",
            params={"q": "test"},
            headers=authorization_headers(sample_org_token()),
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
        # Setup: Create collection with only private entities from other collection
        collection1 = await create_collection(ac, "RestrictedCollection")
        collection2 = await create_collection(ac, "AccessibleCollection")

        # Create searchable private entity in collection1
        await create_dataset(
            ac,
            collection1["name"],
            "RestrictedDataset",
            is_private=True,
            description="restricted searchable content",
        )

        # Create a public reference in collection2 so user has something
        await create_dataset(
            ac,
            collection2["name"],
            "PublicDataset",
            is_private=False,
            description="public",
        )

        # Search for term that only matches restricted entity
        resp = await ac.get(
            "/api/v1/datasets/search",
            params={"q": "restricted"},
            headers=authorization_headers(sample_org_token()),
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
            headers=authorization_headers(sample_org_token()),
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
