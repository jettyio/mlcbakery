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
    Boolean,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship, backref
from sqlalchemy_continuum import make_versioned
from .database import Base

# Initialize versioning BEFORE any model definitions
# Pass Agent as the user class for transaction tracking
make_versioned(user_cls='Agent')



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
    
    # IMPORTANT: Only add __versioned__ to the base class for polymorphic inheritance
    __versioned__ = {
        'exclude': ['current_version_hash'],  # Don't version this computed field
        'strategy': 'validity',  # Use validity strategy for better performance
    }

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)  # Discriminator column
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    asset_origin = Column(String, nullable=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=True)
    
    # Add for git-style versioning
    current_version_hash = Column(String(64), nullable=True, index=True)

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
                "activity": link.activity_name,
                "agent": link.agent
            })
        return parents

    def get_child_entities_activities_agents(self):
        children = []
        # Assuming downstream_links is dynamically loaded or use .all() if needed
        for link in self.downstream_links: # These are EntityRelationship objects
            children.append({
                "entity": link.target_entity,
                "activity": link.activity_name,
                "agent": link.agent
            })
        return children

    def create_version_with_hash(self, session, message=None, tags=None):
        """Create a new version with git-style hash and optional tags."""
        # Continuum handles versioning automatically on commit
        # We just need to add our custom hash/tag layer after commit
        
        # Generate content hash
        content = self._serialize_for_hash()
        content_hash = self._compute_content_hash(content)
        
        # Check if we already have this exact version
        existing_hash = session.query(EntityVersionHash).filter_by(
            content_hash=content_hash
        ).first()
        
        if existing_hash:
            # Same content exists, just add tags if provided
            if tags:
                for tag_name in tags:
                    self._add_tag_to_version_hash(session, existing_hash, tag_name)
            return existing_hash
        
        # This will be called after the commit when we have the version
        return content_hash, tags, message

    def finalize_version_hash(self, session, content_hash, tags=None, message=None):
        """Called after commit to create hash record with proper transaction ID."""
        # Get the latest version (created by Continuum)
        if not self.versions:
            return None
            
        latest_version = self.versions[-1]
        
        # Create new hash record
        version_hash = EntityVersionHash(
            entity_id=self.id,
            transaction_id=latest_version.transaction_id,
            content_hash=content_hash,
        )
        session.add(version_hash)
        session.flush()
        
        # Add tags
        if tags:
            for tag_name in tags:
                self._add_tag_to_version_hash(session, version_hash, tag_name)
                
        self.current_version_hash = content_hash
        return version_hash

    def checkout_version_by_hash(self, session, version_hash):
        """Checkout a specific version by its hash."""
        hash_record = session.query(EntityVersionHash).filter_by(
            entity_id=self.id,
            content_hash=version_hash
        ).first()
        
        if not hash_record:
            raise ValueError(f"Version hash {version_hash} not found")
        
        # Find the corresponding Continuum version
        continuum_version = None
        for version in self.versions:
            if version.transaction_id == hash_record.transaction_id:
                continuum_version = version
                break
                
        if continuum_version:
            continuum_version.revert()
            session.commit()
            self.current_version_hash = version_hash
            
    def checkout_version_by_tag(self, session, tag_name):
        """Checkout a version by its semantic tag."""
        version_hash = self.get_version_hash_by_tag(session, tag_name)
        if version_hash:
            self.checkout_version_by_hash(session, version_hash)
        else:
            raise ValueError(f"Tag '{tag_name}' not found for entity {self.id}")

    def tag_current_version(self, session, tag_name):
        """Tag the current version."""
        if not self.current_version_hash:
            raise ValueError("No current version to tag")
            
        hash_record = session.query(EntityVersionHash).filter_by(
            content_hash=self.current_version_hash
        ).first()
        
        if hash_record:
            self._add_tag_to_version_hash(session, hash_record, tag_name)
    
    def get_version_hash_by_tag(self, session, tag_name):
        """Get version hash by semantic tag."""
        tag = session.query(EntityVersionTag).join(EntityVersionHash).filter(
            EntityVersionHash.entity_id == self.id,
            EntityVersionTag.tag_name == tag_name
        ).first()
        
        if tag:
            return tag.version_hash.content_hash
        return None

    def _add_tag_to_version_hash(self, session, version_hash_record, tag_name):
        """Add a tag to a version hash record."""
        # Check if tag already exists
        existing_tag = session.query(EntityVersionTag).filter_by(
            version_hash_id=version_hash_record.id,
            tag_name=tag_name
        ).first()
        
        if not existing_tag:
            tag = EntityVersionTag(
                version_hash_id=version_hash_record.id,
                tag_name=tag_name
            )
            session.add(tag)

    def _serialize_for_hash(self):
        """Serialize entity data for hash computation. Override in subclasses."""
        return {
            'name': self.name,
            'entity_type': self.entity_type,
            'asset_origin': self.asset_origin,
            'collection_id': self.collection_id,
        }

    def _compute_content_hash(self, content):
        """Compute SHA-256 hash of content."""
        import hashlib
        import json
        content_str = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(content_str.encode()).hexdigest()

    __mapper_args__ = {"polymorphic_on": entity_type, "polymorphic_identity": "entity"}


class Dataset(Entity):
    """Represents a dataset in the system."""

    __tablename__ = "datasets"
    
    # DO NOT add __versioned__ here - inherited from Entity

    id = Column(Integer, ForeignKey("entities.id"), primary_key=True)
    data_path = Column(String, nullable=False)
    format = Column(String, nullable=False)
    metadata_version = Column(String, nullable=True)
    dataset_metadata = Column(JSONB, nullable=True)
    preview = Column(LargeBinary, nullable=True)
    preview_type = Column(String, nullable=True)
    long_description = Column(Text, nullable=True)
    
    def _serialize_for_hash(self):
        """Override to include Dataset-specific fields."""
        base_data = super()._serialize_for_hash()
        base_data.update({
            'data_path': self.data_path,
            'format': self.format,
            'metadata_version': self.metadata_version,
            'dataset_metadata': self.dataset_metadata,
            'long_description': self.long_description,
            # Note: Excluding preview as it's binary data
        })
        return base_data
    
    __mapper_args__ = {"polymorphic_identity": "dataset"}


class TrainedModel(Entity):
    """Represents a trained model in the system."""

    __tablename__ = "trained_models"
    
    # DO NOT add __versioned__ here - inherited from Entity

    id = Column(Integer, ForeignKey("entities.id"), primary_key=True)
    model_path = Column(String, nullable=False)
    metadata_version = Column(String, nullable=True)
    model_metadata = Column(JSONB, nullable=True)
    long_description = Column(Text, nullable=True)
    model_attributes = Column(JSONB, nullable=True)

    def _serialize_for_hash(self):
        """Override to include TrainedModel-specific fields."""
        base_data = super()._serialize_for_hash()
        base_data.update({
            'model_path': self.model_path,
            'metadata_version': self.metadata_version,
            'model_metadata': self.model_metadata,
            'long_description': self.long_description,
            'model_attributes': self.model_attributes,
        })
        return base_data

    __mapper_args__ = {"polymorphic_identity": "trained_model"}


class Task(Entity):
    """Represents a workflow Task in the system."""

    __tablename__ = "tasks"
    
    # DO NOT add __versioned__ here - inherited from Entity

    id = Column(Integer, ForeignKey("entities.id"), primary_key=True)
    workflow = Column(JSONB, nullable=False)
    version = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    def _serialize_for_hash(self):
        """Override to include Task-specific fields."""
        base_data = super()._serialize_for_hash()
        base_data.update({
            'workflow': self.workflow,
            'version': self.version,
            'description': self.description,
        })
        return base_data

    __mapper_args__ = {"polymorphic_identity": "task"}


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
        auth_org_id: Optional organization identifier for authentication purposes.
    """

    __tablename__ = "collections"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    storage_info = Column(JSONB, nullable=True)
    storage_provider = Column(String, nullable=True)
    owner_identifier = Column(String, nullable=False)  # Identifier for the owner (user or organization)
    auth_org_id = Column(String, nullable=True)  # Optional organization identifier for authentication

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


# Custom models for git-style versioning (not versioned themselves)
class EntityVersionHash(Base):
    """Maps Continuum version IDs to git-style hashes and tags."""
    
    __tablename__ = "entity_version_hashes"
    
    id = Column(Integer, primary_key=True)
    entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False)
    transaction_id = Column(Integer, nullable=False)  # Continuum's transaction ID
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    entity = relationship("Entity", backref="version_hashes")
    tags = relationship("EntityVersionTag", back_populates="version_hash", cascade="all, delete-orphan")


class EntityVersionTag(Base):
    """Semantic tags for versions."""
    
    __tablename__ = "entity_version_tags"
    
    id = Column(Integer, primary_key=True)
    version_hash_id = Column(Integer, ForeignKey("entity_version_hashes.id"))
    tag_name = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    version_hash = relationship("EntityVersionHash", back_populates="tags")
    
    __table_args__ = (
        UniqueConstraint('version_hash_id', 'tag_name', name='uq_version_tag'),
    )


# IMPORTANT: Call this after all models are defined
import sqlalchemy as sa
sa.orm.configure_mappers()
