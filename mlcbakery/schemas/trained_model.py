from pydantic import ConfigDict
from typing import Optional, List
from datetime import datetime

from .entity import EntityBase
from .activity import ActivityResponse


class TrainedModelBase(EntityBase):
    """Base schema for trained models."""

    name: str
    model_path: str
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    model_metadata: Optional[dict] = None
    asset_origin: Optional[str] = None
    long_description: Optional[str] = None
    model_attributes: Optional[dict] = None
    entity_type: str = "trained_model"


class TrainedModelCreate(EntityBase):
    """Schema for creating a new trained model."""
    name: str
    model_path: str
    collection_name: str
    metadata_version: Optional[str] = None
    model_metadata: Optional[dict] = None
    asset_origin: Optional[str] = None
    long_description: Optional[str] = None
    model_attributes: Optional[dict] = None
    entity_type: str = "trained_model"


class TrainedModelUpdate(TrainedModelBase):
    """Schema for updating a trained model."""
    name: Optional[str] = None
    model_path: Optional[str] = None
    metadata_version: Optional[str] = None
    model_metadata: Optional[dict] = None
    asset_origin: Optional[str] = None
    long_description: Optional[str] = None
    model_attributes: Optional[dict] = None


class TrainedModelResponse(TrainedModelBase):
    id: int
    created_at: datetime
    # input_activities: List[ActivityResponse] = []
    # output_activities: List[ActivityResponse] = []

    model_config = ConfigDict(from_attributes=True)
