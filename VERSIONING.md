# Entity Versioning System (In Progress)

MLCBakery now includes a comprehensive entity versioning system that combines **SQLAlchemy-Continuum** for automatic versioning with **git-style content hashing** and **semantic tagging**. This allows you to track, version, and navigate between different versions of your datasets, models, and tasks seamlessly.

## 🚀 Features

- **Automatic Versioning**: Every change to entities is automatically tracked
- **Git-Style Hashes**: Each version gets a unique SHA-256 content hash
- **Semantic Tags**: Tag versions with meaningful names like `v1.0.0`, `production`, `latest`
- **Polymorphic Inheritance**: Works correctly with `Dataset`, `TrainedModel`, and `Task` entities
- **Version Navigation**: Easily checkout previous versions or specific tags
- **Version Comparison**: Compare any two versions to see what changed
- **Transaction Grouping**: Related changes are grouped together automatically

## 📋 Quick Start

### Basic Usage

```python
from mlcbakery.database import get_async_session
from mlcbakery.version_manager import EntityVersionManager, create_versioned_dataset

async with get_async_session() as session:
    # Create a versioned dataset
    dataset = create_versioned_dataset(
        session=session,
        name="my_dataset",
        data_path="/data/file.csv",
        format_type="csv",
        tags=["v1.0.0", "initial"]
    )
    
    # Make changes
    dataset.name = "my_updated_dataset"
    
    # Create new version with tags
    version_manager = EntityVersionManager(session)
    version_manager.create_version(
        dataset, 
        message="Updated dataset name",
        tags=["v1.1.0", "production"]
    )
```

### Version Navigation

```python
# Checkout specific versions
version_manager.checkout_version(dataset, "v1.0.0")      # By tag
version_manager.checkout_version(dataset, hash_string)   # By hash
version_manager.checkout_version(dataset, 0)            # By index

# Tag current version
version_manager.tag_current_version(dataset, "stable")

# Get version history
history = version_manager.get_version_history(dataset)
for version in history:
    print(f"Version {version['index']}: {version['tags']} - {version['changeset']}")
```

### Version Comparison

```python
# Compare any two versions
comparison = version_manager.compare_versions(dataset, "v1.0.0", "v1.1.0")
print("Differences:")
for field, diff in comparison['differences'].items():
    print(f"  {field}: {diff['version1']} → {diff['version2']}")
```

### Finding Entities by Tags

```python
# Find all entities with a specific tag
production_entities = version_manager.get_entities_by_tag("production")
datasets_only = version_manager.get_entities_by_tag("production", entity_type="dataset")
```

## 🏗️ Architecture

### Database Schema

The versioning system creates several new tables:

- **`transaction`** - Groups related changes together
- **`entities_version`** - Versions of the base Entity fields
- **`datasets_version`** - Versions of Dataset-specific fields  
- **`trained_models_version`** - Versions of TrainedModel-specific fields
- **`tasks_version`** - Versions of Task-specific fields
- **`entity_version_hashes`** - Maps versions to git-style hashes
- **`entity_version_tags`** - Semantic tags for versions

### Polymorphic Inheritance

The system correctly handles your polymorphic inheritance structure:

```python
# Only the base Entity class needs __versioned__
class Entity(Base):
    __versioned__ = {
        'exclude': ['current_version_hash'],
        'strategy': 'validity',
    }

# Subclasses inherit versioning automatically  
class Dataset(Entity):
    # No __versioned__ needed
    pass
```

### Content Hashing

Each version gets a SHA-256 hash based on the entity's content:

```python
def _serialize_for_hash(self):
    """Override in subclasses to include relevant fields."""
    return {
        'name': self.name,
        'entity_type': self.entity_type,
        # ... other fields
    }
```

## 🛠️ API Reference

### EntityVersionManager

Main service class for version management:

- `create_version(entity, message=None, tags=None)` - Create new version
- `tag_version(entity, version_hash, tag_name)` - Tag existing version
- `tag_current_version(entity, tag_name)` - Tag current version
- `checkout_version(entity, version_ref)` - Navigate to version
- `get_version_history(entity)` - Get complete history
- `get_entities_by_tag(tag_name, entity_type=None)` - Find by tag
- `compare_versions(entity, version1, version2)` - Compare versions

### Convenience Functions

- `create_versioned_dataset(session, name, data_path, format_type, tags=None, **kwargs)`
- `create_versioned_model(session, name, model_path, tags=None, **kwargs)` 
- `create_versioned_task(session, name, workflow, tags=None, **kwargs)`

### Entity Methods

Each versioned entity has these methods:

- `entity.versions` - List of all versions (newest first)
- `entity.current_version_hash` - Current version hash
- `entity.checkout_version_by_hash(session, hash)` - Direct checkout
- `entity.checkout_version_by_tag(session, tag)` - Checkout by tag

## 🔄 Migration

The versioning system was added via Alembic migration `4857e3e86526`. This migration:

- Adds `current_version_hash` field to entities
- Creates all versioning tables
- Maintains backward compatibility

## 📝 Examples

See `example_versioning.py` for a complete demonstration of the versioning system in action.

## 🤔 Best Practices

1. **Use Semantic Tags**: Tag important versions with semantic names like `v1.0.0`, `production`, `latest`
2. **Meaningful Messages**: Include descriptive messages when creating versions
3. **Regular Tagging**: Tag stable versions for easy navigation
4. **Content-Based Deduplication**: The system automatically avoids creating duplicate versions for identical content
5. **Transaction Grouping**: Related changes in the same transaction are grouped together

## 🚧 Limitations

- Binary data (like dataset previews) is excluded from hashing for performance
- Versions are immutable once created
- Database storage grows with version history (consider archiving old versions)

## 🔧 Configuration

SQLAlchemy-Continuum is configured with:

- **Strategy**: `validity` (faster version traversal)
- **User Class**: `Agent` (tracks who made changes)
- **Excluded Fields**: `current_version_hash` (computed field)

## 📊 Monitoring

You can monitor version growth and usage:

```sql
-- Count versions per entity type
SELECT entity_type, COUNT(*) as version_count 
FROM entities_version 
GROUP BY entity_type;

-- Find most tagged versions
SELECT evh.content_hash, COUNT(evt.tag_name) as tag_count
FROM entity_version_hashes evh
LEFT JOIN entity_version_tags evt ON evh.id = evt.version_hash_id
GROUP BY evh.content_hash
ORDER BY tag_count DESC;
``` 