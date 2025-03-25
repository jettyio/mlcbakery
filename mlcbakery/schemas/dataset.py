from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class DatasetBase(BaseModel):
    name: str
    collection_id: Optional[int] = None
    generated_by_id: Optional[int] = None
    metadata_version: Optional[str] = None
    dataset_metadata: Optional[Dict[str, Any]] = None


class DatasetCreate(DatasetBase):
    pass


class DatasetUpdate(DatasetBase):
    name: Optional[str] = None


class DatasetResponse(DatasetBase):
    id: int
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # This enables ORM model parsing
