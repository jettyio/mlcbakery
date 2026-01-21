import pytest
import httpx
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from mlcbakery.main import app
from conftest import TEST_ADMIN_TOKEN
from mlcbakery.auth.passthrough_strategy import sample_user_token, sample_org_token, authorization_headers
from mlcbakery import search

# Define headers globally
AUTH_HEADERS = authorization_headers(sample_org_token())

# TestClient for synchronous tests
client = TestClient(app)

def create_collection(name: str):
    """Helper function to create a test collection."""
    collection_data = {
        "name": name,
        "description": "A test collection for trained model API testing."
    }
    response = client.post("/api/v1/collections/", json=collection_data, headers=AUTH_HEADERS)
    assert response.status_code == 200, f"Failed to create collection: {response.text}"
    return response.json()


# Positive test cases for CRUD operations

@pytest.mark.asyncio
async def test_create_trained_model_by_collection_name():
    """Test creating a trained model using collection name."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection first
        collection = create_collection("create-model-test-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Test Model",
            "model_path": "/models/test_model.pt",
            "metadata_version": "1.0.0",
            "model_metadata": {"accuracy": 0.95},
            "asset_origin": "s3://bucket/model.pt",
            "long_description": "A test model",
            "model_attributes": {"input_shape": [224, 224, 3]}
        }
        
        response = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 201, f"Failed to create trained model: {response.text}"
        
        data = response.json()
        assert data["name"] == model_data["name"]
        assert data["model_path"] == model_data["model_path"]
        assert data["metadata_version"] == model_data["metadata_version"]
        assert data["model_metadata"] == model_data["model_metadata"]
        assert data["asset_origin"] == model_data["asset_origin"]
        assert data["long_description"] == model_data["long_description"]
        assert data["model_attributes"] == model_data["model_attributes"]
        assert data["entity_type"] == "trained_model"
        assert "id" in data
        assert "created_at" in data


@pytest.mark.asyncio
async def test_create_trained_model_duplicate_name_in_collection():
    """Test that creating a trained model with duplicate name in same collection fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection first
        collection = create_collection("duplicate-model-test-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Duplicate Model",
            "model_path": "/models/duplicate_model.pt"
        }
        
        # Create first model
        response1 = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert response1.status_code == 201
        
        # Try to create second model with same name
        response2 = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert response2.status_code == 400
        assert "already exists" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_create_trained_model_nonexistent_collection():
    """Test creating a trained model in a nonexistent collection fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        model_data = {
            "name": "Model In Missing Collection",
            "model_path": "/models/missing_collection_model.pt"
        }
        
        response = await ac.post(
            "/api/v1/models/nonexistent-collection", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_trained_models_by_collection():
    """Test listing trained models in a specific collection."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection = create_collection("list-models-test-collection")
        collection_name = collection["name"]
        
        # Create multiple models
        created_models = []
        for i in range(2):
            model_data = {
                "name": f"List Test Model {i+1}",
                "model_path": f"/models/list_test_model_{i+1}.pt"
            }
            resp = await ac.post(
                f"/api/v1/models/{collection_name}", 
                json=model_data, 
                headers=AUTH_HEADERS
            )
            assert resp.status_code == 201
            created_models.append(resp.json())
        
        # List models in the collection
        response = await ac.get(f"/api/v1/models/{collection_name}/", headers=AUTH_HEADERS)
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 2  # Our 2 created models
        
        # Check that our created models are in the list
        model_names = [model["name"] for model in data]
        for model in created_models:
            assert model["name"] in model_names


@pytest.mark.asyncio
async def test_list_trained_models_nonexistent_collection():
    """Test listing trained models in a nonexistent collection fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/models/nonexistent-collection/", headers=AUTH_HEADERS)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_trained_model_by_collection_and_name():
    """Test getting a specific trained model by collection and model name."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("get-model-test-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Get Test Model",
            "model_path": "/models/get_test_model.pt",
            "long_description": "Test model for get operation"
        }
        
        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Get the model
        response = await ac.get(
            f"/api/v1/models/{collection_name}/{model_data['name']}", 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == model_data["name"]
        assert data["model_path"] == model_data["model_path"]
        assert data["long_description"] == model_data["long_description"]


@pytest.mark.asyncio
async def test_get_trained_model_nonexistent_collection_or_model():
    """Test getting a trained model from nonexistent collection or nonexistent model fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Test nonexistent collection
        response1 = await ac.get(
            "/api/v1/models/nonexistent-collection/some-model", 
            headers=AUTH_HEADERS
        )
        assert response1.status_code == 404
        assert "not found" in response1.json()["detail"]
        
        # Test existing collection but nonexistent model
        collection = create_collection("existing-collection-nonexistent-model")
        collection_name = collection["name"]
        
        response2 = await ac.get(
            f"/api/v1/models/{collection_name}/nonexistent-model", 
            headers=AUTH_HEADERS
        )
        assert response2.status_code == 404
        assert "not found" in response2.json()["detail"]


@pytest.mark.asyncio
async def test_delete_trained_model_by_collection_and_name():
    """Test deleting a trained model by collection and model name."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("delete-model-test-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Delete Test Model",
            "model_path": "/models/delete_test_model.pt"
        }
        
        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Delete the model
        response = await ac.delete(
            f"/api/v1/models/{collection_name}/{model_data['name']}", 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]
        
        # Verify model is deleted
        get_response = await ac.get(
            f"/api/v1/models/{collection_name}/{model_data['name']}", 
            headers=AUTH_HEADERS
        )
        assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_delete_trained_model_nonexistent():
    """Test deleting a nonexistent trained model fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        collection = create_collection("delete-nonexistent-model-collection")
        collection_name = collection["name"]
        
        response = await ac.delete(
            f"/api/v1/models/{collection_name}/nonexistent-model", 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_case_insensitive_model_names():
    """Test that model names are case-insensitive."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection = create_collection("case-insensitive-model-collection")
        collection_name = collection["name"]
        
        # Create model with mixed case name
        model_data = {
            "name": "Case Test Model",
            "model_path": "/models/case_test_model.pt"
        }
        
        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Get model using different case
        response = await ac.get(
            f"/api/v1/models/{collection_name}/Case Test Model", 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == model_data["name"]


@pytest.mark.asyncio
async def test_update_trained_model_by_collection_and_name():
    """Test updating a trained model by collection and model name."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("update-model-test-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Update Test Model",
            "model_path": "/models/update_test_model.pt",
            "long_description": "Original description"
        }
        
        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Update the model
        update_data = {
            "name": "Updated Test Model",
            "long_description": "Updated description",
            "model_metadata": {"updated": True}
        }
        
        response = await ac.put(
            f"/api/v1/models/{collection_name}/{model_data['name']}", 
            json=update_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["long_description"] == update_data["long_description"]
        assert data["model_metadata"] == update_data["model_metadata"]
        # Original model_path should remain unchanged
        assert data["model_path"] == model_data["model_path"]
        
        # Verify we can get the model by its new name
        get_response = await ac.get(
            f"/api/v1/models/{collection_name}/{update_data['name']}", 
            headers=AUTH_HEADERS
        )
        assert get_response.status_code == 200


@pytest.mark.asyncio
async def test_update_trained_model_partial():
    """Test partial update of a trained model."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("partial-update-model-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Partial Update Model",
            "model_path": "/models/partial_update_model.pt",
            "long_description": "Original description",
            "model_metadata": {"version": 1}
        }
        
        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Partial update - only update long_description
        update_data = {
            "long_description": "Partially updated description"
        }
        
        response = await ac.put(
            f"/api/v1/models/{collection_name}/{model_data['name']}", 
            json=update_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        
        data = response.json()
        # Updated field
        assert data["long_description"] == update_data["long_description"]
        # Unchanged fields
        assert data["name"] == model_data["name"]
        assert data["model_path"] == model_data["model_path"]
        assert data["model_metadata"] == model_data["model_metadata"]


@pytest.mark.asyncio
async def test_update_trained_model_duplicate_name():
    """Test that updating a trained model name to an existing name in the same collection fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection = create_collection("duplicate-name-update-collection")
        collection_name = collection["name"]
        
        # Create two models
        model1_data = {
            "name": "Model One",
            "model_path": "/models/model_one.pt"
        }
        model2_data = {
            "name": "Model Two",
            "model_path": "/models/model_two.pt"
        }
        
        create_resp1 = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model1_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp1.status_code == 201
        
        create_resp2 = await ac.post(
            f"/api/v1/models/{collection_name}", 
            json=model2_data, 
            headers=AUTH_HEADERS
        )
        assert create_resp2.status_code == 201
        
        # Try to update model2 name to model1's name
        update_data = {
            "name": "Model One"  # Same as model1
        }
        
        response = await ac.put(
            f"/api/v1/models/{collection_name}/{model2_data['name']}", 
            json=update_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]


@pytest.mark.asyncio
async def test_update_nonexistent_trained_model():
    """Test updating a nonexistent trained model fails."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        collection = create_collection("update-nonexistent-model-collection")
        collection_name = collection["name"]
        
        update_data = {
            "name": "Updated Name",
            "long_description": "Updated description"
        }
        
        response = await ac.put(
            f"/api/v1/models/{collection_name}/nonexistent-model", 
            json=update_data, 
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


# Authentication requirement tests for read endpoints
@pytest.mark.asyncio
async def test_list_trained_models_without_authorization():
    """Test that listing trained models requires authentication."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection with proper auth first
        collection = create_collection("auth-required-list-models-collection")
        collection_name = collection["name"]
        
        # Try to list models without authorization headers
        response = await ac.get(f"/api/v1/models/{collection_name}/")
        assert response.status_code == 401
        assert response.json()["detail"]  # Verify there's an error detail


@pytest.mark.asyncio
async def test_get_trained_model_without_authorization():
    """Test that getting a specific trained model requires authentication."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model with proper auth first
        collection = create_collection("auth-required-get-model-collection")
        collection_name = collection["name"]

        model_data = {
            "name": "Auth Required Test Model",
            "model_path": "/models/auth_required_model.pt"
        }

        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201

        # Try to get model without authorization headers
        response = await ac.get(f"/api/v1/models/{collection_name}/{model_data['name']}")
        assert response.status_code == 401
        assert response.json()["detail"]  # Verify there's an error detail


# Write access restriction tests
@pytest.mark.asyncio
async def test_create_trained_model_without_write_access():
    """Test that users without write access cannot create trained models."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection with admin access first
        collection = create_collection("write-access-test-models-collection")
        collection_name = collection["name"]
        
        # Try to create model with read-only access (non-admin role)
        read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
        model_data = {
            "name": "Unauthorized Model",
            "model_path": "/models/unauthorized_model.pt"
        }
        
        response = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=read_only_headers
        )
        assert response.status_code == 403
        assert "Access level WRITE required" in response.json()["detail"]


# Additional edge case tests for better coverage

@pytest.mark.asyncio
async def test_list_trained_models_by_collection_with_pagination():
    """Test listing trained models with pagination parameters."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection with multiple models
        collection = create_collection("pagination-test-models-collection")
        collection_name = collection["name"]
        
        # Create 3 models
        for i in range(3):
            model_data = {
                "name": f"Pagination Model {i+1}",
                "model_path": f"/models/pagination_model_{i+1}.pt"
            }
            create_resp = await ac.post(
                f"/api/v1/models/{collection_name}",
                json=model_data,
                headers=AUTH_HEADERS
            )
            assert create_resp.status_code == 201
        
        # Test pagination with limit
        response = await ac.get(
            f"/api/v1/models/{collection_name}/?limit=2",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Test pagination with skip
        response = await ac.get(
            f"/api/v1/models/{collection_name}/?skip=1&limit=2",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


@pytest.mark.asyncio
async def test_update_trained_model_name_same_case():
    """Test updating model name to the same name (same case) should succeed."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("same-name-update-models-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Same Name Model",
            "model_path": "/models/same_name.pt"
        }
        
        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Update with the exact same name should succeed
        update_data = {
            "name": "Same Name Model",
            "long_description": "Updated description"
        }
        
        response = await ac.put(
            f"/api/v1/models/{collection_name}/{model_data['name']}",
            json=update_data,
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["long_description"] == update_data["long_description"]


@pytest.mark.asyncio
async def test_create_trained_model_with_all_optional_fields():
    """Test creating model with comprehensive field coverage."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection = create_collection("all-fields-models-collection")
        collection_name = collection["name"]
        
        # Test with all optional fields
        comprehensive_model_data = {
            "name": "Comprehensive Model",
            "model_path": "/models/comprehensive.pt",
            "metadata_version": "2.0.0",
            "model_metadata": {"accuracy": 0.95, "framework": "pytorch"},
            "asset_origin": "s3://bucket/model.pt",
            "long_description": "A comprehensive model for testing",
            "model_attributes": {"input_size": 224, "num_classes": 1000}
        }
        
        response = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=comprehensive_model_data,
            headers=AUTH_HEADERS
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == comprehensive_model_data["name"]
        assert data["model_metadata"] == comprehensive_model_data["model_metadata"]
        assert data["model_attributes"] == comprehensive_model_data["model_attributes"]
        assert data["entity_type"] == "trained_model"


@pytest.mark.asyncio
async def test_update_trained_model_without_write_access():
    """Test that users without write access cannot update trained models."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model with admin access
        collection = create_collection("update-access-test-models-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Update Test Model",
            "model_path": "/models/update_test_model.pt"
        }
        
        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Try to update model with read-only access
        read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))
        update_data = {
            "long_description": "Updated description"
        }
        
        response = await ac.put(
            f"/api/v1/models/{collection_name}/{model_data['name']}",
            json=update_data,
            headers=read_only_headers
        )
        assert response.status_code == 403
        assert "Access level WRITE required" in response.json()["detail"]


# Additional edge case tests for better coverage

@pytest.mark.asyncio
async def test_list_trained_models_by_collection_with_pagination():
    """Test listing trained models with pagination parameters."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection with multiple models
        collection = create_collection("pagination-test-models-collection")
        collection_name = collection["name"]
        
        # Create 3 models
        for i in range(3):
            model_data = {
                "name": f"Pagination Model {i+1}",
                "model_path": f"/models/pagination_model_{i+1}.pt"
            }
            create_resp = await ac.post(
                f"/api/v1/models/{collection_name}",
                json=model_data,
                headers=AUTH_HEADERS
            )
            assert create_resp.status_code == 201
        
        # Test pagination with limit
        response = await ac.get(
            f"/api/v1/models/{collection_name}/?limit=2",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        # Test pagination with skip
        response = await ac.get(
            f"/api/v1/models/{collection_name}/?skip=1&limit=2",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


@pytest.mark.asyncio
async def test_update_trained_model_name_same_case():
    """Test updating model name to the same name (same case) should succeed."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("same-name-update-models-collection")
        collection_name = collection["name"]
        
        model_data = {
            "name": "Same Name Model",
            "model_path": "/models/same_name.pt"
        }
        
        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201
        
        # Update with the exact same name should succeed
        update_data = {
            "name": "Same Name Model",
            "long_description": "Updated description"
        }
        
        response = await ac.put(
            f"/api/v1/models/{collection_name}/{model_data['name']}",
            json=update_data,
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["long_description"] == update_data["long_description"]


@pytest.mark.asyncio
async def test_create_trained_model_with_all_optional_fields():
    """Test creating model with comprehensive field coverage."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection
        collection = create_collection("all-fields-models-collection")
        collection_name = collection["name"]

        # Test with all optional fields
        comprehensive_model_data = {
            "name": "Comprehensive Model",
            "model_path": "/models/comprehensive.pt",
            "metadata_version": "2.0.0",
            "model_metadata": {"accuracy": 0.95, "framework": "pytorch"},
            "asset_origin": "s3://bucket/model.pt",
            "long_description": "A comprehensive model for testing",
            "model_attributes": {"input_size": 224, "num_classes": 1000}
        }

        response = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=comprehensive_model_data,
            headers=AUTH_HEADERS
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == comprehensive_model_data["name"]
        assert data["model_metadata"] == comprehensive_model_data["model_metadata"]
        assert data["model_attributes"] == comprehensive_model_data["model_attributes"]
        assert data["entity_type"] == "trained_model"


@pytest.mark.asyncio
async def test_delete_trained_model_without_write_access():
    """Test that users without write access cannot delete trained models."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model with admin access
        collection = create_collection("delete-access-test-models-collection")
        collection_name = collection["name"]

        model_data = {
            "name": "Delete Test Model",
            "model_path": "/models/delete_test_model.pt"
        }

        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201

        # Try to delete model with read-only access
        read_only_headers = authorization_headers(sample_org_token(org_role="org:member"))

        response = await ac.delete(
            f"/api/v1/models/{collection_name}/{model_data['name']}",
            headers=read_only_headers
        )
        assert response.status_code == 403
        assert "Access level WRITE required" in response.json()["detail"]


# Version history tests

@pytest.mark.asyncio
async def test_get_trained_model_version_history():
    """Test getting the version history of a trained model."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("version-history-model-collection")
        collection_name = collection["name"]

        model_data = {
            "name": "Version History Model",
            "model_path": "/models/version_history.pt"
        }

        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201

        # Update the model to create a version
        update_data = {"long_description": "Updated description for version history"}
        await ac.put(
            f"/api/v1/models/{collection_name}/{model_data['name']}",
            json=update_data,
            headers=AUTH_HEADERS
        )

        # Get version history
        response = await ac.get(
            f"/api/v1/models/{collection_name}/{model_data['name']}/history",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert data["entity_name"] == model_data["name"]
        assert data["entity_type"] == "trained_model"
        assert "total_versions" in data
        assert "versions" in data


@pytest.mark.asyncio
async def test_get_trained_model_version_history_not_found():
    """Test getting version history for a nonexistent trained model."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/api/v1/models/nonexistent-collection/nonexistent-model/history",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_specific_version():
    """Test getting a trained model at a specific version using index reference."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("specific-version-model-collection")
        collection_name = collection["name"]

        model_data = {
            "name": "Specific Version Model",
            "model_path": "/models/specific_version.pt"
        }

        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201

        # Update the model to create another version
        update_data = {"long_description": "Version 2 description"}
        await ac.put(
            f"/api/v1/models/{collection_name}/{model_data['name']}",
            json=update_data,
            headers=AUTH_HEADERS
        )

        # Get specific version using index (~0 for the first version)
        response = await ac.get(
            f"/api/v1/models/{collection_name}/{model_data['name']}/versions/~0",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "index" in data
        assert "transaction_id" in data


@pytest.mark.asyncio
async def test_get_trained_model_version_not_found():
    """Test getting a trained model at a nonexistent version."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("version-not-found-model-collection")
        collection_name = collection["name"]

        model_data = {
            "name": "Version Not Found Model",
            "model_path": "/models/version_not_found.pt"
        }

        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201

        # Try to get version with invalid index
        response = await ac.get(
            f"/api/v1/models/{collection_name}/{model_data['name']}/versions/~99",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_trained_model_version_invalid_ref():
    """Test getting a trained model with an invalid version reference."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Create collection and model
        collection = create_collection("invalid-ref-model-collection")
        collection_name = collection["name"]

        model_data = {
            "name": "Invalid Ref Model",
            "model_path": "/models/invalid_ref.pt"
        }

        create_resp = await ac.post(
            f"/api/v1/models/{collection_name}",
            json=model_data,
            headers=AUTH_HEADERS
        )
        assert create_resp.status_code == 201

        # Try to get version with invalid reference format
        response = await ac.get(
            f"/api/v1/models/{collection_name}/{model_data['name']}/versions/~invalid",
            headers=AUTH_HEADERS
        )
        assert response.status_code == 400
        assert "Invalid version index" in response.json()["detail"]


# Search tests with mocked Typesense

def _create_mock_typesense_client():
    """Create a mock Typesense client."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_documents = MagicMock()

    # Setup the mock chain: client.collections[name].documents.search()
    mock_client.collections.__getitem__ = MagicMock(return_value=mock_collection)
    mock_collection.documents = mock_documents

    return mock_client, mock_documents


@pytest.mark.asyncio
async def test_search_trained_models_success():
    """Test searching trained models with mocked Typesense."""
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock search results
    mock_documents.search.return_value = {
        "hits": [
            {
                "document": {
                    "entity_name": "test-model",
                    "collection_name": "test-collection",
                    "entity_type": "trained_model",
                    "full_name": "test-collection/test-model"
                }
            }
        ]
    }

    # Override the dependency
    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/models/search?q=test",
                headers=AUTH_HEADERS
            )

            assert response.status_code == 200
            data = response.json()
            assert "hits" in data
            assert len(data["hits"]) == 1
            assert data["hits"][0]["document"]["entity_type"] == "trained_model"
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_trained_models_empty_results():
    """Test searching trained models with no results."""
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock with empty results
    mock_documents.search.return_value = {"hits": []}

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/models/search?q=nonexistent",
                headers=AUTH_HEADERS
            )

            assert response.status_code == 200
            data = response.json()
            assert "hits" in data
            assert len(data["hits"]) == 0
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_trained_models_with_limit():
    """Test searching trained models with limit parameter."""
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock search results
    mock_documents.search.return_value = {
        "hits": [
            {"document": {"entity_name": f"model-{i}", "entity_type": "trained_model"}}
            for i in range(5)
        ]
    }

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/models/search?q=model&limit=5",
                headers=AUTH_HEADERS
            )

            assert response.status_code == 200
            data = response.json()
            assert "hits" in data

            # Verify the search was called with the correct limit
            mock_documents.search.assert_called_once()
            call_args = mock_documents.search.call_args[0][0]
            assert call_args["per_page"] == 5
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_trained_models_collection_not_found():
    """Test searching trained models when Typesense collection doesn't exist."""
    import typesense
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock to raise ObjectNotFound
    mock_documents.search.side_effect = typesense.exceptions.ObjectNotFound("Collection not found")

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/models/search?q=test",
                headers=AUTH_HEADERS
            )

            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_trained_models_typesense_error():
    """Test searching trained models when Typesense returns an error."""
    import typesense
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock to raise TypesenseClientError
    mock_documents.search.side_effect = typesense.exceptions.TypesenseClientError("API error")

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/models/search?q=test",
                headers=AUTH_HEADERS
            )

            assert response.status_code == 500
            assert "failed" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_trained_models_missing_query():
    """Test searching trained models without query parameter returns 422."""
    mock_client, mock_documents = _create_mock_typesense_client()

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/api/v1/models/search",
                headers=AUTH_HEADERS
            )

            assert response.status_code == 422  # Validation error for missing required param
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)


@pytest.mark.asyncio
async def test_search_trained_models_unauthenticated():
    """Test searching trained models without authentication (should work for public models)."""
    mock_client, mock_documents = _create_mock_typesense_client()

    # Setup mock search results
    mock_documents.search.return_value = {
        "hits": [
            {
                "document": {
                    "entity_name": "public-model",
                    "entity_type": "trained_model",
                    "is_private": False
                }
            }
        ]
    }

    app.dependency_overrides[search.setup_and_get_typesense_client] = lambda: mock_client

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            # Search without auth header - should still work for public models
            response = await ac.get("/api/v1/models/search?q=public")

            assert response.status_code == 200
            data = response.json()
            assert "hits" in data
    finally:
        app.dependency_overrides.pop(search.setup_and_get_typesense_client, None)
