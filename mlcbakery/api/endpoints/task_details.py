from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import Any

from mlcbakery.models import Task, Collection
from mlcbakery.schemas.task import TaskResponse
from mlcbakery.database import get_async_db
from mlcbakery.api.dependencies import apply_auth_to_stmt, get_flexible_auth
from mlcbakery.api.access_level import AccessLevel

router = APIRouter()

@router.get("/task-details/{collection_name}/{task_name}", response_model=TaskResponse)
async def get_task_details_with_flexible_auth(
    collection_name: str,
    task_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth_data: tuple[str, Any] = Depends(get_flexible_auth)
):
    """
    Get task details using either API key or JWT authentication.
    
    For API key authentication:
    - The API key must belong to the collection containing the task
    - Admin API key allows access to any collection
    
    For JWT authentication:
    - User can only access tasks in collections they own
    """
    auth_type, auth_payload = auth_data

    if auth_type == 'api_key':
        # Handle API key authentication (existing logic)
        if auth_payload is None:
            # Admin API key - search across all collections
            stmt = (
                select(Task)
                .join(Collection, Task.collection_id == Collection.id)
                .where(Task.name == task_name)
                .where(Collection.name == collection_name)
                .options(
                    selectinload(Task.collection),
                )
            )
        else:
            # Regular API key - verify collection access
            collection, api_key = auth_payload
            
            # Verify the collection name matches the API key's collection
            if collection.name != collection_name:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="API key not valid for this collection"
                )
            
            # Find the task in the specific collection
            stmt = (
                select(Task)
                .where(Task.collection_id == collection.id)
                .where(Task.name == task_name)
                .options(
                    selectinload(Task.collection),
                )
            )
    
    elif auth_type == 'jwt':
        # Handle JWT authentication
        stmt = (
            select(Task)
            .join(Collection, Task.collection_id == Collection.id)
            .where(Task.name == task_name)
            .where(Collection.name == collection_name)
            .options(
                selectinload(Task.collection),
            )
        )
        
        # Apply auth filtering based on access level
        if auth_payload.get("access_level") == AccessLevel.ADMIN:
            # Admin level access - no additional filtering needed
            # The task will be found if it exists in the specified collection
            pass
        else:
            # Regular user access - restrict to user's collections
            stmt = apply_auth_to_stmt(stmt, auth_payload)
    
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid authentication type"
        )
    
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_name}' not found in collection '{collection_name}'"
        )
    
    # Create TaskResponse with collection environment variables and storage details
    task_response = TaskResponse.model_validate(task)
    # access the task collection:
    collection_stmt = select(Collection).where(Collection.id == task.collection_id)
    collection_result = await db.execute(collection_stmt)
    collection = collection_result.scalar_one_or_none()
    
    task_response.environment_variables = collection.environment_variables
    task_response.storage_info = collection.storage_info
    task_response.storage_provider = collection.storage_provider

    return task_response 