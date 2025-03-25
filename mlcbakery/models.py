from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Table,
    JSON,
    Text,
    LargeBinary,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


# Association tables
was_generated_by = Table(
    "was_generated_by",
    Base.metadata,
    Column("entity_id", Integer, ForeignKey("entities.id"), primary_key=True),
    Column("activity_id", Integer, ForeignKey("activities.id"), primary_key=True),
)

was_associated_with = Table(
    "was_associated_with",
    Base.metadata,
    Column("activity_id", Integer, ForeignKey("activities.id"), primary_key=True),
    Column("agent_id", Integer, ForeignKey("agents.id"), primary_key=True),
)


class Collection(Base):
    """Represents a collection in the system.

    A collection is a logical grouping of datasets that can be tracked together.

    Attributes:
        id: The primary key for the collection.
        name: The name of the collection.
        description: A description of what the collection contains.
        datasets: Relationship to associated datasets.
    """

    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)

    # Relationships
    datasets = relationship("Dataset", back_populates="collection")


class Dataset(Base):
    """Represents a dataset in the system.

    A dataset is a collection of data that can be associated with entities
    and tracked through its generation process.

    Attributes:
        id: The primary key for the dataset.
        collection_id: Foreign key reference to the associated collection.
        name: The name of the dataset.
        generated_by_id: ID of the process that generated this dataset.
        metadata_version: Version of the metadata schema used.
        dataset_metadata: JSON metadata associated with the dataset.
        preview: Binary data representing a preview of the dataset.
        preview_type: Type of the preview (e.g., 'image/png', 'text/csv').
        collection: Relationship to the parent collection.
    """

    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True)
    collection_id = Column(Integer, ForeignKey("collections.id"))
    name = Column(String)
    generated_by_id = Column(Integer)
    metadata_version = Column(String)
    dataset_metadata = Column(JSON, nullable=True)
    preview = Column(LargeBinary, nullable=True)
    preview_type = Column(String, nullable=True)

    # Relationships
    collection = relationship("Collection", back_populates="datasets")


class Entity(Base):
    """Represents an entity in the provenance system."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=True)
    generated_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    activities = relationship(
        "Activity",
        secondary=was_generated_by,
        back_populates="entities",
    )


class Activity(Base):
    """Represents an activity in the provenance system."""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    start_time = Column(DateTime)
    end_time = Column(DateTime)

    # Relationships
    entities = relationship(
        "Entity",
        secondary=was_generated_by,
        back_populates="activities",
    )
    agents = relationship(
        "Agent",
        secondary=was_associated_with,
        back_populates="activities",
    )


class Agent(Base):
    """Represents an agent in the provenance system."""

    __tablename__ = "agents"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String)

    # Relationships
    activities = relationship(
        "Activity",
        secondary=was_associated_with,
        back_populates="agents",
    )
