from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from .entity import EntityBase


class TrainedModelBase(EntityBase):
    """Base schema for trained models."""

    model_path: str
    framework: str
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    model_metadata: Optional[Dict[str, Any]] = None


class TrainedModelCreate(TrainedModelBase):
    """Schema for creating a new trained model."""

    pass


class TrainedModelResponse(TrainedModelBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
