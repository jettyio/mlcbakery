from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, ForwardRef
from datetime import datetime
from .entity import EntityBase
from .activity import ActivityResponse

# Create a forward reference for UpstreamEntityNode
UpstreamEntityNodeRef = ForwardRef("UpstreamEntityNode")


class DatasetBase(EntityBase):
    name: str
    data_path: Optional[str] = None
    format: Optional[str] = None
    collection_id: Optional[int] = None
    metadata_version: Optional[str] = None
    dataset_metadata: Optional[dict] = None
    preview_type: Optional[str] = None
    entity_type: str = "dataset"
    long_description: Optional[str] = None
    asset_origin: Optional[str] = None


class UpstreamEntityNode(BaseModel):
    """Represents a node in the upstream entity tree."""

    id: int
    name: str
    collection_name: str
    entity_type: str
    activity_id: Optional[int] = None
    activity_name: Optional[str] = None
    children: List[UpstreamEntityNodeRef] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


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
    long_description: Optional[str] = None


class DatasetListResponse(DatasetBase):
    id: int
    name: Optional[str] = None
    collection_name: Optional[str] = None


class DatasetResponse(DatasetBase):
    id: int
    created_at: datetime
    input_activities: List[ActivityResponse] = []
    output_activities: List[ActivityResponse] = []
    model_config = ConfigDict(from_attributes=True)


class DatasetPreviewResponse(DatasetResponse):
    preview: Optional[bytes] = None
    preview_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Update the forward reference
UpstreamEntityNode.update_forward_refs()
