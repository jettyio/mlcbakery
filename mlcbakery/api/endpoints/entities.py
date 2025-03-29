import fastapi
from sqlalchemy.orm import Session
from typing import List

from mlcbakery.models import Entity, Dataset, TrainedModel
from mlcbakery.schemas.entity import (
    EntityResponse,
    DatasetResponse,
    TrainedModelResponse,
    DatasetBase,
    TrainedModelBase,
)
from mlcbakery.database import get_db

router = fastapi.APIRouter()


@router.get("/entities/", response_model=List[EntityResponse])
async def list_entities(
    skip: int = 0, limit: int = 100, db: Session = fastapi.Depends(get_db)
):
    """
    Get all entities from the database with pagination.
    """
    if skip < 0 or limit < 0:
        raise fastapi.HTTPException(
            status_code=422, detail="Invalid pagination parameters"
        )
    entities = db.query(Entity).offset(skip).limit(limit).all()
    return entities


@router.get("/datasets/", response_model=List[DatasetResponse])
async def list_datasets(
    skip: int = 0, limit: int = 100, db: Session = fastapi.Depends(get_db)
):
    """
    Get all datasets from the database with pagination.
    """
    if skip < 0 or limit < 0:
        raise fastapi.HTTPException(
            status_code=422, detail="Invalid pagination parameters"
        )
    datasets = db.query(Dataset).offset(skip).limit(limit).all()
    return datasets


@router.get("/trained-models/", response_model=List[TrainedModelResponse])
async def list_trained_models(
    skip: int = 0, limit: int = 100, db: Session = fastapi.Depends(get_db)
):
    """
    Get all trained models from the database with pagination.
    """
    if skip < 0 or limit < 0:
        raise fastapi.HTTPException(
            status_code=422, detail="Invalid pagination parameters"
        )
    models = db.query(TrainedModel).offset(skip).limit(limit).all()
    return models


@router.post("/datasets/", response_model=DatasetResponse)
async def create_dataset(dataset: DatasetBase, db: Session = fastapi.Depends(get_db)):
    """
    Create a new dataset.
    """
    db_dataset = Dataset(**dataset.model_dump())
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


@router.post("/trained-models/", response_model=TrainedModelResponse)
async def create_trained_model(
    model: TrainedModelBase, db: Session = fastapi.Depends(get_db)
):
    """
    Create a new trained model.
    """
    db_model = TrainedModel(**model.model_dump())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model
