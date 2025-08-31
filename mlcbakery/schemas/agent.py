from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class AgentBase(BaseModel):
    name: str
    type: Optional[str] = None
    collection_id: Optional[int] = None


class AgentCreate(BaseModel):
    """Schema for creating agents using collection_name from URL path."""
    name: str
    type: Optional[str] = None


class AgentUpdate(BaseModel):
    """Schema for updating agents."""
    name: Optional[str] = None
    type: Optional[str] = None


class AgentListResponse(AgentBase):
    """Lightweight listing presentation for agents."""
    id: int
    collection_name: Optional[str] = None


class AgentResponse(AgentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
