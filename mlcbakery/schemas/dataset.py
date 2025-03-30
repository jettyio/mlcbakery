from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from .entity import EntityBase


class DatasetBase(EntityBase):
    data_path: str
    format: str
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    dataset_metadata: Optional[Dict[str, Any]] = None
    preview_type: Optional[str] = None
    entity_type: str = "dataset"


class DatasetCreate(DatasetBase):
    pass


class DatasetUpdate(DatasetBase):
    name: Optional[str] = None
    data_path: Optional[str] = None
    format: Optional[str] = None


class DatasetResponse(DatasetBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True  # This enables ORM model parsing


class DatasetPreviewResponse(BaseModel):
    id: int
    preview_type: str

    class Config:
        from_attributes = True
