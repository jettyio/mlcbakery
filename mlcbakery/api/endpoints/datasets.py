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
from typing import Set
import os
import typesense
import tempfile

from mlcbakery.models import Dataset, Collection, Activity, Entity
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
from mlcbakery.api.dependencies import verify_admin_token
from mlcbakery.search import get_typesense_client, TYPESENSE_COLLECTION_NAME
from mlcbakery.croissant_validation import (
    validate_json,
    validate_croissant,
    validate_records,
    generate_validation_report,
    ValidationResult as CroissantValidationResult,  # Alias to avoid potential name conflicts
)

# Create a "created" activity for the dataset
# from mlcbakery.schemas.activity import ActivityCreate
# from mlcbakery.api.endpoints.activities import create_activity
from mlcbakery.models import Agent

router = APIRouter()


@router.get("/datasets/search")
async def search_datasets(
    q: str = Query(..., min_length=1, description="Search query term"),
    limit: int = Query(
        default=30, ge=1, le=100, description="Number of results to return"
    ),
    ts: typesense.Client = Depends(get_typesense_client),
):
    """Search datasets using Typesense based on query term."""
    search_parameters = {
        "q": q,
        "query_by": "long_description, metadata, collection_name, dataset_name, full_name",
        "per_page": limit,
        "include_fields": "collection_name, dataset_name, full_name",
    }

    try:
        search_results = ts.collections[TYPESENSE_COLLECTION_NAME].documents.search(
            search_parameters
        )
        return {"hits": search_results["hits"]}
    except typesense.exceptions.ObjectNotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Typesense collection '{TYPESENSE_COLLECTION_NAME}' not found. Please build the index first.",
        )
    except typesense.exceptions.TypesenseClientError as e:
        print(f"Typesense API error: {e}")
        raise HTTPException(status_code=500, detail=f"Typesense search failed: {e}")
    except Exception as e:
        print(f"Unexpected error during Typesense search: {e}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred during search"
        )


@router.post("/datasets/", response_model=DatasetResponse)
async def create_dataset(
    dataset: DatasetCreate,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """Create a new dataset (async)."""
    if dataset.collection_id:
        stmt_coll = select(Collection).where(Collection.id == dataset.collection_id)
        result_coll = await db.execute(stmt_coll)
        if not result_coll.scalar_one_or_none():
            raise HTTPException(
                status_code=404,
                detail=f"Collection with id {dataset.collection_id} not found",
            )
    else:
        raise HTTPException(status_code=400, detail="Collection ID is required")

    stmt_check = (
        select(Dataset)
        .where(Dataset.name == dataset.name)
        .where(Dataset.collection_id == dataset.collection_id)
    )
    result_check = await db.execute(stmt_check)
    if result_check.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Dataset already exists")

    db_dataset = Dataset(**dataset.model_dump())
    db.add(db_dataset)
    await db.commit()
    await db.flush([db_dataset])
    # new_dataset_id = db_dataset.id
    

    
    # # Fetch the collection for this dataset
    # stmt_coll = select(Collection).where(Collection.id == dataset.collection_id)
    # result_coll = await db.execute(stmt_coll)
    # collection = result_coll.scalar_one_or_none()
    
    # # Find the default agent for this collection
    # agent_name = f"{collection.name} Owner"
    # stmt_agent = select(Agent).where(Agent.name == agent_name).where(Agent.collection_id == collection.id)
    # result_agent = await db.execute(stmt_agent)
    # default_agent = result_agent.scalar_one_or_none()

    # TODO: Add activity creation back in
    # activity_data = ActivityCreate(
    #     name="created",
    #     output_entity_id=new_dataset_id,
    #     input_entity_ids=dataset.input_entity_ids,
    #     agent_ids=[default_agent.id] if default_agent else []
    # )
    #
    # await create_activity(activity=activity_data, db=db)

    # stmt_refresh = (
    #     select(Dataset)
    #     .where(Dataset.id == new_dataset_id)
    #     .options(
    #         selectinload(Dataset.collection),
    #         selectinload(Dataset.input_activities).options(
    #             selectinload(Activity.input_entities).options(
    #                 selectinload(Entity.collection)
    #             ),
    #             selectinload(Activity.output_entity).options(
    #                 selectinload(Entity.collection)
    #             ),
    #             selectinload(Activity.agents),
    #         ),
    #         selectinload(Dataset.output_activities).options(
    #             selectinload(Activity.input_entities).options(
    #                 selectinload(Entity.collection)
    #             ),
    #             selectinload(Activity.agents),
    #         ),
    #     )
    # )
    # result_refresh = await db.execute(stmt_refresh)
    # refreshed_dataset = result_refresh.scalars().unique().one_or_none()

    # if not refreshed_dataset:
    #     raise HTTPException(
    #         status_code=500, detail="Failed to reload dataset after creation"
    #     )

    
    return db_dataset


@router.get("/datasets/", response_model=list[DatasetListResponse])
async def list_datasets(
    skip: int = Query(default=0, description="Number of records to skip"),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a list of datasets with pagination (async)."""
    if skip < 0 or limit < 0:
        raise HTTPException(
            status_code=400, detail="Offset and limit must be non-negative"
        )
    stmt = (
        select(Dataset)
        .where(Dataset.entity_type == "dataset")
        .options(
            selectinload(Dataset.collection),
            
        )
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
        .where(Dataset.entity_type == "dataset")
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

@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int,
    dataset_update: DatasetUpdate,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """Update a dataset (async)."""
    stmt_get = (
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .where(Dataset.entity_type == "dataset")
    )
    result_get = await db.execute(stmt_get)
    db_dataset = result_get.scalar_one_or_none()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    update_data = dataset_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_dataset, field, value)

    db.add(db_dataset)
    await db.commit()

    
    result_refresh = await db.execute(await _refresh_dataset(db_dataset))
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()

    if not refreshed_dataset:
        raise HTTPException(
            status_code=500, detail="Failed to reload dataset after update"
        )

    return refreshed_dataset


@router.delete("/datasets/{dataset_id}", status_code=200)
async def delete_dataset(
    dataset_id: int,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """Delete a dataset (async)."""
    stmt = (
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .where(Dataset.entity_type == "dataset")
    )
    result = await db.execute(stmt)
    db_dataset = result.scalar_one_or_none()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await db.delete(db_dataset)
    await db.commit()
    return {"message": "Dataset deleted successfully"}


@router.patch("/datasets/{dataset_id}/metadata", response_model=DatasetResponse)
async def update_dataset_metadata(
    dataset_id: int,
    metadata: dict,
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """Update just the metadata of a dataset (async)."""
    stmt_get = (
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .where(Dataset.entity_type == "dataset")
    )
    result_get = await db.execute(stmt_get)
    db_dataset = result_get.scalar_one_or_none()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    db_dataset.dataset_metadata = metadata
    db.add(db_dataset)
    await db.commit()

   
    result_refresh = await db.execute(await _refresh_dataset(db_dataset))
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()

    if not refreshed_dataset:
        raise HTTPException(
            status_code=500, detail="Failed to reload dataset after metadata update"
        )

    return refreshed_dataset


@router.put("/datasets/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def update_dataset_preview(
    dataset_id: int,
    preview_update: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
    _: HTTPAuthorizationCredentials = Depends(verify_admin_token),
):
    """Update a dataset's preview (async) using file upload."""
    stmt_get = (
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .where(Dataset.entity_type == "dataset")
    )
    result_get = await db.execute(stmt_get)
    db_dataset = result_get.scalar_one_or_none()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    preview_data: bytes = await preview_update.read()

    if not preview_data:
        db_dataset.preview = None
        db_dataset.preview_type = None
    else:
        db_dataset.preview = preview_data
        db_dataset.preview_type = preview_update.content_type

    db.add(db_dataset)
    await db.commit()

    result_refresh = await db.execute(await _refresh_dataset(db_dataset))
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()

    if not refreshed_dataset:
        raise HTTPException(
            status_code=500, detail="Failed to reload dataset after preview update"
        )

    return refreshed_dataset


@router.get("/datasets/{collection_name}/{dataset_name}/preview")
async def get_dataset_preview(
    collection_name: str, dataset_name: str, db: AsyncSession = Depends(get_async_db)
):
    """Get a dataset's preview (async)."""
    dataset = await _find_dataset_by_name(collection_name, dataset_name, db)
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
    ),
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
    stmt = (
        select(Dataset)
        .join(Collection, Dataset.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .where(Dataset.name == dataset_name)
        .where(Dataset.entity_type == "dataset")
        .options(
            selectinload(Dataset.collection),
        )
    )
    result = await db.execute(stmt)
    dataset = result.scalars().unique().one_or_none()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.dataset_metadata:
        raise HTTPException(status_code=404, detail="Dataset has no Croissant metadata")

    return dataset.dataset_metadata
