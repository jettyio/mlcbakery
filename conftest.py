import pytest
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from sqlalchemy.orm import sessionmaker
import httpx
from unittest import mock
import pytest_asyncio # Import pytest_asyncio

# Assuming models.py and database.py are importable from the root
# Adjust the import path if your structure is different
from mlcbakery import models # Add this import
from mlcbakery.database import get_async_db # Import the dependency getter
from mlcbakery.main import app # Import the FastAPI app

# --- Test Admin Token ---
TEST_ADMIN_TOKEN = "test-super-secret-token" # Define a constant for the test token

# --- Global Test Database Setup ---

# Create async test database connection URL (ensure this matches your test DB)
SQLALCHEMY_TEST_DATABASE_URL = os.environ.get("DATABASE_TEST_URL")

# Create global async engine
engine = create_async_engine(SQLALCHEMY_TEST_DATABASE_URL, echo=True, poolclass=NullPool) # Change echo to True

# Create global async session factory
TestingSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# --- Global Dependency Override ---

# Define the async override function
async def override_get_async_db():
    async with TestingSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

# Apply the override to the FastAPI app instance
# This needs to happen before tests run that use the app/client
app.dependency_overrides[get_async_db] = override_get_async_db

# --- Fixture to Set Admin Auth Token Env Var ---
@pytest.fixture(scope="session", autouse=True) # Use session scope and autouse
def set_admin_token_env():
    original_token = os.environ.get("ADMIN_AUTH_TOKEN")
    os.environ["ADMIN_AUTH_TOKEN"] = TEST_ADMIN_TOKEN
    print(f"\n--- Set ADMIN_AUTH_TOKEN to: {TEST_ADMIN_TOKEN} ---") # Added print
    yield
    # Teardown: restore original value or unset
    if original_token is None:
        del os.environ["ADMIN_AUTH_TOKEN"]
        print("\n--- Unset ADMIN_AUTH_TOKEN ---") # Added print
    else:
        os.environ["ADMIN_AUTH_TOKEN"] = original_token
        print(f"\n--- Restored ADMIN_AUTH_TOKEN to: {original_token} ---") # Added print

# --- Global Autouse Async Fixture for DB Setup/Teardown ---
# This fixture needs to run *after* the env var is set, 
# if the app initialization depends on it (unlikely here, but good practice)
# Since set_admin_token_env is session-scoped and autouse, it runs first.
@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Auto-running fixture to set up and tear down the test database for each function."""
    # Ensure Base is imported if not already available globally
    # This might need adjustment depending on where Base is defined.
    # If it's in models.py:
    # from mlcbakery.models import Base # Remove this line

    # Use engine.begin() for explicit transaction management during DDL
    async with engine.begin() as conn: # Use engine.begin()
        try:
            print("\n--- Global Fixture: Dropping tables... ---")
            await conn.run_sync(models.Base.metadata.drop_all) # Use models.Base
            print("--- Global Fixture: Creating tables... ---")
            await conn.run_sync(models.Base.metadata.create_all) # Use models.Base
            # Commit is handled implicitly by engine.begin() context manager on success
            print("--- Global Fixture: Tables created (Transaction Committing). ---")
        except Exception as e:
            print(f"!!! Global Fixture Error during table setup: {e} !!!")
            # Rollback is handled implicitly by engine.begin() context manager on error
            pytest.fail(f"Global fixture setup failed: {e}")

    # Optional: Seed minimal common data if needed by *most* tests
    # Be cautious with global seeding - keep it minimal or handle in specific tests/fixtures
    # Example:
    # async with TestingSessionLocal() as session:
    #     try:
    #         print("--- Global Fixture: Seeding common data... ---")
    #         # Add truly common data here
    #         await session.commit()
    #         print("--- Global Fixture: Common data seeded. ---")
    #     except Exception as e:
    #         print(f"!!! Global Fixture Error during common data seeding: {e} !!!")
    #         await session.rollback()
    #         pytest.fail(f"Global fixture setup failed during seeding: {e}")

    # --- Test runs here ---
    print("--- Global Fixture: Yielding to test function... ---")
    yield # Fixture pauses here while test runs
    # --- Test finished ---
    print("--- Global Fixture: Test function finished. ---")

    # Teardown: Drop tables after test finishes within its own transaction
    async with engine.begin() as conn: # Use engine.begin()
        try:
            print("--- Global Fixture: Dropping tables (teardown)... ---")
            await conn.run_sync(models.Base.metadata.drop_all) # Use models.Base
            # Commit is handled implicitly by engine.begin() context manager on success
            print("--- Global Fixture: Tables dropped (Teardown Transaction Committing). ---")
        except Exception as e:
            print(f"!!! Global Fixture Error during table teardown: {e} !!!")
            # Rollback is handled implicitly by engine.begin() context manager on error



# --- Add Async Test Client Fixture ---

@pytest_asyncio.fixture(scope="function")
async def async_client(): # REMOVED setup_test_db dependency here
    """Provides an asynchronous test client for making requests to the app."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest.fixture(scope="function")
def auth_headers():
    """Returns headers with admin authentication token."""
    return {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}

@pytest_asyncio.fixture(scope="function")
async def test_client():
    """Provides an asynchronous test client for making requests to the app."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        yield client

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Provides a database session for tests."""
    async with TestingSessionLocal() as session:
        yield session

@pytest.fixture(scope="function")
def mocked_gcs(mocker):
    """Mock Google Cloud Storage client for testing."""
    # Mock GCS client creation
    mock_client = mocker.MagicMock()
    mock_bucket = mocker.MagicMock()
    mock_blob = mocker.MagicMock()
    
    # Setup the mock chain
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob
    mock_bucket.list_blobs.return_value = []
    
    # Mock specific methods
    mock_blob.upload_from_string.return_value = None
    mock_blob.name = "test_path"
    mock_blob.generate_signed_url.return_value = "https://example.com/signed-url"
    mock_blob.download_as_bytes.return_value = b"test content"
    
    # Patch the create_gcs_client function
    mocker.patch("mlcbakery.storage.gcp.create_gcs_client", return_value=mock_client)
    
    return mock_client