import pytest
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from sqlalchemy.orm import sessionmaker
import httpx

# Assuming models.py and database.py are importable from the root
# Adjust the import path if your structure is different
from mlcbakery.database import get_async_db # Import the dependency getter
from mlcbakery.main import app # Import the FastAPI app

# --- Global Test Database Setup ---

# Create async test database connection URL (ensure this matches your test DB)
SQLALCHEMY_TEST_DATABASE_URL = os.getenv("DATABASE_URL")

# Create global async engine
engine = create_async_engine(SQLALCHEMY_TEST_DATABASE_URL, echo=False, poolclass=NullPool) # Echo can be noisy globally

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

# --- Global Autouse Async Fixture for DB Setup/Teardown ---

@pytest.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Auto-running fixture to set up and tear down the test database for each function."""
    # Use engine.begin() for explicit transaction management during DDL
    async with engine.begin() as conn: # Use engine.begin()
        try:
            print("\n--- Global Fixture: Dropping tables... ---")
            await conn.run_sync(Base.metadata.drop_all)
            print("--- Global Fixture: Creating tables... ---")
            await conn.run_sync(Base.metadata.create_all)
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
            await conn.run_sync(Base.metadata.drop_all)
            # Commit is handled implicitly by engine.begin() context manager on success
            print("--- Global Fixture: Tables dropped (Teardown Transaction Committing). ---")
        except Exception as e:
            print(f"!!! Global Fixture Error during table teardown: {e} !!!")
            # Rollback is handled implicitly by engine.begin() context manager on error



# --- Add Async Test Client Fixture ---

@pytest.fixture(scope="function")
async def async_client(): # REMOVED setup_test_db dependency here
    """Provides an asynchronous test client for making requests to the app."""
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client 