from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Sequence
from fastapi.security import HTTPAuthorizationCredentials

from ...database import get_async_db
from ...models import Activity, Entity, Agent
from ...schemas.activity import ActivityCreate, ActivityResponse
from mlcbakery.api.dependencies import verify_admin_token

router = APIRouter()


@router.post("/activities/", response_model=ActivityResponse)
async def create_activity(
    activity: ActivityCreate,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """Create a new activity with relationships (async)."""
    # Verify input entities exist
    stmt_entities = select(Entity).where(Entity.id.in_(activity.input_entity_ids))
    result_entities = await db.execute(stmt_entities)
    input_entities: Sequence[Entity] = result_entities.scalars().all()
    if len(input_entities) != len(activity.input_entity_ids):
        raise HTTPException(
            status_code=404, detail="One or more input entities not found"
        )

    # Verify output entity exists if specified
    output_entity = None
    if activity.output_entity_id:
        stmt_output = select(Entity).where(Entity.id == activity.output_entity_id)
        result_output = await db.execute(stmt_output)
        output_entity = result_output.scalar_one_or_none()
        if not output_entity:
            raise HTTPException(status_code=404, detail="Output entity not found")

    # Verify agents exist if specified
    agents: Sequence[Agent] = []
    if activity.agent_ids:
        stmt_agents = select(Agent).where(Agent.id.in_(activity.agent_ids))
        result_agents = await db.execute(stmt_agents)
        agents = result_agents.scalars().all()
        if len(agents) != len(activity.agent_ids):
            raise HTTPException(status_code=404, detail="One or more agents not found")

    # Create activity
    db_activity = Activity(name=activity.name)
    db_activity.input_entities = list(input_entities)
    if output_entity:
        db_activity.output_entity = output_entity
    if agents:
        db_activity.agents = list(agents)

    db.add(db_activity)
    await db.commit()
    await db.refresh(db_activity)
    # Eager load relationships for the response
    stmt_refresh = (
        select(Activity)
        .where(Activity.id == db_activity.id)
        .options(
            selectinload(Activity.input_entities),
            selectinload(Activity.output_entity),
            selectinload(Activity.agents),
        )
    )
    result_refresh = await db.execute(stmt_refresh)
    refreshed_activity = result_refresh.scalar_one()
    return refreshed_activity


@router.get("/activities/", response_model=List[ActivityResponse])
async def list_activities(
    skip: int = Query(default=0, description="Number of records to skip"),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
):
    """List all activities with pagination (async)."""
    stmt = (
        select(Activity)
        .offset(skip)
        .limit(limit)
        .options(
            selectinload(Activity.input_entities),
            selectinload(Activity.output_entity),
            selectinload(Activity.agents),
        )
    )
    result = await db.execute(stmt)
    activities = result.scalars().all()
    return activities


@router.get("/activities/{activity_id}", response_model=ActivityResponse)
async def get_activity(activity_id: int, db: AsyncSession = Depends(get_async_db)):
    """Get a specific activity by ID (async)."""
    stmt = (
        select(Activity)
        .where(Activity.id == activity_id)
        .options(
            selectinload(Activity.input_entities),
            selectinload(Activity.output_entity),
            selectinload(Activity.agents),
        )
    )
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@router.delete("/activities/{activity_id}", status_code=200)
async def delete_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """Delete an activity (async)."""
    # First get the activity to ensure it exists
    stmt = select(Activity).where(Activity.id == activity_id)
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    await db.delete(activity)
    await db.commit()
    return {"message": "Activity deleted successfully"}
