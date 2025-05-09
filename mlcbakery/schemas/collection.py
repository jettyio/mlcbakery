from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any


class CollectionBase(BaseModel):
    name: str
    description: Optional[str] = None


class CollectionCreate(CollectionBase):
    storage_info: Optional[Dict[str, Any]] = None
    storage_provider: Optional[str] = None


class CollectionResponse(CollectionBase):
    id: int

    model_config = ConfigDict(
        from_attributes=True
    )


class CollectionStorageResponse(CollectionResponse):
    storage_info: Optional[Dict[str, Any]] = None
    storage_provider: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True
    )
