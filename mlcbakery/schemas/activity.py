from pydantic import BaseModel, ConfigDict, computed_field
from typing import List, Optional
from datetime import datetime
from .dataset import DatasetResponse
from .trained_model import TrainedModelResponse
from .agent import AgentResponse


class ActivityBase(BaseModel):
    name: str


class ActivityCreate(ActivityBase):
    input_dataset_ids: List[int]
    output_model_id: Optional[int] = None
    agent_ids: Optional[List[int]] = None


class ActivityResponse(ActivityBase):
    id: int
    created_at: datetime
    input_datasets: List[DatasetResponse]
    output_model: Optional[TrainedModelResponse]
    agents: List[AgentResponse]

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={datetime: lambda v: v.isoformat()},
        populate_by_name=True,
    )

    @computed_field
    def input_dataset_ids(self) -> List[int]:
        return [dataset.id for dataset in self.input_datasets]

    @computed_field
    def output_model_id(self) -> Optional[int]:
        return self.output_model.id if self.output_model else None

    @computed_field
    def agent_ids(self) -> Optional[List[int]]:
        return [agent.id for agent in self.agents]
