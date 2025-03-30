from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from ...database import get_db
from ...models import TrainedModel
from ...schemas.trained_model import (
    TrainedModelCreate,
    TrainedModelResponse,
)

router = APIRouter()


@router.post("/trained_models", response_model=TrainedModelResponse)
def create_trained_model(
    trained_model: TrainedModelCreate, db: Session = Depends(get_db)
):
    """Create a new trained model."""
    db_trained_model = TrainedModel(
        name=trained_model.name,
        entity_type="trained_model",
        model_path=trained_model.model_path,
        framework=trained_model.framework,
    )
    db.add(db_trained_model)
    db.commit()
    db.refresh(db_trained_model)
    return db_trained_model


@router.get("/trained_models", response_model=List[TrainedModelResponse])
def list_trained_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all trained models."""
    trained_models = db.query(TrainedModel).offset(skip).limit(limit).all()
    return trained_models


@router.get("/trained_models/{trained_model_id}", response_model=TrainedModelResponse)
def get_trained_model(trained_model_id: int, db: Session = Depends(get_db)):
    """Get a specific trained model by ID."""
    trained_model = (
        db.query(TrainedModel).filter(TrainedModel.id == trained_model_id).first()
    )
    if trained_model is None:
        raise HTTPException(status_code=404, detail="Trained model not found")
    return trained_model


@router.delete("/trained_models/{trained_model_id}")
def delete_trained_model(trained_model_id: int, db: Session = Depends(get_db)):
    """Delete a trained model."""
    trained_model = (
        db.query(TrainedModel).filter(TrainedModel.id == trained_model_id).first()
    )
    if trained_model is None:
        raise HTTPException(status_code=404, detail="Trained model not found")
    db.delete(trained_model)
    db.commit()
    return {"message": "Trained model deleted successfully"}
