import pytest
from pydantic import ValidationError
from mlcbakery.schemas.task import TaskCreate, TaskUpdate

def test_task_create_valid():
    """Test successful creation of a TaskCreate schema."""
    data = {
        "name": "My Test Task",
        "workflow": {"steps": ["step1", "step2"]},
        "version": "1.0",
        "description": "A test task"
    }
    task = TaskCreate(**data)
    assert task.name == data["name"]
    assert task.workflow == data["workflow"]
    assert task.version == data["version"]
    assert task.description == data["description"]
    assert task.has_file_uploads == False  # Default value
    assert task.entity_type == "task"

def test_task_create_missing_required_fields():
    """Test TaskCreate with missing required fields."""
    with pytest.raises(ValidationError) as excinfo:
        TaskCreate()
    errors = excinfo.value.errors()
    assert any(e['type'] == 'missing' and e['loc'] == ('name',) for e in errors)
    assert any(e['type'] == 'missing' and e['loc'] == ('workflow',) for e in errors)

def test_task_create_optional_fields_none():
    """Test TaskCreate with optional fields as None."""
    data = {
        "name": "Minimal Task",
        "workflow": {"steps": []},
        "version": None,
        "description": None,
    }
    task = TaskCreate(**data)
    assert task.version is None
    assert task.description is None
    assert task.has_file_uploads == False  # Default value

def test_task_create_with_file_uploads():
    """Test TaskCreate with has_file_uploads set to True."""
    data = {
        "name": "File Upload Task",
        "workflow": {"steps": ["upload", "process"]},
        "has_file_uploads": True,
    }
    task = TaskCreate(**data)
    assert task.has_file_uploads == True

def test_task_update_all_fields():
    """Test TaskUpdate with all fields."""
    data = {
        "name": "Updated Task",
        "workflow": {"new_steps": []},
        "version": "1.1",
        "description": "Updated desc",
        "has_file_uploads": True
    }
    update_schema = TaskUpdate(**data)
    for key, value in data.items():
        assert getattr(update_schema, key) == value

def test_task_update_some_fields():
    """Test TaskUpdate with a subset of fields."""
    data = {"description": "Only updating description", "has_file_uploads": True}
    update_schema = TaskUpdate(**data)
    assert update_schema.description == data["description"]
    assert update_schema.has_file_uploads == data["has_file_uploads"]
    assert update_schema.name is None
    assert update_schema.workflow is None

def test_task_update_no_fields():
    """Test TaskUpdate with no fields."""
    update_schema = TaskUpdate()
    assert update_schema.name is None
    assert update_schema.workflow is None
    assert update_schema.version is None
    assert update_schema.description is None
    assert update_schema.has_file_uploads is None

def test_task_create_invalid_types():
    """Test TaskCreate with invalid data types."""
    with pytest.raises(ValidationError):
        TaskCreate(
            name="Invalid Task",
            workflow="not-a-dict"
        )

def test_task_update_invalid_types():
    """Test TaskUpdate with invalid data types."""
    with pytest.raises(ValidationError):
        TaskUpdate(workflow="not-a-dict") 
