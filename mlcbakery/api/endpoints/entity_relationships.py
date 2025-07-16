from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
# from sqlalchemy.orm import selectinload # Not strictly needed for create, but good for consistency
from typing import Optional

from mlcbakery.database import get_async_db # Adjusted import path based on typical FastAPI structure
from mlcbakery.models import Entity, Activity, EntityRelationship, Collection # Adjusted import path
from mlcbakery.schemas.activity import EntityRelationshipResponse # Reusing from activity schemas
from mlcbakery.schemas.entity_relationship import EntityLinkCreateRequest # New request schema
from mlcbakery.api.dependencies import verify_auth, verify_auth_with_write_access, apply_auth_to_stmt # Adjusted import path

# Added imports for the new endpoint
from mlcbakery.schemas.dataset import ProvenanceEntityNode
from mlcbakery.api.endpoints.datasets import build_upstream_tree_async
# Note: build_upstream_tree_async internally uses _find_entity_by_id from datasets.py

router = APIRouter(
    prefix="/entity-relationships",
    tags=["Entity Relationships"],
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
    auth = Depends(verify_auth_with_write_access),
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

    # check if the relationship already exists
    existing_relationship = await db.execute(
        select(EntityRelationship).where(
            EntityRelationship.source_entity_id == source_entity.id if source_entity else None,
            EntityRelationship.target_entity_id == target_entity.id,
            EntityRelationship.activity_name == link_request.activity_name
        )
    )
    existing_relationship = existing_relationship.scalar_one_or_none()
    if existing_relationship:
        return existing_relationship

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

@router.get("/{entity_type}/{collection_name}/{entity_name}/upstream", response_model=ProvenanceEntityNode)
async def get_entity_upstream_tree(
    entity_type: str,
    collection_name: str,
    entity_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
) -> ProvenanceEntityNode:
    """
    Get the provenance tree for any specified entity.
    The tree includes both upstream and downstream links from each node's perspective.
    """
    entity_str = f"{entity_type}/{collection_name}/{entity_name}"
    
    # Resolve the starting entity
    # _resolve_entity_from_string will raise HTTPException if not found or format is bad.
    # It expects entity_role for error messaging, "starting" or "root" seems appropriate.
    starting_entity = await _resolve_entity_from_string(entity_str, db, entity_role="starting")

    if not starting_entity:
        # This case should ideally be covered by _resolve_entity_from_string raising an error,
        # but as a safeguard or if _resolve_entity_from_string is modified to return None.
        raise HTTPException(status_code=404, detail=f"Entity '{entity_str}' not found.")

    # Build the provenance tree using the imported function
    # The `build_upstream_tree_async` function explores both upstream and downstream relationships
    # for each node it processes, filling the respective fields in ProvenanceEntityNode.
    # The initial call has no preceding link, hence `link=None`.
    # A new set for visited nodes is created for each call to get a full tree from the starting point.
    provenance_tree = await build_upstream_tree_async(starting_entity, None, db, set())
    
    if not provenance_tree:
        # This might happen if the starting_entity itself was None after resolution,
        # or if build_upstream_tree_async returns None for some reason (e.g. initial entity is in visited, though unlikely for root).
        raise HTTPException(status_code=500, detail=f"Could not generate provenance tree for entity '{entity_str}'.")

    return provenance_tree 