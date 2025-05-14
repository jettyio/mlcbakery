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
from sqlalchemy.orm import relationship, backref
from .database import Base


# Association tables
# was_associated_with = Table(
#     "was_associated_with",
#     Base.metadata,
#     Column("activity_id", Integer, ForeignKey("activities.id"), primary_key=True),
#     Column("agent_id", Integer, ForeignKey("agents.id"), primary_key=True),
# )

# activity_entities = Table(
#     "activity_entities",
#     Base.metadata,
#     Column("activity_id", Integer, ForeignKey("activities.id"), primary_key=True),
#     Column("entity_id", Integer, ForeignKey("entities.id"), primary_key=True),
# )


# NEW EntityRelationship class
class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id = Column(Integer, primary_key=True, index=True)
    source_entity_id = Column(Integer, ForeignKey("entities.id"), index=True, nullable=True)
    target_entity_id = Column(Integer, ForeignKey("entities.id"), index=True, nullable=True)
    activity_name = Column(String, nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)

    # Relationships to the actual objects
    source_entity = relationship("Entity", foreign_keys=[source_entity_id], back_populates="downstream_links")
    target_entity = relationship("Entity", foreign_keys=[target_entity_id], back_populates="upstream_links")
    agent = relationship("Agent", backref=backref("performed_links", lazy="dynamic"))


class Entity(Base):
    """Base class for all entities in the system."""

    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)  # Discriminator column
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    asset_origin = Column(String, nullable=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)
    # input_entity_ids = None # This seems unused, can be removed if so

    # Relationships
    collection = relationship("Collection", back_populates="entities")
    upstream_links = relationship("EntityRelationship", foreign_keys=[EntityRelationship.target_entity_id], back_populates="target_entity", lazy="selectin")
    downstream_links = relationship("EntityRelationship", foreign_keys=[EntityRelationship.source_entity_id], back_populates="source_entity", lazy="selectin")

    # upstream_links and downstream_links are now available via backrefs from EntityRelationship
    # Example accessors (add these or similar to your Entity class for convenience)
    def get_parent_entities_activities_agents(self):
        parents = []
        # Assuming upstream_links is dynamically loaded or use .all() if needed
        for link in self.upstream_links: # These are EntityRelationship objects
            parents.append({
                "entity": link.source_entity,
                "activity": link.activity,
                "agent": link.agent
            })
        return parents

    def get_child_entities_activities_agents(self):
        children = []
        # Assuming downstream_links is dynamically loaded or use .all() if needed
        for link in self.downstream_links: # These are EntityRelationship objects
            children.append({
                "entity": link.target_entity,
                "activity": link.activity,
                "agent": link.agent
            })
        return children

    __mapper_args__ = {"polymorphic_on": entity_type, "polymorphic_identity": "entity"}


class Dataset(Entity):
    """Represents a dataset in the system."""

    __tablename__ = "datasets"

    id = Column(Integer, ForeignKey("entities.id"), primary_key=True)
    data_path = Column(String, nullable=False)
    format = Column(String, nullable=False)
    metadata_version = Column(String, nullable=True)
    dataset_metadata = Column(JSON, nullable=True)
    preview = Column(LargeBinary, nullable=True)
    preview_type = Column(String, nullable=True)
    long_description = Column(Text, nullable=True)
    __mapper_args__ = {"polymorphic_identity": "dataset"}


class TrainedModel(Entity):
    """Represents a trained model in the system."""

    __tablename__ = "trained_models"

    id = Column(Integer, ForeignKey("entities.id"), primary_key=True)
    model_path = Column(String, nullable=False)
    framework = Column(String, nullable=False)
    metadata_version = Column(String, nullable=True)
    model_metadata = Column(JSON, nullable=True)

    __mapper_args__ = {"polymorphic_identity": "trained_model"}


class Collection(Base):
    """Represents a collection in the system.

    A collection is a logical grouping of entities (datasets and models) that can be tracked together.

    Attributes:
        id: The primary key for the collection.
        name: The name of the collection.
        description: A description of what the collection contains.
        storage_info: JSON field containing storage credentials and location information.
        storage_provider: String identifying the storage provider (e.g., 'aws', 'gcp', 'azure').
        entities: Relationship to associated entities (datasets and models).
        agents: Relationship to associated agents.
    """

    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    storage_info = Column(JSON, nullable=True)
    storage_provider = Column(String, nullable=True)

    # Relationships
    entities = relationship("Entity", back_populates="collection")
    agents = relationship("Agent", back_populates="collection")


class Activity(Base):
    """Represents an activity in the provenance system."""

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Agent(Base):
    """Represents an agent in the provenance system."""

    __tablename__ = "agents"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)

    # Relationships
    collection = relationship("Collection", back_populates="agents")
    # activities = relationship( # REMOVE THIS
    #     "Activity",
    #     secondary=was_associated_with,
    #     back_populates="agents",
    # )
    # performed_links is now available via backref from EntityRelationship
