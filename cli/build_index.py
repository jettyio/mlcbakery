import os
import asyncio
import typesense # Keep for exception types, though direct use is reduced

from dotenv import load_dotenv
import argparse

# Import the new rebuild_index function and necessary components from search
from mlcbakery.search import (
    rebuild_index,
    TYPESENSE_HOST_ENV,
    TYPESENSE_PORT_ENV,
    TYPESENSE_PROTOCOL_ENV,
    TYPESENSE_API_KEY_ENV,
    TYPESENSE_COLLECTION_NAME_ENV, # Use the env var from search.py as default
)

load_dotenv()

# --- Configuration ---
DATABASE_URL = os.getenv("DATABASE_URL", "")
# Typesense connection details will be sourced from mlcbakery.search constants (which read from env)

async def build_cli_index():
    """
    Command-line interface entry point to rebuild the Typesense index.
    Loads configuration from environment variables and calls the shared rebuild_index function.
    """
    if not DATABASE_URL:
        print("DATABASE_URL environment variable is not set. Exiting.")
        return
    if not TYPESENSE_API_KEY_ENV: # Check if API key is set via the imported constant
        print("TYPESENSE_API_KEY environment variable is not set. Exiting.")
        return
    if not TYPESENSE_COLLECTION_NAME_ENV:
        print("TYPESENSE_COLLECTION_NAME environment variable is not set. Exiting.")
        return

    print("Starting Typesense index build process via CLI...")
    try:
        await rebuild_index(
            db_url=DATABASE_URL,
            typesense_host=TYPESENSE_HOST_ENV,
            typesense_port=TYPESENSE_PORT_ENV,
            typesense_protocol=TYPESENSE_PROTOCOL_ENV,
            typesense_api_key=TYPESENSE_API_KEY_ENV,
            typesense_collection_name=TYPESENSE_COLLECTION_NAME_ENV,
        )
        print("Typesense index build process completed successfully via CLI.")
    except Exception as e:
        print(f"An error occurred during the index build process: {e}")
        # Potentially exit with a non-zero status code
        # import sys
        # sys.exit(1)

async def main():
    parser = argparse.ArgumentParser(
        description="Build Typesense index for MLC Bakery entities."
    )
    # Add any CLI-specific arguments here if needed in the future
    # For now, all config is via environment variables for simplicity
    parser.parse_args()

    await build_cli_index()

if __name__ == "__main__":
    asyncio.run(main())
