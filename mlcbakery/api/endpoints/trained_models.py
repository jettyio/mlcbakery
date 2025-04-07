from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from mlcbakery.database import get_async_db
from ...models import TrainedModel, Collection, Activity, Entity
from ...schemas.trained_model import (
    TrainedModelCreate,
    TrainedModelResponse,
)

router = APIRouter()


@router.post("/trained_models/", response_model=TrainedModelResponse)
async def create_trained_model(
    trained_model: TrainedModelCreate, db: AsyncSession = Depends(get_async_db)
):
    """Create a new trained model (async)."""
    if trained_model.collection_id:
        stmt_coll = select(Collection).where(Collection.id == trained_model.collection_id)
        result_coll = await db.execute(stmt_coll)
        if not result_coll.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Collection with id {trained_model.collection_id} not found")

    db_trained_model = TrainedModel(**trained_model.model_dump())
    db.add(db_trained_model)
    
    await db.commit()
    await db.refresh(db_trained_model)
    

    stmt_refresh = (
        select(TrainedModel)
        .where(TrainedModel.id == db_trained_model.id)
        .options(
            selectinload(TrainedModel.collection),
            selectinload(TrainedModel.input_activities).options( # Load activities where this dataset is an input
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(TrainedModel.output_activities).options( # Load the activity that *created* this dataset
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            )
        )
    )
    result_refresh = await db.execute(stmt_refresh)
    refreshed_trained_model = result_refresh.scalars().unique().one_or_none()

    if not refreshed_trained_model:
        raise HTTPException(status_code=500, detail="Failed to reload trained model after creation")

    return refreshed_trained_model

@router.get("/trained_models/", response_model=List[TrainedModelResponse])
async def list_trained_models(
    skip: int = Query(default=0, description="Number of records to skip"), 
    limit: int = Query(default=100, description="Maximum number of records to return"), 
    db: AsyncSession = Depends(get_async_db)
):
    """List all trained models (async)."""
    stmt = (
        select(TrainedModel)
        .where(TrainedModel.entity_type == 'trained_model')
        .offset(skip)
        .limit(limit)
        .options(
            selectinload(TrainedModel.collection),
            selectinload(TrainedModel.input_activities).options(
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(TrainedModel.output_activities).options(
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            )
        )
    )
    result = await db.execute(stmt)
    trained_models = result.scalars().all()
    return trained_models


@router.get("/trained_models/{trained_model_id}", response_model=TrainedModelResponse)
async def get_trained_model(trained_model_id: int, db: AsyncSession = Depends(get_async_db)):
    """Get a specific trained model by ID (async)."""
    stmt = (
        select(TrainedModel)
        .where(TrainedModel.id == trained_model_id)
        .where(TrainedModel.entity_type == 'trained_model')
        .options(
            selectinload(TrainedModel.collection),
            selectinload(TrainedModel.input_activities).options(
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(TrainedModel.output_activities).options(
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            )
        )
    )
    result = await db.execute(stmt)
    trained_model = result.scalar_one_or_none()
    
    if trained_model is None:
        raise HTTPException(status_code=404, detail="Trained model not found")
    return trained_model


@router.delete("/trained_models/{trained_model_id}", status_code=200)
async def delete_trained_model(trained_model_id: int, db: AsyncSession = Depends(get_async_db)):
    """Delete a trained model (async)."""
    stmt = select(TrainedModel).where(TrainedModel.id == trained_model_id).where(TrainedModel.entity_type == 'trained_model')
    result = await db.execute(stmt)
    trained_model = result.scalar_one_or_none()

    if trained_model is None:
        raise HTTPException(status_code=404, detail="Trained model not found")
    
    await db.delete(trained_model)
    await db.commit()
    return {"message": "Trained model deleted successfully"}
