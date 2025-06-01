import os
import typesense
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()  # Load environment variables from .env file if present

TYPESENSE_HOST = os.getenv(
    "TYPESENSE_HOST", "search"
)  # Default to service name inside docker
TYPESENSE_PORT = int(os.getenv("TYPESENSE_PORT", 8108))
TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY")
TYPESENSE_COLLECTION_NAME = os.getenv("TYPESENSE_COLLECTION_NAME")


def get_typesense_client() -> typesense.Client:
    """FastAPI dependency to provide the Typesense client."""

    # Initialize Typesense client
    try:
        ts_client = typesense.Client(
            {
                "nodes": [
                    {
                        "host": TYPESENSE_HOST,
                        "port": TYPESENSE_PORT,
                        "protocol": TYPESENSE_PROTOCOL,
                    }
                ],
                "api_key": TYPESENSE_API_KEY,
                "connection_timeout_seconds": 5,
            }
        )
        # Optional: Perform an initial health check during startup
        print(
            f"Typesense client initialized successfully to {TYPESENSE_HOST}:{TYPESENSE_PORT}"
        )
        return ts_client
    except Exception as e:
        print(
            f"Failed to initialize Typesense client: {e}"
        )  # Replace with proper logging
        # Decide how to handle startup failure (e.g., exit, log warning)
        ts_client = None  # Ensure ts_client is defined even on failure

    if ts_client is None:
        # Handle case where client initialization failed at startup
        raise HTTPException(status_code=503, detail="Typesense client not initialized")

async def run_search_query(search_parameters: dict, ts: typesense.Client) -> dict:
    """Run a search query against Typesense."""    
    try:
        search_results = ts.collections[TYPESENSE_COLLECTION_NAME].documents.search(
            search_parameters
        )
        return {"hits": search_results["hits"]}
    except typesense.exceptions.ObjectNotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Typesense collection '{TYPESENSE_COLLECTION_NAME}' not found. Please build the index first.",
        )
    except typesense.exceptions.TypesenseClientError as e:
        print(f"Typesense API error: {e}")
        raise HTTPException(status_code=500, detail=f"Typesense search failed: {e}")
    except Exception as e:
        print(f"Unexpected error during Typesense search: {e}")
        raise HTTPException(
            status_code=500, detail="An unexpected error occurred during search"
        )
