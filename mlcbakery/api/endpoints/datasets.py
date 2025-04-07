from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    File,
    UploadFile,
    Response,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, contains_eager, joinedload
from typing import Annotated, List, Set

from mlcbakery.models import Dataset, Collection, Activity, Entity
from mlcbakery.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DatasetPreviewResponse,
    UpstreamEntityNode,
)
from mlcbakery.database import get_async_db

router = APIRouter()


@router.post("/datasets/", response_model=DatasetResponse)
async def create_dataset(dataset: DatasetCreate, db: AsyncSession = Depends(get_async_db)):
    """Create a new dataset (async)."""
    # Check if collection_id exists if provided
    if dataset.collection_id:
        stmt_coll = select(Collection).where(Collection.id == dataset.collection_id)
        result_coll = await db.execute(stmt_coll)
        if not result_coll.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Collection with id {dataset.collection_id} not found")

    db_dataset = Dataset(**dataset.model_dump())
    db.add(db_dataset)
    await db.commit()
    # Need the ID after commit before re-fetching
    await db.flush([db_dataset]) # Ensure ID is available
    new_dataset_id = db_dataset.id 
    # No need for db.refresh, re-fetch with eager loading

    # Re-fetch the created dataset with all required relationships eager loaded for the response
    stmt_refresh = (
        select(Dataset)
        .where(Dataset.id == new_dataset_id) # Use the ID obtained after commit/flush
        .options(
            selectinload(Dataset.collection),
            selectinload(Dataset.input_activities).options( # Load activities where this dataset is an input
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(Dataset.output_activities).options( # Load the activity that *created* this dataset
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            )
        )
    )
    result_refresh = await db.execute(stmt_refresh)
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()
    
    if not refreshed_dataset:
         # Should not happen ideally after a successful insert and commit
         raise HTTPException(status_code=500, detail="Failed to reload dataset after creation")

    return refreshed_dataset


@router.get("/datasets/", response_model=list[DatasetResponse])
async def list_datasets(
    skip: int = Query(default=0, description="Number of records to skip"),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    db: AsyncSession = Depends(get_async_db),
):
    """Get a list of datasets with pagination (async)."""
    stmt = (
        select(Dataset)
        .where(Dataset.entity_type == 'dataset')
        .options(
            # Load the Dataset's immediate relationships
            selectinload(Dataset.collection),
            selectinload(Dataset.input_activities).options( # Load activities where this dataset is an input
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)), # Eager load entities within those activities
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(Dataset.output_activities).options( # Load the activity that *created* this dataset
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)), # Eager load inputs to the creation activity
                # Output entity of output_activity is the dataset itself, no need to load recursively here
                selectinload(Activity.agents)
            )
        )
        .offset(skip)
        .limit(limit)
        .order_by(Dataset.id) # Add consistent ordering
    )
    result = await db.execute(stmt)
    # Use unique() because options loading can cause duplicate parent rows
    datasets = result.scalars().unique().all()
    return datasets


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: int, db: AsyncSession = Depends(get_async_db)):
    """Get a specific dataset by ID (async)."""
    stmt = (
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .where(Dataset.entity_type == 'dataset')
        .options(
            selectinload(Dataset.collection),
            selectinload(Dataset.input_activities).options(
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(Dataset.output_activities).options(
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            )
        )
    )
    result = await db.execute(stmt)
    dataset = result.scalars().unique().one_or_none() # Use unique().one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int, dataset_update: DatasetUpdate, db: AsyncSession = Depends(get_async_db)
):
    """Update a dataset (async)."""
    # Fetch the dataset first to ensure it exists
    stmt_get = select(Dataset).where(Dataset.id == dataset_id).where(Dataset.entity_type == 'dataset')
    result_get = await db.execute(stmt_get)
    db_dataset = result_get.scalar_one_or_none()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Update only provided fields
    update_data = dataset_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_dataset, field, value)

    db.add(db_dataset)
    await db.commit()
    # We don't need db.refresh(db_dataset) because we will re-fetch with eager loading

    # Fetch the updated dataset with all required relationships eager loaded
    stmt_refresh = (
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .options(
            selectinload(Dataset.collection),
            selectinload(Dataset.input_activities).options( # Load activities where this dataset is an input
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(Dataset.output_activities).options( # Load the activity that *created* this dataset
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            )
        )
    )
    result_refresh = await db.execute(stmt_refresh)
    # Use unique().one_or_none() as ID should guarantee uniqueness here
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()
    
    # This check shouldn't fail if the update succeeded, but good practice
    if not refreshed_dataset:
         raise HTTPException(status_code=500, detail="Failed to reload dataset after update")
         
    return refreshed_dataset


@router.delete("/datasets/{dataset_id}", status_code=200)
async def delete_dataset(dataset_id: int, db: AsyncSession = Depends(get_async_db)):
    """Delete a dataset (async)."""
    stmt = select(Dataset).where(Dataset.id == dataset_id).where(Dataset.entity_type == 'dataset')
    result = await db.execute(stmt)
    db_dataset = result.scalar_one_or_none()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await db.delete(db_dataset)
    await db.commit()
    return {"message": "Dataset deleted successfully"}


@router.patch("/datasets/{dataset_id}/metadata", response_model=DatasetResponse)
async def update_dataset_metadata(
    dataset_id: int, metadata: dict, db: AsyncSession = Depends(get_async_db)
):
    """Update just the metadata of a dataset (async)."""
    # Fetch the dataset first to ensure it exists
    stmt_get = select(Dataset).where(Dataset.id == dataset_id).where(Dataset.entity_type == 'dataset')
    result_get = await db.execute(stmt_get)
    db_dataset = result_get.scalar_one_or_none()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    db_dataset.dataset_metadata = metadata
    db.add(db_dataset)
    await db.commit()
    # No need for db.refresh, re-fetch with eager loading

    # Re-fetch the updated dataset with all required relationships eager loaded
    stmt_refresh = (
        select(Dataset)
        .where(Dataset.id == dataset_id)
        .options(
            selectinload(Dataset.collection),
            selectinload(Dataset.input_activities).options( # Load activities where this dataset is an input
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(Dataset.output_activities).options( # Load the activity that *created* this dataset
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            )
        )
    )
    result_refresh = await db.execute(stmt_refresh)
    refreshed_dataset = result_refresh.scalars().unique().one_or_none()

    if not refreshed_dataset:
         raise HTTPException(status_code=500, detail="Failed to reload dataset after metadata update")

    return refreshed_dataset


@router.put("/datasets/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def update_dataset_preview(
    dataset_id: int,
    preview: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db),
):
    """Update a dataset's preview (async)."""
    stmt_get = select(Dataset).where(Dataset.id == dataset_id).where(Dataset.entity_type == 'dataset')
    result_get = await db.execute(stmt_get)
    db_dataset = result_get.scalar_one_or_none()

    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Read the file content
    preview_data = await preview.read()

    # Update the dataset
    db_dataset.preview = preview_data
    db_dataset.preview_type = preview.content_type

    db.add(db_dataset)
    await db.commit()
    await db.refresh(db_dataset)
    # Don't need to eager load collection here as preview response doesn't need it
    return db_dataset


@router.get("/datasets/{dataset_id}/preview")
async def get_dataset_preview(dataset_id: int, db: AsyncSession = Depends(get_async_db)):
    """Get a dataset's preview (async)."""
    stmt = select(Dataset.preview, Dataset.preview_type).where(Dataset.id == dataset_id).where(Dataset.entity_type == 'dataset')
    result = await db.execute(stmt)
    preview_data = result.one_or_none()

    if not preview_data or not preview_data.preview or not preview_data.preview_type:
        raise HTTPException(status_code=404, detail="Dataset preview not found or incomplete")

    return Response(
        content=preview_data.preview,
        media_type=preview_data.preview_type,
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
    stmt = (
        select(Dataset)
        .join(Collection, Dataset.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .where(Dataset.name == dataset_name)
        .where(Dataset.entity_type == 'dataset')
        .options(
            # Add comprehensive eager loading
            selectinload(Dataset.collection),
            selectinload(Dataset.input_activities).options(
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.output_entity).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            ),
            selectinload(Dataset.output_activities).options(
                selectinload(Activity.input_entities).options(selectinload(Entity.collection)),
                selectinload(Activity.agents)
            )
        )
    )
    result = await db.execute(stmt)
    # Add .unique() before fetching the result
    dataset = result.scalars().unique().one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


# Helper function to recursively build the upstream tree asynchronously
async def build_upstream_tree_async(entity_id: int, db: AsyncSession, visited: Set[int]) -> UpstreamEntityNode:
    if entity_id in visited:
        # Avoid cycles and redundant fetches
        return None 
    visited.add(entity_id)

    # Fetch the current entity and its immediate relationships needed for the node
    stmt = select(Entity).where(Entity.id == entity_id).options(
        selectinload(Entity.collection),
        selectinload(Entity.output_activities).options( # Load the activity that produced this entity
            selectinload(Activity.input_entities).options( # Load the inputs to that activity
                 selectinload(Entity.collection) # And their collections
            )
        )
    )
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()

    if not entity:
        return None # Should not happen if called from a valid starting entity

    # Create the node for the current entity
    node = UpstreamEntityNode(
        id=entity.id,
        name=entity.name,
        collection_name=entity.collection.name if entity.collection else "N/A",
        entity_type=entity.entity_type,
        children=[] # Initialize children list
    )

    # Get activity information from output_activities
    if entity.output_activities:
        # Assuming one activity creates an entity for simplicity here
        activity = entity.output_activities[0]
        node.activity_id = activity.id
        node.activity_name = activity.name

        # Recursively build for input entities of this activity
        for input_entity in activity.input_entities:
            child_node = await build_upstream_tree_async(input_entity.id, db, visited)
            if child_node:
                node.children.append(child_node)

    return node


@router.get(
    "/datasets/{collection_name}/{dataset_name}/upstream",
    response_model=UpstreamEntityNode,
)
async def get_dataset_upstream_tree(
    collection_name: str,
    dataset_name: str,
    db: AsyncSession = Depends(get_async_db),
) -> UpstreamEntityNode:
    """Get the upstream entity tree for a dataset (async)."""
    # Get the starting dataset ID
    stmt_start = (
        select(Dataset.id)
        .join(Collection, Dataset.collection_id == Collection.id)
        .where(Collection.name == collection_name)
        .where(Dataset.name == dataset_name)
        .where(Dataset.entity_type == 'dataset')
    )
    result_start = await db.execute(stmt_start)
    dataset_id = result_start.scalar_one_or_none()

    if not dataset_id:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Build the tree starting from the dataset using the async helper
    tree = await build_upstream_tree_async(dataset_id, db, set())
    if not tree: # Should theoretically not happen if dataset_id was found
         raise HTTPException(status_code=500, detail="Failed to build upstream tree")
    return tree
