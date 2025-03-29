from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal


class EntityBase(BaseModel):
    name: str
    entity_type: Literal["entity", "dataset", "trained_model"]


class EntityResponse(EntityBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetBase(EntityBase):
    data_path: str
    format: str
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    dataset_metadata: Optional[dict] = None
    preview_type: Optional[str] = None


class DatasetResponse(DatasetBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TrainedModelBase(EntityBase):
    model_path: str
    framework: str


class TrainedModelResponse(TrainedModelBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
