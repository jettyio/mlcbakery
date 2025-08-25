import dataclasses
import io
import json
import logging
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Union

import requests
import mlcroissant as mlc
import pandas as pd

_LOGGER = logging.getLogger(__name__)

_LONG_DESCRIPTION_TEMPLATE = """
# {dataset_name}

## Collection

{collection_name}
"""

_DATASET_METADATA_TEMPLATE = """
{
    "@context": {
      "@language": "en",
      "@vocab": "https://schema.org/",
      "citeAs": "cr:citeAs",
      "column": "cr:column",
      "conformsTo": "dct:conformsTo",
      "cr": "http://mlcommons.org/croissant/",
      "rai": "http://mlcommons.org/croissant/RAI/",
      "data": {
        "@id": "cr:data",
        "@type": "@json"
      },
      "dataType": {
        "@id": "cr:dataType",
        "@type": "@vocab"
      },
      "dct": "http://purl.org/dc/terms/",
      "examples": {
        "@id": "cr:examples",
        "@type": "@json"
      },
      "extract": "cr:extract",
      "field": "cr:field",
      "fileProperty": "cr:fileProperty",
      "fileObject": "cr:fileObject",
      "fileSet": "cr:fileSet",
      "format": "cr:format",
      "includes": "cr:includes",
      "isLiveDataset": "cr:isLiveDataset",
      "jsonPath": "cr:jsonPath",
      "key": "cr:key",
      "md5": "cr:md5",
      "parentField": "cr:parentField",
      "path": "cr:path",
      "recordSet": "cr:recordSet",
      "references": "cr:references",
      "regex": "cr:regex",
      "repeated": "cr:repeated",
      "replace": "cr:replace",
      "sc": "https://schema.org/",
      "separator": "cr:separator",
      "source": "cr:source",
      "subField": "cr:subField",
      "transform": "cr:transform"
    },
    "@type": "sc:Dataset",
    "name": "{dataset_name}",
    "description": "",
    "conformsTo": "http://mlcommons.org/croissant/1.0",
    "citeAs": "",
    "license": "unknown",
    "url": "{url}"
  }
"""

# Configure basic logging if not already configured
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclasses.dataclass
class BakeryCollection:
    id: str
    name: str
    description: str
    storage_info: dict[str, Any] | None = None
    storage_provider: str | None = None
    auth_org_id: str | None = None

@dataclasses.dataclass
class BakeryDataset:
    id: str
    name: str
    collection_id: str
    collection_name: str | None = None
    parent_collection_dataset: str | None = None
    metadata: mlc.Dataset | None = None
    preview: pd.DataFrame | None = None
    format: str | None = None
    created_at: str | None = None
    metadata_version: str | None = None
    data_path: str | None = None
    long_description: str | None = None
    asset_origin: str | None = None


@dataclasses.dataclass
class BakeryTask:
    id: str
    name: str
    collection_id: str
    workflow: dict[str, Any]
    collection_name: str | None = None
    version: str | None = None
    description: str | None = None
    has_file_uploads: bool = False
    entity_type: str = "task"
    asset_origin: str | None = None
    created_at: str | None = None


@dataclasses.dataclass
class BakeryModel:
    id: str
    name: str
    collection_id: str
    model_path: str  # Path to the model artifact
    collection_name: str | None = None
    metadata_version: str | None = None
    model_metadata: dict[str, Any] | None = None
    asset_origin: str | None = None
    long_description: str | None = None
    model_attributes: dict[str, Any] | None = None
    created_at: str | None = None
    parent_collection_model: str | None = None # Similar to parent_collection_dataset for datasets


class Client:
    def __init__(
        self,
        bakery_url: str = "http://localhost:8000",
        token: str | None = None
    ):
        """
        Initializes the BakeryClient.

        Args:
            bakery_url: The base URL of the MLC Bakery API.
            token: Optional bearer token for authentication.
        """
        self.bakery_url = bakery_url.rstrip("/") + "/api/v1"
        self.token = token  # Store the token

    def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,  # Defaulting to None, will be set below
        stream: bool = False,
    ) -> requests.Response:
        """Helper method to make requests to the Bakery API."""
        # Initialize headers if None or provide default
        if headers is None:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

        url = f"{self.bakery_url}/{endpoint.lstrip('/')}"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                files=files,
                headers=headers,
                verify=True,  # Keep verify=True for HTTPS
                stream=stream,
            )
            response.raise_for_status()  # Let this raise HTTPError for bad responses
            return response
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Request failed: {e}")
            # Optionally re-raise or handle specific exceptions
            raise

    def validate_croissant_dataset(
        self, dataset_input: Union[mlc.Dataset, dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Validates a Croissant dataset by sending its metadata to the
        MLC Bakery API's validation endpoint.

        Args:
            dataset_input: An mlcroissant.Dataset object or a dictionary
                           representing the JSON-LD metadata.

        Returns:
            A dictionary containing the validation report from the API.

        Raises:
            TypeError: If the input is neither an mlcroissant.Dataset nor a dict.
            requests.exceptions.RequestException: If the API request fails.
        """
        _LOGGER.info("Requesting Croissant dataset validation from API.")

        # 1. Determine JSON data
        json_data: dict[str, Any]
        if isinstance(dataset_input, mlc.Dataset):
            json_data = dataset_input.jsonld
        else:
            json_data = dataset_input

        # 2. Call the validation API endpoint
        endpoint = "/datasets/mlcroissant-validation"
        try:
            _LOGGER.info(f"Sending validation request to {endpoint}")
            # Convert JSON data to a file-like object for upload
            json_file = io.BytesIO(json.dumps(json_data).encode("utf-8"))
            files = {"file": ("metadata.json", json_file, "application/json")}
            response = self._request("POST", endpoint, files=files, headers={})
            report = response.json()
            _LOGGER.info(
                f"Validation API response received. Overall result: {'Passed' if report.get('overall_passed') else 'Failed'}"
            )
            return report
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"API request for Croissant validation failed: {e}")
            # Re-raise the exception to signal failure
            raise
        except json.JSONDecodeError as e:
            _LOGGER.error(f"Failed to decode JSON response from validation API: {e}")
            # Raise a more specific error or handle as appropriate
            raise ValueError(
                "Invalid JSON response received from validation API."
            ) from e

    def find_or_create_by_collection_name(
        self, collection_name: str
    ) -> BakeryCollection:
        """Get a collection by collection name and create it if it doesn't exist."""
        # TODO: check if the collection already exists
        try:
            return self.get_collection_by_name(collection_name)
        except Exception as e:
            # If GET fails (e.g., 404 if no collections yet), proceed to create
            _LOGGER.warning(f"Could not list collections, attempting to create: {e}")

        # If collection doesn't exist, create it
        try:
            return self.create_collection(collection_name)
        except Exception as e:
            raise Exception(
                f"Failed to create collection {collection_name}: {e}"
            ) from e
    
    def get_collection_by_name(self, collection_name: str) -> BakeryCollection | None:
        """Get a collection by name."""
        endpoint = f"/collections/{collection_name}"
        try:
            response = self._request("GET", endpoint)
            response.raise_for_status()
            return BakeryCollection(
                id=response.json().get("id", ""),
                name=response.json().get("name", ""),
                description=response.json().get("description", ""),
                auth_org_id=response.json().get("auth_org_id", ""),
            )
        except Exception as e:
            raise Exception(
                f"Failed to get collection {collection_name}: {e}"
            ) from e
    
    def create_collection(self, collection_name: str, description: str = "") -> BakeryCollection:
        """Create a collection."""
        endpoint = "/collections/"
        payload = {
            "name": collection_name,
            "description": description,
        }
        response = self._request("POST", endpoint, json_data=payload)
        return BakeryCollection(
            id=response.json().get("id", ""),
            name=response.json().get("name", ""),
            description=response.json().get("description", ""),
        )

    def create_entity_relationship(
        self,
        target_entity_str: str,
        activity_name: str,
        source_entity_str: str | None = None,
    ) -> dict:
        """
        Creates an entity relationship in the MLC Bakery.

        Args:
            target_entity_str: The string identifier for the target entity (e.g., "dataset/collection_name/dataset_name").
            activity_name: The name of the activity that generated this relationship.
            source_entity_str: Optional. The string identifier for the source entity.

        Returns:
            A dictionary representing the created entity relationship.

        Raises:
            requests.exceptions.RequestException: If the API request fails.
        """
        _LOGGER.info(
            f"Requesting creation of entity relationship for target '{target_entity_str}' "
            f"with activity '{activity_name}' and source '{source_entity_str if source_entity_str else 'None'}'."
        )
        endpoint = "/entity-relationships/"
        payload = {
            "target_entity_str": target_entity_str,
            "activity_name": activity_name,
        }
        if source_entity_str:
            payload["source_entity_str"] = source_entity_str

        try:
            response = self._request("POST", endpoint, json_data=payload)
            relationship_data = response.json()
            _LOGGER.info(
                f"Successfully created entity relationship with ID: {relationship_data.get('id')}"
            )
            return relationship_data
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"API request for creating entity relationship failed: {e}")
            raise
        except json.JSONDecodeError as e:
            _LOGGER.error(
                f"Failed to decode JSON response from entity relationship API: {e}"
            )
            raise ValueError(
                "Invalid JSON response received from entity relationship API."
            ) from e

    def push_dataset(
        self,
        dataset_path: str,
        data_path: str,
        format: str,
        metadata: dict[str, Any],
        preview: bytes | None = None,
        asset_origin: str | None = None,
        long_description: str | None = None,
        metadata_version: str = "1.0.0",
        data_file_path: str | None = None
    ) -> BakeryDataset:
        """Push a dataset to the bakery.

        If data_file_path is provided, the file will be uploaded to storage after dataset creation/update.
        """
        if "/" not in dataset_path:
            raise ValueError(
                "dataset_path must be in the format 'collection_name/dataset_name'"
            )
        collection_name, dataset_name = dataset_path.split("/", 1)

        collection = self.find_or_create_by_collection_name(collection_name)

        dataset = self.get_dataset_by_name(collection_name, dataset_name)

        entity_payload = {
            "name": dataset_name,
            "collection_id": collection.id,
            "dataset_metadata": metadata,
            "data_path": data_path,
            "format": format,
            "asset_origin": asset_origin,
            "preview_type": "parquet",
            "entity_type": "dataset",
            "long_description": str(long_description),
            "metadata_version": metadata_version,
        }
        
        # Filter out None values from payload to avoid overwriting existing fields with null
        entity_payload = {k: v for k, v in entity_payload.items() if v is not None}

        if dataset:
            # Update existing dataset
            _LOGGER.info(
                f"Updating dataset {dataset_name} in collection {collection_name}"
            )
            dataset = self.update_dataset(collection_name, dataset_name, entity_payload)
        else:
            # Create new dataset
            _LOGGER.info(
                f"Creating dataset {dataset_name} in collection {collection_name} with collection_id {collection.id}"
            )

            dataset = self.create_dataset(
                collection.name,
                dataset_name,
                entity_payload.copy(),
            )

        # Update the preview regardless of create/update
        if preview:
            self.save_preview(collection_name, dataset_name, preview)

        # Upload data file if provided
        if data_file_path:
            try:
                _LOGGER.info(
                    f"Uploading data file for dataset {dataset_name} in collection {collection_name}"
                )
                self.upload_dataset_data(collection_name, dataset_name, data_file_path)
            except Exception as e:
                _LOGGER.error(f"Failed to upload data file: {e}")
                # Continue even if data upload fails, as the dataset was created/updated successfully

        # Fetch the final state of the dataset after creation/update and preview save
        return self.get_dataset_by_name(collection_name, dataset_name)

    def get_dataset_by_name(
        self, collection_name: str, dataset_name: str
    ) -> BakeryDataset | None:
        """Get a dataset by name in a collection if it exists."""
        endpoint = f"/datasets/{collection_name}/{dataset_name}"
        try:
            response = self._request("GET", endpoint)
            dataset_response = response.json()

            json_str = dataset_response.get("dataset_metadata")

            metadata = None
            if json_str and "@context" in json_str:
                try:
                    # The API returns metadata as a dict, mlcroissant expects file path or dict
                    metadata = mlc.Dataset(jsonld=json_str)
                except Exception as e:
                    _LOGGER.error(
                        f"Failed to parse Croissant metadata for dataset {dataset_response.get('id')}: {e}"
                    )
                    metadata = None  # Set to None if parsing fails

            preview_df = None
            try:
                preview_df = self.get_preview(collection_name, dataset_name)
            except Exception as e:
                _LOGGER.warning(
                    f"Could not fetch or parse preview for dataset {dataset_response.get('id')}: {e}"
                )

            return BakeryDataset(
                id=dataset_response["id"],
                name=dataset_response["name"],
                collection_id=dataset_response["collection_id"],
                collection_name=collection_name,
                metadata=metadata,
                preview=preview_df,
                metadata_version=dataset_response.get("metadata_version"),
                format=dataset_response.get("format"),
                created_at=dataset_response.get("created_at"),
                data_path=dataset_response.get("data_path"),
                long_description=dataset_response.get("long_description"),
                asset_origin=dataset_response.get("asset_origin"),
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                _LOGGER.info(f"Dataset '{collection_name}/{dataset_name}' not found.")
                return None
            else:
                _LOGGER.error(
                    f"HTTP error fetching dataset '{collection_name}/{dataset_name}': {e}"
                )
                raise  # Re-raise other HTTP errors
        except Exception as e:
            _LOGGER.error(
                f"Error fetching dataset '{collection_name}/{dataset_name}': {e}"
            )
            raise

    def get_preview(
        self, collection_name: str, dataset_name: str
    ) -> pd.DataFrame | None:
        """Get a preview for a dataset."""
        endpoint = f"/datasets/{collection_name}/{dataset_name}/preview"
        try:
            response = self._request("GET", endpoint)
            # Check content type? API might return 404 or empty if no preview
            if response.status_code == 200 and response.content:
                # Check if content is actually parquet before trying to read
                # A simple check might involve magic bytes or content type header if reliable
                # Assuming it's parquet if status is 200 and content exists
                return pd.read_parquet(io.BytesIO(response.content))
            else:
                _LOGGER.info(
                    f"No preview content found for dataset {collection_name}/{dataset_name} (status: {response.status_code})."
                )
                return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                _LOGGER.info(
                    f"Preview for dataset {collection_name}/{dataset_name} not found."
                )
                return None
            else:
                _LOGGER.error(
                    f"HTTP error fetching preview for dataset {collection_name}/{dataset_name}: {e}"
                )
                raise  # Re-raise other HTTP errors
        except Exception as e:
            _LOGGER.error(
                f"Error fetching or parsing preview for dataset {collection_name}/{dataset_name}: {e}"
            )
            # Decide if to return None or raise. Returning None might be safer.
            return None

    def create_dataset(
        self, collection_name: str, dataset_name: str, params: dict = dict()
    ) -> BakeryDataset:
        """Create a dataset in a collection."""
        endpoint = f"/datasets/{collection_name}"
        payload = {
            "name": dataset_name,
            "entity_type": "dataset",
            **params,
        }

        try:
            response = self._request("POST", endpoint, json_data=payload)
            json_response = response.json()
            # Basic validation of response
            if "id" not in json_response or "name" not in json_response:
                raise ValueError("Invalid response received from create dataset API")

            return BakeryDataset(
                id=json_response["id"],
                name=json_response["name"],
                collection_id=json_response.get("collection_id"),
                collection_name=collection_name,
                # Include other fields if the API returns them on creation
                metadata=None,  # Metadata likely not set on creation
                preview=None,  # Preview not set on creation
                format=json_response.get("format"),
                data_path=json_response.get("data_path"),
                long_description=json_response.get("long_description"),
            )
        except Exception as e:
            raise Exception(
                f"Failed to create dataset {dataset_name} in collection {collection_name}: {e}"
            ) from e

    def update_dataset(self, collection_name: str, dataset_name: str, params: dict) -> BakeryDataset:
        """Update a dataset."""
        endpoint = f"/datasets/{collection_name}/{dataset_name}"
        try:
            response = self._request("PUT", endpoint, json_data=params)
            json_response = response.json()
            # Basic validation of response
            if "id" not in json_response or "name" not in json_response:
                raise ValueError("Invalid response received from update dataset API")

            # Fetch full dataset details after update? Or construct from response?
            # Constructing from response might be incomplete. Let's assume response is sufficient for now.
            return BakeryDataset(
                id=json_response["id"],
                name=json_response["name"],
                collection_id=json_response["collection_id"],
                # Add other fields if returned by PUT response, otherwise they'll be None or default
                format=json_response.get("format"),
                data_path=json_response.get("data_path"),
                long_description=json_response.get("long_description"),
                metadata_version=json_response.get("metadata_version"),
                # Fetch metadata and preview separately if needed, or assume they are not returned here
                metadata=None,  # Or fetch if needed: self.get_dataset_by_name(...)
                preview=None,  # Or fetch if needed: self.get_preview(...)
            )

        except Exception as e:
            raise Exception(f"Failed to update dataset {collection_name}/{dataset_name}: {e}") from e

    def save_metadata(self, collection_name: str, dataset_name: str, metadata: dict):
        """Save metadata to a dataset. Assumes metadata is a JSON-serializable dict."""
        endpoint = f"/datasets/{collection_name}/{dataset_name}/metadata"
        try:
            # Changed to PUT as per discussion? Or is PATCH correct? Assuming PATCH.
            self._request("PATCH", endpoint, json_data=metadata)
        # No return value needed, just raise on error
        except Exception as e:
            raise Exception(
                f"Failed to save metadata to dataset {collection_name}/{dataset_name}: {e}"
            ) from e

    def save_preview(self, collection_name: str, dataset_name: str, preview: bytes):
        """Save a preview (as parquet bytes) to a dataset."""
        endpoint = f"/datasets/{collection_name}/{dataset_name}/preview"
        files = {"preview_update": ("preview.parquet", preview, "application/parquet")}
        try:
            # PUT seems appropriate for replacing/uploading the preview file
            self._request("PUT", endpoint, files=files, headers={})
            # No return value needed, just raise on error
        except Exception as e:
            raise Exception(
                f"Failed to save preview to dataset {collection_name}/{dataset_name}: {e}"
            ) from e

    def get_upstream_entities(
        self, entity_type: str, collection_name: str, entity_name: str
    ) -> list[dict] | None:
        """Get the upstream entities (provenance) for a dataset."""
        endpoint = f"/entity-relationships/{entity_type}/{collection_name}/{entity_name}/upstream"
        try:
            response = self._request("GET", endpoint)
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                _LOGGER.info(
                    f"Upstream entities for {entity_type} '{collection_name}/{entity_name}' not found (or dataset itself not found)."
                )
                return None  # Return None if the dataset or upstream info doesn't exist
            else:
                _LOGGER.error(
                    f"HTTP error fetching upstream entities for '{collection_name}/{entity_name}': {e}"
                )
                raise  # Re-raise other HTTP errors
        except Exception as e:
            _LOGGER.error(
                f"Error fetching upstream entities for '{collection_name}/{entity_name}': {e}"
            )
            raise  # Re-raise unexpected errors

    def get_datasets_by_collection(self, collection_name: str) -> list[BakeryDataset]:
        """List all datasets within a specific collection."""
        endpoint = f"/collections/{collection_name}/datasets"
        datasets = []
        try:
            response = self._request("GET", endpoint)
            datasets_data = response.json()

            for ds_data in datasets_data:
                # Reconstruct BakeryDataset objects. This might be simplified if
                # we have a method to fetch full dataset details by ID,
                # or if this endpoint returns sufficient detail.
                # Assuming it returns enough for basic listing:
                datasets.append(
                    BakeryDataset(
                        id=ds_data["id"],
                        name=ds_data["name"],
                        collection_id=ds_data["collection_id"],
                        # Add other fields if available in the response
                        format=ds_data.get("format"),
                        created_at=ds_data.get("created_at"),
                        metadata_version=ds_data.get("metadata_version"),
                        # Metadata and preview would likely require separate calls if needed here
                    )
                )
            return datasets
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                _LOGGER.info(
                    f"Collection '{collection_name}' not found or has no datasets."
                )
                return []  # Return empty list if collection not found
            else:
                _LOGGER.error(
                    f"HTTP error fetching datasets for collection '{collection_name}': {e}"
                )
                raise
        except Exception as e:
            _LOGGER.error(
                f"Error fetching datasets for collection '{collection_name}': {e}"
            )
            raise

    def get_collection_storage_info(self, collection_name: str) -> BakeryCollection:
        """Get a collection's storage information.

        This endpoint requires valid authentication token.

        Args:
            collection_name: The name of the collection to retrieve storage info for.

        Returns:
            A BakeryCollection object with storage_info and storage_provider populated.

        Raises:
            requests.exceptions.RequestException: If the API request fails or authentication is invalid.
            ValueError: If the collection is not found.
        """
        endpoint = f"/collections/{collection_name}/storage"
        try:
            response = self._request("GET", endpoint)
            collection_data = response.json()
            return BakeryCollection(
                id=collection_data["id"],
                name=collection_data["name"],
                description=collection_data.get("description", ""),
                storage_info=collection_data.get("storage_info"),
                storage_provider=collection_data.get("storage_provider"),
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Collection '{collection_name}' not found.")
            else:
                _LOGGER.error(
                    f"HTTP error fetching storage info for collection '{collection_name}': {e}"
                )
                raise
        except Exception as e:
            _LOGGER.error(
                f"Error fetching storage info for collection '{collection_name}': {e}"
            )
            raise

    def update_collection_storage_info(
        self,
        collection_name: str,
        storage_info: dict[str, Any] | None = None,
        storage_provider: str | None = None,
    ) -> BakeryCollection:
        """Update a collection's storage information.

        This endpoint requires valid authentication token.

        Args:
            collection_name: The name of the collection to update.
            storage_info: Dictionary containing storage credentials and location information.
            storage_provider: String identifying the storage provider (e.g., 'aws', 'gcp', 'azure').

        Returns:
            The updated BakeryCollection object with storage_info and storage_provider populated.

        Raises:
            requests.exceptions.RequestException: If the API request fails or authentication is invalid.
            ValueError: If the collection is not found.
        """
        endpoint = f"/collections/{collection_name}/storage"

        # Build the request payload, only including fields that are provided
        storage_data = {}
        if storage_info is not None:
            storage_data["storage_info"] = storage_info
        if storage_provider is not None:
            storage_data["storage_provider"] = storage_provider

        if not storage_data:
            raise ValueError(
                "At least one of storage_info or storage_provider must be provided."
            )

        try:
            response = self._request("PATCH", endpoint, json_data=storage_data)
            collection_data = response.json()
            return BakeryCollection(
                id=collection_data["id"],
                name=collection_data["name"],
                description=collection_data.get("description", ""),
                storage_info=collection_data.get("storage_info"),
                storage_provider=collection_data.get("storage_provider"),
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Collection '{collection_name}' not found.")
            else:
                _LOGGER.error(
                    f"HTTP error updating storage info for collection '{collection_name}': {e}"
                )
                raise
        except Exception as e:
            _LOGGER.error(
                f"Error updating storage info for collection '{collection_name}': {e}"
            )
            raise

    def get_collections(self) -> list[BakeryCollection]:
        """List all available collections."""
        endpoint = "/collections/"
        collections = []
        try:
            response = self._request("GET", endpoint)
            collections_data = response.json()
            for c_data in collections_data:
                collections.append(
                    BakeryCollection(
                        id=c_data["id"],
                        name=c_data["name"],
                        description=c_data.get(
                            "description", ""
                        ),  # Handle potentially missing description
                        auth_org_id=c_data.get("auth_org_id", ""),
                    )
                )
            return collections
        except Exception as e:
            _LOGGER.error(f"Error fetching collections: {e}")
            # Depending on desired behavior, could return empty list or raise
            raise  # Raising for now, as listing collections seems fundamental

    def search_models(self, query: str, limit: int = 30) -> list[dict]:
        """Search models using a query string.
        """
        endpoint = "/models/search"
        params = {"q": query, "limit": limit}
        try:
            response = self._request("GET", endpoint, params=params)
            results = response.json()
            return results.get("hits", [])
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Error searching datasets with query '{query}': {e}")
            # Return empty list on error, or could re-raise
            return []
        except Exception as e:
            _LOGGER.error(f"Unexpected error searching datasets: {e}")
            return []

    def search_datasets(self, query: str, limit: int = 30) -> list[dict]:
        """Search datasets using a query string.

        Args:
            query: The search term.
            limit: The maximum number of results to return.

        Returns:
            A list of search result 'hits' (dictionaries) from Typesense.
        """
        endpoint = "/datasets/search"
        params = {"q": query, "limit": limit}
        try:
            response = self._request("GET", endpoint, params=params)
            results = response.json()
            return results.get("hits", [])
        except requests.exceptions.RequestException as e:
            _LOGGER.error(f"Error searching datasets with query '{query}': {e}")
            # Return empty list on error, or could re-raise
            return []
        except Exception as e:
            _LOGGER.error(f"Unexpected error searching datasets: {e}")
            return []

    def upload_dataset_data(
        self, collection_name: str, dataset_name: str, data_file_path: str
    ) -> dict:
        """Upload a dataset's data as a tar.gz file.

        This method requires a valid authentication token to be set in the client.

        Args:
            collection_name: Name of the collection
            dataset_name: Name of the dataset
            data_file_path: Path to the tar.gz file to upload

        Returns:
            Dictionary with information about the uploaded file

        Raises:
            ValueError: If collection or dataset doesn't exist, or if collection
                        doesn't have storage configuration
            requests.exceptions.RequestException: If the API request fails
        """
        endpoint = f"/datasets/{collection_name}/{dataset_name}/data"

        # Prepare the file for upload
        with open(data_file_path, "rb") as file:
            files = {
                "data_file": (
                    os.path.basename(data_file_path),
                    file,
                    "application/gzip",
                )
            }
            headers = {}  # Let _request handle auth

            try:
                response = self._request("POST", endpoint, files=files, headers=headers)
                return response.json()
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    raise ValueError(
                        f"Dataset '{collection_name}/{dataset_name}' not found."
                    )
                elif e.response.status_code == 400:
                    raise ValueError(
                        "Collection doesn't have required storage configuration."
                    )
                else:
                    _LOGGER.error(f"HTTP error uploading dataset data: {e}")
                    raise
            except Exception as e:
                _LOGGER.error(f"Error uploading dataset data: {e}")
                raise

    def get_dataset_data_download_url(
        self, collection_name: str, dataset_name: str, file_number: int
    ) -> str:
        """Get a temporary download URL for a dataset's data file.

        This method requires a valid authentication token to be set in the client.

        Args:
            collection_name: Name of the collection
            dataset_name: Name of the dataset
            file_number: The enumerated file number to download

        Returns:
            A signed URL to download the data file

        Raises:
            ValueError: If collection or dataset doesn't exist
            requests.exceptions.RequestException: If the API request fails
        """
        endpoint = f"/datasets/{collection_name}/{dataset_name}/data/{file_number}"

        try:
            response = self._request("GET", endpoint)
            result = response.json()
            return result.get("download_url")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(
                    f"Dataset '{collection_name}/{dataset_name}' not found."
                )
            elif e.response.status_code == 400:
                raise ValueError(
                    "Collection doesn't have required storage configuration."
                )
            else:
                _LOGGER.error(f"HTTP error getting download URL: {e}")
                raise
        except Exception as e:
            _LOGGER.error(f"Error getting download URL: {e}")
            raise

    def update_dataset_data(
        self, collection_name: str, dataset_name: str, data_file_path: str
    ) -> dict:
        """Update a dataset with a new data file.

        This is a convenience method that uploads a new data file for an existing dataset.
        It requires the dataset to exist and the collection to have storage configuration.

        Args:
            collection_name: Name of the collection
            dataset_name: Name of the dataset
            data_file_path: Path to the tar.gz file to upload

        Returns:
            Dictionary with information about the uploaded file

        Raises:
            ValueError: If dataset doesn't exist
            requests.exceptions.RequestException: If the API request fails
        """
        # First verify the dataset exists
        dataset = self.get_dataset_by_name(collection_name, dataset_name)
        if not dataset:
            raise ValueError(f"Dataset '{collection_name}/{dataset_name}' not found.")

        # Upload the data file
        return self.upload_dataset_data(collection_name, dataset_name, data_file_path)

    def prepare_dataset(self, dataset_path: str, dataset_name: str, collection_name: str, origin="mlcbakery", metadata_version="1.0.0") -> dict[str, Any]:
        """Prepares a dataset folder for the bakery by creating a .manifest.json file.

        Args:
            dataset_path: Path to the dataset folder
            params: Dictionary with dataset parameters including:
                - properties: Basic dataset properties
                - parents: Provenance information
                - assets: References to dataset assets

        Returns:
            The created bakery metadata as a dictionary

        Raises:
            ValueError: If dataset path doesn't exist
            IOError: If unable to write the .manifest.json file
        """
        dataset_dir = Path(dataset_path)
        if not dataset_dir.exists():
            raise ValueError(f"Dataset path '{dataset_path}' doesn't exist")
        
        if not dataset_dir.is_dir():
            raise ValueError(f"Dataset path '{dataset_path}' is not a directory")
        
        
        # Store input_entity_ids in params for later use when creating the dataset
        params = {}
        params["properties"] = {
            "name": dataset_name,
            "collection_name": collection_name,
            "type": "dataset",
            "origin": origin,
            "metadata_version": metadata_version,
        }
        params["parents"] = []
        params["assets"] = {
            "metadata": "metadata.json",
            "long_description": "README.md",
        }
        long_description_path = dataset_dir / "README.md"
        metadata_path = dataset_dir / "metadata.json"
        if not long_description_path.exists():
            long_description_path.write_text(_LONG_DESCRIPTION_TEMPLATE.replace("{dataset_name}", dataset_name).replace("{collection_name}", collection_name))
        if not metadata_path.exists():
            with open(metadata_path, "w") as f:
                url = f"{self.bakery_url}/api/v1/datasets/{collection_name}/{dataset_name}"
                data = json.loads(_DATASET_METADATA_TEMPLATE.replace("{dataset_name}", dataset_name).replace("{url}", url))
                json.dump(data, f, indent=2)
        # Create .manifest.json file with the provided parameters
        bakery_json_path = dataset_dir / ".manifest.json"
        
        try:
            with open(bakery_json_path, "w") as f:
                json.dump(params, f, indent=2)
            _LOGGER.info(f"Created .manifest.json in '{dataset_path}'")
            return params
        except Exception as e:
            raise IOError(f"Failed to write .manifest.json: {e}") from e
    
    def duplicate_dataset(self, source_path: str, dest_path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Duplicates a dataset to a new folder and updates the bakery metadata.

        Args:
            source_path: Path to the source dataset folder
            dest_path: Path where to create the duplicated dataset folder
            params: Dictionary with updated parameters for the duplicated dataset
            attributed_to: Person or entity to attribute the duplication to

        Returns:
            The updated bakery metadata as a dictionary

        Raises:
            ValueError: If source doesn't exist or destination already exists
            IOError: If unable to copy files or write the .manifest.json file
        """
        source_dir = Path(source_path)
        dest_dir = Path(dest_path)
        
        # Validation
        if not source_dir.exists():
            raise ValueError(f"Source dataset '{source_path}' doesn't exist")
        
        if not source_dir.is_dir():
            raise ValueError(f"Source dataset '{source_path}' is not a directory")
        
        if dest_dir.exists():
            raise ValueError(f"Destination '{dest_path}' already exists")
        
        # Read the source .manifest.json file
        source_bakery_path = source_dir / ".manifest.json"
        if not source_bakery_path.exists():
            raise ValueError(f"Source dataset '{source_path}' has no .manifest.json file")
        
        try:
            with open(source_bakery_path, "r") as f:
                bakery_data = json.load(f)
        except Exception as e:
            raise IOError(f"Failed to read source .manifest.json: {e}") from e
        
        # Copy the dataset folder
        try:
            shutil.copytree(source_dir, dest_dir)
            _LOGGER.info(f"Copied dataset from '{source_path}' to '{dest_path}'")
        except Exception as e:
            raise IOError(f"Failed to copy dataset: {e}") from e
        
        # First capture the source dataset name before any modifications
        source_entity_name = bakery_data.get("properties", {}).get("name")
        source_collection_name = bakery_data.get("properties", {}).get("collection_name")
        source_entity_type = bakery_data.get("properties", {}).get("type")
        
        # Update the bakery data with new parameters
        # Handle properties update
        if "properties" in params:
            if "properties" not in bakery_data:
                bakery_data["properties"] = {}
            bakery_data["properties"].update(params["properties"])
        
        # Replace parents with a new lineage entry pointing to the source dataset
        parent_record = {
            "generated": f"{source_entity_type}/{source_collection_name}/{source_entity_name}"
        }
        bakery_data["parents"] = [parent_record]
        
        # Update other sections if provided
        for key in ["assets"]:
            if key in params and key not in bakery_data:
                bakery_data[key] = params[key]
            elif key in params:
                bakery_data[key].update(params[key])
        
        # Write the updated .manifest.json to the destination
        dest_bakery_path = dest_dir / ".manifest.json"
        try:
            with open(dest_bakery_path, "w") as f:
                json.dump(bakery_data, f, indent=2)
            _LOGGER.info(f"Updated .manifest.json in '{dest_path}'")
            return bakery_data
        except Exception as e:
            raise IOError(f"Failed to write updated .manifest.json: {e}") from e
    
    def _get_default_agent_id(self, collection_name: str) -> int | None:
        """Get the default agent ID for a collection, if it exists."""
        try:
            endpoint = f"/collections/{collection_name}/agents/"
            response = self._request("GET", endpoint)
            agents = response.json()
            for agent in agents:
                if agent["name"] == f"{collection_name} Owner":
                    return agent["id"]
            return None
        except Exception as e:
            _LOGGER.warning(f"Could not fetch default agent for collection {collection_name}: {e}")
            return None

    def save_to_bakery(self, dataset_path: str, upload_data: bool = False) -> BakeryDataset:
        """Saves a local dataset to the bakery API.

        Reads the .manifest.json file from the dataset folder and pushes the dataset to the bakery API.
        If upload_data is True and a data folder exists, it will be compressed and uploaded.)

        Args:
            dataset_path: Path to the dataset folder
            upload_data: Whether to upload the data folder as a tar.gz file

        Returns:
            The BakeryDataset object from the API

        Raises:
            ValueError: If dataset path doesn't exist or has no .manifest.json
            IOError: If unable to read files or create tar.gz
        """
        dataset_dir = Path(dataset_path)
        
        # Validation
        if not dataset_dir.exists() or not dataset_dir.is_dir():
            raise ValueError(f"Dataset path '{dataset_path}' doesn't exist or is not a directory")
        
        bakery_json_path = dataset_dir / ".manifest.json"
        if not bakery_json_path.exists():
            raise ValueError(f"Dataset '{dataset_path}' has no .manifest.json file")
        
        # Read the .manifest.json file
        try:
            with open(bakery_json_path, "r") as f:
                bakery_data = json.load(f)
        except Exception as e:
            raise IOError(f"Failed to read .manifest.json: {e}") from e
        
        # Check if the required fields are present
        if "properties" not in bakery_data:
            raise ValueError("Missing 'properties' in .manifest.json")
        
        properties = bakery_data["properties"]
        if "name" not in properties or "collection_name" not in properties:
            raise ValueError("Missing required properties 'name' or 'collection_name' in .manifest.json")
        
        dataset_name = properties["name"]
        collection_name = properties["collection_name"]
        dataset_path_arg = f"{collection_name}/{dataset_name}"
        
        # Read the Croissant metadata file if it exists
        metadata_file = None
        if "assets" in bakery_data and "metadata" in bakery_data["assets"]:
            metadata_file = dataset_dir / bakery_data["assets"]["metadata"]
        else:
            metadata_file = dataset_dir / "metadata.json"
        
        if not metadata_file.exists():
            raise ValueError(f"Metadata file {metadata_file} not found")
        
        try:
            # test if the file is json:
            metadata = mlc.Dataset(jsonld=str(metadata_file))
            # load as json:
            with open(metadata_file, "r") as f:
                metadata = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse Croissant metadata: {e}") from e
        
        # Read the long description if it exists
        long_description = None
        if "assets" in bakery_data and "long_description" in bakery_data["assets"]:
            long_desc_file = dataset_dir / bakery_data["assets"]["long_description"]
            if long_desc_file.exists():
                try:
                    with open(long_desc_file, "r") as f:
                        long_description = f.read()
                except Exception as e:
                    _LOGGER.warning(f"Failed to read long description: {e}")
        
        # Create a tar.gz of the data folder if requested and it exists
        data_file_path = None
        if upload_data:
            data_dir = dataset_dir / "data"
            if data_dir.exists() and data_dir.is_dir():
                try:
                    # Create a temporary file for the tar.gz
                    with tempfile.NamedTemporaryFile(suffix='.tar.gz', delete=False) as tmp_file:
                        data_file_path = tmp_file.name
                    
                    # Create the tar.gz
                    with tarfile.open(data_file_path, "w:gz") as tar:
                        tar.add(data_dir, arcname="data")
                    
                    _LOGGER.info(f"Created tar.gz of data folder at {data_file_path}")
                except Exception as e:
                    if data_file_path and os.path.exists(data_file_path):
                        os.unlink(data_file_path)
                    raise IOError(f"Failed to create tar.gz of data folder: {e}") from e
        
        # Generate a preview if possible (implement as needed)
        preview = None
        
        # Infer format from the dataset contents
        format_type = "csv"  # Default, can be improved by actually checking the data files
        
        # Push the dataset to the Bakery API
        _LOGGER.info(f"Pushing dataset '{dataset_path_arg}' to Bakery API")
        try:
            result = self.push_dataset(
                dataset_path=dataset_path_arg,
                data_path=str(dataset_dir / "data") if (dataset_dir / "data").exists() else None,
                format=format_type,
                metadata=metadata,
                preview=preview,
                asset_origin=properties.get("origin"),
                long_description=long_description,
                metadata_version=properties.get("metadata_version", "1.0.0"),
                data_file_path=data_file_path if upload_data else None
            )
            
            # Clean up the temporary data file if created
            if data_file_path and os.path.exists(data_file_path):
                os.unlink(data_file_path)
                
            parents = bakery_data.get("parents", [])
            if parents:
                for parent in parents:
                    source_entity_str = parent.get("generated")
                    if source_entity_str:
                        try:
                            target_entity_str = f"dataset/{collection_name}/{dataset_name}"
                            _LOGGER.info(
                                f"Creating entity relationship: {source_entity_str} -> generated -> {target_entity_str}"
                            )
                            self.create_entity_relationship(
                                target_entity_str=target_entity_str,
                                activity_name="generated",
                                source_entity_str=source_entity_str,
                            )
                        except Exception as e:
                            _LOGGER.warning(
                                f"Failed to create entity relationship for parent {source_entity_str}: {e}"
                            )
                            # Continue even if one relationship fails
            
            return result
        except Exception as e:
            # Clean up the temporary data file if created
            if data_file_path and os.path.exists(data_file_path):
                os.unlink(data_file_path)
            raise Exception(f"Failed to push dataset to Bakery API: {e}") from e

    def download_dataset_data(
        self, collection_name: str, dataset_name: str, output_path: str = None
    ) -> str:
        """Download the latest dataset data file.

        This method requires a valid authentication token to be set in the client.

        Args:
            collection_name: Name of the collection
            dataset_name: Name of the dataset
            output_path: Path where to save the downloaded file. If None, a temporary path is used.

        Returns:
            Path to the downloaded file

        Raises:
            ValueError: If collection or dataset doesn't exist
            requests.exceptions.RequestException: If the API request fails
        """
        endpoint = f"/datasets/data/latest/{collection_name}/{dataset_name}"

        try:
            # Stream the download to avoid loading large files into memory
            headers = {"Accept": "application/gzip"}
            response = self._request("GET", endpoint, headers=headers, stream=True)
            response.raise_for_status()

            # Get the filename from the Content-Disposition header
            content_disposition = response.headers.get("Content-Disposition", "")
            filename = None
            if "filename=" in content_disposition:
                filename = content_disposition.split("filename=")[1].strip('"')
            else:
                filename = f"data_{collection_name}_{dataset_name}.tar.gz"

            # Determine the output path
            file_path = output_path if output_path else os.path.join("/tmp", filename)

            # Save the file
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            return file_path

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(
                    f"Dataset '{collection_name}/{dataset_name}' not found or has no data files."
                )
            elif e.response.status_code == 400:
                raise ValueError(
                    "Collection doesn't have required storage configuration."
                )
            else:
                _LOGGER.error(f"HTTP error downloading dataset data: {e}")
                raise
        except Exception as e:
            _LOGGER.error(f"Error downloading dataset data: {e}")
            raise

    def get_model_by_name(
        self, collection_name: str, model_name: str
    ) -> BakeryModel | None:
        """Get a model by name in a collection if it exists."""
        endpoint = f"/models/{collection_name}/{model_name}"
        try:
            response = self._request("GET", endpoint)
            model_response = response.json()

            return BakeryModel(
                id=model_response["id"],
                name=model_response["name"],
                collection_id=model_response["collection_id"],
                collection_name=collection_name,
                model_path=model_response.get("model_path"),
                metadata_version=model_response.get("metadata_version"),
                model_metadata=model_response.get("model_metadata"),
                asset_origin=model_response.get("asset_origin"),
                long_description=model_response.get("long_description"),
                model_attributes=model_response.get("model_attributes"),
                created_at=model_response.get("created_at"),
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                _LOGGER.info(f"Model '{collection_name}/{model_name}' not found.")
                return None
            else:
                _LOGGER.error(
                    f"HTTP error fetching model '{collection_name}/{model_name}': {e}"
                )
                raise
        except Exception as e:
            _LOGGER.error(
                f"Error fetching model '{collection_name}/{model_name}': {e}"
            )
            raise

    def create_model(
        self, collection_name: str, model_name: str, params: dict = dict()
    ) -> BakeryModel:
        """Create a model in a collection."""
        endpoint = "/models"  # As per API: POST /models
        # Ensure collection_name is in params for the API, even if collection_id is also used internally
        payload = {
            "name": model_name,
            "collection_name": collection_name, # API expects collection_name for creation
            "entity_type": "trained_model", # Default entity type
            **params, # params should include model_path and other metadata
        }
        
        # Ensure model_path is present, as it's required by the schema
        if "model_path" not in payload or not payload["model_path"]:
            raise ValueError("model_path is required to create a model.")

        try:
            response = self._request("POST", endpoint, json_data=payload)
            json_response = response.json()
            if "id" not in json_response or "name" not in json_response:
                raise ValueError("Invalid response received from create model API")

            return BakeryModel(
                id=json_response["id"],
                name=json_response["name"],
                collection_id=json_response.get("collection_id"),
                model_path=json_response.get("model_path"),
                metadata_version=json_response.get("metadata_version"),
                model_metadata=json_response.get("model_metadata"),
                asset_origin=json_response.get("asset_origin"),
                long_description=json_response.get("long_description"),
                model_attributes=json_response.get("model_attributes"),
                created_at=json_response.get("created_at"),
            )
        except Exception as e:
            raise Exception(
                f"Failed to create model {model_name} in collection {collection_name}: {e}"
            ) from e

    def update_model(self, model_id: str, params: dict) -> BakeryModel:
        """Update a model."""
        endpoint = f"/models/{model_id}" # As per API: PUT /models/{model_id}
        try:
            response = self._request("PUT", endpoint, json_data=params)
            json_response = response.json()
            if "id" not in json_response or "name" not in json_response:
                raise ValueError("Invalid response received from update model API")

            return BakeryModel(
                id=json_response["id"],
                name=json_response["name"],
                collection_id=json_response.get("collection_id"),
                model_path=json_response.get("model_path"),
                metadata_version=json_response.get("metadata_version"),
                model_metadata=json_response.get("model_metadata"),
                asset_origin=json_response.get("asset_origin"),
                long_description=json_response.get("long_description"),
                model_attributes=json_response.get("model_attributes"),
                created_at=json_response.get("created_at"),
            )
        except Exception as e:
            raise Exception(f"Failed to update model {model_id}: {e}") from e

    def push_model(
        self,
        model_identifier: str, # e.g., "collection_name/model_name"
        model_physical_path: str, # Actual path to model artifact, e.g., /path/to/model.pkl or s3://bucket/model
        model_metadata: dict[str, Any] | None = None,
        asset_origin: str | None = None,
        long_description: str | None = None,
        metadata_version: str = "1.0.0",
        model_attributes: dict[str, Any] | None = None,
        # No data_file_path or preview for models as per current scope
    ) -> BakeryModel:
        """Push a model's metadata to the bakery.

        Args:
            model_identifier: String in the format 'collection_name/model_name'.
            model_physical_path: The actual path or URI to the model artifact.
            model_metadata: Optional dictionary for arbitrary model metadata.
            asset_origin: Optional string indicating the origin of the model asset.
            long_description: Optional detailed description of the model.
            metadata_version: Version string for the metadata.
            model_attributes: Optional dictionary for specific model attributes.

        Returns:
            The BakeryModel object representing the pushed model.
        """
        if "/" not in model_identifier:
            raise ValueError(
                "model_identifier must be in the format 'collection_name/model_name'"
            )
        collection_name, model_name = model_identifier.split("/", 1)

        collection = self.find_or_create_by_collection_name(collection_name)
        if not collection: # Should not happen if find_or_create is correct
             raise Exception(f"Failed to find or create collection {collection_name}")


        existing_model = self.get_model_by_name(collection_name, model_name)

        entity_payload = {
            "model_path": model_physical_path,
            "model_metadata": model_metadata,
            "asset_origin": asset_origin,
            "long_description": long_description,
            "metadata_version": metadata_version,
            "model_attributes": model_attributes,
            # name and collection_name/collection_id handled by create_model/update_model
        }
        
        # Filter out None values from payload to avoid overwriting existing fields with null during update
        # For creation, all provided fields will be used.
        # The API schema for update (TrainedModelUpdate) has optional fields, so sending None might clear them.
        # It's safer to only send fields that have a value.
        entity_payload_for_update = {k: v for k, v in entity_payload.items() if v is not None}


        pushed_model: BakeryModel
        if existing_model:
            # Update existing model
            _LOGGER.info(
                f"Updating model {model_name} in collection {collection_name}"
            )
            # The update payload should not contain 'name' or 'collection_id' as they are immutable or set via URL
            pushed_model = self.update_model(existing_model.id, entity_payload_for_update)
        else:
            # Create new model
            _LOGGER.info(
                f"Creating model {model_name} in collection {collection_name}"
            )
            # For creation, we pass all relevant fields, including those that might be None if the API handles defaults.
            # The create_model method expects collection_name and model_name as separate args.
            # The payload for create_model needs 'collection_name' for the API.
            creation_payload = entity_payload.copy() # Start with all fields
            # collection_name is passed as an argument to self.create_model
            # model_name is passed as an argument to self.create_model
            pushed_model = self.create_model(
                collection_name, # Passed to create_model, which puts it in payload for API
                model_name,
                creation_payload, # Contains model_path, metadata etc.
            )
        
        # Note: Entity relationships are not explicitly handled here yet,
        # but could be added if a manifest-like structure is introduced for models
        # or if parent information is passed to push_model.
        # For now, returning the created/updated model.

        # Fetch the final state of the model after creation/update
        final_model = self.get_model_by_name(collection_name, model_name)
        if not final_model:
            # This should ideally not happen if create/update was successful
            _LOGGER.error(f"Failed to retrieve model {collection_name}/{model_name} after push operation.")
            # Fallback to the model object returned by create/update, though it might be less complete.
            return pushed_model 
        return final_model

    def get_task_by_name(
        self, collection_name: str, task_name: str
    ) -> BakeryTask | None:
        """Get a task by name in a collection if it exists."""
        endpoint = f"/tasks/{collection_name}/{task_name}"
        try:
            response = self._request("GET", endpoint)
            task_response = response.json()

            return BakeryTask(
                id=task_response["id"],
                name=task_response["name"],
                collection_id=task_response["collection_id"],
                collection_name=collection_name,
                workflow=task_response.get("workflow", {}),
                version=task_response.get("version"),
                description=task_response.get("description"),
                entity_type=task_response.get("entity_type", "task"),
                asset_origin=task_response.get("asset_origin"),
                created_at=task_response.get("created_at"),
            )
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                _LOGGER.info(f"Task '{collection_name}/{task_name}' not found.")
                return None
            else:
                _LOGGER.error(
                    f"HTTP error fetching task '{collection_name}/{task_name}': {e}"
                )
                raise
        except Exception as e:
            _LOGGER.error(
                f"Error fetching task '{collection_name}/{task_name}': {e}"
            )
            raise

    def create_task(
        self, collection_name: str, task_name: str, workflow: dict[str, Any], version: str="1.0.0", description: str="", params: dict = dict()
    ) -> BakeryTask:
        """Create a task in a collection."""
        endpoint = "/tasks" 
        # Ensure collection_name is in params for the API
        payload = {
            "name": task_name,
            "collection_name": collection_name, 
            "workflow": workflow,
            "entity_type": "task", 
            "version": version,
            "description": description,
            **params, 
        }

        try:
            response = self._request("POST", endpoint, json_data=payload)
            json_response = response.json()
            if "id" not in json_response or "name" not in json_response:
                raise ValueError("Invalid response received from create task API")

            return BakeryTask(
                id=json_response["id"],
                name=json_response["name"],
                collection_id=json_response.get("collection_id"),
                collection_name=collection_name,
                workflow=json_response.get("workflow", {}),
                version=json_response.get("version"),
                description=json_response.get("description"),
                entity_type=json_response.get("entity_type", "task"),
                asset_origin=json_response.get("asset_origin"),
                created_at=json_response.get("created_at"),
            )
        except Exception as e:
            raise Exception(
                f"Failed to create task {task_name} in collection {collection_name}: {e}"
            ) from e

    def update_task(self, task_id: str, params: dict) -> BakeryTask:
        """Update a task."""
        endpoint = f"/tasks/{task_id}"  # As per API: PUT /tasks/{task_id}
        try:
            response = self._request("PUT", endpoint, json_data=params)
            json_response = response.json()
            if "id" not in json_response or "name" not in json_response:
                raise ValueError("Invalid response received from update task API")

            return BakeryTask(
                id=json_response["id"],
                name=json_response["name"],
                collection_id=json_response.get("collection_id"),
                workflow=json_response.get("workflow", {}),
                version=json_response.get("version"),
                description=json_response.get("description"),
                entity_type=json_response.get("entity_type", "task"),
                asset_origin=json_response.get("asset_origin"),
                created_at=json_response.get("created_at"),
            )
        except Exception as e:
            raise Exception(f"Failed to update task {task_id}: {e}") from e

    def list_tasks(self, skip: int = 0, limit: int = 100) -> list[BakeryTask]:
        """List all tasks."""
        endpoint = "/tasks/"
        params = {"skip": skip, "limit": limit}
        try:
            response = self._request("GET", endpoint, params=params)
            tasks_data = response.json()
            
            tasks = []
            for task_data in tasks_data:
                tasks.append(BakeryTask(
                    id=task_data["id"],
                    name=task_data["name"],
                    collection_id=task_data["collection_id"],
                    collection_name=task_data.get("collection_name"),
                    workflow=task_data.get("workflow", {}),
                    version=task_data.get("version"),
                    description=task_data.get("description"),
                    entity_type=task_data.get("entity_type", "task"),
                    asset_origin=task_data.get("asset_origin"),
                    created_at=task_data.get("created_at"),
                ))
            return tasks
        except Exception as e:
            raise Exception(f"Failed to list tasks: {e}") from e

    def search_tasks(self, query: str, limit: int = 30) -> list[dict]:
        """Search for tasks using a query string."""
        endpoint = "/tasks/search"
        params = {"q": query, "limit": limit}
        try:
            response = self._request("GET", endpoint, params=params)
            return response.json()
        except Exception as e:
            raise Exception(f"Failed to search tasks: {e}") from e

    def delete_task(self, task_id: str) -> None:
        """Delete a task."""
        endpoint = f"/tasks/{task_id}"
        try:
            response = self._request("DELETE", endpoint)
            if response.status_code != 204:
                raise ValueError("Unexpected response code from delete task API")
        except Exception as e:
            raise Exception(f"Failed to delete task {task_id}: {e}") from e

    def push_task(
        self,
        task_identifier: str,  # e.g., "collection_name/task_name"
        workflow: dict[str, Any],
        version: str | None = None,
        description: str | None = None,
        asset_origin: str | None = None,
    ) -> BakeryTask:
        """Push a task to the bakery.

        Args:
            task_identifier: String in the format 'collection_name/task_name'.
            workflow: Dictionary containing the workflow definition.
            version: Optional version string for the task.
            description: Optional description of the task.
            asset_origin: Optional string indicating the origin of the task.

        Returns:
            The BakeryTask object representing the pushed task.
        """
        if "/" not in task_identifier:
            raise ValueError(
                "task_identifier must be in the format 'collection_name/task_name'"
            )
        collection_name, task_name = task_identifier.split("/", 1)

        collection = self.find_or_create_by_collection_name(collection_name)
        if not collection:
            raise Exception(f"Failed to find or create collection {collection_name}")

        existing_task = self.get_task_by_name(collection_name, task_name)

        entity_payload = {
            "workflow": workflow,
            "version": version,
            "description": description,
            "asset_origin": asset_origin,
        }
        
        # Filter out None values from payload to avoid overwriting existing fields
        entity_payload_for_update = {k: v for k, v in entity_payload.items() if v is not None}

        pushed_task: BakeryTask
        if existing_task:
            # Update existing task
            _LOGGER.info(
                f"Updating task {task_name} in collection {collection_name}"
            )
            pushed_task = self.update_task(existing_task.id, entity_payload_for_update)
        else:
            # Create new task
            _LOGGER.info(
                f"Creating task {task_name} in collection {collection_name}"
            )
            creation_payload = entity_payload.copy()
            pushed_task = self.create_task(
                collection_name,
                task_name,
                workflow,
                creation_payload,
            )
        
        # Fetch the final state of the task after creation/update
        final_task = self.get_task_by_name(collection_name, task_name)
        if not final_task:
            _LOGGER.error(f"Failed to retrieve task {collection_name}/{task_name} after push operation.")
            return pushed_task 
        return final_task
