from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Sequence
from fastapi.security import HTTPAuthorizationCredentials

from ...database import get_async_db
from ...models import Activity
from ...schemas.activity import ActivityCreate, ActivityResponse
from mlcbakery.api.dependencies import verify_admin_token

router = APIRouter()


@router.delete("/activities/{activity_id}", status_code=200)
async def delete_activity(
    activity_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """Delete an activity (async).
    Note: If the activity is part of any relationships in 'entity_relationships',
    deletion might be restricted by the database depending on foreign key constraints (default NO ACTION/RESTRICT).
    """
    stmt = select(Activity).where(Activity.id == activity_id)
    result = await db.execute(stmt)
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    await db.delete(activity)
    await db.commit()
    return {"message": "Activity deleted successfully"}
