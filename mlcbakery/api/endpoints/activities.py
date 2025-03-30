from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from ...database import get_db
from ...models import Activity, Dataset, TrainedModel, Agent
from ...schemas.activity import ActivityCreate, ActivityResponse

router = APIRouter()


@router.post("/activities/", response_model=ActivityResponse)
def create_activity(activity: ActivityCreate, db: Session = Depends(get_db)):
    """Create a new activity with relationships."""
    # Verify input datasets exist
    input_datasets = (
        db.query(Dataset).filter(Dataset.id.in_(activity.input_dataset_ids)).all()
    )
    if len(input_datasets) != len(activity.input_dataset_ids):
        raise HTTPException(
            status_code=404, detail="One or more input datasets not found"
        )

    # Verify output model exists if specified
    output_model = None
    if activity.output_model_id:
        output_model = (
            db.query(TrainedModel)
            .filter(TrainedModel.id == activity.output_model_id)
            .first()
        )
        if not output_model:
            raise HTTPException(status_code=404, detail="Output model not found")

    # Verify agents exist if specified
    agents = []
    if activity.agent_ids:
        agents = db.query(Agent).filter(Agent.id.in_(activity.agent_ids)).all()
        if len(agents) != len(activity.agent_ids):
            raise HTTPException(status_code=404, detail="One or more agents not found")

    # Create activity
    db_activity = Activity(name=activity.name)
    db_activity.input_datasets = input_datasets
    if output_model:
        db_activity.output_model = output_model
    if agents:
        db_activity.agents = agents

    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity


@router.get("/activities/", response_model=List[ActivityResponse])
def list_activities(
    skip: int = Query(default=0, description="Number of records to skip"),
    limit: int = Query(default=100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
):
    """List all activities with pagination."""
    activities = db.query(Activity).offset(skip).limit(limit).all()
    return activities


@router.get("/activities/{activity_id}", response_model=ActivityResponse)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    """Get a specific activity by ID."""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@router.delete("/activities/{activity_id}")
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    """Delete an activity."""
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    db.delete(activity)
    db.commit()
    return {"message": "Activity deleted successfully"}
