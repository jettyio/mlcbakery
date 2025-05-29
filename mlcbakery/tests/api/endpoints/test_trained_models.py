import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import status

from mlcbakery.main import app # Assuming your FastAPI app instance is named 'app'
from mlcbakery.models import Collection, TrainedModel, Entity
from mlcbakery.schemas.trained_model import TrainedModelCreate, TrainedModelUpdate

# Dummy admin token for testing
ADMIN_TOKEN = "admin_secret_token"
HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}

@pytest.fixture
async def test_collection(db: AsyncSession):
    collection = Collection(name="Test Collection for Models", description="A test collection for trained models")
    db.add(collection)
    await db.commit()
    await db.refresh(collection)
    return collection

@pytest.fixture
async def test_trained_model(db: AsyncSession, test_collection: Collection):
    model = TrainedModel(
        name="Test Model 1",
        model_path="/path/to/model1.pt",
        collection_id=test_collection.id,
        entity_type="trained_model"
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model

@pytest.mark.asyncio
async def test_create_trained_model(async_client: AsyncClient, db: AsyncSession, test_collection: Collection):
    model_data = {
        "name": "New Test Model",
        "model_path": "/path/to/new_model.pt",
        "collection_name": test_collection.name,
        "metadata_version": "1.0",
        "model_metadata": {"accuracy": 0.95},
        "asset_origin": "s3://bucket/new_model.pt",
        "long_description": "A detailed description of the new model.",
        "model_attributes": {"input_shape": [1, 28, 28]}
    }
    response = await async_client.post("/models", json=model_data, headers=HEADERS)
    assert response.status_code == status.HTTP_201_CREATED
    created_model = response.json()
    assert created_model["name"] == model_data["name"]
    assert created_model["model_path"] == model_data["model_path"]
    assert created_model["collection_id"] == test_collection.id
    assert created_model["metadata_version"] == model_data["metadata_version"]
    assert created_model["model_metadata"] == model_data["model_metadata"]
    assert created_model["entity_type"] == "trained_model"

@pytest.mark.asyncio
async def test_create_trained_model_duplicate_name(async_client: AsyncClient, test_trained_model: TrainedModel, test_collection: Collection):
    model_data = {
        "name": test_trained_model.name, # Same name as existing model
        "model_path": "/path/to/another.pt",
        "collection_name": test_collection.name
    }
    response = await async_client.post("/models", json=model_data, headers=HEADERS)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert f"Trained model with name '{test_trained_model.name}' already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_create_trained_model_collection_not_found(async_client: AsyncClient):
    model_data = {
        "name": "Orphan Model",
        "model_path": "/path/to/orphan.pt",
        "collection_name": "NonExistentCollection"
    }
    response = await async_client.post("/models", json=model_data, headers=HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Not Found"


@pytest.mark.asyncio
async def test_update_trained_model(async_client: AsyncClient, test_trained_model: TrainedModel, db: AsyncSession):
    update_data = {
        "model_path": "/path/to/updated_model.pt",
        "metadata_version": "1.1",
        "model_metadata": {"accuracy": 0.98, "new_key": "new_value"},
        "long_description": "An updated description."
    }
    response = await async_client.put(f"/models/{test_trained_model.id}", json=update_data, headers=HEADERS)
    assert response.status_code == status.HTTP_200_OK
    updated_model_response = response.json()
    assert updated_model_response["model_path"] == update_data["model_path"]
    assert updated_model_response["metadata_version"] == update_data["metadata_version"]
    assert updated_model_response["model_metadata"] == update_data["model_metadata"]
    assert updated_model_response["long_description"] == update_data["long_description"]

    # Verify in DB
    await db.refresh(test_trained_model)
    assert test_trained_model.model_path == update_data["model_path"]
    assert test_trained_model.metadata_version == update_data["metadata_version"]

@pytest.mark.asyncio
async def test_update_trained_model_not_found(async_client: AsyncClient):
    update_data = {"model_path": "/path/to/ghost.pt"}
    response = await async_client.put("/models/9999", json=update_data, headers=HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Not Found"

@pytest.mark.asyncio
async def test_update_trained_model_try_change_name(async_client: AsyncClient, test_trained_model: TrainedModel):
    update_data = {"name": "Attempt to Change Name"}
    response = await async_client.put(f"/models/{test_trained_model.id}", json=update_data, headers=HEADERS)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Updating the model name is not allowed." in response.json()["detail"]

@pytest.mark.asyncio
async def test_update_trained_model_try_change_collection(async_client: AsyncClient, test_trained_model: TrainedModel, db: AsyncSession):
    # Create another collection to attempt to move the model to
    other_collection = Collection(name="Other Collection", description="Another test collection")
    db.add(other_collection)
    await db.commit()
    await db.refresh(other_collection)

    update_data = {"collection_id": other_collection.id} # Attempting to change collection_id
    response = await async_client.put(f"/models/{test_trained_model.id}", json=update_data, headers=HEADERS)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Changing the model's collection is not allowed." in response.json()["detail"]


@pytest.mark.asyncio
async def test_delete_trained_model(async_client: AsyncClient, test_trained_model: TrainedModel, db: AsyncSession):
    response = await async_client.delete(f"/models/{test_trained_model.id}", headers=HEADERS)
    assert response.status_code == status.HTTP_204_NO_CONTENT

    # Verify it's deleted from DB
    deleted_model = await db.get(TrainedModel, test_trained_model.id)
    assert deleted_model is None

@pytest.mark.asyncio
async def test_delete_trained_model_not_found(async_client: AsyncClient):
    response = await async_client.delete("/models/9999", headers=HEADERS)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Not Found"

# TODO: Add tests for unauthorized access (missing or invalid token) for all endpoints
# This requires setting up the verify_admin_token dependency in a way that can be tested,
# e.g., by allowing injection of a test token verifier or by mocking the actual one. 