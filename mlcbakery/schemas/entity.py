from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Literal, Optional


class EntityBase(BaseModel):
    name: str
    entity_type: Literal["entity", "dataset", "trained_model", "task"]
    is_private: Optional[bool] = True


class EntityResponse(EntityBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrainedModelBase(EntityBase):
    model_path: str
    framework: str


class TrainedModelResponse(TrainedModelBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
