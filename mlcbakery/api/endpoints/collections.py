import fastapi
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload  # For eager loading entities
from typing import List
from fastapi.security import HTTPAuthorizationCredentials

from mlcbakery.models import Collection, Dataset, Entity, Activity
from mlcbakery.schemas.collection import (
    CollectionCreate,
    CollectionResponse,
    CollectionStorageResponse,
)
from mlcbakery.schemas.dataset import DatasetResponse
from mlcbakery.database import get_async_db  # Use async dependency
from mlcbakery.api.dependencies import verify_admin_token  # Add this import

router = fastapi.APIRouter()


@router.post("/collections/", response_model=CollectionResponse)
async def create_collection(
    collection: CollectionCreate,
    db: AsyncSession = fastapi.Depends(get_async_db),
    _: HTTPAuthorizationCredentials = fastapi.Depends(verify_admin_token),
):
    """
    Create a new collection (async).
    """
    db_collection = Collection(
        name=collection.name,
        description=collection.description,
        storage_info=collection.storage_info,
        storage_provider=collection.storage_provider,
    )
    db.add(db_collection)
    await db.commit()
    await db.refresh(db_collection)
    return db_collection


@router.get("/collections/", response_model=List[CollectionResponse])
async def list_collections(
    skip: int = 0, limit: int = 100, db: AsyncSession = fastapi.Depends(get_async_db)
):
    """
    Get collections from the database with pagination (async).
    """
    if skip < 0 or limit < 0:
        raise fastapi.HTTPException(
            status_code=422, detail="Invalid pagination parameters"
        )
    stmt = select(Collection).offset(skip).limit(limit)
    # Add .options(selectinload(Collection.entities)) if eager loading needed
    result = await db.execute(stmt)
    collections = result.scalars().all()
    return collections


@router.get(
    "/collections/{collection_name}/storage", response_model=CollectionStorageResponse
)
async def get_collection_storage_info(
    collection_name: str,
    db: AsyncSession = fastapi.Depends(get_async_db),
    _: HTTPAuthorizationCredentials = fastapi.Depends(verify_admin_token),
):
    """Get storage information for a specific collection.
    This endpoint requires admin authentication.
    """
    # First verify the collection exists
    stmt_coll = select(Collection).where(Collection.name == collection_name)
    result_coll = await db.execute(stmt_coll)
    collection = result_coll.scalar_one_or_none()

    if not collection:
        raise fastapi.HTTPException(status_code=404, detail="Collection not found")

    return collection


@router.patch(
    "/collections/{collection_name}/storage", response_model=CollectionStorageResponse
)
async def update_collection_storage_info(
    collection_name: str,
    storage_info: dict = fastapi.Body(...),
    db: AsyncSession = fastapi.Depends(get_async_db),
    _: HTTPAuthorizationCredentials = fastapi.Depends(verify_admin_token),
):
    """Update storage information for a specific collection.
    This endpoint requires admin authentication.
    """
    stmt_coll = select(Collection).where(Collection.name == collection_name)
    result_coll = await db.execute(stmt_coll)
    collection = result_coll.scalar_one_or_none()

    if not collection:
        raise fastapi.HTTPException(status_code=404, detail="Collection not found")

    if "storage_info" in storage_info:
        collection.storage_info = storage_info["storage_info"]
    if "storage_provider" in storage_info:
        collection.storage_provider = storage_info["storage_provider"]

    await db.commit()
    await db.refresh(collection)

    return collection


@router.get(
    "/collections/{collection_name}/datasets/", response_model=List[DatasetResponse]
)
async def list_datasets_by_collection(
    collection_name: str,
    skip: int = fastapi.Query(default=0, description="Number of records to skip"),
    limit: int = fastapi.Query(
        default=100, description="Maximum number of records to return"
    ),
    db: AsyncSession = fastapi.Depends(get_async_db),
):
    """Get a list of datasets for a specific collection with pagination (async)."""
    # First verify the collection exists
    stmt_coll = select(Collection).where(Collection.name == collection_name)
    result_coll = await db.execute(stmt_coll)
    collection = result_coll.scalar_one_or_none()

    if not collection:
        raise fastapi.HTTPException(status_code=404, detail="Collection not found")

    # Query datasets associated with the collection ID
    stmt_datasets = (
        select(Dataset)
        .where(Dataset.collection_id == collection.id)
        .where(Dataset.entity_type == "dataset")  # Explicitly filter for datasets
        .options(
            selectinload(Dataset.collection),
            selectinload(Dataset.input_activities).options(
                selectinload(Activity.input_entities).options(
                    selectinload(Entity.collection)
                ),
                selectinload(Activity.output_entity).options(
                    selectinload(Entity.collection)
                ),
                selectinload(Activity.agents),
            ),
            selectinload(Dataset.output_activities).options(
                selectinload(Activity.input_entities).options(
                    selectinload(Entity.collection)
                ),
                selectinload(Activity.agents),
            ),
        )
        .offset(skip)
        .limit(limit)
        .order_by(Dataset.id)  # Add consistent ordering
    )
    result_datasets = await db.execute(stmt_datasets)
    datasets = result_datasets.scalars().unique().all()
    return datasets
