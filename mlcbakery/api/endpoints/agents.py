from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload # Needed if Agent has relationships to eager load
from typing import List
import python_multipart
from ...database import get_async_db
from ...models import Agent
from ...schemas.agent import AgentCreate, AgentResponse

router = APIRouter()


@router.post("/agents/", response_model=AgentResponse)
async def create_agent(agent: AgentCreate, db: AsyncSession = Depends(get_async_db)):
    """Create a new agent (async)."""
    db_agent = Agent(**agent.model_dump())
    db.add(db_agent)
    await db.commit()
    await db.refresh(db_agent)
    # If Agent has relationships, eager load them here for the response if needed
    # stmt = select(Agent).where(Agent.id == db_agent.id).options(selectinload(...))
    # result = await db.execute(stmt)
    # db_agent = result.scalar_one()
    return db_agent


@router.get("/agents/", response_model=List[AgentResponse])
async def list_agents(
    skip: int = Query(default=0, description="Number of records to skip"),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db)
):
    """List all agents (async)."""
    stmt = select(Agent).offset(skip).limit(limit)
    # Add .options(selectinload(...)) if eager loading is needed
    result = await db.execute(stmt)
    agents = result.scalars().all()
    return agents


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_async_db)):
    """Get a specific agent by ID (async)."""
    stmt = select(Agent).where(Agent.id == agent_id)
    # Add .options(selectinload(...)) if eager loading is needed
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int, agent_update: AgentCreate, db: AsyncSession = Depends(get_async_db)
):
    """Update an agent (async)."""
    # Get the existing agent
    stmt_get = select(Agent).where(Agent.id == agent_id)
    result_get = await db.execute(stmt_get)
    db_agent = result_get.scalar_one_or_none()

    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Update only provided fields
    update_data = agent_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_agent, field, value)

    db.add(db_agent) # Add to session to track changes
    await db.commit()
    await db.refresh(db_agent)
    # Eager load if necessary for the response
    # stmt_refresh = select(Agent).where(Agent.id == db_agent.id).options(selectinload(...))
    # result_refresh = await db.execute(stmt_refresh)
    # db_agent = result_refresh.scalar_one()
    return db_agent


@router.delete("/agents/{agent_id}", status_code=200)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_async_db)):
    """Delete an agent (async)."""
    stmt = select(Agent).where(Agent.id == agent_id)
    result = await db.execute(stmt)
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    await db.delete(agent)
    await db.commit()
    return {"message": "Agent deleted successfully"}
