from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    File,
    UploadFile,
    Response,
)
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import func # Added for func.lower
from typing import Set
import os
import typesense
import tempfile

from mlcbakery.models import Dataset, Collection, Entity
from mlcbakery.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DatasetPreviewResponse,
    DatasetListResponse,
    ProvenanceEntityNode,
)
from mlcbakery.models import EntityRelationship
from mlcbakery.database import get_async_db
from mlcbakery.api.dependencies import verify_auth_with_write_access, apply_auth_to_stmt, verify_auth, optional_auth, get_user_collection_id
from mlcbakery import search
from mlcbakery.croissant_validation import (
    validate_json,
    validate_croissant,
    validate_records,
    generate_validation_report,
    ValidationResult as CroissantValidationResult,  # Alias to avoid potential name conflicts
)
from opentelemetry import trace # Import for span manipulation
from mlcbakery.metrics import get_metric, NAME_SEARCH_QUERIES_TOTAL



router = APIRouter()



@router.get("/datasets/search")
async def search_datasets(
    q: str = Query(..., min_length=1, description="Search query term"),
    limit: int = Query(
        default=30, ge=1, le=100, description="Number of results to return"
    ),
    ts: typesense.Client = Depends(search.setup_and_get_typesense_client),
    auth: dict | None = Depends(optional_auth),
    db: AsyncSession = Depends(get_async_db),
):
    """Search datasets using Typesense based on query term, respecting privacy settings."""
    # Get the current span
    current_span = trace.get_current_span()
    # Add the search query as an attribute to the span
    current_span.set_attribute("search.query", q)

    # Get user's collection ID for privacy filtering
    user_collection_id = await get_user_collection_id(auth, db)

    # Build privacy filter
    privacy_filter = search.build_privacy_filter(user_collection_id)

    # Build base filter
    base_filter = "entity_type:dataset"
    if privacy_filter:
        filter_by = f"{base_filter} && {privacy_filter}"
    else:
        filter_by = base_filter

    search_parameters = {
        "q": q,
        "query_by": "long_description, metadata, collection_name, entity_name, full_name",
        "per_page": limit,
        "filter_by": filter_by,
        "include_fields": "collection_name, entity_name, full_name, entity_type, metadata, is_private",
    }

    return await search.run_search_query(search_parameters, ts)


@router.post("/datasets/{collection_name}", response_model=DatasetResponse)
async def create_dataset(
    collection_name: str,
    dataset: DatasetCreate,
    db: AsyncSession = Depends(get_async_db),
    auth: HTTPAuthorizationCredentials = Depends(verify_auth_with_write_access),
):
    """Create a new dataset (async)."""
    # Find the collection by name
    stmt_coll = select(Collection).where(Collection.name == collection_name)
    stmt_coll = apply_auth_to_stmt(stmt_coll, auth)
    result_coll = await db.execute(stmt_coll)
    collection = result_coll.scalar_one_or_none()
    if not collection:
        raise HTTPException(
            status_code=404,
            detail=f"Collection with name '{collection_name}' not found",
        )
    # Check for duplicate dataset name (case-insensitive) within the same collection
    stmt_check = (
        select(Dataset)
        .where(func.lower(Dataset.name) == func.lower(dataset.name))
        .where(Dataset.collection_id == collection.id)
    )
    result_check = await db.execute(stmt_check)
    if result_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Dataset already exists")
    db_dataset = Dataset(**dataset.model_dump(exclude={"collection_id"}), collection_id=collection.id)
    db.add(db_dataset)
    await db.commit()
    await db.flush([db_dataset])

    # Index to Typesense for immediate search availability
    # This is async and non-blocking - failures don't affect entity creation
    try:
        # Refresh to ensure collection relationship is loaded
        from sqlalchemy.orm import selectinload as sl
        stmt_refresh = select(Dataset).where(Dataset.id == db_dataset.id).options(sl(Dataset.collection))
        result_refresh = await db.execute(stmt_refresh)
        refreshed_dataset = result_refresh.scalar_one_or_none()
        if refreshed_dataset:
            await search.index_entity_to_typesense(refreshed_dataset)
    except Exception as e:
        print(f"Warning: Failed to index dataset to Typesense: {e}")

    return db_dataset

@router.get("/datasets/{collection_name}", response_model=list[DatasetListResponse])
async def list_datasets(
    collection_name: str,
    skip: int = Query(default=0, description="Number of records to skip"),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a list of datasets in a collection with pagination (async)."""
    if skip < 0 or limit < 0:
        raise HTTPException(
            status_code=400, detail="Offset and limit must be non-negative"
        )
    stmt = (
        select(Dataset)
        .join(Collection, Dataset.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .options(selectinload(Dataset.collection))
        .offset(skip)
        .limit(limit)
        .order_by(Dataset.id)
    )
    result = await db.execute(stmt)
    datasets = result.scalars().unique().all()
    return [
        DatasetListResponse(
            id=dataset.id,
            name=dataset.name,
            data_path=dataset.data_path,
            format=dataset.format,
            collection_name=dataset.collection.name if dataset.collection else None,
        )
        for dataset in datasets
        if dataset.collection and dataset.name
    ]

async def _refresh_dataset(dataset: Dataset) -> Dataset:
    return (
        select(Dataset)
        .where(Dataset.id == dataset.id)
        .options(
            selectinload(Dataset.collection),
            selectinload(Dataset.upstream_links).options(
                selectinload(EntityRelationship.source_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
            selectinload(Dataset.downstream_links).options(
                selectinload(EntityRelationship.target_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
        )
    )
async def _find_dataset_by_name(collection_name: str, dataset_name: str, db: AsyncSession) -> Dataset:
    stmt = (
        select(Dataset)
        .join(Collection, Dataset.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .where(Dataset.name == dataset_name)
        .options(
            selectinload(Dataset.collection),
            selectinload(Dataset.upstream_links).options(
                selectinload(EntityRelationship.source_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
            selectinload(Dataset.downstream_links).options(
                selectinload(EntityRelationship.target_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def _find_entity_by_id(entity_id: int, db: AsyncSession) -> Entity:
    stmt = select(Entity).where(Entity.id == entity_id).options(
        selectinload(Entity.collection),
        selectinload(Entity.upstream_links).options(
            selectinload(EntityRelationship.source_entity).options(
                selectinload(Entity.collection)
            ),
        ),
        selectinload(Entity.downstream_links).options(
            selectinload(EntityRelationship.target_entity).options(
                selectinload(Entity.collection)
            ),
        ),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

@router.put("/datasets/{collection_name}/{dataset_name}", response_model=DatasetResponse)
async def update_dataset(
    collection_name: str,
    dataset_name: str,
    dataset_update: DatasetUpdate,
    db: AsyncSession = Depends(get_async_db),
    _ = Depends(verify_auth_with_write_access),
):
    """Update a dataset (async)."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    update_data = dataset_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(dataset, field, value)
    db.add(dataset)
    await db.commit()
    result_refresh = await db.execute(await _refresh_dataset(dataset))
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()
    if not refreshed_dataset:
        raise HTTPException(
            status_code=500, detail="Failed to reload dataset after update"
        )

    # Re-index to Typesense with updated fields (especially privacy settings)
    try:
        await search.index_entity_to_typesense(refreshed_dataset)
    except Exception as e:
        print(f"Warning: Failed to re-index dataset to Typesense: {e}")

    return refreshed_dataset

@router.delete("/datasets/{collection_name}/{dataset_name}", status_code=200)
async def delete_dataset(
    collection_name: str,
    dataset_name: str,
    db: AsyncSession = Depends(get_async_db),
    _ = Depends(verify_auth_with_write_access),
):
    """Delete a dataset (async)."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    from mlcbakery.utils import delete_entity_with_versions
    await delete_entity_with_versions(dataset, db)
    await db.commit()
    return {"message": "Dataset deleted successfully"}

@router.patch("/datasets/{collection_name}/{dataset_name}/metadata", response_model=DatasetResponse)
async def update_dataset_metadata(
    collection_name: str,
    dataset_name: str,
    metadata: dict,
    db: AsyncSession = Depends(get_async_db),
    _ = Depends(verify_auth_with_write_access),
):
    """Update just the metadata of a dataset (async)."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    dataset.dataset_metadata = metadata
    db.add(dataset)
    await db.commit()
    result_refresh = await db.execute(await _refresh_dataset(dataset))
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()
    if not refreshed_dataset:
        raise HTTPException(
            status_code=500, detail="Failed to reload dataset after metadata update"
        )
    return refreshed_dataset

@router.put("/datasets/{collection_name}/{dataset_name}/preview", response_model=DatasetPreviewResponse)
async def update_dataset_preview(
    collection_name: str,
    dataset_name: str,
    preview_update: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    _ = Depends(verify_auth_with_write_access),
):
    """Update a dataset's preview (async) using file upload."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    preview_data: bytes = await preview_update.read()
    if not preview_data:
        dataset.preview = None
        dataset.preview_type = None
    else:
        dataset.preview = preview_data
        dataset.preview_type = preview_update.content_type
    db.add(dataset)
    await db.commit()
    result_refresh = await db.execute(await _refresh_dataset(dataset))
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()
    if not refreshed_dataset:
        raise HTTPException(
            status_code=500, detail="Failed to reload dataset after preview update"
        )
    return refreshed_dataset


@router.get("/datasets/{collection_name}/{dataset_name}/preview")
async def get_dataset_preview(
    collection_name: str, 
    dataset_name: str, 
    db: AsyncSession = Depends(get_async_db),
):
    """Get a dataset's preview (async)."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    preview_data = dataset.preview
    preview_type = dataset.preview_type

    if not preview_data or not preview_type:
        raise HTTPException(
            status_code=404, detail="Dataset preview not found or incomplete"
        )

    return Response(
        content=preview_data,
        media_type=preview_type,
    )


# The canonical way to fetch a dataset is now by collection_name and dataset_name
@router.get(
    "/datasets/{collection_name}/{dataset_name}", response_model=DatasetResponse
)
async def get_dataset_by_name(
    collection_name: str,
    dataset_name: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific dataset by collection name and dataset name (async)."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset

async def build_upstream_tree_async(
    entity: Entity | None, link: EntityRelationship | None, db: AsyncSession, visited: Set[int]
) -> ProvenanceEntityNode | None:
    """Build the upstream entity tree for a dataset (async)."""
    if entity is None:
        return None

    if entity.id in visited:
        return None
    
    # refresh the entity to get the latest data
    entity = await _find_entity_by_id(entity.id, db)

    visited.add(entity.id)

    current_node = ProvenanceEntityNode(
        id=entity.id,
        name=entity.name,
        collection_name=entity.collection.name if entity.collection else "N/A",
        entity_type=entity.entity_type,
        activity_name=link.activity_name if link else None,
    )

    if entity.upstream_links:
        for link in entity.upstream_links:
            child_node = await build_upstream_tree_async(link.source_entity, link, db, visited)
            if child_node:
                current_node.upstream_entities.append(child_node)

    if entity.downstream_links:
        for link in entity.downstream_links:
            child_node = await build_upstream_tree_async(link.target_entity, link, db, visited)
            if child_node:
                current_node.downstream_entities.append(child_node)

    return current_node


@router.get(
    "/datasets/{collection_name}/{dataset_name}/upstream",
    response_model=ProvenanceEntityNode,
)
async def get_dataset_upstream_tree(
    collection_name: str,
    dataset_name: str,
    db: AsyncSession = Depends(get_async_db),
) -> ProvenanceEntityNode:
    """Get the upstream entity tree for a dataset (async)."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return await build_upstream_tree_async(dataset, None, db, set())


@router.post("/datasets/mlcroissant-validation", response_model=dict)
async def validate_mlcroissant_file(
    file: UploadFile = File(
        ..., description="Croissant JSON-LD metadata file to validate"
    )
):
    """
    Validate an uploaded Croissant metadata file.

    Performs the following checks:
    1. Validates if the file is proper JSON.
    2. Validates if the JSON adheres to the Croissant schema.
    3. Validates if records can be generated (with a timeout).

    Returns a detailed report and structured validation results.
    """
    results: list[tuple[str, CroissantValidationResult]] = []
    temp_file_path = None

    try:
        # Create a temporary file to store the uploaded content
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        # 1. Validate JSON
        json_validation_result = validate_json(temp_file_path)
        results.append(("JSON Validation", json_validation_result))

        if json_validation_result.passed and json_validation_result.valid_json_data:
            # 2. Validate Croissant Schema
            croissant_validation_result = validate_croissant(
                json_validation_result.valid_json_data
            )
            results.append(("Croissant Schema Validation", croissant_validation_result))

            if croissant_validation_result.passed:
                # 3. Validate Records Generation
                records_validation_result = validate_records(
                    json_validation_result.valid_json_data
                )
                results.append(
                    ("Records Generation Validation", records_validation_result)
                )

        # Generate the structured report (now returns a dict)
        report = generate_validation_report(
            file.filename or "uploaded_file",
            json_validation_result.valid_json_data,
            results,
        )

        # Return the structured report directly
        return report

    except Exception as e:
        # Catch any unexpected errors during the process
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred during validation: {str(e)}",
        )
    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


@router.get("/datasets/{collection_name}/{dataset_name}/mlcroissant")
async def get_dataset_mlcroissant(
    collection_name: str,
    dataset_name: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a dataset's Croissant metadata (async)."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.dataset_metadata:
        raise HTTPException(status_code=404, detail="Dataset has no Croissant metadata")

    return dataset.dataset_metadata
