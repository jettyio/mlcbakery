from pydantic import BaseModel
from typing import Optional


class CollectionBase(BaseModel):
    name: str
    description: Optional[str] = None


class CollectionCreate(CollectionBase):
    pass


class CollectionResponse(CollectionBase):
    id: int

    class Config:
        from_attributes = True
