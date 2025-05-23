from pydantic import ConfigDict
from typing import Optional, List
from datetime import datetime

from .entity import EntityBase
from .activity import ActivityResponse


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
    input_activities: List[ActivityResponse] = []
    output_activities: List[ActivityResponse] = []

    model_config = ConfigDict(from_attributes=True)
