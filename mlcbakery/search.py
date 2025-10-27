import os
import json
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import typesense
from dotenv import load_dotenv
from fastapi import HTTPException

from mlcbakery.models import Dataset, Entity, EntityRelationship, TrainedModel

def setup_and_get_typesense_client():
    """Setup the Typesense client."""
    load_dotenv()
    TYPESENSE_HOST_ENV = os.getenv(
        "TYPESENSE_HOST", "search"
    )  # Default to service name inside docker
    TYPESENSE_PORT_ENV = int(os.getenv("TYPESENSE_PORT", 8108))
    TYPESENSE_PROTOCOL_ENV = os.getenv("TYPESENSE_PROTOCOL", "http")
    TYPESENSE_API_KEY_ENV = os.getenv("TYPESENSE_API_KEY")
    return get_typesense_client(
        host=TYPESENSE_HOST_ENV,
        port=TYPESENSE_PORT_ENV,
        protocol=TYPESENSE_PROTOCOL_ENV,
        api_key=TYPESENSE_API_KEY_ENV,
    )

def get_typesense_client(
    host: str | None = None,
    port: int | None = None,
    protocol: str | None = None,
    api_key: str | None = None,
) -> typesense.Client:
    """FastAPI dependency to provide the Typesense client.
    Can also be used directly by passing connection parameters.
    """
    resolved_host = host 
    resolved_port = port
    resolved_protocol = protocol
    resolved_api_key = api_key

    if not resolved_api_key:
        print("Typesense API key is not configured. Cannot initialize client.")
        # For direct calls, we might want to raise an error or return None
        # For FastAPI, it might be handled differently by the dependency injection
        raise ValueError("Typesense API key must be provided either as a parameter or via TYPESENSE_API_KEY environment variable.")

    # Initialize Typesense client
    try:
        ts_client = typesense.Client(
            {
                "nodes": [
                    {
                        "host": resolved_host,
                        "port": resolved_port,
                        "protocol": resolved_protocol,
                    }
                ],
                "api_key": resolved_api_key,
                "connection_timeout_seconds": 5,
            }
        )
        # Optional: Perform an initial health check during startup
        print(
            f"Typesense client initialized successfully to {resolved_host}:{resolved_port}"
        )
        return ts_client
    except Exception as e:
        print(
            f"Failed to initialize Typesense client: {e}"
        )  # Replace with proper logging
        # Decide how to handle startup failure (e.g., exit, log warning)
        # For FastAPI context, raising HTTPException might be appropriate if this is used as a dependency
        # For direct calls, re-raising or returning None could be options
        raise RuntimeError(f"Failed to initialize Typesense client: {e}")


# --- Typesense Schema Definition ---
# This schema will be used by the rebuild_index function.
# The collection name will be passed as a parameter to rebuild_index.
def get_typesense_schema(collection_name: str) -> dict:
    return {
        "name": collection_name,
        "enable_nested_fields": True,
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "asset_origin", "type": "string", "optional": True},
            {"name": "collection_name", "type": "string", "facet": True},
            {"name": "collection_id", "type": "int32", "facet": True},
            {"name": "entity_name", "type": "string", "facet": True},
            {"name": "full_name", "type": "string"},
            {"name": "entity_type", "type": "string", "default": "dataset", "facet": True},
            {"name": "is_private", "type": "bool", "facet": True},
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
    datasets = result.scalars().unique().all()
    return datasets

async def get_all_trained_models(db: AsyncSession):
    """Fetches all trained models with their collections from the database."""
    stmt = (
        select(TrainedModel)
        .options(
            selectinload(TrainedModel.collection),
            # Add other necessary selectinload options for model-specific data
            # e.g., selectinload(TrainedModel.input_entities), selectinload(TrainedModel.output_entities)
        )
    )
    result = await db.execute(stmt)
    models = result.scalars().unique().all()
    return models


async def rebuild_index(
    db_url: str,
    typesense_host: str,
    typesense_port: int,
    typesense_protocol: str,
    typesense_api_key: str,
    typesense_collection_name: str,
):
    """Flushes and rebuilds the Typesense index with data from the database."""
    
    print(f"Attempting to rebuild index for collection: {typesense_collection_name} using Typesense at {typesense_host}:{typesense_port}")

    ts_client = get_typesense_client(
        host=typesense_host,
        port=typesense_port,
        protocol=typesense_protocol,
        api_key=typesense_api_key,
    )

    print(f"Connecting to Typesense at {typesense_host}:{typesense_port}...")
    try:
        health = ts_client.operations.is_healthy()
        print(f"Typesense health: {health}")
    except Exception as e:
        print(f"Error connecting to Typesense: {e}")
        raise  # Re-raise to indicate failure

    # 1. Delete existing collection if it exists
    print(f"Checking for existing collection '{typesense_collection_name}'...")
    try:
        ts_client.collections[typesense_collection_name].delete()
        print(f"Collection '{typesense_collection_name}' deleted.")
    except typesense.exceptions.ObjectNotFound:
        print(f"Collection '{typesense_collection_name}' does not exist, will create a new one.")
    except Exception as e:
        print(f"Error deleting collection '{typesense_collection_name}': {e}")
        # Depending on policy, might want to raise here or attempt to proceed cautiously
        raise

    # 2. Create new collection
    schema = get_typesense_schema(typesense_collection_name)
    print(f"Creating collection '{typesense_collection_name}' with schema: {json.dumps(schema, indent=2)}")
    try:
        ts_client.collections.create(schema)
        print(f"Collection '{typesense_collection_name}' created successfully.")
    except typesense.exceptions.RequestError as e:
        if "already exists" in str(e).lower():
            print(
                f"Collection '{typesense_collection_name}' already exists (race condition or failed deletion). Attempting to proceed."
            )
        else:
            print(f"Error creating collection '{typesense_collection_name}': {e}")
            raise
    except Exception as e:
        print(f"Unexpected error creating collection '{typesense_collection_name}': {e}")
        raise

    # 3. Fetch data from database
    print("Fetching data from database...")
    documents_to_index = []

    # Database Setup (Async using SQLAlchemy)
    engine = create_async_engine(
        db_url, echo=False, connect_args={"statement_cache_size": 0} # For pgbouncer
    )
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with AsyncSessionLocal() as db:
        try:
            datasets = await get_all_datasets(db)
            print(f"Found {len(datasets)} datasets.")
            for dataset in datasets:
                if not dataset.collection:
                    print(f" Skipping dataset ID {dataset.id} (name: {dataset.name}) due to missing collection.")
                    continue
                
                print(f" Processing dataset: {dataset.collection.name}/{dataset.name}")
                doc_id = f"{dataset.entity_type}/{dataset.collection.name}/{dataset.name}"
                
                metadata = dataset.dataset_metadata or {}
                # Ensure metadata keys don't contain '@' which is problematic for some systems or if used in field names
                # And ensure values are strings, as per original logic for dataset_metadata
                processed_metadata = {
                    k.replace("@", "__"): v 
                    for k, v in metadata.items() 
                    if isinstance(v, (str, int, float, bool)) # Allow basic types, convert others to string or skip
                }
                # Convert non-string simple types to string if schema expects string, or handle type mapping.
                # For simplicity here, assuming string or typesense handles conversion for 'object'.
                # Original code filtered for isinstance(v, str) for dataset.dataset_metadata.
                # If specific fields in metadata need to be typed, schema needs to be more detailed or data cleaned accordingly.
                
                document = {
                    "id": doc_id,
                    "collection_name": dataset.collection.name,
                    "collection_id": dataset.collection.id,
                    "entity_name": dataset.name,
                    "full_name": doc_id,
                    "is_private": dataset.is_private if dataset.is_private is not None else True,
                    "long_description": dataset.long_description,
                    "metadata": processed_metadata or None,
                    "created_at_timestamp": int(dataset.created_at.timestamp()) if dataset.created_at else None,
                    "entity_type": "dataset", # Explicitly set from dataset.entity_type if available and different
                }
                document = {k: v for k, v in document.items() if v is not None}
                documents_to_index.append(document)

            trained_models = await get_all_trained_models(db)
            print(f"Found {len(trained_models)} trained models.")
            for model in trained_models:
                if not model.collection:
                    print(f" Skipping model ID {model.id} (name: {model.name}) due to missing collection.")
                    continue

                print(f" Processing trained model: {model.collection.name}/{model.name}")
                doc_id = f"{model.entity_type}/{model.collection.name}/{model.name}"
                
                model_meta = model.model_metadata or {}
                processed_model_meta = {
                    k.replace("@", "__"): v 
                    for k, v in model_meta.items()
                    if isinstance(v, (str, int, float, bool)) # Similar processing for model metadata
                }

                document = {
                    "id": doc_id,
                    "collection_name": model.collection.name,
                    "collection_id": model.collection.id,
                    "entity_name": model.name,
                    "full_name": doc_id,
                    "is_private": model.is_private if model.is_private is not None else True,
                    "long_description": model.long_description,
                    "metadata": processed_model_meta or None,
                    "created_at_timestamp": int(model.created_at.timestamp()) if model.created_at else None,
                    "entity_type": "trained_model", # Explicitly set from model.entity_type
                }
                document = {k: v for k, v in document.items() if v is not None}
                documents_to_index.append(document)

        except Exception as e:
            print(f"Error fetching data from database: {e}")
            await engine.dispose() # Clean up engine resources on error
            raise
        finally:
            await engine.dispose() # Ensure engine is disposed

    # 4. Index documents
    print(f"Indexing {len(documents_to_index)} documents into '{typesense_collection_name}'...")
    if documents_to_index:
        try:
            batch_size = 100
            for i in range(0, len(documents_to_index), batch_size):
                batch = documents_to_index[i : i + batch_size]
                results = ts_client.collections[typesense_collection_name].documents.import_(
                    batch, {"action": "upsert"}
                )
                errors = [res for res in results if not res.get("success")]
                if errors:
                    print(f"WARNING: Errors occurred during batch import into '{typesense_collection_name}': {errors}")
                else:
                    print(f" Indexed batch {i // batch_size + 1} successfully into '{typesense_collection_name}'.")
            print(f"Indexing for '{typesense_collection_name}' complete.")
        except Exception as e:
            print(f"Error indexing documents into '{typesense_collection_name}': {e}")
            raise
    else:
        print(f"No documents to index for '{typesense_collection_name}'.")

def build_privacy_filter(user_collection_id: int | list[int] | None) -> str:
    """Generate Typesense filter clause for user's accessible entities.

    Returns filter that includes:
    - All public entities (is_private:false)
    - User's own private entities (is_private:true && collection_id:user_collection_id(s))

    Args:
        user_collection_id: The ID(s) of the user's collection(s), or None for admin/no-auth
                           Can be a single int or a list of ints

    Returns:
        Typesense filter string for privacy filtering
    """
    if user_collection_id is None:
        # Admin or no-auth: no privacy filter (see all entities)
        return ""

    # Handle both single ID and list of IDs
    if isinstance(user_collection_id, list):
        # Multiple collections: (is_private:false) || (is_private:true && collection_id:[id1,id2,...])
        collection_ids = ",".join(str(id) for id in user_collection_id)
        return f"(is_private:false) || (is_private:true && collection_id:[{collection_ids}])"
    else:
        # Single collection: (is_private:false) || (is_private:true && collection_id:id)
        return f"(is_private:false) || (is_private:true && collection_id:{user_collection_id})"

async def index_entity_to_typesense(entity: Dataset | TrainedModel, ts: typesense.Client | None = None) -> bool:
    """Index a single entity to Typesense with privacy metadata.

    This function is used to index newly created or updated entities so they
    appear immediately in search results without waiting for a full re-index.

    Args:
        entity: The Dataset or TrainedModel entity to index
        ts: Optional Typesense client. If not provided, creates a new one.

    Returns:
        True if indexing succeeded, False if it failed or was skipped.
    """
    try:
        load_dotenv()

        # Get or create Typesense client
        if ts is None:
            ts = setup_and_get_typesense_client()

        collection_to_index = os.getenv("TYPESENSE_COLLECTION_NAME", "mlcbakery_entities")
        if not collection_to_index:
            print("Typesense collection name not configured. Skipping indexing.")
            return False

        # Check if entity has required relationships loaded
        if not hasattr(entity, "collection") or entity.collection is None:
            print(f"Entity {entity.id} missing collection. Skipping indexing.")
            return False

        # Build document
        doc_id = f"{entity.entity_type}/{entity.collection.name}/{entity.name}"
        metadata = {}

        if isinstance(entity, Dataset):
            metadata = entity.dataset_metadata or {}
        elif isinstance(entity, TrainedModel):
            metadata = entity.model_metadata or {}

        # Process metadata to ensure valid types
        processed_metadata = {
            k.replace("@", "__"): v
            for k, v in metadata.items()
            if isinstance(v, (str, int, float, bool))
        }

        document = {
            "id": doc_id,
            "collection_name": entity.collection.name,
            "collection_id": entity.collection.id,
            "entity_name": entity.name,
            "full_name": doc_id,
            "is_private": entity.is_private if entity.is_private is not None else True,
            "long_description": entity.long_description,
            "metadata": processed_metadata or None,
            "created_at_timestamp": int(entity.created_at.timestamp()) if entity.created_at else None,
            "entity_type": entity.entity_type,
        }

        # Remove None values
        document = {k: v for k, v in document.items() if v is not None}

        # Index the document
        result = ts.collections[collection_to_index].documents.upsert(document)

        if result.get("success"):
            print(f"Successfully indexed entity {doc_id}")
            return True
        else:
            print(f"Failed to index entity {doc_id}: {result}")
            return False

    except Exception as e:
        print(f"Error indexing entity to Typesense: {e}")
        # Don't raise - log and continue to avoid blocking entity creation
        return False

async def run_search_query(search_parameters: dict, ts: typesense.Client) -> dict:
    """Run a search query against Typesense."""
    load_dotenv()
    collection_to_search = os.getenv("TYPESENSE_COLLECTION_NAME", "mlcbakery_entities")
    if not collection_to_search:
        raise HTTPException(status_code=500, detail="Typesense collection name not configured for search.")

    try:
        search_results = ts.collections[collection_to_search].documents.search(
            search_parameters
        )
        return {"hits": search_results["hits"]}
    except typesense.exceptions.ObjectNotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Typesense collection '{collection_to_search}' not found. Please build the index first.",
        )
    except typesense.exceptions.TypesenseClientError as e:
        print(f"Typesense API error: {e}")
        raise HTTPException(status_code=500, detail=f"Typesense search failed: {e}")
    except Exception as e:
        print(f"Unexpected error during Typesense search: {e}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred during search"
        )
