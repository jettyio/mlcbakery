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

from mlcbakery.models import Dataset, Collection, Entity, EntityVersionHash, EntityVersionTag
from mlcbakery.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DatasetPreviewResponse,
    DatasetListResponse,
    ProvenanceEntityNode,
)
from mlcbakery.schemas.version import (
    VersionHistoryItem,
    VersionHistoryResponse,
    VersionDetailResponse,
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


# --------------------------------------------
# Helper utilities
# --------------------------------------------

async def _get_entity_updated_at(entity_id: int, db: AsyncSession):
    """Get the updated_at timestamp from the latest version's transaction."""
    from sqlalchemy import text
    query = text("""
        SELECT t.issued_at
        FROM entities_version ev
        JOIN transaction t ON ev.transaction_id = t.id
        WHERE ev.id = :entity_id
        ORDER BY ev.transaction_id DESC
        LIMIT 1
    """)
    result = await db.execute(query, {"entity_id": entity_id})
    row = result.fetchone()
    return row[0] if row else None



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

    # Get updated_at from latest version transaction
    updated_at = await _get_entity_updated_at(dataset.id, db)

    return DatasetResponse(
        id=dataset.id,
        name=dataset.name,
        data_path=dataset.data_path,
        format=dataset.format,
        collection_id=dataset.collection_id,
        metadata_version=dataset.metadata_version,
        dataset_metadata=dataset.dataset_metadata,
        preview_type=dataset.preview_type,
        long_description=dataset.long_description,
        asset_origin=dataset.asset_origin,
        is_private=dataset.is_private,
        croissant_metadata=dataset.croissant_metadata,
        created_at=dataset.created_at,
        updated_at=updated_at,
    )

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


# --------------------------------------------
# Version History Endpoints
# --------------------------------------------

async def _get_dataset_version_history(
    entity_id: int,
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    include_changeset: bool = False,
) -> tuple[list[dict], int]:
    """Get version history for a dataset."""
    from sqlalchemy import text

    # Get version hashes and tags
    hash_stmt = (
        select(EntityVersionHash)
        .where(EntityVersionHash.entity_id == entity_id)
        .options(selectinload(EntityVersionHash.tags))
        .order_by(EntityVersionHash.transaction_id.desc())
    )
    hash_result = await db.execute(hash_stmt)
    hash_records = {h.transaction_id: h for h in hash_result.scalars().all()}

    # Query version tables with transaction timestamp
    version_query = text("""
        SELECT
            ev.transaction_id,
            ev.end_transaction_id,
            ev.operation_type,
            ev.name,
            ev.entity_type,
            ev.is_private,
            ev.croissant_metadata,
            dv.data_path,
            dv.format,
            dv.metadata_version,
            dv.dataset_metadata,
            dv.long_description,
            t.issued_at
        FROM entities_version ev
        JOIN datasets_version dv ON ev.id = dv.id AND ev.transaction_id = dv.transaction_id
        LEFT JOIN transaction t ON ev.transaction_id = t.id
        WHERE ev.id = :entity_id
        ORDER BY ev.transaction_id DESC
        OFFSET :skip
        LIMIT :limit
    """)

    result = await db.execute(version_query, {"entity_id": entity_id, "skip": skip, "limit": limit})
    rows = result.fetchall()

    # Count total versions
    count_query = text("SELECT COUNT(*) FROM entities_version WHERE id = :entity_id")
    count_result = await db.execute(count_query, {"entity_id": entity_id})
    total_count = count_result.scalar()

    history = []
    for i, row in enumerate(rows):
        row_dict = row._mapping
        transaction_id = row_dict["transaction_id"]
        hash_record = hash_records.get(transaction_id)
        version_index = total_count - skip - i - 1

        # Use issued_at from transaction table as the authoritative timestamp
        # Fall back to EntityVersionHash.created_at if available
        version_timestamp = row_dict.get("issued_at")
        if version_timestamp is None and hash_record:
            version_timestamp = hash_record.created_at

        item = {
            "index": version_index,
            "transaction_id": transaction_id,
            "content_hash": hash_record.content_hash if hash_record else None,
            "tags": [t.tag_name for t in hash_record.tags] if hash_record else [],
            "created_at": version_timestamp,
            "operation_type": str(row_dict.get("operation_type", "")).upper() if row_dict.get("operation_type") else None,
        }

        if include_changeset:
            changeset = {}
            for key in ["name", "data_path", "format", "metadata_version", "long_description", "is_private"]:
                if key in row_dict and row_dict[key] is not None:
                    changeset[key] = row_dict[key]
            item["changeset"] = changeset

        history.append(item)

    return history, total_count


async def _resolve_dataset_version_ref(
    entity_id: int,
    version_ref: str,
    db: AsyncSession,
) -> tuple[int, EntityVersionHash | None]:
    """Resolve a version reference to a transaction_id and hash record."""
    from sqlalchemy import text
    from fastapi import HTTPException, status

    count_query = text("SELECT COUNT(*) FROM entities_version WHERE id = :entity_id")
    count_result = await db.execute(count_query, {"entity_id": entity_id})
    total_versions = count_result.scalar()

    if total_versions == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity has no version history")

    if version_ref.startswith("~"):
        try:
            index = int(version_ref[1:])
            if index < 0:
                index = total_versions + index
            if index < 0 or index >= total_versions:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Version index {version_ref} out of range (0-{total_versions - 1})"
                )

            index_query = text("""
                SELECT transaction_id FROM entities_version
                WHERE id = :entity_id ORDER BY transaction_id ASC OFFSET :idx LIMIT 1
            """)
            result = await db.execute(index_query, {"entity_id": entity_id, "idx": index})
            transaction_id = result.scalar()

            hash_stmt = (
                select(EntityVersionHash)
                .where(EntityVersionHash.entity_id == entity_id)
                .where(EntityVersionHash.transaction_id == transaction_id)
                .options(selectinload(EntityVersionHash.tags))
            )
            hash_result = await db.execute(hash_stmt)
            return transaction_id, hash_result.scalar_one_or_none()
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid version index: {version_ref}")

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version hash '{version_ref}' not found")
        return hash_record.transaction_id, hash_record

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version tag '{version_ref}' not found")
    return tag.version_hash.transaction_id, tag.version_hash


@router.get(
    "/datasets/{collection_name}/{dataset_name}/history",
    response_model=VersionHistoryResponse,
    summary="Get Dataset Version History",
    tags=["Datasets", "Versions"],
    operation_id="get_dataset_version_history",
)
async def get_dataset_version_history(
    collection_name: str,
    dataset_name: str,
    skip: int = Query(0, ge=0, description="Number of versions to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max versions to return"),
    include_changeset: bool = Query(False, description="Include field changes in response"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """Get the version history for a dataset."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    history, total_count = await _get_dataset_version_history(
        dataset.id, db, skip, limit, include_changeset
    )

    return VersionHistoryResponse(
        entity_name=dataset.name,
        entity_type="dataset",
        collection_name=collection_name,
        total_versions=total_count,
        versions=[VersionHistoryItem(**item) for item in history],
    )


@router.get(
    "/datasets/{collection_name}/{dataset_name}/versions/{version_ref}",
    response_model=VersionDetailResponse,
    summary="Get Dataset at Specific Version",
    tags=["Datasets", "Versions"],
    operation_id="get_dataset_version",
)
async def get_dataset_version(
    collection_name: str,
    dataset_name: str,
    version_ref: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """Get the full dataset data at a specific version."""
    from sqlalchemy import text

    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    transaction_id, hash_record = await _resolve_dataset_version_ref(dataset.id, version_ref, db)

    version_query = text("""
        SELECT
            ev.transaction_id,
            ev.operation_type,
            ev.name,
            ev.entity_type,
            ev.is_private,
            ev.croissant_metadata,
            dv.data_path,
            dv.format,
            dv.metadata_version,
            dv.dataset_metadata,
            dv.long_description
        FROM entities_version ev
        JOIN datasets_version dv ON ev.id = dv.id AND ev.transaction_id = dv.transaction_id
        WHERE ev.id = :entity_id AND ev.transaction_id = :transaction_id
    """)
    result = await db.execute(version_query, {"entity_id": dataset.id, "transaction_id": transaction_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Version data not found for transaction {transaction_id}")

    row_dict = row._mapping

    count_query = text("""
        SELECT COUNT(*) FROM entities_version
        WHERE id = :entity_id AND transaction_id <= :transaction_id
    """)
    count_result = await db.execute(count_query, {"entity_id": dataset.id, "transaction_id": transaction_id})
    version_index = count_result.scalar() - 1

    data = {
        "name": row_dict.get("name"),
        "entity_type": row_dict.get("entity_type"),
        "is_private": row_dict.get("is_private"),
        "croissant_metadata": row_dict.get("croissant_metadata"),
        "data_path": row_dict.get("data_path"),
        "format": row_dict.get("format"),
        "metadata_version": row_dict.get("metadata_version"),
        "dataset_metadata": row_dict.get("dataset_metadata"),
        "long_description": row_dict.get("long_description"),
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
