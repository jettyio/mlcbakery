from pydantic import BaseModel, ConfigDict, computed_field
from typing import List, Optional
from datetime import datetime
from .entity import EntityResponse
from .agent import AgentResponse


class ActivityBase(BaseModel):
    name: str


class ActivityCreate(ActivityBase):
    input_entity_ids: List[int]
    output_entity_id: Optional[int] = None
    agent_ids: Optional[List[int]] = None


class ActivityResponse(ActivityBase):
    id: int
    created_at: datetime
    input_entities: List[EntityResponse]
    output_entity: Optional[EntityResponse]
    agents: List[AgentResponse]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"json_encoders": {datetime: lambda v: v.isoformat()}},
        populate_by_name=True,
    )

    @computed_field
    def input_entity_ids(self) -> List[int]:
        return [entity.id for entity in self.input_entities]

    @computed_field
    def output_entity_id(self) -> Optional[int]:
        return self.output_entity.id if self.output_entity else None

    @computed_field
    def agent_ids(self) -> Optional[List[int]]:
        return [agent.id for agent in self.agents]
