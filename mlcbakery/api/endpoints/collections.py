import fastapi
from sqlalchemy.orm import Session
from typing import List

from mlcbakery.models import Collection, Dataset
from mlcbakery.schemas.collection import CollectionCreate, CollectionResponse
from mlcbakery.schemas.dataset import DatasetResponse
from mlcbakery.database import get_db

router = fastapi.APIRouter()


@router.post("/collections/", response_model=CollectionResponse)
async def create_collection(
    collection: CollectionCreate, db: Session = fastapi.Depends(get_db)
):
    """
    Create a new collection.
    """
    db_collection = Collection(name=collection.name, description=collection.description)
    db.add(db_collection)
    db.commit()
    db.refresh(db_collection)
    return db_collection


@router.get("/collections/", response_model=List[CollectionResponse])
async def list_collections(
    skip: int = 0, limit: int = 100, db: Session = fastapi.Depends(get_db)
):
    """
    Get collections from the database with pagination.
    """
    if skip < 0 or limit < 0:
        raise fastapi.HTTPException(
            status_code=422, detail="Invalid pagination parameters"
        )
    collections = db.query(Collection).offset(skip).limit(limit).all()
    return collections


@router.get(
    "/collections/{collection_name}/datasets/", response_model=List[DatasetResponse]
)
async def list_datasets_by_collection(
    collection_name: str,
    skip: int = fastapi.Query(default=0, description="Number of records to skip"),
    limit: int = fastapi.Query(
        default=100, description="Maximum number of records to return"
    ),
    db: Session = fastapi.Depends(get_db),
):
    """Get a list of datasets for a specific collection with pagination."""
    # First verify the collection exists
    collection = db.query(Collection).filter(Collection.name == collection_name).first()
    if not collection:
        raise fastapi.HTTPException(status_code=404, detail="Collection not found")

    datasets = (
        db.query(Dataset)
        .filter(Dataset.collection_id == collection.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return datasets
