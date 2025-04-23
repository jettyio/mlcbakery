import os # Import os module
import asyncio # Import asyncio
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine # Import async engine creator

from alembic import context

# Import your models here
from mlcbakery.database import Base
from mlcbakery.models import Entity, TrainedModel, Activity, Dataset

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Set the database URL from the environment variable
# This overrides the value in alembic.ini if it exists
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    raise ValueError("DATABASE_URL environment variable not set for Alembic")
config.set_main_option('sqlalchemy.url', db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # url = config.get_main_option("sqlalchemy.url") # No longer needed, set above
    context.configure(
        # url=url, # Use url directly from config object
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # Get the engine configuration from alembic.ini
    # config object already has the URL set from environment variable
    url = config.get_main_option("sqlalchemy.url")
    if not url:
         raise ValueError("Database URL not found in Alembic config or environment.")

    # Create an async engine
    connectable = create_async_engine(url, poolclass=pool.NullPool)

    # Define the migration function to be run synchronously
    def do_run_migrations(connection):
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    # Define the main async task
    async def async_run_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)

        # Dispose the engine
        await connectable.dispose()

    # Run the async task
    asyncio.run(async_run_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
