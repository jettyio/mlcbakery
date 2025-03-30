from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ActivityBase(BaseModel):
    name: str


class ActivityCreate(ActivityBase):
    input_dataset_ids: List[int]
    output_model_id: Optional[int] = None
    agent_ids: Optional[List[int]] = None


class Activity(ActivityBase):
    id: int
    created_at: datetime
    input_dataset_ids: List[int]
    output_model_id: Optional[int] = None
    agent_ids: Optional[List[int]] = None

    class Config:
        from_attributes = True
        json_encoders = {datetime: lambda v: v.isoformat()}
