from pydantic import ConfigDict, BaseModel
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
    """Schema for creating trained models using collection_name from URL path."""
    name: str
    model_path: str
    metadata_version: Optional[str] = None
    model_metadata: Optional[dict] = None
    asset_origin: Optional[str] = None
    long_description: Optional[str] = None
    model_attributes: Optional[dict] = None
    entity_type: str = "trained_model"


class TrainedModelUpdate(BaseModel):
    """Schema for updating trained models."""
    name: Optional[str] = None
    model_path: Optional[str] = None
    metadata_version: Optional[str] = None
    model_metadata: Optional[dict] = None
    asset_origin: Optional[str] = None
    long_description: Optional[str] = None
    model_attributes: Optional[dict] = None
    is_private: Optional[bool] = None


class TrainedModelListResponse(TrainedModelBase):
    """Lightweight listing presentation for trained models."""
    
    id: int
    collection_name: Optional[str] = None


class TrainedModelResponse(TrainedModelBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
