from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
# from sqlalchemy.orm import selectinload # Not strictly needed for create, but good for consistency
from typing import Optional

from mlcbakery.database import get_async_db # Adjusted import path based on typical FastAPI structure
from mlcbakery.models import Entity, Activity, EntityRelationship, Collection # Adjusted import path
from mlcbakery.schemas.activity import EntityRelationshipResponse # Reusing from activity schemas
from mlcbakery.schemas.entity_relationship import EntityLinkCreateRequest # New request schema
from fastapi.security import HTTPAuthorizationCredentials # For consistency with other endpoints
from mlcbakery.api.dependencies import verify_admin_token # Adjusted import path

router = APIRouter(
    prefix="/entity-relationships",
    tags=["Entity Relationships"],
    dependencies=[Depends(verify_admin_token)] # Apply auth to all routes in this router
)

async def _resolve_entity_from_string(entity_str: Optional[str], db: AsyncSession, entity_role: str) -> Optional[Entity]:
    """Helper to resolve an Entity from its string identifier."""
    if not entity_str:
        return None

    parts = entity_str.split('/')
    if len(parts) != 3:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid {entity_role} entity string format: '{entity_str}'. Expected '{{entity_type}}/{{collection_name}}/{{entity_name}}'."
        )
    
    entity_type, collection_name, entity_name = parts

    # Find collection
    coll_stmt = select(Collection).where(Collection.name == collection_name)
    collection = (await db.execute(coll_stmt)).scalar_one_or_none()
    if not collection:
        raise HTTPException(
            status_code=404, 
            detail=f"Collection '{collection_name}' for {entity_role} entity '{entity_str}' not found."
        )

    # Find entity within that collection
    entity_stmt = select(Entity).where(
        Entity.name == entity_name,
        Entity.entity_type == entity_type,
        Entity.collection_id == collection.id
    )
    entity = (await db.execute(entity_stmt)).scalar_one_or_none()
    if not entity:
        raise HTTPException(
            status_code=404, 
            detail=f"{entity_role.capitalize()} entity '{entity_name}' of type '{entity_type}' not found in collection '{collection_name}'."
        )
    return entity

@router.post("/", response_model=EntityRelationshipResponse, status_code=201)
async def create_entity_link(
    link_request: EntityLinkCreateRequest,
    db: AsyncSession = Depends(get_async_db),
    # Admin token dependency is now at the router level
):
    """
    Create a new relationship (link) between two entities via an activity name.
    - Source and target entities are identified by a string: {entity_type}/{collection_name}/{entity_name}.
    - Target entity is required. Source entity is optional.
    - The activity_name is taken directly from the request.
    - Agent ID is set to NULL for now.
    """
    source_entity = await _resolve_entity_from_string(link_request.source_entity_str, db, entity_role="source")
    # Target entity must resolve, _resolve_entity_from_string will raise HTTPException if not found or format is bad.
    target_entity = await _resolve_entity_from_string(link_request.target_entity_str, db, entity_role="target")

    if not target_entity: # Should be caught by _resolve, but as a safeguard.
        raise HTTPException(status_code=404, detail=f"Target entity '{link_request.target_entity_str}' could not be resolved.")

    db_entity_relationship = EntityRelationship(
        source_entity_id=source_entity.id if source_entity else None,
        target_entity_id=target_entity.id, # target_entity is guaranteed to be not None here
        activity_name=link_request.activity_name, # Use activity_name directly
        agent_id=None  # As per requirement
    )
    db.add(db_entity_relationship)
    await db.commit()
    await db.refresh(db_entity_relationship)
    
    return db_entity_relationship 