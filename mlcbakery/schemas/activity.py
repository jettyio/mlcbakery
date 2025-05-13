from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime
from .entity import EntityResponse
from .agent import AgentResponse


# New Schema for EntityRelationship links
class EntityRelationshipResponse(BaseModel):
    id: int
    source_entity_id: Optional[int] = None
    target_entity_id: Optional[int] = None
    activity_id: int
    agent_id: Optional[int] = None

    # Optionally, include full objects if the API needs to return them directly within a link
    # source_entity: Optional[EntityResponse] = None 
    # target_entity: Optional[EntityResponse] = None
    # agent: Optional[AgentResponse] = None

    model_config = ConfigDict(from_attributes=True)


class ActivityBase(BaseModel):
    name: str


class ActivityCreate(ActivityBase):
    # Removed: input_entity_ids, output_entity_id, agent_ids
    # Relationships will be handled by creating EntityRelationship objects separately
    # or through a more dedicated service layer logic if needed during creation.
    pass # No other fields needed for basic activity creation based on new model


class ActivityResponse(ActivityBase):
    id: int
    created_at: datetime
    
    # Replaced old direct entity/agent lists with a list of relationships
    involved_in_links: List[EntityRelationshipResponse] = []

    # Removed input_entities, output_entity, agents
    # Removed computed_fields: input_entity_ids, output_entity_id, agent_ids

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True, # Keep if useful for your setup
    )

# The old computed_fields are removed as their underlying direct relationships are gone.
# If you need to expose aggregated IDs directly on ActivityResponse, 
# you would iterate through involved_in_links in new computed_fields.
# For example:
#    @computed_field
#    def source_entity_ids(self) -> List[int]:
#        ids = set()
#        for link in self.involved_in_links:
#            if link.source_entity_id is not None:
#                ids.add(link.source_entity_id)
#        return list(ids)
