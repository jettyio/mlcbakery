from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List

from mlcbakery.schemas.trained_model import (
    TrainedModelCreate,
    TrainedModelResponse,
    TrainedModelUpdate,
)
from mlcbakery.database import get_async_db
from mlcbakery.api.dependencies import verify_admin_token

from mlcbakery.models import TrainedModel, Collection, Entity

router = APIRouter()

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

