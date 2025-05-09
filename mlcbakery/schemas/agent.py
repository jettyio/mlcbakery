from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class AgentBase(BaseModel):
    name: str
    type: Optional[str] = None


class AgentCreate(AgentBase):
    pass


class AgentResponse(AgentBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"json_encoders": {datetime: lambda v: v.isoformat()}}
    )
