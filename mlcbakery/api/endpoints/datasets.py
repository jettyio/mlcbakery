from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Response
from sqlalchemy.orm import Session
from typing import Annotated, List

from mlcbakery.models import Dataset, Collection, Activity, Entity
from mlcbakery.schemas.dataset import (
    DatasetCreate,
    DatasetUpdate,
    DatasetResponse,
    DatasetPreviewResponse,
    UpstreamEntityNode,
)
from mlcbakery.database import get_db

router = APIRouter()


@router.post("/datasets/", response_model=DatasetResponse)
async def create_dataset(dataset: DatasetCreate, db: Session = Depends(get_db)):
    """Create a new dataset."""
    db_dataset = Dataset(**dataset.model_dump())
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


@router.get("/datasets/", response_model=list[DatasetResponse])
async def list_datasets(
    skip: int = Query(default=0, description="Number of records to skip"),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
):
    """Get a list of datasets with pagination."""

    datasets = db.query(Dataset).offset(skip).limit(limit).all()
    return datasets


@router.get("/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """Get a specific dataset by ID."""
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.put("/datasets/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: int, dataset_update: DatasetUpdate, db: Session = Depends(get_db)
):
    """Update a dataset."""
    db_dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Update only provided fields
    update_data = dataset_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_dataset, field, value)

    db.commit()
    db.refresh(db_dataset)
    return db_dataset


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """Delete a dataset."""
    db_dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    db.delete(db_dataset)
    db.commit()
    return {"message": "Dataset deleted successfully"}


@router.patch("/datasets/{dataset_id}/metadata", response_model=DatasetResponse)
async def update_dataset_metadata(
    dataset_id: int, metadata: dict, db: Session = Depends(get_db)
):
    """Update just the metadata of a dataset."""
    db_dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    db_dataset.dataset_metadata = metadata
    db.commit()
    db.refresh(db_dataset)
    return db_dataset


@router.put("/datasets/{dataset_id}/preview", response_model=DatasetPreviewResponse)
async def update_dataset_preview(
    dataset_id: int,
    preview: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Update a dataset's preview."""
    db_dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Read the file content
    preview_data = await preview.read()

    # Update the dataset
    db_dataset.preview = preview_data
    db_dataset.preview_type = preview.content_type

    db.commit()
    db.refresh(db_dataset)
    return db_dataset


@router.get("/datasets/{dataset_id}/preview")
async def get_dataset_preview(dataset_id: int, db: Session = Depends(get_db)):
    """Get a dataset's preview."""
    db_dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not db_dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not db_dataset.preview or not db_dataset.preview_type:
        raise HTTPException(status_code=404, detail="Dataset has no preview")

    return Response(
        content=db_dataset.preview,
        media_type=db_dataset.preview_type,
    )


@router.get(
    "/datasets/{collection_name}/{dataset_name}", response_model=DatasetResponse
)
async def get_dataset_by_name(
    collection_name: str,
    dataset_name: str,
    db: Session = Depends(get_db),
):
    """Get a specific dataset by collection name and dataset name."""
    dataset = (
        db.query(Dataset)
        .join(Collection)
        .filter(Collection.name == collection_name)
        .filter(Dataset.name == dataset_name)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.get(
    "/datasets/{collection_name}/{dataset_name}/upstream",
    response_model=UpstreamEntityNode,
)
async def get_dataset_upstream_tree(
    collection_name: str,
    dataset_name: str,
    db: Session = Depends(get_db),
) -> UpstreamEntityNode:
    """Get the upstream entity tree for a dataset, showing all entities that contributed to its creation."""
    # Get the dataset by collection name and dataset name
    dataset = (
        db.query(Dataset)
        .join(Collection)
        .filter(Collection.name == collection_name)
        .filter(Dataset.name == dataset_name)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    def build_upstream_tree(entity: Entity, visited: set = None) -> UpstreamEntityNode:
        if visited is None:
            visited = set()

        # Create the node for the current entity
        node = UpstreamEntityNode(
            id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
        )

        # Get activity information from output_activities (the activity that created this entity)
        if entity.output_activities:
            activity = entity.output_activities[0]  # Get the most recent activity
            node.activity_id = activity.id
            node.activity_name = activity.name

            # Add input entities from this activity as children
            for input_entity in activity.input_entities:
                if input_entity.id not in visited:
                    visited.add(input_entity.id)
                    child_node = build_upstream_tree(input_entity, visited)
                    node.children.append(child_node)

        return node

    # Build the tree starting from the dataset
    return build_upstream_tree(dataset)
