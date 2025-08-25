from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List
from ...database import get_async_db
from ...models import Agent
from ...schemas.agent import AgentResponse, AgentCreate, AgentListResponse, AgentUpdate
from mlcbakery.api.dependencies import verify_auth, verify_auth_with_write_access, apply_auth_to_stmt
from mlcbakery.models import Collection
from sqlalchemy.orm import selectinload

router = APIRouter()

@router.get(
    "/agents/{collection_name}/",
    response_model=List[AgentListResponse],
    summary="List Agents by Collection",
    tags=["Agents"],
    operation_id="list_agents_by_collection",
)
async def list_agents_by_collection(
    collection_name: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """List all agents in a specific collection owned by the user."""
    # First verify the collection exists and user has access
    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )
    
    # Get agents in the collection
    stmt = (
        select(Agent)
        .join(Collection, Agent.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .options(selectinload(Agent.collection))
        .offset(skip)
        .limit(limit)
        .order_by(Agent.id)
    )
    stmt = apply_auth_to_stmt(stmt, auth)
    result = await db.execute(stmt)
    agents = result.scalars().all()

    return [
        AgentListResponse(
            id=agent.id,
            name=agent.name,
            type=agent.type,
            collection_id=agent.collection_id,
            collection_name=agent.collection.name if agent.collection else None,
        )
        for agent in agents
    ]


@router.get(
    "/agents/{collection_name}/{agent_name}",
    response_model=AgentResponse,
    summary="Get an Agent by Collection and Agent Name",
    tags=["Agents"],
    operation_id="get_agent_by_name",
)
async def get_agent_by_name(
    collection_name: str,
    agent_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """
    Get a specific agent by its collection name and agent name.

    - **collection_name**: Name of the collection the agent belongs to.
    - **agent_name**: Name of the agent.
    """
    # First verify the collection exists and user has access
    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )

    db_agent = await _find_agent_by_name(collection_name, agent_name, db)
    if not db_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{agent_name}' in collection '{collection_name}' not found"
        )
    return db_agent


@router.post(
    "/agents/{collection_name}",
    response_model=AgentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Agent by Collection Name",
    tags=["Agents"],
    operation_id="create_agent_by_name",
)
async def create_agent_by_name(
    collection_name: str,
    agent_in: AgentCreate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Create a new agent in the database using collection name.

    - **collection_name**: Name of the collection this agent belongs to (from URL path).
    - **name**: Name of the agent (required)
    - **type**: Type of the agent (optional)
    """
    # Find collection by name and verify access
    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )

    # Check if agent with the same name already exists in the collection (case-insensitive)
    stmt_check = (
        select(Agent)
        .where(func.lower(Agent.name) == func.lower(agent_in.name))
        .where(Agent.collection_id == collection.id)
    )
    result_check = await db.execute(stmt_check)
    if result_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent with name '{agent_in.name}' already exists in collection '{collection.name}'"
        )
    
    # Prepare agent data for creation, explicitly setting collection_id
    agent_data_for_db = agent_in.model_dump()
    agent_data_for_db["collection_id"] = collection.id

    db_agent = Agent(**agent_data_for_db)
    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)

    return db_agent


@router.put(
    "/agents/{collection_name}/{agent_name}",
    response_model=AgentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an Agent by Collection and Agent Name",
    tags=["Agents"],
    operation_id="update_agent_by_name",
)
async def update_agent_by_name(
    collection_name: str,
    agent_name: str,
    agent_update: AgentUpdate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Update an agent by its collection name and agent name.

    - **collection_name**: Name of the collection the agent belongs to.
    - **agent_name**: Name of the agent to update.
    - **name**: New name for the agent (optional).
    - **type**: New type for the agent (optional).
    
    Note: The agent name and collection cannot be changed if it would create a duplicate.
    """
    # Find the agent to update
    agent = await _find_agent_by_name(collection_name, agent_name, db)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    update_data = agent_update.model_dump(exclude_unset=True)
    
    # If name is being updated, check for duplicates
    if "name" in update_data and update_data["name"] != agent.name:
        stmt_check = (
            select(Agent)
            .where(func.lower(Agent.name) == func.lower(update_data["name"]))
            .where(Agent.collection_id == agent.collection_id)
            .where(Agent.id != agent.id)  # Exclude current agent
        )
        result_check = await db.execute(stmt_check)
        if result_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent with name '{update_data['name']}' already exists in collection '{collection_name}'"
            )

    # Apply updates
    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete(
    "/agents/{collection_name}/{agent_name}",
    status_code=status.HTTP_200_OK,
    summary="Delete an Agent by Collection and Agent Name",
    tags=["Agents"],
    operation_id="delete_agent_by_name",
)
async def delete_agent_by_name(
    collection_name: str,
    agent_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Delete an agent by its collection name and agent name.

    - **collection_name**: Name of the collection the agent belongs to.
    - **agent_name**: Name of the agent to delete.
    """
    agent = await _find_agent_by_name(collection_name, agent_name, db)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found"
        )

    await db.delete(agent)
    await db.commit()
    return {"message": "Agent deleted successfully"}


async def _find_agent_by_name(collection_name: str, agent_name: str, db: AsyncSession) -> Agent | None:
    stmt = (
        select(Agent)
        .join(Collection, Agent.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .where(func.lower(Agent.name) == func.lower(agent_name))  # Case-insensitive name match
        .options(selectinload(Agent.collection))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
