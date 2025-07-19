from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ApiKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: str
    collection_name: str

class ApiKeyResponse(BaseModel):
    """Schema for API key response (without the actual key)."""
    id: int
    collection_id: int
    collection_name: str
    name: str
    key_prefix: str
    created_at: datetime
    created_by_agent_id: Optional[int] = None
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)

class ApiKeyCreatedResponse(ApiKeyResponse):
    """Schema for API key creation response (includes the actual key once)."""
    api_key: str

class ApiKeyUpdate(BaseModel):
    """Schema for updating an API key."""
    name: Optional[str] = None
    is_active: Optional[bool] = None 