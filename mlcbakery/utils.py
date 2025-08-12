"""
Shared utility functions for the MLCBakery API.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from mlcbakery.models import Entity


# Mapping of entity types to their corresponding version table names
ENTITY_VERSION_TABLES = {
    "task": "tasks_version",
    "dataset": "datasets_version", 
    "trained_model": "trained_models_version",
}

# Mapping of entity types to their corresponding main table names
ENTITY_MAIN_TABLES = {
    "task": "tasks",
    "dataset": "datasets",
    "trained_model": "trained_models",
}


async def delete_entity_with_versions(entity: Entity, db: AsyncSession) -> None:
    """
    Properly delete an entity and its versioned records.
    
    SQLAlchemy Continuum creates versioned tables with foreign key constraints
    back to the main entity table. We need to delete all versioned records first,
    then delete the main entity using raw SQL to bypass Continuum's versioning system.
    
    Args:
        entity: The entity to delete
        db: The database session
        
    Raises:
        ValueError: If the entity type is not supported
    """
    entity_id = entity.id
    entity_type = entity.entity_type
    
    # Validate that we support this entity type
    if entity_type not in ENTITY_VERSION_TABLES:
        raise ValueError(f"Unsupported entity type for deletion: {entity_type}")
    
    # First, delete all versioned records to avoid foreign key constraints
    await db.execute(
        text("DELETE FROM entity_version_hashes WHERE entity_id = :entity_id"), 
        {"entity_id": entity_id}
    )
    
    # Delete from the specific entity version table
    version_table = ENTITY_VERSION_TABLES[entity_type]
    await db.execute(
        text(f"DELETE FROM {version_table} WHERE id = :entity_id"), 
        {"entity_id": entity_id}
    )
    
    # Delete from the general entities version table
    await db.execute(
        text("DELETE FROM entities_version WHERE id = :entity_id"), 
        {"entity_id": entity_id}
    )
    
    # Now delete the main entity records using raw SQL to bypass Continuum versioning
    main_table = ENTITY_MAIN_TABLES[entity_type]
    await db.execute(
        text(f"DELETE FROM {main_table} WHERE id = :entity_id"), 
        {"entity_id": entity_id}
    )
    
    # Finally, delete from the main entities table
    await db.execute(
        text("DELETE FROM entities WHERE id = :entity_id"), 
        {"entity_id": entity_id}
    )
