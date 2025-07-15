from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from mlcbakery.models import Task, Collection, ApiKey
from mlcbakery.schemas.task import TaskResponse
from mlcbakery.database import get_async_db
from mlcbakery.api.dependencies import verify_api_key_for_collection

router = APIRouter()

@router.get("/task-details/{collection_name}/{task_name}", response_model=TaskResponse)
async def get_task_details_with_api_key(
    collection_name: str,
    task_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth_data: tuple[Collection, ApiKey] = Depends(verify_api_key_for_collection)
):
    """
    Get task details using API key authentication.
    The API key must belong to the collection containing the task.
    """
    collection, api_key = auth_data
    
    # Verify the collection name matches the API key's collection
    if collection.name != collection_name:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key not valid for this collection"
        )
    
    # Find the task
    stmt = (
        select(Task)
        .where(Task.collection_id == collection.id)
        .where(Task.name == task_name)
        .where(Task.entity_type == "task")
        .options(
            selectinload(Task.collection),
            selectinload(Task.upstream_links),
            selectinload(Task.downstream_links)
        )
    )
    
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_name}' not found in collection '{collection_name}'"
        )
    
    return task 