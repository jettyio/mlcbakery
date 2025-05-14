from pydantic import BaseModel, Field
from typing import Optional

class EntityLinkCreateRequest(BaseModel):
    source_entity_str: Optional[str] = Field(
        default=None,
        description="Source entity identifier: {entity_type}/{collection_name}/{entity_name} or null if no source.",
        examples=["dataset/my_collection/source_data"]
    )
    target_entity_str: str = Field(
        ..., # Ellipsis means it's a required field
        description="Target entity identifier: {entity_type}/{collection_name}/{entity_name}",
        examples=["dataset/my_collection/derived_data"]
    )
    activity_name: str = Field(
        ..., # Ellipsis means it's a required field
        description="Name of the activity that links the source to the target (e.g., 'generated_from', 'processed'). Will be found or created.",
        examples=["processed_data"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "source_entity_str": "dataset/official_releases/titanic_raw_data_v1",
                    "target_entity_str": "dataset/user_experiments/titanic_cleaned_data_v1",
                    "activity_name": "data_cleaning_script_run_123"
                },
                {
                    "target_entity_str": "dataset/new_uploads/initial_sensor_data_batch_1",
                    "activity_name": "initial_ingestion"
                }
            ]
        }
    } 