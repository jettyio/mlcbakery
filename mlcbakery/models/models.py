"""SQLAlchemy models for provenance tracking system."""

# Standard library imports
from datetime import datetime

# Third-party imports
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


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


class Dataset(Base):
    """Represents a dataset in the system.

    A dataset is a collection of data that can be associated with entities
    and tracked through its generation process.

    Attributes:
        id: The primary key for the dataset.
        collection_id: Foreign key reference to the associated entity.
        name: The name of the dataset.
        generated_by_id: ID of the process that generated this dataset.
        metadata_version: Version of the metadata schema used.
    """

    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True)
    collection_id = Column(Integer, ForeignKey("entities.id"))
    name = Column(String)
    generated_by_id = Column(Integer)
    metadata_version = Column(String)


class Entity(Base):
    """Represents an entity in the provenance system.

    An entity is a physical, digital, or conceptual thing with some fixed aspects
    that can be involved in activities.

    Attributes:
        id: The primary key for the entity.
        name: The name of the entity.
        type: The type of entity.
        entity_id: Reference to another entity if applicable.
        generated_by: ID of the process that generated this entity.
        created_at: Timestamp of entity creation.
        activities: Related activities through was_generated_by relationship.
    """

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String)
    entity_id = Column(Integer)
    generated_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    activities = relationship(
        "Activity",
        secondary=was_generated_by,
        back_populates="entities",
    )


class Activity(Base):
    """Represents an activity in the provenance system.

    An activity is something that occurs over a period of time and
    acts upon or with entities.

    Attributes:
        id: The primary key for the activity.
        name: The name of the activity.
        start_time: When the activity began.
        end_time: When the activity completed.
        entities: Related entities through was_generated_by relationship.
        agents: Related agents through was_associated_with relationship.
    """

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
    """Represents an agent in the provenance system.

    An agent is something that bears some form of responsibility for an activity
    taking place or for the existence of an entity.

    Attributes:
        id: The primary key for the agent.
        name: The name of the agent.
        type: The type of agent.
        activities: Related activities through was_associated_with relationship.
    """

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
