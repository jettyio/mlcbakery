from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class EntityResponse(BaseModel):
    id: int
    name: str
    type: Optional[str]
    entity_id: Optional[int]
    generated_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True  # This enables ORM model parsing
