from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from .entity import EntityBase
from .activity import ActivityResponse
import base64


class DatasetBase(EntityBase):
    name: str
    data_path: str
    format: str
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    dataset_metadata: Optional[dict] = None
    preview_type: Optional[str] = None
    entity_type: str = "dataset"


class UpstreamEntityNode(BaseModel):
    """Represents a node in the upstream entity tree."""

    id: int
    name: str
    entity_type: str
    activity_id: Optional[int] = None
    activity_name: Optional[str] = None
    children: List["UpstreamEntityNode"] = []

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )


class DatasetCreate(DatasetBase):
    pass


class DatasetUpdate(DatasetBase):
    name: Optional[str] = None
    data_path: Optional[str] = None
    format: Optional[str] = None
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    dataset_metadata: Optional[dict] = None
    preview_type: Optional[str] = None


class DatasetResponse(DatasetBase):
    id: int
    created_at: datetime
    input_activities: List[ActivityResponse] = []
    output_activities: List[ActivityResponse] = []

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
    )


class DatasetPreviewResponse(DatasetResponse):
    preview: Optional[bytes] = None
    preview_type: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
            bytes: lambda v: base64.b64encode(v).decode("utf-8") if v else None,
        },
    )
