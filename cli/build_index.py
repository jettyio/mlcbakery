"""
Build Typesense Index CLI

This script rebuilds the Typesense search index from the database.

Prerequisites:
--------------
1. Cloud SQL Proxy: If using Cloud SQL, you need to run the Cloud SQL Auth Proxy:
   
   cloud-sql-proxy bakerydev:us-central1:bakery-prod
   
2. Environment Variables: Create a .env file with the following:

   # Database connection (use localhost when running Cloud SQL Proxy)
   DATABASE_URL="postgresql+asyncpg://postgres:YOUR_PASSWORD@0.0.0.0:5432/mlbakery"
   
   # Typesense configuration
   TYPESENSE_HOST=localhost           # Use 'search' inside Docker, 'localhost' for local dev
   TYPESENSE_PORT=8108
   TYPESENSE_PROTOCOL=http            # Use 'https' for production
   TYPESENSE_API_KEY=your_api_key
   TYPESENSE_COLLECTION_NAME=mlcbakery_entities

Usage:
------
   cd mlcbakery
   uv run python -m cli.build_index
"""

import os
import asyncio

from dotenv import load_dotenv
import argparse

load_dotenv()

from mlcbakery.search import rebuild_index


# --- Configuration from environment variables ---
DATABASE_URL = os.getenv("DATABASE_URL", "")
TYPESENSE_HOST = os.getenv("TYPESENSE_HOST", "search")
TYPESENSE_PORT = int(os.getenv("TYPESENSE_PORT", 8108))
TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY")
TYPESENSE_COLLECTION_NAME = os.getenv("TYPESENSE_COLLECTION_NAME", "mlcbakery_entities")


async def build_cli_index():
    """
    Command-line interface entry point to rebuild the Typesense index.
    Loads configuration from environment variables and calls the shared rebuild_index function.
    """
    if not DATABASE_URL:
        print("DATABASE_URL environment variable is not set. Exiting.")
        return
    if not TYPESENSE_API_KEY:
        print("TYPESENSE_API_KEY environment variable is not set. Exiting.")
        return
    if not TYPESENSE_COLLECTION_NAME:
        print("TYPESENSE_COLLECTION_NAME environment variable is not set. Exiting.")
        return

    print("Starting Typesense index build process via CLI...")
    try:
        await rebuild_index(
            db_url=DATABASE_URL,
            typesense_host=TYPESENSE_HOST,
            typesense_port=TYPESENSE_PORT,
            typesense_protocol=TYPESENSE_PROTOCOL,
            typesense_api_key=TYPESENSE_API_KEY,
            typesense_collection_name=TYPESENSE_COLLECTION_NAME,
        )
        print("Typesense index build process completed successfully via CLI.")
    except Exception as e:
        print(f"An error occurred during the index build process: {e}")


async def main():
    parser = argparse.ArgumentParser(
        description="Build Typesense index for MLC Bakery entities."
    )
    parser.parse_args()

    await build_cli_index()


if __name__ == "__main__":
    asyncio.run(main())
