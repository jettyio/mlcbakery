import pytest
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import create_engine
from datetime import datetime
import datetime as dt

from mlcbakery.models import Base, Dataset, Activity, Entity

# Create test database
SQLALCHEMY_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/test_db"

engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    # Drop all tables first to ensure clean state
    Base.metadata.drop_all(bind=engine)
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create a new session
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_dataset_generation_from_another_dataset(test_db):
    """Test that a dataset can be generated from another dataset through an activity."""
    try:
        # Create source dataset
        source_dataset = Dataset(
            name="Source Dataset",
            data_path="/path/to/source/data",
            format="csv",
            entity_type="dataset",
            metadata_version="1.0",
            dataset_metadata={"description": "Original source dataset"},
        )
        test_db.add(source_dataset)
        test_db.commit()
        test_db.refresh(source_dataset)

        # Create activity that will generate the new dataset
        activity = Activity(
            name="Data Preprocessing",
            created_at=dt.datetime.now(dt.UTC),
        )
        activity.input_datasets = [source_dataset]
        test_db.add(activity)
        test_db.commit()
        test_db.refresh(activity)

        # Create derived dataset
        derived_dataset = Dataset(
            name="Preprocessed Dataset",
            data_path="/path/to/preprocessed/data",
            format="parquet",
            entity_type="dataset",
            metadata_version="1.0",
            dataset_metadata={
                "description": "Preprocessed version of source dataset",
                "source_dataset_id": source_dataset.id,
                "preprocessing_steps": ["normalization", "feature engineering"],
            },
        )
        test_db.add(derived_dataset)
        test_db.commit()
        test_db.refresh(derived_dataset)

        # Add derived dataset to the activity
        activity.input_datasets.append(derived_dataset)
        test_db.commit()
        test_db.refresh(activity)

        # Verify relationships
        assert len(activity.input_datasets) == 2
        assert source_dataset in activity.input_datasets
        assert derived_dataset in activity.input_datasets

        # Verify we can trace the dependency
        source_activities = source_dataset.activities
        assert len(source_activities) == 1
        assert source_activities[0].name == "Data Preprocessing"

        derived_activities = derived_dataset.activities
        assert len(derived_activities) == 1
        assert derived_activities[0].name == "Data Preprocessing"

        # Verify metadata captures the relationship
        assert (
            derived_dataset.dataset_metadata["source_dataset_id"] == source_dataset.id
        )
        assert "preprocessing_steps" in derived_dataset.dataset_metadata

        # Verify we can query all entities and see both datasets
        all_entities = test_db.query(Entity).all()
        assert len(all_entities) == 2
        assert any(
            isinstance(e, Dataset) and e.name == "Source Dataset" for e in all_entities
        )
        assert any(
            isinstance(e, Dataset) and e.name == "Preprocessed Dataset"
            for e in all_entities
        )

    finally:
        test_db.close()
