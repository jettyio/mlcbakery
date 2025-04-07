import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Ensure DATABASE_URL uses async driver, e.g., postgresql+asyncpg://...
if "postgresql://" in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
    # Basic replacement, adjust if your URL is complex
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif not DATABASE_URL.startswith("postgresql+asyncpg"):
     # Consider raising an error or logging a warning for unsupported/unexpected formats
     print(f"Warning: DATABASE_URL format ({DATABASE_URL}) might not be compatible with asyncpg.")


# Create async engine
engine = create_async_engine(DATABASE_URL, echo=True) # Add echo=True for debugging

# Create async session factory
AsyncSessionFactory = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False # Recommended for FastAPI
)

Base = declarative_base()

# Async dependency for FastAPI routes
async def get_async_db() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        try:
            yield session
            # Decide commit/rollback strategy: either here or in service/route layer
            # Example: await session.commit()
        except Exception as e:
            await session.rollback()
            # Optionally re-raise or log the exception
            raise e
        finally:
            # Session is automatically closed by the context manager
            pass
