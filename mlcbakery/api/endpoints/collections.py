import fastapi
from sqlalchemy.orm import Session
from typing import List

from mlcbakery.models import Collection
from mlcbakery.schemas.collection import CollectionCreate, CollectionResponse
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
