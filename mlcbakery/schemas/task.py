from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime

from .entity import EntityBase


class TaskBase(EntityBase):
    """Base schema shared by Task operations."""

    name: str
    workflow: dict
    collection_id: Optional[int] = None
    version: Optional[str] = None
    description: Optional[str] = None
    has_file_uploads: bool = False
    entity_type: str = "task"


class TaskCreate(BaseModel):
    """Schema for creating tasks using collection_name from URL path."""
    name: str
    workflow: dict
    version: Optional[str] = None
    description: Optional[str] = None
    has_file_uploads: bool = False
    entity_type: str = "task"
    croissant_metadata: Optional[dict] = None
    is_private: bool = True  # Private by default


class TaskUpdate(BaseModel):
    """Schema for updating tasks."""
    name: Optional[str] = None
    workflow: Optional[dict] = None
    version: Optional[str] = None
    description: Optional[str] = None
    has_file_uploads: Optional[bool] = None
    is_private: Optional[bool] = None
    croissant_metadata: Optional[dict] = None


class TaskListResponse(TaskBase):
    """Lightweight listing presentation."""

    id: int
    collection_name: Optional[str] = None


class TaskResponse(TaskBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None  # Computed from version history
    # Collection environment variables and storage details
    environment_variables: Optional[Dict[str, Any]] = None
    storage_info: Optional[Dict[str, Any]] = None
    storage_provider: Optional[str] = None

    model_config = ConfigDict(from_attributes=True) 
