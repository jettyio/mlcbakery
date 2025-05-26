import pytest
from pydantic import ValidationError
from mlcbakery.schemas.trained_model import TrainedModelCreate, TrainedModelUpdate

def test_trained_model_create_valid():
    """Test successful creation of a TrainedModelCreate schema."""
    data = {
        "name": "My Test Model",
        "model_path": "/path/to/model.pt",
        "entity_type": "trained_model", # This is fixed in the schema, but good to include for completeness
        "collection_name": "test-collection",
        "metadata_version": "1.0.0",
        "model_metadata": {"accuracy": 0.95, "layers": 5},
        "asset_origin": "s3://my-bucket/models/model.pt",
        "long_description": "A detailed description of the test model.",
        "model_attributes": {"input_shape": [None, 224, 224, 3], "output_classes": 1000}
    }
    model = TrainedModelCreate(**data)
    assert model.name == data["name"]
    assert model.model_path == data["model_path"]
    assert model.asset_origin == data["asset_origin"]
    assert model.long_description == data["long_description"]
    assert model.model_attributes == data["model_attributes"]
    assert model.model_metadata == data["model_metadata"]
    assert model.collection_name == data["collection_name"]

def test_trained_model_create_missing_required_fields():
    """Test TrainedModelCreate with missing required fields (name, model_path)."""
    with pytest.raises(ValidationError) as excinfo:
        TrainedModelCreate(
            long_description="A model missing essential details"
        )
    errors = excinfo.value.errors()
    assert any(e['type'] == 'missing' and e['loc'] == ('name',) for e in errors)
    assert any(e['type'] == 'missing' and e['loc'] == ('model_path',) for e in errors)

def test_trained_model_create_optional_fields_none():
    """Test TrainedModelCreate with optional fields explicitly set to None."""
    data = {
        "name": "Minimal Model",
        "model_path": "/path/to/minimal.h5",
        "collection_name": "test-collection",
        "asset_origin": None,
        "long_description": None,
        "model_attributes": None,
        "model_metadata": None,
        "metadata_version": None,
    }
    model = TrainedModelCreate(**data)
    assert model.name == data["name"]
    assert model.model_path == data["model_path"]
    assert model.collection_name == data["collection_name"]
    assert model.asset_origin is None
    assert model.long_description is None
    assert model.model_attributes is None
    assert model.model_metadata is None

def test_trained_model_create_default_entity_type():
    """Test that entity_type has the correct default."""
    model = TrainedModelCreate(name="Test", model_path="/path", collection_name="test-collection")
    assert model.entity_type == "trained_model"

def test_trained_model_update_all_fields():
    """Test TrainedModelUpdate with all fields provided."""
    data = {
        "name": "Updated Model Name",
        "model_path": "/new/path/model.onnx",
        "collection_id": 2,
        "metadata_version": "1.0.1",
        "model_metadata": {"new_metric": 0.99},
        "asset_origin": "azure://blob/container/model.onnx",
        "long_description": "Updated long description.",
        "model_attributes": {"framework_version": "1.10"}
    }
    update_schema = TrainedModelUpdate(**data)
    for key, value in data.items():
        assert getattr(update_schema, key) == value

def test_trained_model_update_some_fields():
    """Test TrainedModelUpdate with only some fields provided."""
    data = {
        "long_description": "Only updating the description.",
        "model_attributes": {"status": "experimental"}
    }
    update_schema = TrainedModelUpdate(**data)
    assert update_schema.long_description == data["long_description"]
    assert update_schema.model_attributes == data["model_attributes"]
    assert update_schema.name is None # Ensure other fields are None
    assert update_schema.model_path is None

def test_trained_model_update_no_fields():
    """Test TrainedModelUpdate with no fields provided (all should be None)."""
    update_schema = TrainedModelUpdate()
    assert update_schema.model_path is None
    assert update_schema.collection_id is None
    assert update_schema.metadata_version is None
    assert update_schema.model_metadata is None
    assert update_schema.asset_origin is None
    assert update_schema.long_description is None
    assert update_schema.model_attributes is None