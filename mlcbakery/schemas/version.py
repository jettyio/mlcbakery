"""
Version history schemas for entity versioning API.
"""

from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime


class VersionHistoryItem(BaseModel):
    """A single version entry in the history."""

    index: int  # Version index (0 = oldest)
    transaction_id: int  # Continuum transaction ID
    content_hash: Optional[str] = None  # SHA-256 content hash
    tags: List[str] = []  # Semantic tags (e.g., "v1.0.0", "production")
    created_at: Optional[datetime] = None  # When this version was created
    operation_type: Optional[str] = None  # INSERT, UPDATE, DELETE
    changeset: Optional[Dict[str, Any]] = None  # Field changes {field: [old, new]}

    model_config = ConfigDict(from_attributes=True)


class VersionHistoryResponse(BaseModel):
    """Response containing version history for an entity."""

    entity_name: str
    entity_type: str
    collection_name: str
    total_versions: int
    versions: List[VersionHistoryItem]

    model_config = ConfigDict(from_attributes=True)


class VersionDetailResponse(BaseModel):
    """Full snapshot of entity at a specific version."""

    index: int
    transaction_id: int
    content_hash: Optional[str] = None
    tags: List[str] = []
    created_at: Optional[datetime] = None
    operation_type: Optional[str] = None
    data: Dict[str, Any]  # Complete entity data at this version

    model_config = ConfigDict(from_attributes=True)


class TagVersionRequest(BaseModel):
    """Request to add a tag to a version."""

    version_ref: str  # Hash, tag name, or ~index
    tag_name: str  # New tag to add


class VersionCompareResponse(BaseModel):
    """Response comparing two versions."""

    version1: VersionHistoryItem
    version2: VersionHistoryItem
    differences: Dict[str, Dict[str, Any]]  # {field: {version1: val, version2: val}}

    model_config = ConfigDict(from_attributes=True)
