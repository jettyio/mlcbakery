from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from typing import List
import typesense

from mlcbakery import search

from mlcbakery.schemas.trained_model import (
    TrainedModelCreate,
    TrainedModelResponse,
    TrainedModelUpdate,
    TrainedModelListResponse,
)
from mlcbakery.database import get_async_db
from mlcbakery.api.dependencies import verify_auth, optional_auth, apply_auth_to_stmt, get_auth, verify_auth_with_write_access, get_user_collection_id
from opentelemetry import trace # Import for span manipulation
from mlcbakery.models import TrainedModel, Collection, Entity, EntityRelationship, EntityVersionHash, EntityVersionTag
from mlcbakery.schemas.version import (
    VersionHistoryItem,
    VersionHistoryResponse,
    VersionDetailResponse,
)
from sqlalchemy.orm import selectinload

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


# Helper function to find a model by collection name and model name
async def _find_model_by_name(collection_name: str, model_name: str, db: AsyncSession) -> TrainedModel | None:
    stmt = (
        select(TrainedModel)
        .join(Collection, TrainedModel.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .where(func.lower(TrainedModel.name) == func.lower(model_name)) # Case-insensitive name match
        .options(
            selectinload(TrainedModel.collection),
            # Add other selectinloads if needed in the future, e.g., for relationships
            selectinload(TrainedModel.upstream_links).options(
                selectinload(EntityRelationship.source_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
            selectinload(TrainedModel.downstream_links).options(
                selectinload(EntityRelationship.target_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

# Search endpoint (kept separate as it's global)
@router.get("/models/search")
async def search_models(
    q: str = Query(..., min_length=1, description="Search query term"),
    limit: int = Query(
        default=30, ge=1, le=100, description="Number of results to return"
    ),
    ts = Depends(search.setup_and_get_typesense_client),
    auth: dict | None = Depends(optional_auth),
    db: AsyncSession = Depends(get_async_db),
):
    """Search models using Typesense based on query term, respecting privacy settings."""
    # Get the current span
    current_span = trace.get_current_span()
    # Add the search query as an attribute to the span
    current_span.set_attribute("search.query", q)

    # Get user's collection ID for privacy filtering
    user_collection_id = await get_user_collection_id(auth, db)

    # Build privacy filter
    privacy_filter = search.build_privacy_filter(user_collection_id)

    # Build base filter
    base_filter = "entity_type:trained_model"
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

# GET endpoints first

@router.get(
    "/models/",
    response_model=List[TrainedModelListResponse],
    summary="List All Trained Models",
    tags=["Trained Models"],
    operation_id="list_all_trained_models",
)
async def list_trained_models(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """List all trained models accessible to the user."""
    # Admin users can see all models, regular users only see their own
    stmt = (
        select(TrainedModel)
        .join(Collection, TrainedModel.collection_id == Collection.id)
        .options(selectinload(TrainedModel.collection))
        .offset(skip)
        .limit(limit)
        .order_by(TrainedModel.id)
    )

    stmt = apply_auth_to_stmt(stmt, auth)
    result = await db.execute(stmt)
    models = result.scalars().all()

    return [
        TrainedModelListResponse(
            id=model.id,
            name=model.name,
            model_path=model.model_path,
            collection_id=model.collection_id,
            collection_name=model.collection.name if model.collection else None,
            metadata_version=model.metadata_version,
            model_metadata=model.model_metadata,
            asset_origin=model.asset_origin,
            long_description=model.long_description,
            model_attributes=model.model_attributes,
            entity_type=model.entity_type,
        )
        for model in models
    ]


@router.get(
    "/models/{collection_name}/",
    response_model=List[TrainedModelListResponse],
    summary="List Trained Models by Collection",
    tags=["Trained Models"],
    operation_id="list_trained_models_by_collection",
)
async def list_trained_models_by_collection(
    collection_name: str,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """List all trained models in a specific collection owned by the user."""
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
    
    # Get models in the collection
    stmt = (
        select(TrainedModel)
        .join(Collection, TrainedModel.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .options(selectinload(TrainedModel.collection))
        .offset(skip)
        .limit(limit)
        .order_by(TrainedModel.id)
    )
    stmt = apply_auth_to_stmt(stmt, auth)
    result = await db.execute(stmt)
    models = result.scalars().all()

    return [
        TrainedModelListResponse(
            id=model.id,
            name=model.name,
            model_path=model.model_path,
            collection_id=model.collection_id,
            collection_name=model.collection.name if model.collection else None,
            metadata_version=model.metadata_version,
            model_metadata=model.model_metadata,
            asset_origin=model.asset_origin,
            long_description=model.long_description,
            model_attributes=model.model_attributes,
            entity_type=model.entity_type,
        )
        for model in models
    ]


@router.get(
    "/models/{collection_name}/{model_name}", 
    response_model=TrainedModelResponse,
    summary="Get a Trained Model by Collection and Model Name",
    tags=["Trained Models"],
    operation_id="get_trained_model_by_name",
)
async def get_trained_model_by_name(
    collection_name: str, 
    model_name: str, 
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """
    Get a specific trained model by its collection name and model name.

    - **collection_name**: Name of the collection the model belongs to.
    - **model_name**: Name of the model.
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

    db_trained_model = await _find_model_by_name(collection_name, model_name, db)
    if not db_trained_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trained model '{model_name}' in collection '{collection_name}' not found"
        )

    # Get updated_at from latest version transaction
    updated_at = await _get_entity_updated_at(db_trained_model.id, db)

    return TrainedModelResponse(
        id=db_trained_model.id,
        name=db_trained_model.name,
        model_path=db_trained_model.model_path,
        collection_id=db_trained_model.collection_id,
        metadata_version=db_trained_model.metadata_version,
        model_metadata=db_trained_model.model_metadata,
        asset_origin=db_trained_model.asset_origin,
        long_description=db_trained_model.long_description,
        model_attributes=db_trained_model.model_attributes,
        is_private=db_trained_model.is_private,
        croissant_metadata=db_trained_model.croissant_metadata,
        created_at=db_trained_model.created_at,
        updated_at=updated_at,
    )

# POST endpoints

@router.post(
    "/models/{collection_name}",
    response_model=TrainedModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new Trained Model by Collection Name",
    tags=["Trained Models"],
    operation_id="create_trained_model_by_name",
)
async def create_trained_model_by_name(
    collection_name: str,
    trained_model_in: TrainedModelCreate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Create a new trained model in the database using collection name.

    - **collection_name**: Name of the collection this model belongs to (from URL path).
    - **name**: Name of the model (required)
    - **model_path**: Path to the model artifact (required)
    - **metadata_version**: Optional version string for the metadata.
    - **model_metadata**: Optional dictionary for arbitrary model metadata.
    - **asset_origin**: Optional string indicating the origin of the model asset (e.g., S3 URI).
    - **long_description**: Optional detailed description of the model.
    - **model_attributes**: Optional dictionary for specific model attributes (e.g., input shape, output classes).
    """
    # Find collection by name and verify access
    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )

    # Check if model with the same name already exists in the collection (case-insensitive)
    stmt_check = (
        select(TrainedModel)
        .where(func.lower(Entity.name) == func.lower(trained_model_in.name))
        .where(Entity.collection_id == collection.id)
    )
    result_check = await db.execute(stmt_check)
    if result_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Trained model with name '{trained_model_in.name}' already exists in collection '{collection.name}'"
        )
    
    # Prepare model data for creation, explicitly setting collection_id
    model_data_for_db = trained_model_in.model_dump(exclude={"collection_name"})
    model_data_for_db["collection_id"] = collection.id

    db_trained_model = TrainedModel(**model_data_for_db)
    db.add(db_trained_model)
    await db.commit()
    await db.refresh(db_trained_model)

    # Index to Typesense for immediate search availability
    try:
        # Refresh to ensure collection relationship is loaded
        from sqlalchemy.orm import selectinload as sl
        stmt_refresh = select(TrainedModel).where(TrainedModel.id == db_trained_model.id).options(sl(TrainedModel.collection))
        result_refresh = await db.execute(stmt_refresh)
        refreshed_model = result_refresh.scalar_one_or_none()
        if refreshed_model:
            await search.index_entity_to_typesense(refreshed_model)
    except Exception as e:
        print(f"Warning: Failed to index model to Typesense: {e}")

    return db_trained_model

# PUT endpoints

@router.put(
    "/models/{collection_name}/{model_name}",
    response_model=TrainedModelResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a Trained Model by Collection and Model Name",
    tags=["Trained Models"],
    operation_id="update_trained_model_by_name",
)
async def update_trained_model_by_name(
    collection_name: str,
    model_name: str,
    trained_model_in: TrainedModelUpdate,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Update an existing trained model by its collection name and model name.

    - **collection_name**: Name of the collection the model belongs to.
    - **model_name**: Name of the model to update.
    - **name**: New name for the model (optional).
    - **model_path**: Path to the model artifact (optional).
    - **metadata_version**: Optional version string for the metadata.
    - **model_metadata**: Optional dictionary for arbitrary model metadata.
    - **asset_origin**: Optional string indicating the origin of the model asset.
    - **long_description**: Optional detailed description of the model.
    - **model_attributes**: Optional dictionary for specific model attributes.
    
    Note: The model name can be updated, but it cannot duplicate an existing model name in the same collection.
    """
    db_trained_model = await _find_model_by_name(collection_name, model_name, db)
    if not db_trained_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trained model '{model_name}' in collection '{collection_name}' not found"
        )

    # If updating name, check for duplicates (case-insensitive)
    update_data = trained_model_in.model_dump(exclude_unset=True)
    if "name" in update_data and update_data["name"].lower() != db_trained_model.name.lower():
        stmt_check = (
            select(TrainedModel)
            .where(func.lower(Entity.name) == func.lower(update_data["name"]))
            .where(Entity.collection_id == db_trained_model.collection_id)
            .where(TrainedModel.id != db_trained_model.id)  # Exclude current model
        )
        result_check = await db.execute(stmt_check)
        if result_check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Trained model with name '{update_data['name']}' already exists in collection '{collection_name}'"
            )

    for field, value in update_data.items():
        setattr(db_trained_model, field, value)

    await db.commit()
    await db.refresh(db_trained_model)

    # Re-index to Typesense with updated fields (especially privacy settings)
    try:
        await search.index_entity_to_typesense(db_trained_model)
    except Exception as e:
        print(f"Warning: Failed to re-index model to Typesense: {e}")

    return db_trained_model

# DELETE endpoints

@router.delete(
    "/models/{collection_name}/{model_name}",
    status_code=status.HTTP_200_OK,
    summary="Delete a Trained Model by Collection and Model Name",
    tags=["Trained Models"],
    operation_id="delete_trained_model_by_name",
)
async def delete_trained_model_by_name(
    collection_name: str,
    model_name: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth_with_write_access),
):
    """
    Delete a trained model by its collection name and model name.

    - **collection_name**: Name of the collection the model belongs to.
    - **model_name**: Name of the model to delete.
    """
    trained_model = await _find_model_by_name(collection_name, model_name, db)
    if not trained_model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trained model not found"
        )

    from mlcbakery.utils import delete_entity_with_versions
    await delete_entity_with_versions(trained_model, db)
    await db.commit()
    return {"message": "Trained model deleted successfully"}


# --------------------------------------------
# Version History Endpoints
# --------------------------------------------

async def _get_model_version_history(
    entity_id: int,
    db: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    include_changeset: bool = False,
) -> tuple[list[dict], int]:
    """Get version history for a trained model."""
    from sqlalchemy import text

    hash_stmt = (
        select(EntityVersionHash)
        .where(EntityVersionHash.entity_id == entity_id)
        .options(selectinload(EntityVersionHash.tags))
        .order_by(EntityVersionHash.transaction_id.desc())
    )
    hash_result = await db.execute(hash_stmt)
    hash_records = {h.transaction_id: h for h in hash_result.scalars().all()}

    version_query = text("""
        SELECT
            ev.transaction_id,
            ev.end_transaction_id,
            ev.operation_type,
            ev.name,
            ev.entity_type,
            ev.is_private,
            ev.croissant_metadata,
            mv.model_path,
            mv.metadata_version,
            mv.model_metadata,
            mv.long_description,
            mv.model_attributes,
            t.issued_at
        FROM entities_version ev
        JOIN trained_models_version mv ON ev.id = mv.id AND ev.transaction_id = mv.transaction_id
        LEFT JOIN transaction t ON ev.transaction_id = t.id
        WHERE ev.id = :entity_id
        ORDER BY ev.transaction_id DESC
        OFFSET :skip
        LIMIT :limit
    """)

    result = await db.execute(version_query, {"entity_id": entity_id, "skip": skip, "limit": limit})
    rows = result.fetchall()

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
            for key in ["name", "model_path", "metadata_version", "long_description", "is_private"]:
                if key in row_dict and row_dict[key] is not None:
                    changeset[key] = row_dict[key]
            item["changeset"] = changeset

        history.append(item)

    return history, total_count


async def _resolve_model_version_ref(
    entity_id: int,
    version_ref: str,
    db: AsyncSession,
) -> tuple[int, EntityVersionHash | None]:
    """Resolve a version reference to a transaction_id and hash record."""
    from sqlalchemy import text

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
    "/models/{collection_name}/{model_name}/history",
    response_model=VersionHistoryResponse,
    summary="Get Trained Model Version History",
    tags=["Trained Models", "Versions"],
    operation_id="get_trained_model_version_history",
)
async def get_trained_model_version_history(
    collection_name: str,
    model_name: str,
    skip: int = Query(0, ge=0, description="Number of versions to skip"),
    limit: int = Query(50, ge=1, le=100, description="Max versions to return"),
    include_changeset: bool = Query(False, description="Include field changes in response"),
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """Get the version history for a trained model."""
    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )

    model = await _find_model_by_name(collection_name, model_name, db)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trained model '{model_name}' in collection '{collection_name}' not found",
        )

    history, total_count = await _get_model_version_history(
        model.id, db, skip, limit, include_changeset
    )

    return VersionHistoryResponse(
        entity_name=model.name,
        entity_type="trained_model",
        collection_name=collection_name,
        total_versions=total_count,
        versions=[VersionHistoryItem(**item) for item in history],
    )


@router.get(
    "/models/{collection_name}/{model_name}/versions/{version_ref}",
    response_model=VersionDetailResponse,
    summary="Get Trained Model at Specific Version",
    tags=["Trained Models", "Versions"],
    operation_id="get_trained_model_version",
)
async def get_trained_model_version(
    collection_name: str,
    model_name: str,
    version_ref: str,
    db: AsyncSession = Depends(get_async_db),
    auth = Depends(verify_auth),
):
    """Get the full trained model data at a specific version."""
    from sqlalchemy import text

    stmt_collection = select(Collection).where(Collection.name == collection_name)
    stmt_collection = apply_auth_to_stmt(stmt_collection, auth)
    result_collection = await db.execute(stmt_collection)
    collection = result_collection.scalar_one_or_none()

    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collection with name '{collection_name}' not found",
        )

    model = await _find_model_by_name(collection_name, model_name, db)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trained model '{model_name}' in collection '{collection_name}' not found",
        )

    transaction_id, hash_record = await _resolve_model_version_ref(model.id, version_ref, db)

    version_query = text("""
        SELECT
            ev.transaction_id,
            ev.operation_type,
            ev.name,
            ev.entity_type,
            ev.is_private,
            ev.croissant_metadata,
            mv.model_path,
            mv.metadata_version,
            mv.model_metadata,
            mv.long_description,
            mv.model_attributes
        FROM entities_version ev
        JOIN trained_models_version mv ON ev.id = mv.id AND ev.transaction_id = mv.transaction_id
        WHERE ev.id = :entity_id AND ev.transaction_id = :transaction_id
    """)
    result = await db.execute(version_query, {"entity_id": model.id, "transaction_id": transaction_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Version data not found for transaction {transaction_id}")

    row_dict = row._mapping

    count_query = text("""
        SELECT COUNT(*) FROM entities_version
        WHERE id = :entity_id AND transaction_id <= :transaction_id
    """)
    count_result = await db.execute(count_query, {"entity_id": model.id, "transaction_id": transaction_id})
    version_index = count_result.scalar() - 1

    data = {
        "name": row_dict.get("name"),
        "entity_type": row_dict.get("entity_type"),
        "is_private": row_dict.get("is_private"),
        "croissant_metadata": row_dict.get("croissant_metadata"),
        "model_path": row_dict.get("model_path"),
        "metadata_version": row_dict.get("metadata_version"),
        "model_metadata": row_dict.get("model_metadata"),
        "long_description": row_dict.get("long_description"),
        "model_attributes": row_dict.get("model_attributes"),
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
