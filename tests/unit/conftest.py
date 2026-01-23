"""Conftest for unit tests that don't require database connection."""
import pytest


@pytest.fixture(scope="function", autouse=True)
def setup_test_db():
    """Override the database setup fixture from parent conftest - no-op for unit tests."""
    yield
