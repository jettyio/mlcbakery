"""
Entity Version Management Service

This module provides a high-level service for managing entity versions
using SQLAlchemy-Continuum and custom git-style hashing.
"""

from typing import List, Optional, Union, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy_continuum import version_class
from .models import Entity, EntityVersionHash, EntityVersionTag, Dataset, TrainedModel, Task


class EntityVersionManager:
    """Service class for managing entity versions with git-style hashing and tagging."""
    
    def __init__(self, session: Session, agent=None):
        self.session = session
        self.agent = agent
    
    def create_version(self, entity: Entity, message: Optional[str] = None, 
                      tags: Optional[List[str]] = None) -> EntityVersionHash:
        """
        Create a new version of an entity with optional semantic tags.
        
        Args:
            entity: The entity to version
            message: Optional commit-style message
            tags: Optional list of semantic tags (e.g., ['v1.0.0', 'production'])
            
        Returns:
            EntityVersionHash record for the new version
        """
        # Prepare for version creation
        result = entity.create_version_with_hash(self.session, message, tags)
        
        if isinstance(result, EntityVersionHash):
            # Content already exists, just added tags
            return result
            
        # Commit to let Continuum create the version
        self.session.commit()
        
        # Finalize with our custom hash
        content_hash, tags, message = result
        version_hash = entity.finalize_version_hash(
            self.session, content_hash, tags, message
        )
        
        self.session.commit()
        return version_hash
    
    def tag_version(self, entity: Entity, version_hash: str, tag_name: str) -> None:
        """Add a semantic tag to an existing version."""
        hash_record = self.session.query(EntityVersionHash).filter_by(
            entity_id=entity.id,
            content_hash=version_hash
        ).first()
        
        if not hash_record:
            raise ValueError(f"Version hash {version_hash} not found for entity {entity.id}")
        
        entity._add_tag_to_version_hash(self.session, hash_record, tag_name)
        self.session.commit()
    
    def tag_current_version(self, entity: Entity, tag_name: str) -> None:
        """Tag the current version of an entity."""
        entity.tag_current_version(self.session, tag_name)
        self.session.commit()
    
    def checkout_version(self, entity: Entity, 
                        version_ref: Union[str, int]) -> None:
        """
        Checkout a specific version by hash, tag, or version number.
        
        Args:
            entity: The entity to checkout
            version_ref: Version hash, semantic tag, or version index
        """
        if isinstance(version_ref, str):
            if len(version_ref) == 64:  # Assume it's a hash
                entity.checkout_version_by_hash(self.session, version_ref)
            else:  # Assume it's a tag
                entity.checkout_version_by_tag(self.session, version_ref)
        elif isinstance(version_ref, int):
            # Checkout by version index
            if version_ref < 0 or version_ref >= len(entity.versions):
                raise ValueError(f"Version index {version_ref} out of range")
            entity.versions[version_ref].revert()
            self.session.commit()
        else:
            raise ValueError("version_ref must be a string (hash/tag) or int (index)")
    
    def get_version_history(self, entity: Entity) -> List[Dict[str, Any]]:
        """Get the complete version history of an entity."""
        history = []
        
        for i, version in enumerate(entity.versions):
            # Find corresponding hash record
            hash_record = self.session.query(EntityVersionHash).filter_by(
                entity_id=entity.id,
                transaction_id=version.transaction_id
            ).first()
            
            tags = []
            if hash_record:
                tags = [tag.tag_name for tag in hash_record.tags]
            
            history.append({
                'index': i,
                'transaction_id': version.transaction_id,
                'content_hash': hash_record.content_hash if hash_record else None,
                'tags': tags,
                'changeset': version.changeset,
                'created_at': hash_record.created_at if hash_record else None,
                'operation_type': version.operation_type,
            })
        
        return history
    
    def get_entities_by_tag(self, tag_name: str, 
                           entity_type: Optional[str] = None) -> List[Entity]:
        """Find all entities with a specific tag."""
        query = self.session.query(Entity).join(EntityVersionHash).join(EntityVersionTag).filter(
            EntityVersionTag.tag_name == tag_name
        )
        
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)
        
        return query.all()
    
    def compare_versions(self, entity: Entity, version1_ref: Union[str, int], 
                        version2_ref: Union[str, int]) -> Dict[str, Any]:
        """Compare two versions of an entity."""
        # Get the version objects
        if isinstance(version1_ref, int):
            version1 = entity.versions[version1_ref]
        else:
            # Find by hash or tag
            hash_record = self._get_hash_record_by_ref(entity, version1_ref)
            version1 = self._get_version_by_transaction_id(entity, hash_record.transaction_id)
        
        if isinstance(version2_ref, int):
            version2 = entity.versions[version2_ref]
        else:
            hash_record = self._get_hash_record_by_ref(entity, version2_ref)
            version2 = self._get_version_by_transaction_id(entity, hash_record.transaction_id)
        
        return {
            'version1': {
                'transaction_id': version1.transaction_id,
                'changeset': version1.changeset
            },
            'version2': {
                'transaction_id': version2.transaction_id,
                'changeset': version2.changeset
            },
            'differences': self._compute_differences(version1.changeset, version2.changeset)
        }
    
    def _get_hash_record_by_ref(self, entity: Entity, ref: str) -> EntityVersionHash:
        """Get hash record by hash or tag."""
        if len(ref) == 64:  # Hash
            return self.session.query(EntityVersionHash).filter_by(
                entity_id=entity.id, content_hash=ref
            ).first()
        else:  # Tag
            return self.session.query(EntityVersionHash).join(EntityVersionTag).filter(
                EntityVersionHash.entity_id == entity.id,
                EntityVersionTag.tag_name == ref
            ).first()
    
    def _get_version_by_transaction_id(self, entity: Entity, transaction_id: int):
        """Get version object by transaction ID."""
        for version in entity.versions:
            if version.transaction_id == transaction_id:
                return version
        return None
    
    def _compute_differences(self, changeset1: dict, changeset2: dict) -> dict:
        """Compute differences between two changesets."""
        all_keys = set(changeset1.keys()) | set(changeset2.keys())
        differences = {}

        for key in all_keys:
            val1 = changeset1.get(key)
            val2 = changeset2.get(key)

            if val1 != val2:
                differences[key] = {
                    'version1': val1,
                    'version2': val2
                }

        return differences

    def resolve_version_ref(self, entity: Entity, version_ref: str) -> tuple:
        """
        Resolve a version reference to a version object and hash record.

        Args:
            entity: The entity to look up version for
            version_ref: Can be:
                - A 64-character SHA-256 hash
                - A semantic tag (e.g., "v1.0.0")
                - An index prefixed with ~ (e.g., "~0" for first, "~-1" for latest)

        Returns:
            Tuple of (version_object, hash_record, index)
        """
        versions = list(entity.versions)

        if not versions:
            raise ValueError(f"Entity {entity.name} has no versions")

        # Handle index reference (~0, ~1, ~-1, etc.)
        if version_ref.startswith('~'):
            try:
                index = int(version_ref[1:])
                if index < 0:
                    index = len(versions) + index
                if index < 0 or index >= len(versions):
                    raise ValueError(f"Version index {version_ref} out of range (0-{len(versions)-1})")
                version = versions[index]
                hash_record = self.session.query(EntityVersionHash).filter_by(
                    entity_id=entity.id,
                    transaction_id=version.transaction_id
                ).first()
                return version, hash_record, index
            except ValueError as e:
                if "invalid literal" in str(e):
                    raise ValueError(f"Invalid version index: {version_ref}")
                raise

        # Handle 64-char hash
        if len(version_ref) == 64:
            hash_record = self.session.query(EntityVersionHash).filter_by(
                entity_id=entity.id,
                content_hash=version_ref
            ).first()
            if not hash_record:
                raise ValueError(f"Version hash {version_ref} not found")

            for i, v in enumerate(versions):
                if v.transaction_id == hash_record.transaction_id:
                    return v, hash_record, i
            raise ValueError(f"Version with hash {version_ref} not found in history")

        # Handle semantic tag
        tag = self.session.query(EntityVersionTag).join(EntityVersionHash).filter(
            EntityVersionHash.entity_id == entity.id,
            EntityVersionTag.tag_name == version_ref
        ).first()

        if not tag:
            raise ValueError(f"Version tag '{version_ref}' not found")

        hash_record = tag.version_hash
        for i, v in enumerate(versions):
            if v.transaction_id == hash_record.transaction_id:
                return v, hash_record, i

        raise ValueError(f"Version with tag '{version_ref}' not found in history")

    def get_version_data(self, entity: Entity, version_ref: str) -> Dict[str, Any]:
        """
        Get the full entity data at a specific version.

        Args:
            entity: The entity to get version data for
            version_ref: Version reference (hash, tag, or ~index)

        Returns:
            Dictionary containing all entity fields at that version
        """
        version, hash_record, index = self.resolve_version_ref(entity, version_ref)

        # Get all column values from the version object
        # Continuum version objects have the same columns as the original model
        data = {}

        # Get base entity fields
        base_fields = ['name', 'entity_type', 'asset_origin', 'is_private', 'croissant_metadata']
        for field in base_fields:
            if hasattr(version, field):
                data[field] = getattr(version, field)

        # Get entity-type specific fields based on the actual type
        if entity.entity_type == 'task':
            task_fields = ['workflow', 'version', 'description', 'has_file_uploads']
            for field in task_fields:
                if hasattr(version, field):
                    data[field] = getattr(version, field)
        elif entity.entity_type == 'dataset':
            dataset_fields = ['data_path', 'format', 'metadata_version', 'dataset_metadata', 'long_description']
            for field in dataset_fields:
                if hasattr(version, field):
                    data[field] = getattr(version, field)
        elif entity.entity_type == 'trained_model':
            model_fields = ['model_path', 'metadata_version', 'model_metadata', 'long_description', 'model_attributes']
            for field in model_fields:
                if hasattr(version, field):
                    data[field] = getattr(version, field)

        return {
            'index': index,
            'transaction_id': version.transaction_id,
            'content_hash': hash_record.content_hash if hash_record else None,
            'tags': [t.tag_name for t in hash_record.tags] if hash_record else [],
            'created_at': hash_record.created_at if hash_record else None,
            'operation_type': version.operation_type,
            'data': data
        }


# Convenience functions
def create_versioned_dataset(session: Session, name: str, data_path: str, 
                           format_type: str, tags: Optional[List[str]] = None,
                           **kwargs) -> Dataset:
    """Create a new versioned dataset with initial tags."""
    dataset = Dataset(
        name=name,
        data_path=data_path,
        format=format_type,
        **kwargs
    )
    
    session.add(dataset)
    
    version_manager = EntityVersionManager(session)
    version_manager.create_version(dataset, "Initial version", tags)
    
    return dataset


def create_versioned_model(session: Session, name: str, model_path: str,
                          tags: Optional[List[str]] = None,
                          **kwargs) -> TrainedModel:
    """Create a new versioned trained model with initial tags."""
    model = TrainedModel(
        name=name,
        model_path=model_path,
        **kwargs
    )
    
    session.add(model)
    
    version_manager = EntityVersionManager(session)
    version_manager.create_version(model, "Initial version", tags)
    
    return model


def create_versioned_task(session: Session, name: str, workflow: dict,
                         tags: Optional[List[str]] = None,
                         **kwargs) -> Task:
    """Create a new versioned task with initial tags."""
    task = Task(
        name=name,
        workflow=workflow,
        **kwargs
    )
    
    session.add(task)
    
    version_manager = EntityVersionManager(session)
    version_manager.create_version(task, "Initial version", tags)
    
    return task 