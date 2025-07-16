from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from ...database import get_async_db
from ...models import Agent
from ...schemas.agent import AgentCreate, AgentResponse
from mlcbakery.api.dependencies import verify_auth, verify_auth_with_write_access
from mlcbakery.models import Collection

router = APIRouter()


@router.post("/agents/", response_model=AgentResponse)
async def create_agent(
    agent: AgentCreate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """Create a new agent (async)."""
    # Create the agent with all provided fields (including collection_id if present)
    db_agent = Agent(**agent.model_dump())
    
    # If collection_id is provided, validate it exists and is owned by the user
    if agent.collection_id is not None:
        stmt = select(Collection).where(
            Collection.id == agent.collection_id,
            Collection.owner_identifier == auth['identifier']
        )
        result = await db.execute(stmt)
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection with id {agent.collection_id} not found")
    
    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)
    return db_agent


@router.get("/agents/", response_model=List[AgentResponse])
async def list_agents(
    skip: int = Query(default=0, description="Number of records to skip"),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth)
):
    """List all agents owned by the authenticated user (async)."""
    # Filter agents by collections owned by the user
    stmt = (
        select(Agent)
        .join(Collection, Agent.collection_id == Collection.id)
        .where(Collection.owner_identifier == auth['identifier'])
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    agents = result.scalars().all()
    return agents


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_async_db), auth = Depends(verify_auth)):
    """Get a specific agent by ID, only if owned by the authenticated user (async)."""
    # Filter agent by collection ownership
    stmt = (
        select(Agent)
        .join(Collection, Agent.collection_id == Collection.id)
        .where(
            Agent.id == agent_id,
            Collection.owner_identifier == auth['identifier']
        )
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_update: AgentCreate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """Update an agent, only if owned by the authenticated user (async)."""
    # Get agent and verify ownership
    stmt_get = (
        select(Agent)
        .join(Collection, Agent.collection_id == Collection.id)
        .where(
            Agent.id == agent_id,
            Collection.owner_identifier == auth['identifier']
        )
    )
    result_get = await db.execute(stmt_get)
    db_agent = result_get.scalar_one_or_none()

    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # If collection_id is being updated, validate it exists and is owned by the user
    if agent_update.collection_id is not None and agent_update.collection_id != db_agent.collection_id:
        stmt = select(Collection).where(
            Collection.id == agent_update.collection_id,
            Collection.owner_identifier == auth['identifier']
        )
        result = await db.execute(stmt)
        collection = result.scalar_one_or_none()
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection with id {agent_update.collection_id} not found")

    update_data = agent_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_agent, field, value)

    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)
    return db_agent


@router.delete("/agents/{agent_id}", status_code=200)
async def delete_agent(
    agent_id: int,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """Delete an agent, only if owned by the authenticated user (async)."""
    # Get agent and verify ownership
    stmt = (
        select(Agent)
        .join(Collection, Agent.collection_id == Collection.id)
        .where(
            Agent.id == agent_id,
            Collection.owner_identifier == auth['identifier']
        )
    )
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    await db.delete(agent)
    await db.commit()
    return {"message": "Agent deleted successfully"}
