from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List
import typesense

from mlcbakery import search

from mlcbakery.schemas.trained_model import (
    TrainedModelCreate,
    TrainedModelResponse,
    TrainedModelUpdate,
)
from mlcbakery.database import get_async_db
from mlcbakery.api.dependencies import verify_admin_token
from opentelemetry import trace # Import for span manipulation
from mlcbakery.models import TrainedModel, Collection, Entity, EntityRelationship
from sqlalchemy.orm import selectinload

router = APIRouter()

# Helper function to find a model by collection name and model name
async def _find_model_by_name(collection_name: str, model_name: str, db: AsyncSession) -> TrainedModel | None:
    stmt = (
        select(TrainedModel)
        .join(Collection, TrainedModel.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .where(func.lower(TrainedModel.name) == func.lower(model_name)) # Case-insensitive name match
        .where(TrainedModel.entity_type == "trained_model") # Ensure it is a trained model
        .options(
            selectinload(TrainedModel.collection),
            # Add other selectinloads if needed in the future, e.g., for relationships
            selectinload(TrainedModel.upstream_links).options(
                selectinload(EntityRelationship.source_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
            selectinload(TrainedModel.downstream_links).options(
                selectinload(EntityRelationship.target_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

@router.get("/models/search")
async def search_models(
    q: str = Query(..., min_length=1, description="Search query term"),
    limit: int = Query(
        default=30, ge=1, le=100, description="Number of results to return"
    ),
    ts: typesense.Client = Depends(search.setup_and_get_typesense_client),
):
    """Search models using Typesense based on query term."""
    # Get the current span
    current_span = trace.get_current_span()
    # Add the search query as an attribute to the span
    current_span.set_attribute("search.query", q)

    search_parameters = {
        "q": q,
        "query_by": "long_description, metadata, collection_name, entity_name, full_name",
        "per_page": limit,
        "filter_by": "entity_type:trained_model",
        "include_fields": "collection_name, entity_name, full_name, entity_type, metadata",
    }

    return await search.run_search_query(search_parameters, ts)

@router.post(
    "/models",
    response_model=TrainedModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Trained Model",
    tags=["Trained Models"],
)
async def create_trained_model(
    trained_model_in: TrainedModelCreate,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """
    Create a new trained model in the database.

    Requires admin privileges.

    - **name**: Name of the model (required)
    - **model_path**: Path to the model artifact (required)
    - **collection_name**: Name of the collection this model belongs to (required).
    - **metadata_version**: Optional version string for the metadata.
    - **model_metadata**: Optional dictionary for arbitrary model metadata.
    - **asset_origin**: Optional string indicating the origin of the model asset (e.g., S3 URI).
    - **long_description**: Optional detailed description of the model.
    - **model_attributes**: Optional dictionary for specific model attributes (e.g., input shape, output classes).
    """
    # Find collection by name
    stmt_collection = select(Collection).where(Collection.name == trained_model_in.collection_name)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{trained_model_in.collection_name}' not found",
        )

    # Check if model with the same name already exists in the collection (case-insensitive)
    stmt_check = (
        select(TrainedModel)
        .where(func.lower(Entity.name) == func.lower(trained_model_in.name))
        .where(Entity.collection_id == collection.id)
    )
    result_check = await db.execute(stmt_check)
    if result_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trained model with name '{trained_model_in.name}' already exists in collection '{collection.name}'"
        )
    
    # Prepare model data for creation, explicitly setting collection_id
    model_data_for_db = trained_model_in.model_dump(exclude={"collection_name"})
    model_data_for_db["collection_id"] = collection.id

    db_trained_model = TrainedModel(**model_data_for_db)
    db.add(db_trained_model)
    await db.commit()
    await db.refresh(db_trained_model)

    return db_trained_model


@router.put(
    "/models/{model_id}",
    response_model=TrainedModelResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a Trained Model",
    tags=["Trained Models"],
)
async def update_trained_model(
    model_id: int,
    trained_model_in: TrainedModelUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """
    Update an existing trained model in the database.

    Requires admin privileges.

    - **model_id**: ID of the model to update.
    - **model_path**: Path to the model artifact.
    - **metadata_version**: Optional version string for the metadata.
    - **model_metadata**: Optional dictionary for arbitrary model metadata.
    - **asset_origin**: Optional string indicating the origin of the model asset (e.g., S3 URI).
    - **long_description**: Optional detailed description of the model.
    - **model_attributes**: Optional dictionary for specific model attributes.

    The model name and collection cannot be changed.
    """
    stmt = select(TrainedModel).where(TrainedModel.id == model_id)
    result = await db.execute(stmt)
    db_trained_model = result.scalar_one_or_none()

    if "name" in trained_model_in.model_dump(exclude_unset=True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Updating the model name is not allowed.",
        )

    if "collection_id" in trained_model_in.model_dump(exclude_unset=True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Updating the model collection is not allowed.",
        )

    if not db_trained_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trained model with id {model_id} not found",
        )

    update_data = trained_model_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(db_trained_model, field, value)

    await db.commit()
    await db.refresh(db_trained_model)
    return db_trained_model


@router.delete(
    "/models/{model_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Trained Model",
    tags=["Trained Models"],
)
async def delete_trained_model(
    model_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """
    Delete a trained model from the database.

    Requires admin privileges.

    - **model_id**: ID of the model to delete.
    """
    stmt = select(TrainedModel).where(TrainedModel.id == model_id)
    result = await db.execute(stmt)
    db_trained_model = result.scalar_one_or_none()

    if not db_trained_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trained model with id {model_id} not found",
        )

    await db.delete(db_trained_model)
    await db.commit()
    return None


@router.get(
    "/models/{collection_name}/{model_name}", 
    response_model=TrainedModelResponse,
    summary="Get a Trained Model by Collection and Model Name",
    tags=["Trained Models"],
)
async def get_trained_model_by_name(
    collection_name: str, 
    model_name: str, 
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get a specific trained model by its collection name and model name.

    - **collection_name**: Name of the collection the model belongs to.
    - **model_name**: Name of the model.
    """
    db_trained_model = await _find_model_by_name(collection_name, model_name, db)
    if not db_trained_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trained model '{model_name}' in collection '{collection_name}' not found"
        )
    return db_trained_model

