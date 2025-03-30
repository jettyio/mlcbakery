from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime

from .entity import EntityBase


class TrainedModelBase(EntityBase):
    """Base schema for trained models."""

    name: str
    model_path: str
    framework: str
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    model_metadata: Optional[dict] = None
    entity_type: str = "trained_model"


class TrainedModelCreate(TrainedModelBase):
    """Schema for creating a new trained model."""

    pass


class TrainedModelResponse(TrainedModelBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )
