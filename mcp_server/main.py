from typing import Any, Dict
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from mcp.server.sse import SseServerTransport
from starlette.requests import Request
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount, Route
from mcp.server import Server
import uvicorn
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import dataclasses
from mcp.server.fastmcp.prompts import base
from mlcbakery import bakery_client as bc
import os
from fastapi import HTTPException, Query, UploadFile, File
import json
import requests
from mlcbakery import croissant_validation

_BAKERY_API_URL = os.getenv("MLCBAKERY_API_BASE_URL")
_AUTH_TOKEN = os.getenv("ADMIN_AUTH_TOKEN")
_BAKERY_HOST = os.getenv("MLCBAKERY_HOST")
@dataclasses.dataclass
class AppContext:
    pass

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle with type-safe context"""
    # Initialize on startup
    try:
        yield
    finally:
        # Cleanup on shutdown
        pass


mcp = FastMCP("MLC-Bakery-MPC", lifespan=app_lifespan)


@mcp.resource("config://app", description="App configuration")
def get_config() -> str:
    """Static configuration data"""
    return "{}"



@mcp.tool("datasets-preview-url/{collection}/{dataset}", description="get a download url for a dataset preview")
async def get_dataset_preview_url(collection: str, dataset: str) -> str:
    """Get a download url for a dataset preview. To read the preview, use pandas.read_parquet({url}).
    """
    return f"{_BAKERY_HOST}/datasets/{collection}/{dataset}/preview"

@mcp.tool("search-datasets/{query}", description="Search for datasets using a query string")
async def search_datasets_tool(query: str = Query(..., description="The search term for datasets")) -> list[dict]:
    """Search datasets via the MLC Bakery API.

    Args:
        query: The search term.

    Returns:
        A list of search result 'hits' (dictionaries).
    """
    client = bc.Client(_BAKERY_API_URL, token=_AUTH_TOKEN)
    try:
        # Use the client method now
        hits = client.search_datasets(query=query, limit=40) 
        print(f"MCP Tool: Received {len(hits)} hits from client search")
        return hits
    except Exception as exc:
        # Log the exception if the client method raises one unexpectedly
        print(f"MCP Tool: Error calling client.search_datasets: {exc}")
        return [] # Return empty list on any error from the client call

@mcp.tool("help", description="Get help for the MLC Bakery API")
async def get_help() -> str:
    """Get help for the MLC Bakery API
    """
    # load the help.md file
    with open(os.path.join(os.path.dirname(__file__), "templates/help.md"), "r") as f:
        return f.read().replace("{_BAKERY_HOST}", _BAKERY_HOST)

@mcp.tool("dataset/{collection}/{dataset}/mlcroissant", description="Get the Croissant dataset template")
async def get_dataset_metadata(collection: str, dataset: str) -> object | None:
    """Get the Croissant dataset metadata
    """
    client = bc.Client(_BAKERY_API_URL, token=_AUTH_TOKEN)
    dataset = client.get_dataset_by_name(collection,dataset)
    if dataset is None:
        return None
    return dataset.metadata.jsonld

@mcp.tool("validate-croissant", description="Validate a Croissant metadata file")
async def validate_croissant(metadata_json: dict[str, Any]) -> dict:
    """Validate a Croissant metadata.

    Args:
        metadata_json: send the JSON data as a dictionary without escaping or quoting.

    Returns:
        A dictionary indicating passed status (true or false)
        and any error message if invalid.
    """
    try:
        
        result = croissant_validation.validate_croissant(metadata_json)
        return dataclasses.asdict(result)
    except Exception as e:
        return {"passed": False, "message": f"Croissant validation failed: {e}"}


@mcp.prompt()
def debug_error(error: str) -> list[base.Message]:
    return [
        base.UserMessage("I'm seeing this error:"),
        base.UserMessage(error),
        base.AssistantMessage("I'll help debug that. What have you tried so far?"),
    ]

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that can server the provied mcp server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    # Define CORS middleware
    middleware = [
        Middleware(CORSMiddleware, allow_origins=['*'], allow_methods=['*'], allow_headers=['*'])
    ]

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
        middleware=middleware
    )


if __name__ == "__main__":
    mcp_server = mcp._mcp_server  # noqa: WPS437

    import argparse
    
    parser = argparse.ArgumentParser(description='Run MCP SSE-based server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()

    # Bind SSE request handling to MCP server
    starlette_app = create_starlette_app(mcp_server, debug=True)

    uvicorn.run(starlette_app, host=args.host, port=args.port)
