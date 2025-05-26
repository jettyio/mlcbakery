import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import typesense  # Keep for exception types

from mlcbakery.models import Dataset, Entity, EntityRelationship
import argparse

from dotenv import load_dotenv

# Import from shared search module
from mlcbakery.search import (
    get_typesense_client,
    TYPESENSE_HOST,
    TYPESENSE_PORT,
    TYPESENSE_COLLECTION_NAME,
)  # Use shared client and constants

load_dotenv()  # Keep load_dotenv for DATABASE_URL

# --- Configuration ---
# REMOVE Typesense specific constants, they are now imported

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Use imported constant
COLLECTION_NAME = TYPESENSE_COLLECTION_NAME

# --- Typesense Client ---


# --- Database Setup (Async using SQLAlchemy) ---
# Add connect_args to disable prepared statement caching for pgbouncer compatibility
engine = create_async_engine(
    DATABASE_URL, echo=False, connect_args={"statement_cache_size": 0}
)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# --- Typesense Schema Definition ---
schema = {
    "name": COLLECTION_NAME,
    "enable_nested_fields": True,
    "fields": [
        # Document ID will be collection_name/dataset_name
        {"name": "id", "type": "string"},
        {"name": "collection_name", "type": "string", "facet": True},
        {"name": "dataset_name", "type": "string", "facet": True},
        {"name": "full_name", "type": "string"},
        {"name": "long_description", "type": "string", "optional": True},
        {"name": "metadata", "type": "object", "optional": True},
        {
            "name": "created_at_timestamp",
            "type": "int64",
            "optional": True,
            "sort": True,
        },
    ],
}

# TODO: Define a new schema for Trained Models if using a separate collection
# trained_model_schema = {
#     "name": "trained_models_collection", # Or your preferred name
#     "fields": [
#         {"name": "id", "type": "string"}, # e.g., collection_name/model_name
#         {"name": "collection_name", "type": "string", "facet": True},
#         {"name": "model_name", "type": "string", "facet": True},
#         {"name": "full_name", "type": "string"},
#         {"name": "long_description", "type": "string", "optional": True},
#         {"name": "model_path", "type": "string"},
#         {"name": "asset_origin", "type": "string", "optional": True},
#         {"name": "model_metadata", "type": "object", "optional": True},
#         {"name": "model_attributes", "type": "object", "optional": True},
#         {"name": "created_at_timestamp", "type": "int64", "optional": True, "sort": True},
#         {"name": "entity_type", "type": "string", "default": "trained_model"}, # Helpful for multi-collection searches client-side
#     ],
#     "enable_nested_fields": True
# }


async def get_all_datasets(db: AsyncSession):
    """Fetches all datasets with their collections from the database."""
    stmt = (
        select(Dataset)
        .options(
            selectinload(Dataset.collection),
            selectinload(Dataset.upstream_links).options(
                selectinload(EntityRelationship.source_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
            selectinload(Dataset.downstream_links).options(
                selectinload(EntityRelationship.target_entity).options(
                    selectinload(Entity.collection)
                ),
            ),
        )
    )
    result = await db.execute(stmt)
    # Use unique() because eager loading might cause duplicate parent rows
    datasets = result.scalars().unique().all()
    return datasets


# TODO: Create a new function get_all_trained_models(db: AsyncSession) similar to get_all_datasets
# async def get_all_trained_models(db: AsyncSession):
#     # from mlcbakery.models import TrainedModel # Make sure to import TrainedModel
#     stmt = (
#         select(TrainedModel) # Assuming TrainedModel is imported from mlcbakery.models
#         .options(
#             selectinload(TrainedModel.collection), # Ensure relationships are loaded
#             # Add other necessary selectinload options for model-specific data
#             # e.g., selectinload(TrainedModel.input_entities), selectinload(TrainedModel.output_entities)
#         )
#     )
#     result = await db.execute(stmt)
#     models = result.scalars().unique().all()
#     return models


async def build_index():
    """Flushes and rebuilds the Typesense index with data from the database."""
    # Use imported client instance
    ts_client = get_typesense_client()
    if not ts_client:
        print(
            "Typesense client is not initialized (check search.py and environment variables). Exiting."
        )
        return

    print(f"Connecting to Typesense at {TYPESENSE_HOST}:{TYPESENSE_PORT}...")
    try:
        # Use the client directly, health check is optional here
        health = ts_client.operations.is_healthy()
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
    # TODO: Repeat deletion for trained_models_collection if using a separate one
    # try:
    #     # from mlcbakery.search import TRAINED_MODEL_COLLECTION_NAME # Define and use this constant
    #     ts_client.collections["trained_models_collection"].delete() # Or use constant
    #     print(f"Collection 'trained_models_collection' deleted.")
    # except typesense.exceptions.ObjectNotFound:
    #     print(f"Collection 'trained_models_collection' does not exist, creating new one.")
    # except Exception as e:
    #     print(f"Error deleting trained model collection: {e}")

    # 2. Create new collection
    print(f"Creating collection '{COLLECTION_NAME}'...")
    try:
        ts_client.collections.create(schema)
        print(f"Collection '{COLLECTION_NAME}' created successfully.")
    except typesense.exceptions.RequestError as e:
        if "already exists" in str(
            e
        ):  # Handle race condition or if deletion failed silently
            print(
                f"Collection '{COLLECTION_NAME}' already exists. Attempting to proceed with indexing."
            )
        else:
            print(f"Error creating collection: {e}")
            return  # Exit if creation fails for other reasons
    except Exception as e:
        print(f"Error creating collection: {e}")
        return  # Exit if creation fails
    # TODO: Repeat creation for trained_models_collection if using a separate one
    # try:
    #     # ts_client.collections.create(trained_model_schema) # Assuming trained_model_schema is defined
    #     # print(f"Collection 'trained_models_collection' created successfully.")
    # except typesense.exceptions.RequestError as e:
    #     if "already exists" in str(e):
    #         print(f"Collection 'trained_models_collection' already exists.")
    #     else:
    #         print(f"Error creating trained model collection: {e}")
    #         return
    # except Exception as e:
    #     print(f"Error creating trained model collection: {e}")
    #     return

    # 3. Fetch data from database
    print("Fetching datasets from database...")
    documents_to_index = [] # This will hold dataset documents
    # TODO: Create a separate list for trained model documents if indexing them
    # model_documents_to_index = []

    async with AsyncSessionLocal() as db:
        try:
            datasets = await get_all_datasets(db)
            print(f"Found {len(datasets)} datasets.")

            for dataset in datasets:
                if not dataset.collection:  # Safety check
                    print(
                        f" Skipping dataset ID {dataset.id} (name: {dataset.name}) due to missing collection."
                    )
                    continue

                print(f" Processing dataset: {dataset.collection.name}/{dataset.name}")
                doc_id = f"{dataset.collection.name}/{dataset.name}"
                document = {
                    "id": doc_id,
                    "collection_name": dataset.collection.name,
                    "dataset_name": dataset.name, # TODO: Consider renaming to entity_name if generalizing schema for multiple entity types
                    "full_name": doc_id, 
                    "long_description": dataset.long_description,
                    "metadata": dataset.dataset_metadata or None, 
                    "created_at_timestamp": int(dataset.created_at.timestamp())
                    if dataset.created_at
                    else None,
                    # TODO: Add "entity_type": "dataset" if generalizing the schema
                }
                document = {k: v for k, v in document.items() if v is not None}
                documents_to_index.append(document)

            # TODO: Fetch and process trained models
            # # from mlcbakery.models import TrainedModel # Ensure TrainedModel is imported if not done globally for the script
            # trained_models = await get_all_trained_models(db) # Assumes get_all_trained_models is defined
            # print(f"Found {len(trained_models)} trained models.")
            # for model in trained_models:
            #     if not model.collection:
            #         print(f" Skipping model ID {model.id} (name: {model.name}) due to missing collection.")
            #         continue
            #     print(f" Processing model: {model.collection.name}/{model.name}")
            #     model_doc_id = f"{model.collection.name}/{model.name}"
            #     model_document = {
            #         "id": model_doc_id,
            #         "collection_name": model.collection.name,
            #         "model_name": model.name, # Or "entity_name": model.name if generalizing schema
            #         "full_name": model_doc_id,
            #         "long_description": model.long_description,
            #         "model_path": model.model_path,
            #         "asset_origin": model.asset_origin,
            #         "model_metadata": model.model_metadata or None,
            #         "model_attributes": model.model_attributes or None,
            #         "created_at_timestamp": int(model.created_at.timestamp()) if model.created_at else None,
            #         "entity_type": "trained_model", # Crucial if using a combined collection
            #     }
            #     model_document = {k: v for k, v in model_document.items() if v is not None}
            #     # if using separate list: model_documents_to_index.append(model_document)
            #     # if using combined list: documents_to_index.append(model_document)

        except Exception as e:
            print(f"Error fetching data from database: {e}")
            return  # Exit if data fetching fails

    # 4. Index documents
    print(f"Indexing {len(documents_to_index)} documents...")
    if documents_to_index:
        try:
            # Index in batches for large datasets
            batch_size = 100
            for i in range(0, len(documents_to_index), batch_size):
                batch = documents_to_index[i : i + batch_size]
                results = ts_client.collections[COLLECTION_NAME].documents.import_(
                    batch, {"action": "upsert"}
                )
                # Simple error checking for the batch import result
                errors = [res for res in results if not res["success"]]
                if errors:
                    print(f"WARNING: Errors occurred during batch import: {errors}")
                    # Optionally log the specific documents that failed
                print(f" Indexed batch {i // batch_size + 1} for datasets...")

            print("Dataset indexing complete.")
        except Exception as e:
            print(f"Error indexing dataset documents: {e}")
    else:
        print("No dataset documents to index.")

    # TODO: Index trained model documents
    # # print(f"Indexing {len(model_documents_to_index)} trained model documents...") # Assuming model_documents_to_index is populated
    # # if model_documents_to_index:
    # #     try:
    # #         batch_size = 100
    # #         for i in range(0, len(model_documents_to_index), batch_size):
    # #             batch = model_documents_to_index[i : i + batch_size]
    # #             # Index into the new collection or the generalized existing one
    # #             # collection_target = "trained_models_collection" # if separate, and TRAINED_MODEL_COLLECTION_NAME constant defined
    # #             collection_target = COLLECTION_NAME # if combined and schema supports it
    # #             results = ts_client.collections[collection_target].documents.import_(
    # #                 batch, {"action": "upsert"}
    # #             )
    # #             errors = [res for res in results if not res["success"]]
    # #             if errors:
    # #                 print(f"WARNING: Errors occurred during batch import for models: {errors}")
    # #             print(f" Indexed batch {i // batch_size + 1} for trained models...")
    # #         print("Trained model indexing complete.")
    # #     except Exception as e:
    # #         print(f"Error indexing trained model documents: {e}")
    # # else:
    # #     print("No trained model documents to index.")


async def main():
    parser = argparse.ArgumentParser(
        description="Build Typesense index for MLC Bakery datasets."
    )
    # Add any specific command-line arguments if needed
    parser.parse_args()

    await build_index()


if __name__ == "__main__":
    asyncio.run(main())
