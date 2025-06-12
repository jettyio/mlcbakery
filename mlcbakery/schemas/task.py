from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

from .entity import EntityBase


class TaskBase(EntityBase):
    """Base schema shared by Task operations."""

    name: str
    workflow: dict
    collection_id: Optional[int] = None
    version: Optional[str] = None
    description: Optional[str] = None
    entity_type: str = "task"


class TaskCreate(BaseModel):
    """Schema for creating a Task via API request."""

    # For creation, the user provides collection name rather than ID to mimic datasets/trained_models convention.
    name: str
    workflow: dict
    collection_name: str
    version: Optional[str] = None
    description: Optional[str] = None
    entity_type: str = "task"


class TaskUpdate(TaskBase):
    """Schema for updating a Task (name & collection are immutable)."""

    name: Optional[str] = None
    workflow: Optional[dict] = None
    version: Optional[str] = None
    description: Optional[str] = None


class TaskListResponse(TaskBase):
    """Lightweight listing presentation."""

    id: int
    collection_name: Optional[str] = None


class TaskResponse(TaskBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True) 