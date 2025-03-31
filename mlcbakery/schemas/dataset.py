from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from .entity import EntityBase
from .activity import ActivityResponse


class DatasetBase(EntityBase):
    name: str
    data_path: str
    format: str
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    dataset_metadata: Optional[dict] = None
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
    input_activities: List[ActivityResponse] = []
    output_activities: List[ActivityResponse] = []

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )


class DatasetPreviewResponse(BaseModel):
    id: int
    preview_type: str

    class Config:
        from_attributes = True
