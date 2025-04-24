import os
import typesense
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv() # Load environment variables from .env file if present

TYPESENSE_HOST = os.getenv("TYPESENSE_HOST", "search") # Default to service name inside docker
TYPESENSE_PORT = int(os.getenv("TYPESENSE_PORT", 8108))
TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY")
TYPESENSE_COLLECTION_NAME = os.getenv("TYPESENSE_COLLECTION_NAME")

# Initialize Typesense client
try:
    ts_client = typesense.Client({
        'nodes': [{
            'host': TYPESENSE_HOST,
            'port': TYPESENSE_PORT,
            'protocol': TYPESENSE_PROTOCOL
        }],
        'api_key': TYPESENSE_API_KEY,
        'connection_timeout_seconds': 5
    })
    # Optional: Perform an initial health check during startup
    # ts_client.health.retrieve()
    print(f"Typesense client initialized successfully to {TYPESENSE_HOST}:{TYPESENSE_PORT}")
except Exception as e:
    print(f"Failed to initialize Typesense client: {e}") # Replace with proper logging
    # Decide how to handle startup failure (e.g., exit, log warning)
    ts_client = None # Ensure ts_client is defined even on failure


async def get_typesense_client():
    """FastAPI dependency to provide the Typesense client."""
    if ts_client is None:
         # Handle case where client initialization failed at startup
         raise HTTPException(status_code=503, detail="Typesense client not initialized")
    # You might add more robust health checks here if needed
    try:
        # Quick health check before returning the client? Depends on performance needs.
        # ts_client.health.retrieve() # Consider potential overhead
        return ts_client
    except Exception as e:
        print(f"Error checking Typesense connection: {e}") # Replace with proper logging
        raise HTTPException(status_code=503, detail="Could not connect to Typesense service") 