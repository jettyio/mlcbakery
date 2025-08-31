from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from typing import List
import typesense

from mlcbakery import search
from mlcbakery.models import Task, Collection, Entity, EntityRelationship
from mlcbakery.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TaskListResponse,
)
from mlcbakery.database import get_async_db
from mlcbakery.api.dependencies import verify_auth, apply_auth_to_stmt, verify_auth_with_write_access
from opentelemetry import trace

router = APIRouter()

# --------------------------------------------
# Helper utilities
# --------------------------------------------

async def _find_task_by_name(collection_name: str, task_name: str, db: AsyncSession) -> Task | None:
    stmt = (
        select(Task)
        .join(Collection, Task.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .where(func.lower(Task.name) == func.lower(task_name))
        .options(
            selectinload(Task.collection),
            selectinload(Task.upstream_links).options(
                selectinload(EntityRelationship.source_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
            selectinload(Task.downstream_links).options(
                selectinload(EntityRelationship.target_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# --------------------------------------------
# Search
# --------------------------------------------
@router.get("/tasks/search")
async def search_tasks(
    q: str = Query(..., min_length=1, description="Search query term"),
    limit: int = Query(default=30, ge=1, le=100, description="Number of results to return"),
    ts: typesense.Client = Depends(search.setup_and_get_typesense_client),
):
    """Search tasks using Typesense based on query term."""
    current_span = trace.get_current_span()
    current_span.set_attribute("search.query", q)

    search_parameters = {
        "q": q,
        "query_by": "description, workflow, collection_name, entity_name, full_name",
        "per_page": limit,
        "filter_by": "entity_type:task",
        "include_fields": "collection_name, entity_name, full_name, entity_type, metadata",
    }

    return await search.run_search_query(search_parameters, ts)

# GET endpoints first

@router.get(
    "/tasks/",
    response_model=List[TaskListResponse],
    summary="List All Tasks",
    tags=["Tasks"],
    operation_id="list_all_tasks",
)
async def list_tasks(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """List all tasks accessible to the user."""
    # Admin users can see all tasks, regular users only see their own
    stmt = (
        select(Task)
        .join(Collection, Task.collection_id == Collection.id)
        .options(selectinload(Task.collection))
        .offset(skip)
        .limit(limit)
        .order_by(Task.id)
    )

    stmt = apply_auth_to_stmt(stmt, auth)

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return [
        TaskListResponse(
            id=task.id,
            name=task.name,
            workflow=task.workflow,
            version=task.version,
            description=task.description,
            has_file_uploads=task.has_file_uploads,
            collection_id=task.collection_id,
            collection_name=task.collection.name if task.collection else None,
        )
        for task in tasks
    ]


@router.get(
    "/tasks/{collection_name}/",
    response_model=List[TaskListResponse],
    summary="List Tasks by Collection",
    tags=["Tasks"],
    operation_id="list_tasks_by_collection",
)
async def list_tasks_by_collection(
    collection_name: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """List all tasks in a specific collection owned by the user."""
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

    # Get tasks in the collection
    stmt = (
        select(Task)
        .join(Collection, Task.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .options(selectinload(Task.collection))
        .offset(skip)
        .limit(limit)
        .order_by(Task.id)
    )
    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return [
        TaskListResponse(
            id=task.id,
            name=task.name,
            workflow=task.workflow,
            version=task.version,
            description=task.description,
            has_file_uploads=task.has_file_uploads,
            collection_id=task.collection_id,
            collection_name=task.collection.name if task.collection else None,
        )
        for task in tasks
    ]


@router.get(
    "/tasks/{collection_name}/{task_name}",
    response_model=TaskResponse,
    summary="Get a Task by Collection and Name",
    tags=["Tasks"],
    operation_id="get_task_by_name",
)
async def get_task_by_name(
    collection_name: str,
    task_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """
    Get a specific task by its collection name and task name.

    - **collection_name**: Name of the collection the task belongs to.
    - **task_name**: Name of the task.
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

    db_task = await _find_task_by_name(collection_name, task_name, db)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_name}' in collection '{collection_name}' not found",
        )
    return db_task

# POST endpoints

@router.post(
    "/tasks/{collection_name}",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Task by Collection Name",
    tags=["Tasks"],
    operation_id="create_task_by_name",
)
async def create_task_by_name(
    collection_name: str,
    task_in: TaskCreate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Create a new workflow task in the database using collection name.

    - **collection_name**: Name of the collection this task belongs to (from URL path).
    - **name**: Name of the task (required)
    - **workflow**: Workflow definition (required)
    - **version**: Version of the task (optional)
    - **description**: Description of the task (optional)
    - **has_file_uploads**: Whether the task has file uploads (default: false)
    """
    # Find collection by name and verify ownership
    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )

    # Duplicate check (case-insensitive)
    stmt_check = (
        select(Task)
        .where(func.lower(Task.name) == func.lower(task_in.name))
        .where(Task.collection_id == collection.id)
    )
    result_check = await db.execute(stmt_check)
    if result_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task with name '{task_in.name}' already exists in collection '{collection.name}'",
        )

    task_data = task_in.model_dump(exclude={"collection_name"})
    task_data["collection_id"] = collection.id

    db_task = Task(**task_data)
    db.add(db_task)
    await db.commit()
    await db.refresh(db_task)

    return db_task

# PUT endpoints

@router.put(
    "/tasks/{collection_name}/{task_name}",
    response_model=TaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a Task by Collection and Task Name",
    tags=["Tasks"],
    operation_id="update_task_by_name",
)
async def update_task_by_name(
    collection_name: str,
    task_name: str,
    task_update: TaskUpdate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Update an existing task by its collection name and task name.

    - **collection_name**: Name of the collection the task belongs to.
    - **task_name**: Name of the task to update.
    - **name**: New name for the task (optional).
    - **workflow**: New workflow definition (optional).
    - **version**: New version string (optional).
    - **description**: New description (optional).
    - **has_file_uploads**: Whether the task has file uploads (optional).
    
    Note: The task name can be updated, but it cannot duplicate an existing task name in the same collection.
    """
    db_task = await _find_task_by_name(collection_name, task_name, db)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_name}' in collection '{collection_name}' not found"
        )

    # If updating name, check for duplicates (case-insensitive)
    update_data = task_update.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"].lower() != db_task.name.lower():
        stmt_check = (
            select(Task)
            .where(func.lower(Task.name) == func.lower(update_data["name"]))
            .where(Task.collection_id == db_task.collection_id)
            .where(Task.id != db_task.id)  # Exclude current task
        )
        result_check = await db.execute(stmt_check)
        if result_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task with name '{update_data['name']}' already exists in collection '{collection_name}'"
            )

    for field, value in update_data.items():
        setattr(db_task, field, value)

    await db.commit()
    await db.refresh(db_task)
    return db_task

# DELETE endpoints

@router.delete(
    "/tasks/{collection_name}/{task_name}",
    status_code=status.HTTP_200_OK,
    summary="Delete a Task by Collection and Task Name",
    tags=["Tasks"],
    operation_id="delete_task_by_name",
)
async def delete_task_by_name(
    collection_name: str,
    task_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Delete a task by its collection name and task name.

    - **collection_name**: Name of the collection the task belongs to.
    - **task_name**: Name of the task to delete.
    """
    task = await _find_task_by_name(collection_name, task_name, db)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    from mlcbakery.utils import delete_entity_with_versions
    await delete_entity_with_versions(task, db)
    await db.commit()
    return {"message": "Task deleted successfully"}
