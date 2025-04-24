import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import typesense # Keep for exception types

from mlcbakery.models import Collection, Dataset, Activity, Entity # Import necessary models
import argparse
import json
from dotenv import load_dotenv

# Import from shared search module
from mlcbakery.search import ts_client, TYPESENSE_HOST, TYPESENSE_PORT, TYPESENSE_COLLECTION_NAME, TYPESENSE_API_KEY # Use shared client and constants

load_dotenv() # Keep load_dotenv for DATABASE_URL

# --- Configuration ---
# REMOVE Typesense specific constants, they are now imported
# TYPESENSE_HOST = ...
# TYPESENSE_PORT = ...
# TYPESENSE_PROTOCOL = ...
# TYPESENSE_API_KEY = ...
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Use imported constant
COLLECTION_NAME = TYPESENSE_COLLECTION_NAME

# --- Typesense Client ---
# REMOVE client initialization, it's now imported
# ts_client = typesense.Client({...})

# --- Database Setup (Async using SQLAlchemy) ---
engine = create_async_engine(DATABASE_URL, echo=False) # Set echo=True for debugging SQL
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- Typesense Schema Definition ---
schema = {
    'name': COLLECTION_NAME,
    'enable_nested_fields': True,
    'fields': [
        # Document ID will be collection_name/dataset_name
        {'name': 'id', 'type': 'string'}, 
        {'name': 'collection_name', 'type': 'string', 'facet': True},
        {'name': 'dataset_name', 'type': 'string', 'facet': True},
        {'name': 'full_name', 'type': 'string'}, 
        # Adding authors and other fields from the model if needed/available
        # {'name': 'authors', 'type': 'string[]', 'optional': True}, 
        {'name': 'long_description', 'type': 'string', 'optional': True},
        {'name': 'metadata', 'type': 'object', 'optional': True}, 
        # Add created_at as timestamp for potential sorting
        {'name': 'created_at_timestamp', 'type': 'int64', 'optional': True, 'sort': True}, 
        # Consider adding updated_at if available and useful for sorting
        # {'name': 'updated_at_timestamp', 'type': 'int64', 'optional': True, 'sort': True}, 
    ],
}

async def get_all_datasets(db: AsyncSession):
    """Fetches all datasets with their collections from the database."""
    stmt = (
        select(Dataset)
        # Eager load the collection relationship to avoid separate queries per dataset
        .options(selectinload(Dataset.collection))
        # Eager load activities if you plan to index related info (e.g., agent names)
        # .options(selectinload(Dataset.input_activities).selectinload(Activity.agents))
        # .options(selectinload(Dataset.output_activities).selectinload(Activity.agents))
        .where(Dataset.entity_type == 'dataset') # Ensure we only get Datasets
    )
    result = await db.execute(stmt)
    # Use unique() because eager loading might cause duplicate parent rows
    datasets = result.scalars().unique().all()
    return datasets

async def build_index():
    """Flushes and rebuilds the Typesense index with data from the database."""
    # Use imported client instance
    if not ts_client:
        print("Typesense client is not initialized (check search.py and environment variables). Exiting.")
        return
        
    print(f"Connecting to Typesense at {TYPESENSE_HOST}:{TYPESENSE_PORT}...")
    try:
        # Use the client directly, health check is optional here
        health = ts_client.health.retrieve() 
        print(f"Typesense health: {health}")
    except Exception as e:
        print(f"Error connecting to Typesense: {e}")
        return

    # 1. Delete existing collection if it exists
    print(f"Checking for existing collection '{COLLECTION_NAME}'...")
    try:
        ts_client.collections[COLLECTION_NAME].delete()
        print(f"Collection '{COLLECTION_NAME}' deleted.")
    except typesense.exceptions.ObjectNotFound:
        print(f"Collection '{COLLECTION_NAME}' does not exist, creating new one.")
    except Exception as e:
        print(f"Error deleting collection: {e}")
        # Decide if you want to proceed or exit

    # 2. Create new collection
    print(f"Creating collection '{COLLECTION_NAME}'...")
    try:
        ts_client.collections.create(schema)
        print(f"Collection '{COLLECTION_NAME}' created successfully.")
    except typesense.exceptions.RequestError as e:
         if "already exists" in str(e): # Handle race condition or if deletion failed silently
             print(f"Collection '{COLLECTION_NAME}' already exists. Attempting to proceed with indexing.")
         else:
            print(f"Error creating collection: {e}")
            return # Exit if creation fails for other reasons
    except Exception as e:
        print(f"Error creating collection: {e}")
        return # Exit if creation fails

    # 3. Fetch data from database
    print("Fetching datasets from database...")
    documents_to_index = []
    async with AsyncSessionLocal() as db:
        try:
            datasets = await get_all_datasets(db)
            print(f"Found {len(datasets)} datasets.")

            for dataset in datasets:
                if not dataset.collection: # Safety check
                    print(f" Skipping dataset ID {dataset.id} (name: {dataset.name}) due to missing collection.")
                    continue
                    
                print(f" Processing dataset: {dataset.collection.name}/{dataset.name}")
                # Construct the document for Typesense
                doc_id = f"{dataset.collection.name}/{dataset.name}"
                document = {
                    'id': doc_id,
                    'collection_name': dataset.collection.name,
                    'dataset_name': dataset.name,
                    'full_name': doc_id, # Redundant but matches API query_by
                    'long_description': dataset.long_description,
                    'metadata': dataset.dataset_metadata or {}, # Ensure it's an object, not None
                    'created_at_timestamp': int(dataset.created_at.timestamp()) if dataset.created_at else None,
                    # Add other fields as needed based on the schema
                }
                # Filter out None values for optional fields to avoid errors
                document = {k: v for k, v in document.items() if v is not None}
                documents_to_index.append(document)

        except Exception as e:
            print(f"Error fetching data from database: {e}")
            return # Exit if data fetching fails

    # 4. Index documents
    print(f"Indexing {len(documents_to_index)} documents...")
    if documents_to_index:
        try:
            # Index in batches for large datasets
            batch_size = 100 
            for i in range(0, len(documents_to_index), batch_size):
                batch = documents_to_index[i:i+batch_size]
                results = ts_client.collections[COLLECTION_NAME].documents.import_(batch, {'action': 'upsert'})
                # Simple error checking for the batch import result
                errors = [res for res in results if not res['success']]
                if errors:
                    print(f"WARNING: Errors occurred during batch import: {errors}")
                    # Optionally log the specific documents that failed
                print(f" Indexed batch {i//batch_size + 1}...")

            print("Indexing complete.")
        except Exception as e:
            print(f"Error indexing documents: {e}")
    else:
        print("No documents to index.")

async def main():
    parser = argparse.ArgumentParser(description="Build Typesense index for MLC Bakery datasets.")
    # Add any specific command-line arguments if needed
    args = parser.parse_args()

    await build_index()

if __name__ == "__main__":
    asyncio.run(main()) 