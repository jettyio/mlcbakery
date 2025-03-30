from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...models import Agent
from ...schemas.agent import AgentCreate, AgentResponse

router = APIRouter()


@router.post("/agents/", response_model=AgentResponse)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    """Create a new agent."""
    db_agent = Agent(**agent.model_dump())
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    return db_agent


@router.get("/agents/", response_model=List[AgentResponse])
def list_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all agents."""
    agents = db.query(Agent).offset(skip).limit(limit).all()
    return agents


@router.get("/agents/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    """Get a specific agent by ID."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/agents/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int, agent_update: AgentCreate, db: Session = Depends(get_db)
):
    """Update an agent."""
    db_agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not db_agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Update only provided fields
    update_data = agent_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_agent, field, value)

    db.commit()
    db.refresh(db_agent)
    return db_agent


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    """Delete an agent."""
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    db.delete(agent)
    db.commit()
    return {"message": "Agent deleted successfully"}
