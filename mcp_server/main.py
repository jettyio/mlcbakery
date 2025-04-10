from typing import Any
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
from mlcbakery.webclient import client as bakery_client
import pandas as pd
import mlcroissant

_BAKERY_API_URL = "http://api:8000"

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


@mcp.resource("mlcbakery://collections/{pattern}", description="Search for collections")
async def search_collections(pattern: str = "") -> list[str]:
    """Search Collection
    """
    client = bakery_client.BakeryClient(_BAKERY_API_URL)
    collections = client.get_collections()
    return [collection["name"] for collection in collections if pattern.lower() in collection["name"].lower()]

@mcp.tool("mlcbakery://datasets/", description="list all datasets by collection")
async def list_datasets() -> list[str]:
    """List all datasets
    """
    client = bakery_client.BakeryClient(_BAKERY_API_URL)
    collections = client.get_collections()
    dataset_list = []
    for collection in collections:
        datasets = client.get_datasets_by_collection(collection["name"])
        for dataset in datasets:
            dataset_list.append(f"{collection['name']}/{dataset['name']}")
    return dataset_list
    


@mcp.tool("mlcbakery://dataset-preview/{dataset_name}", description="Get a dataset preview as a JSON string")
async def get_dataset_preview(dataset_name: str) -> str | None:
    """Get a dataset preview

    Args:
        dataset_name: The name of the dataset to get the preview for (e.g. 'collection_name/dataset_name')
    """
    client = bakery_client.BakeryClient(_BAKERY_API_URL)
    collection_name, ds_name = dataset_name.split("/")
    dataset = client.get_dataset_by_name(collection_name, ds_name)
    if dataset.preview is None:
        return "No preview available"
    return str(dataset.preview)

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
