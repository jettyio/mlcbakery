import pytest
from datetime import datetime


@pytest.fixture
def sample_entity():
    return {"name": "Test Entity", "type": "test_type", "created_at": datetime.utcnow()}
