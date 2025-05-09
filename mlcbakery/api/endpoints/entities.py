import fastapi
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List

from mlcbakery.models import Entity
from mlcbakery.schemas.entity import (
    EntityResponse,
)
from mlcbakery.database import get_async_db

router = fastapi.APIRouter()


# @router.get("/entities/", response_model=List[EntityResponse])
# async def list_entities(
#     skip: int = fastapi.Query(default=0, description="Number of records to skip"), 
#     limit: int = fastapi.Query(default=100, description="Maximum number of records to return"), 
#     db: AsyncSession = fastapi.Depends(get_async_db)
# ):
#     """
#     Get all entities from the database with pagination (async).
#     Includes Datasets and TrainedModels.
#     """
#     if skip < 0 or limit < 0:
#         raise fastapi.HTTPException(
#             status_code=422, detail="Invalid pagination parameters"
#         )
#     # Eager load collection for all entities
#     stmt = select(Entity).offset(skip).limit(limit).options(selectinload(Entity.collection))
#     result = await db.execute(stmt)
#     entities = result.scalars().all()
#     return entities

# Note: The following list_datasets and list_trained_models might be redundant
# if they are already covered by endpoints in datasets.py and trained_models.py
# Consider removing them here if they exist elsewhere with more specific logic.

# @router.get("/datasets/", response_model=List[DatasetResponse])
# async def list_datasets(
#     skip: int = 0, limit: int = 100, db: AsyncSession = fastapi.Depends(get_async_db)
# ):
#     """
#     Get all datasets from the database with pagination (async).
#     """
#     if skip < 0 or limit < 0:
#         raise fastapi.HTTPException(
#             status_code=422, detail="Invalid pagination parameters"
#         )
#     stmt = select(Dataset).where(Entity.entity_type == 'dataset').offset(skip).limit(limit).options(selectinload(Dataset.collection))
#     result = await db.execute(stmt)
#     datasets = result.scalars().all()
#     return datasets


# @router.get("/trained-models/", response_model=List[TrainedModelResponse])
# async def list_trained_models(
#     skip: int = 0, limit: int = 100, db: AsyncSession = fastapi.Depends(get_async_db)
# ):
#     """
#     Get all trained models from the database with pagination (async).
#     """
#     if skip < 0 or limit < 0:
#         raise fastapi.HTTPException(
#             status_code=422, detail="Invalid pagination parameters"
#         )
#     stmt = select(TrainedModel).where(Entity.entity_type == 'trained_model').offset(skip).limit(limit).options(selectinload(TrainedModel.collection))
#     result = await db.execute(stmt)
#     models = result.scalars().all()
#     return models


# Note: The POST routes below might also be redundant if they exist in
# datasets.py and trained_models.py. Prefer the specific endpoints if available.

# @router.post("/datasets/", response_model=DatasetResponse)
# async def create_dataset(dataset: DatasetCreate, db: AsyncSession = fastapi.Depends(get_async_db)):
#     """
#     Create a new dataset (async) - Use endpoint in datasets.py instead if available.
#     """
#     # Optional: Check if collection exists
#     if dataset.collection_id:
#         stmt_coll = select(Collection).where(Collection.id == dataset.collection_id)
#         result_coll = await db.execute(stmt_coll)
#         if not result_coll.scalar_one_or_none():
#             raise fastapi.HTTPException(status_code=404, detail=f"Collection {dataset.collection_id} not found")

#     db_dataset = Dataset(**dataset.model_dump())
#     db.add(db_dataset)
#     await db.commit()
#     await db.refresh(db_dataset)
#     # Eager load for response
#     stmt_ref = select(Dataset).where(Dataset.id == db_dataset.id).options(selectinload(Dataset.collection))
#     res_ref = await db.execute(stmt_ref)
#     db_dataset = res_ref.scalar_one()
#     return db_dataset


# @router.post("/trained-models/", response_model=TrainedModelResponse)
# async def create_trained_model(
#     model: TrainedModelCreate, db: AsyncSession = fastapi.Depends(get_async_db)
# ):
#     """
#     Create a new trained model (async) - Use endpoint in trained_models.py instead if available.
#     """
#     # Optional: Check if collection exists
#     if model.collection_id:
#         stmt_coll = select(Collection).where(Collection.id == model.collection_id)
#         result_coll = await db.execute(stmt_coll)
#         if not result_coll.scalar_one_or_none():
#             raise fastapi.HTTPException(status_code=404, detail=f"Collection {model.collection_id} not found")
            
#     db_model = TrainedModel(**model.model_dump())
#     db.add(db_model)
#     await db.commit()
#     await db.refresh(db_model)
#     # Eager load for response
#     stmt_ref = select(TrainedModel).where(TrainedModel.id == db_model.id).options(selectinload(TrainedModel.collection))
#     res_ref = await db.execute(stmt_ref)
#     db_model = res_ref.scalar_one()
#     return db_model
