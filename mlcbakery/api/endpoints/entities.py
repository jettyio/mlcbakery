import fastapi
from sqlalchemy.orm import Session
from typing import List

from mlcbakery.models import Entity
from mlcbakery.schemas.entity import EntityResponse  # We'll define this below
from mlcbakery.database import get_db

router = fastapi.APIRouter()


@router.get("/entities/", response_model=List[EntityResponse])
async def list_entities(
    skip: int = 0, limit: int = 100, db: Session = fastapi.Depends(get_db)
):
    """
    Get entities from the database with pagination.
    """
    if skip < 0 or limit < 0:
        raise fastapi.HTTPException(
            status_code=422, detail="Invalid pagination parameters"
        )
    entities = db.query(Entity).offset(skip).limit(limit).all()
    return entities
