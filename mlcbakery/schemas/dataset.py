from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, ForwardRef
from datetime import datetime
from .entity import EntityBase
from .activity import ActivityResponse

# Create a forward reference for UpstreamEntityNode
ProvenanceEntityNodeRef = ForwardRef("ProvenanceEntityNode")


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


class ProvenanceEntityNode(BaseModel):
    """Represents a node in the upstream entity tree."""

    id: int
    name: str
    collection_name: str
    entity_type: str
    activity_name: Optional[str] = None
    upstream_entities: List[ProvenanceEntityNodeRef] = Field(default_factory=list)
    downstream_entities: List[ProvenanceEntityNodeRef] = Field(default_factory=list)
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
    is_private: Optional[bool] = None


class DatasetListResponse(DatasetBase):
    id: int
    name: Optional[str] = None
    collection_name: Optional[str] = None


class DatasetResponse(DatasetBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DatasetPreviewResponse(DatasetResponse):
    preview: Optional[bytes] = None
    preview_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# Update the forward reference
ProvenanceEntityNode.update_forward_refs()
