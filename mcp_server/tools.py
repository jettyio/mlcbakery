from typing import Any
import dataclasses
from mlcbakery import bakery_client as bc
import os
from fastapi import Query
from mlcbakery import croissant_validation

_BAKERY_API_URL = os.getenv("MLCBAKERY_API_BASE_URL")
_AUTH_TOKEN = os.getenv("ADMIN_AUTH_TOKEN")
_BAKERY_HOST = os.getenv("MLCBAKERY_HOST")

_templates = {}


def _read_template(template_name: str) -> str:
    if template_name in _templates:
        return _templates[template_name]

    with open(
        os.path.join(os.path.dirname(__file__), "templates", template_name), "r"
    ) as f:
        template_text = f.read().replace("{_BAKERY_HOST}", _BAKERY_HOST)
        _templates[template_name] = template_text
        return template_text


async def download_dataset(collection: str, dataset: str) -> dict[str, Any]:
    """Download a dataset."""
    client = bc.Client(_BAKERY_API_URL, token=_AUTH_TOKEN)
    dataset = client.get_dataset_by_name(collection, dataset)
    if dataset is None:
        return None
    metadata = None
    if dataset.metadata is not None:
        metadata = dataset.metadata.jsonld
    return {
        "metadata": metadata,
        "asset_origin": dataset.asset_origin,
        "data_path": dataset.data_path,
        "instructions": _read_template(
            f"download_dataset.{dataset.asset_origin}.md"
        ).replace("{data_path}", dataset.data_path),
    }


async def get_dataset_preview_url(collection: str, dataset: str) -> str:
    """Get a download url for a dataset preview. To read the preview, use pandas.read_parquet({url})."""
    return f"{_BAKERY_HOST}/datasets/{collection}/{dataset}/preview"


async def search_datasets_tool(
    query: str = Query(..., description="The search term for datasets"),
) -> list[dict]:
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
        return []  # Return empty list on any error from the client call


async def get_help() -> str:
    """Get help for the MLC Bakery API"""
    # load the help.md file
    return _read_template("help.md")


async def get_dataset_metadata(collection: str, dataset: str) -> object | None:
    """Get the Croissant dataset metadata"""
    client = bc.Client(_BAKERY_API_URL, token=_AUTH_TOKEN)
    dataset = client.get_dataset_by_name(collection, dataset)
    if dataset is None:
        return None
    return dataset.metadata.jsonld


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
