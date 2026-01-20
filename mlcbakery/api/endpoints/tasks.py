from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from typing import List
import typesense

from mlcbakery import search
from mlcbakery.models import Task, Collection, Entity, EntityRelationship, EntityVersionHash, EntityVersionTag
from mlcbakery.schemas.task import (
    TaskCreate,
    TaskResponse,
    TaskUpdate,
    TaskListResponse,
)
from mlcbakery.schemas.version import (
    VersionHistoryItem,
    VersionHistoryResponse,
    VersionDetailResponse,
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


# --------------------------------------------
# Version History Endpoints
# --------------------------------------------

async def _get_version_history_for_entity(
    entity_id: int,
    entity_type: str,
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    include_changeset: bool = False,
) -> list[dict]:
    """Get version history for an entity using raw SQL queries on Continuum tables."""
    from sqlalchemy import text

    # Query the appropriate version table based on entity type
    # Continuum creates tables like: entities_version, tasks_version, etc.
    # We need to join entities_version with tasks_version for task-specific fields

    # First, get version hashes and tags for this entity
    hash_stmt = (
        select(EntityVersionHash)
        .where(EntityVersionHash.entity_id == entity_id)
        .options(selectinload(EntityVersionHash.tags))
        .order_by(EntityVersionHash.transaction_id.desc())
    )
    hash_result = await db.execute(hash_stmt)
    hash_records = {h.transaction_id: h for h in hash_result.scalars().all()}

    # Query version tables using raw SQL since Continuum version classes
    # are not easily accessible in async context
    if entity_type == "task":
        version_query = text("""
            SELECT
                ev.transaction_id,
                ev.end_transaction_id,
                ev.operation_type,
                ev.name,
                ev.entity_type,
                ev.is_private,
                ev.croissant_metadata,
                tv.workflow,
                tv.version,
                tv.description,
                tv.has_file_uploads
            FROM entities_version ev
            JOIN tasks_version tv ON ev.id = tv.id AND ev.transaction_id = tv.transaction_id
            WHERE ev.id = :entity_id
            ORDER BY ev.transaction_id DESC
            OFFSET :skip
            LIMIT :limit
        """)
    else:
        # Fallback for base entity
        version_query = text("""
            SELECT
                transaction_id,
                end_transaction_id,
                operation_type,
                name,
                entity_type,
                is_private,
                croissant_metadata
            FROM entities_version
            WHERE id = :entity_id
            ORDER BY transaction_id DESC
            OFFSET :skip
            LIMIT :limit
        """)

    result = await db.execute(version_query, {"entity_id": entity_id, "skip": skip, "limit": limit})
    rows = result.fetchall()

    # Count total versions
    count_query = text("""
        SELECT COUNT(*) FROM entities_version WHERE id = :entity_id
    """)
    count_result = await db.execute(count_query, {"entity_id": entity_id})
    total_count = count_result.scalar()

    # Build history items
    history = []
    for i, row in enumerate(rows):
        row_dict = row._mapping
        transaction_id = row_dict["transaction_id"]
        hash_record = hash_records.get(transaction_id)

        # Calculate the version index (0 = oldest)
        # Since we're ordering DESC, we need to reverse the index
        version_index = total_count - skip - i - 1

        item = {
            "index": version_index,
            "transaction_id": transaction_id,
            "content_hash": hash_record.content_hash if hash_record else None,
            "tags": [t.tag_name for t in hash_record.tags] if hash_record else [],
            "created_at": hash_record.created_at if hash_record else None,
            "operation_type": str(row_dict.get("operation_type", "")).upper() if row_dict.get("operation_type") else None,
        }

        if include_changeset:
            # Build a simple changeset from the version data
            changeset = {}
            for key in ["name", "workflow", "version", "description", "has_file_uploads", "is_private"]:
                if key in row_dict and row_dict[key] is not None:
                    changeset[key] = row_dict[key]
            item["changeset"] = changeset

        history.append(item)

    return history, total_count


@router.get(
    "/tasks/{collection_name}/{task_name}/history",
    response_model=VersionHistoryResponse,
    summary="Get Task Version History",
    tags=["Tasks", "Versions"],
    operation_id="get_task_version_history",
)
async def get_task_version_history(
    collection_name: str,
    task_name: str,
    skip: int = Query(0, ge=0, description="Number of versions to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max versions to return"),
    include_changeset: bool = Query(False, description="Include field changes in response"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """
    Get the version history for a task.

    Returns a list of all versions with their hashes, tags, and timestamps.
    Versions are returned in reverse chronological order (newest first).
    """
    # Verify collection access
    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )

    # Find the task
    db_task = await _find_task_by_name(collection_name, task_name, db)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_name}' in collection '{collection_name}' not found",
        )

    # Get version history
    history, total_count = await _get_version_history_for_entity(
        db_task.id, "task", db, skip, limit, include_changeset
    )

    return VersionHistoryResponse(
        entity_name=db_task.name,
        entity_type="task",
        collection_name=collection_name,
        total_versions=total_count,
        versions=[VersionHistoryItem(**item) for item in history],
    )


async def _resolve_version_ref(
    entity_id: int,
    version_ref: str,
    db: AsyncSession,
) -> tuple[int, EntityVersionHash | None]:
    """
    Resolve a version reference to a transaction_id and hash record.

    Args:
        entity_id: The entity ID
        version_ref: Can be:
            - A 64-character SHA-256 hash
            - A semantic tag (e.g., "v1.0.0")
            - An index prefixed with ~ (e.g., "~0" for first, "~-1" for latest)
        db: Async database session

    Returns:
        Tuple of (transaction_id, hash_record)
    """
    from sqlalchemy import text

    # Count total versions for index resolution
    count_query = text("SELECT COUNT(*) FROM entities_version WHERE id = :entity_id")
    count_result = await db.execute(count_query, {"entity_id": entity_id})
    total_versions = count_result.scalar()

    if total_versions == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Entity has no version history",
        )

    # Handle index reference (~0, ~1, ~-1, etc.)
    if version_ref.startswith("~"):
        try:
            index = int(version_ref[1:])
            if index < 0:
                index = total_versions + index
            if index < 0 or index >= total_versions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version index {version_ref} out of range (0-{total_versions - 1})",
                )

            # Get transaction_id at this index (ordered ASC for index calculation)
            index_query = text("""
                SELECT transaction_id FROM entities_version
                WHERE id = :entity_id
                ORDER BY transaction_id ASC
                OFFSET :idx
                LIMIT 1
            """)
            result = await db.execute(index_query, {"entity_id": entity_id, "idx": index})
            transaction_id = result.scalar()

            # Get hash record
            hash_stmt = (
                select(EntityVersionHash)
                .where(EntityVersionHash.entity_id == entity_id)
                .where(EntityVersionHash.transaction_id == transaction_id)
                .options(selectinload(EntityVersionHash.tags))
            )
            hash_result = await db.execute(hash_stmt)
            hash_record = hash_result.scalar_one_or_none()

            return transaction_id, hash_record

        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid version index: {version_ref}",
            )

    # Handle 64-char hash
    if len(version_ref) == 64:
        hash_stmt = (
            select(EntityVersionHash)
            .where(EntityVersionHash.entity_id == entity_id)
            .where(EntityVersionHash.content_hash == version_ref)
            .options(selectinload(EntityVersionHash.tags))
        )
        hash_result = await db.execute(hash_stmt)
        hash_record = hash_result.scalar_one_or_none()

        if not hash_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Version hash '{version_ref}' not found",
            )

        return hash_record.transaction_id, hash_record

    # Handle semantic tag
    tag_stmt = (
        select(EntityVersionTag)
        .join(EntityVersionHash)
        .where(EntityVersionHash.entity_id == entity_id)
        .where(EntityVersionTag.tag_name == version_ref)
        .options(selectinload(EntityVersionTag.version_hash).selectinload(EntityVersionHash.tags))
    )
    tag_result = await db.execute(tag_stmt)
    tag = tag_result.scalar_one_or_none()

    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version tag '{version_ref}' not found",
        )

    return tag.version_hash.transaction_id, tag.version_hash


@router.get(
    "/tasks/{collection_name}/{task_name}/versions/{version_ref}",
    response_model=VersionDetailResponse,
    summary="Get Task at Specific Version",
    tags=["Tasks", "Versions"],
    operation_id="get_task_version",
)
async def get_task_version(
    collection_name: str,
    task_name: str,
    version_ref: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """
    Get the full task data at a specific version.

    The version_ref can be:
    - A 64-character SHA-256 hash
    - A semantic tag (e.g., "v1.0.0", "production")
    - An index prefixed with ~ (e.g., "~0" for oldest, "~-1" for latest)
    """
    from sqlalchemy import text

    # Verify collection access
    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )

    # Find the task
    db_task = await _find_task_by_name(collection_name, task_name, db)
    if not db_task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_name}' in collection '{collection_name}' not found",
        )

    # Resolve version reference
    transaction_id, hash_record = await _resolve_version_ref(db_task.id, version_ref, db)

    # Get the version data
    version_query = text("""
        SELECT
            ev.transaction_id,
            ev.operation_type,
            ev.name,
            ev.entity_type,
            ev.is_private,
            ev.croissant_metadata,
            tv.workflow,
            tv.version,
            tv.description,
            tv.has_file_uploads
        FROM entities_version ev
        JOIN tasks_version tv ON ev.id = tv.id AND ev.transaction_id = tv.transaction_id
        WHERE ev.id = :entity_id AND ev.transaction_id = :transaction_id
    """)
    result = await db.execute(version_query, {"entity_id": db_task.id, "transaction_id": transaction_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version data not found for transaction {transaction_id}",
        )

    row_dict = row._mapping

    # Calculate the version index
    count_query = text("""
        SELECT COUNT(*) FROM entities_version
        WHERE id = :entity_id AND transaction_id <= :transaction_id
    """)
    count_result = await db.execute(count_query, {"entity_id": db_task.id, "transaction_id": transaction_id})
    version_index = count_result.scalar() - 1

    # Build the data dict
    data = {
        "name": row_dict.get("name"),
        "entity_type": row_dict.get("entity_type"),
        "is_private": row_dict.get("is_private"),
        "croissant_metadata": row_dict.get("croissant_metadata"),
        "workflow": row_dict.get("workflow"),
        "version": row_dict.get("version"),
        "description": row_dict.get("description"),
        "has_file_uploads": row_dict.get("has_file_uploads"),
    }

    return VersionDetailResponse(
        index=version_index,
        transaction_id=transaction_id,
        content_hash=hash_record.content_hash if hash_record else None,
        tags=[t.tag_name for t in hash_record.tags] if hash_record else [],
        created_at=hash_record.created_at if hash_record else None,
        operation_type=str(row_dict.get("operation_type", "")).upper() if row_dict.get("operation_type") else None,
        data=data,
    )
