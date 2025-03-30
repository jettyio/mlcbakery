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

activity_datasets = Table(
    "activity_datasets",
    Base.metadata,
    Column("activity_id", Integer, ForeignKey("activities.id"), primary_key=True),
    Column("dataset_id", Integer, ForeignKey("datasets.id"), primary_key=True),
)


class Entity(Base):
    """Base class for all entities in the system."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)  # Discriminator column
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __mapper_args__ = {"polymorphic_on": entity_type, "polymorphic_identity": "entity"}


class Dataset(Entity):
    """Represents a dataset in the system."""

    __tablename__ = "datasets"

    id = Column(Integer, ForeignKey("entities.id"), primary_key=True)
    data_path = Column(String, nullable=False)
    format = Column(String, nullable=False)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)
    metadata_version = Column(String, nullable=True)
    dataset_metadata = Column(JSON, nullable=True)
    preview = Column(LargeBinary, nullable=True)
    preview_type = Column(String, nullable=True)

    # Relationships
    collection = relationship("Collection", back_populates="datasets")
    activities = relationship(
        "Activity", secondary=activity_datasets, back_populates="input_datasets"
    )

    __mapper_args__ = {"polymorphic_identity": "dataset"}


class TrainedModel(Entity):
    """Represents a trained model in the system."""

    __tablename__ = "trained_models"

    id = Column(Integer, ForeignKey("entities.id"), primary_key=True)
    model_path = Column(String, nullable=False)
    framework = Column(String, nullable=False)

    # Relationships
    training_activity = relationship(
        "Activity",
        back_populates="output_model",
        uselist=False,
        foreign_keys="Activity.output_model_id",
    )

    __mapper_args__ = {"polymorphic_identity": "trained_model"}


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


class Activity(Base):
    """Represents an activity in the provenance system."""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    output_model_id = Column(Integer, ForeignKey("trained_models.id"), nullable=True)

    # Relationships
    input_datasets = relationship(
        "Dataset", secondary=activity_datasets, back_populates="activities"
    )
    output_model = relationship(
        "TrainedModel",
        back_populates="training_activity",
        foreign_keys=[output_model_id],
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
