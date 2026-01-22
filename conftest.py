import pytest
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from sqlalchemy.orm import sessionmaker
import httpx
import pytest_asyncio
import sqlalchemy as sa

# --- Test Admin Token ---
TEST_ADMIN_TOKEN = "test-super-secret-token"

# --- Global Test Database Setup ---

# Create async test database connection URL (ensure this matches your test DB)
SQLALCHEMY_TEST_DATABASE_URL = os.environ.get("DATABASE_TEST_URL")

# Create global async engine
engine = create_async_engine(
    SQLALCHEMY_TEST_DATABASE_URL, echo=True, poolclass=NullPool
)

# Create global async session factory
TestingSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

# --- Lazy App Loading for Coverage Tracking ---
# We use a cached lazy loader to ensure the app is only configured once,
# but imported after coverage starts tracking.

_app_instance = None


def _get_app():
    """
    Lazy load the FastAPI app to allow coverage to track code execution.

    This function delays the import of the app module until it's actually needed
    by test fixtures. This ensures that pytest-cov has already started tracking
    before the endpoint modules are imported.
    """
    global _app_instance
    if _app_instance is None:
        # Import app and dependencies lazily
        from mlcbakery.main import app
        from mlcbakery.database import get_async_db
        from mlcbakery.api.dependencies import auth_strategies
        from mlcbakery.auth.passthrough_strategy import PassthroughStrategy
        from mlcbakery.auth.admin_token_strategy import AdminTokenStrategy

        # Define the async override function for database sessions
        async def override_get_async_db():
            async with TestingSessionLocal() as session:
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise

        def override_auth_strategies():
            return [
                AdminTokenStrategy(TEST_ADMIN_TOKEN),
                PassthroughStrategy()
            ]

        # Apply dependency overrides
        app.dependency_overrides[get_async_db] = override_get_async_db
        app.dependency_overrides[auth_strategies] = override_auth_strategies

        _app_instance = app

    return _app_instance


def _get_models():
    """Lazy load models module for coverage tracking."""
    from mlcbakery import models
    return models


# --- Global Autouse Async Fixture for DB Setup/Teardown ---
@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Auto-running fixture to set up and tear down the test database for each function."""
    # Lazy load models
    models = _get_models()

    # Use engine.begin() for explicit transaction management during DDL
    async with engine.begin() as conn:
        try:
            print("\n--- Global Fixture: Dropping tables... ---")
            # Use CASCADE to handle foreign key dependencies
            await conn.execute(sa.text("DROP SCHEMA public CASCADE;"))
            await conn.execute(sa.text("CREATE SCHEMA public;"))
            print("--- Global Fixture: Creating tables... ---")
            await conn.run_sync(models.Base.metadata.create_all)
            print("--- Global Fixture: Tables created (Transaction Committing). ---")
        except Exception as e:
            print(f"!!! Global Fixture Error during table setup: {e} !!!")
            pytest.fail(f"Global fixture setup failed: {e}")

    # --- Test runs here ---
    print("--- Global Fixture: Yielding to test function... ---")
    yield
    # --- Test finished ---
    print("--- Global Fixture: Test function finished. ---")

    # Teardown: Drop tables after test finishes within its own transaction
    async with engine.begin() as conn:
        try:
            print("--- Global Fixture: Dropping tables (teardown)... ---")
            # Use CASCADE to handle foreign key dependencies during teardown
            await conn.execute(sa.text("DROP SCHEMA public CASCADE;"))
            await conn.execute(sa.text("CREATE SCHEMA public;"))
            print(
                "--- Global Fixture: Tables dropped (Teardown Transaction Committing). ---"
            )
        except Exception as e:
            print(f"!!! Global Fixture Error during table teardown: {e} !!!")


# --- Add Async Test Client Fixture ---


@pytest_asyncio.fixture(scope="function")
async def async_client():
    """Provides an asynchronous test client for making requests to the app."""
    app = _get_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture(scope="function")
def admin_token_auth_headers():
    """Returns headers with admin authentication token."""
    return {"Authorization": f"Bearer {TEST_ADMIN_TOKEN}"}


@pytest_asyncio.fixture(scope="function")
async def test_client():
    """Provides an asynchronous test client for making requests to the app."""
    app = _get_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
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
