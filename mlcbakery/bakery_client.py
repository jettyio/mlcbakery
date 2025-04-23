import dataclasses
import io
import json
import logging
from typing import Any, Tuple, Optional

import requests
import mlcroissant
import pandas as pd

_LOGGER = logging.getLogger(__name__)

AuthType = Optional[Tuple[str, str]]  # Define a type alias for auth credentials
TokenType = Optional[str] # Define a type alias for bearer token

@dataclasses.dataclass
class BakeryCollection:
    id: str
    name: str
    description: str


@dataclasses.dataclass
class BakeryDataset:
    id: str
    name: str
    collection_id: str
    parent_collection_dataset: str | None = None
    metadata: mlcroissant.Dataset | None = None
    preview: pd.DataFrame | None = None
    format: str | None = None
    created_at: str | None = None
    metadata_version: str | None = None
    data_path: str | None = None
    long_description: str | None = None


class Client:
    def __init__(
        self,
        bakery_url: str = "http://localhost:8000",
        token: TokenType = None, # Changed from auth: AuthType
    ):
        """
        Initializes the BakeryClient.

        Args:
            bakery_url: The base URL of the MLC Bakery API.
            token: Optional bearer token for authentication.
        """
        self.bakery_url = bakery_url.rstrip('/') + "/api/v1"
        self.token = token # Store the token

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        files: Optional[dict[str, Any]] = None,
    ) -> requests.Response:
        """Helper method to make requests to the Bakery API."""
        url = f"{self.bakery_url}/{endpoint.lstrip('/')}"
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        response = requests.request(
            method=method,
            url=url,
            params=params,
            json=json_data,
            files=files,
            headers=headers,
        )
        response.raise_for_status()  # Let this raise HTTPError for bad responses
        return response

    def find_or_create_by_collection_name(
        self, collection_name: str
    ) -> BakeryCollection:
        """Get a collection by collection name and create it if it doesn't exist."""
        try:
            response = self._request("GET", "/collections")
            collections_data = response.json()
        except Exception as e:
             # If GET fails (e.g., 404 if no collections yet), proceed to create
             _LOGGER.warning(f"Could not list collections, attempting to create: {e}")
             collections_data = []


        for c in collections_data:
            if c.get("name") == collection_name:
                return BakeryCollection(
                    id=c["id"], name=c["name"], description=c.get("description", "")
                )

        # If collection doesn't exist, create it
        try:
            response = self._request(
                "POST",
                "/collections",
                json_data={"name": collection_name, "description": ""},
            )
            json_response = response.json()
            return BakeryCollection(
                id=json_response["id"],
                name=json_response["name"],
                description=json_response.get("description", ""),
            )
        except Exception as e:
            raise Exception(
                f"Failed to create collection {collection_name}: {e}"
            ) from e

    def push_dataset(
        self,
        dataset_path: str,
        data_path: str,
        format: str,
        metadata: mlcroissant.Dataset,
        preview: bytes,
        long_description: str | None = None,
    ) -> BakeryDataset:
        """Push a dataset to the bakery."""
        if "/" not in dataset_path:
            raise ValueError("dataset_path must be in the format 'collection_name/dataset_name'")
        collection_name, dataset_name = dataset_path.split("/", 1)

        collection = self.find_or_create_by_collection_name(collection_name)

        dataset = self.get_dataset_by_name(collection_name, dataset_name)

        update_payload = {
            "name": dataset_name,
            "collection_id": collection.id,
            "dataset_metadata": metadata.jsonld,
            "data_path": data_path,
            "format": format,
            "long_description": long_description,
        }
        # Filter out None values from payload to avoid overwriting existing fields with null
        update_payload = {k: v for k, v in update_payload.items() if v is not None}


        if dataset:
            # Update existing dataset
            _LOGGER.info(f"Updating dataset {dataset_name} in collection {collection_name}")
            dataset = self.update_dataset(
                dataset.id,
                update_payload
            )
        else:
            # Create new dataset
            _LOGGER.info(
                f"Creating dataset {dataset_name} in collection {collection_name} with collection_id {collection.id}"
            )
            # Use the same payload structure, but long_description might be specific to creation
            create_payload = update_payload.copy() # Start with common fields
            # Add any fields specific to creation if needed, though structure seems similar

            dataset = self.create_dataset(
                collection.id,
                dataset_name,
                create_payload, # Pass prepared payload
            )

        # Update the preview regardless of create/update
        if preview:
            self.save_preview(dataset.id, preview)

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
            print(json_str)
            
            metadata = None
            if json_str and "@context" in json_str:
                 try:
                     # The API returns metadata as a dict, mlcroissant expects file path or dict
                     metadata = mlcroissant.Dataset(jsonld=json_str)
                 except Exception as e:
                     _LOGGER.error(f"Failed to parse Croissant metadata for dataset {dataset_response.get('id')}: {e}")
                     metadata = None # Set to None if parsing fails

            preview_df = None
            try:
                preview_df = self.get_preview(dataset_response["id"])
            except Exception as e:
                 _LOGGER.warning(f"Could not fetch or parse preview for dataset {dataset_response.get('id')}: {e}")


            return BakeryDataset(
                id=dataset_response["id"],
                name=dataset_response["name"],
                collection_id=dataset_response["collection_id"],
                metadata=metadata,
                preview=preview_df,
                metadata_version=dataset_response.get("metadata_version"),
                format=dataset_response.get("format"),
                created_at=dataset_response.get("created_at"),
                data_path=dataset_response.get("data_path"),
                long_description=dataset_response.get("long_description"),
            )
        except requests.exceptions.HTTPError as e:
             if e.response.status_code == 404:
                 _LOGGER.info(f"Dataset '{collection_name}/{dataset_name}' not found.")
                 return None
             else:
                 _LOGGER.error(f"HTTP error fetching dataset '{collection_name}/{dataset_name}': {e}")
                 raise # Re-raise other HTTP errors
        except Exception as e:
            _LOGGER.error(f"Error fetching dataset '{collection_name}/{dataset_name}': {e}")
            raise


    def get_preview(self, dataset_id: str) -> pd.DataFrame | None:
        """Get a preview for a dataset."""
        endpoint = f"/datasets/{dataset_id}/preview"
        try:
            response = self._request("GET", endpoint)
            # Check content type? API might return 404 or empty if no preview
            if response.status_code == 200 and response.content:
                 # Check if content is actually parquet before trying to read
                 # A simple check might involve magic bytes or content type header if reliable
                 # Assuming it's parquet if status is 200 and content exists
                 return pd.read_parquet(io.BytesIO(response.content))
            else:
                 _LOGGER.info(f"No preview content found for dataset {dataset_id} (status: {response.status_code}).")
                 return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                 _LOGGER.info(f"Preview for dataset {dataset_id} not found.")
                 return None
            else:
                 _LOGGER.error(f"HTTP error fetching preview for dataset {dataset_id}: {e}")
                 raise # Re-raise other HTTP errors
        except Exception as e:
            _LOGGER.error(f"Error fetching or parsing preview for dataset {dataset_id}: {e}")
            # Decide if to return None or raise. Returning None might be safer.
            return None


    def create_dataset(
        self, collection_id: str, dataset_name: str, params: dict = dict()
    ) -> BakeryDataset:
        """Create a dataset in a collection."""
        endpoint = "/datasets"
        payload = {
            "name": dataset_name,
            "collection_id": collection_id,
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
                collection_id=json_response.get("collection_id", collection_id), # Use provided collection_id if not in response
                 # Include other fields if the API returns them on creation
                metadata=None, # Metadata likely not set on creation
                preview=None, # Preview not set on creation
                format=json_response.get("format"),
                data_path=json_response.get("data_path"),
                long_description=json_response.get("long_description"),
            )
        except Exception as e:
            raise Exception(
                f"Failed to create dataset {dataset_name} in collection {collection_id}: {e}"
            ) from e

    def update_dataset(self, dataset_id: str, params: dict) -> BakeryDataset:
        """Update a dataset."""
        endpoint = f"/datasets/{dataset_id}"
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
                metadata=None, # Or fetch if needed: self.get_dataset_by_name(...)
                preview=None, # Or fetch if needed: self.get_preview(...)
            )

        except Exception as e:
            raise Exception(
                f"Failed to update dataset {dataset_id}: {e}"
            ) from e

    def save_metadata(self, dataset_id: str, metadata: dict):
        """Save metadata to a dataset. Assumes metadata is a JSON-serializable dict."""
        endpoint = f"/datasets/{dataset_id}/metadata"
        try:
            # Changed to PUT as per discussion? Or is PATCH correct? Assuming PATCH.
            response = self._request("PATCH", endpoint, json_data=metadata)
             # No return value needed, just raise on error
        except Exception as e:
            raise Exception(
                f"Failed to save metadata to dataset {dataset_id}: {e}"
            ) from e

    def save_preview(self, dataset_id: str, preview: bytes):
        """Save a preview (as parquet bytes) to a dataset."""
        endpoint = f"/datasets/{dataset_id}/preview"
        files = {"preview": ("preview.parquet", preview, "application/parquet")}
        try:
            # PUT seems appropriate for replacing/uploading the preview file
            response = self._request("PUT", endpoint, files=files)
            # No return value needed, just raise on error
        except Exception as e:
            raise Exception(
                f"Failed to save preview to dataset {dataset_id}: {e}"
            ) from e

    def fork_dataset(
        self,
        origin: BakeryDataset,
        destination_path: str, # Changed from 'destination' to 'destination_path' for clarity
        data_path: str,
        format: str,
        metadata: mlcroissant.Dataset,
        preview: bytes,
        long_description: str | None = None, # Added long_description
    ) -> BakeryDataset:
        """Fork a dataset by pushing it to a new destination."""
        # Push acts like create or update, handles finding/creating collection
        forked_dataset = self.push_dataset(
            destination_path, data_path, format, metadata, preview, long_description
        )

        # Define an activity recording the fork
        activity_endpoint = "/activities"
        activity_payload = {
            "name": f"Forked dataset {origin.name} to {forked_dataset.name}", # More descriptive name
            "description": f"Forked from {origin.collection_id}/{origin.name} (ID: {origin.id}) to {forked_dataset.collection_id}/{forked_dataset.name} (ID: {forked_dataset.id})",
            "activity_type": "fork", # Added activity type for clarity
            "input_entity_ids": [origin.id],
            "output_entity_id": forked_dataset.id,
             # Add other relevant context if needed
             #"context": {"user": "...", "reason": "..."}
        }

        try:
            response = self._request("POST", activity_endpoint, json_data=activity_payload)
            activity_response = response.json()
            _LOGGER.info(f"Fork activity recorded: {activity_response.get('id')}")
        except Exception as e:
            # Log error but don't fail the whole fork operation if activity logging fails
            _LOGGER.error(f"Failed to record fork activity for dataset {forked_dataset.id} from {origin.id}: {e}")

        return forked_dataset # Return the newly created/updated dataset


    def get_upstream_entities(self, collection_name: str, dataset_name: str) -> list[dict] | None:
        """Get the upstream entities (provenance) for a dataset."""
        endpoint = f"/datasets/{collection_name}/{dataset_name}/upstream"
        try:
            response = self._request("GET", endpoint)
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                 _LOGGER.info(f"Upstream entities for dataset '{collection_name}/{dataset_name}' not found (or dataset itself not found).")
                 return None # Return None if the dataset or upstream info doesn't exist
            else:
                 _LOGGER.error(f"HTTP error fetching upstream entities for '{collection_name}/{dataset_name}': {e}")
                 raise # Re-raise other HTTP errors
        except Exception as e:
            _LOGGER.error(f"Error fetching upstream entities for '{collection_name}/{dataset_name}': {e}")
            raise # Re-raise unexpected errors

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
                 _LOGGER.info(f"Collection '{collection_name}' not found or has no datasets.")
                 return [] # Return empty list if collection not found
            else:
                 _LOGGER.error(f"HTTP error fetching datasets for collection '{collection_name}': {e}")
                 raise
        except Exception as e:
            _LOGGER.error(f"Error fetching datasets for collection '{collection_name}': {e}")
            raise


    def get_collections(self) -> list[BakeryCollection]:
        """List all available collections."""
        endpoint = "/collections"
        collections = []
        try:
            response = self._request("GET", endpoint)
            collections_data = response.json()
            for c_data in collections_data:
                 collections.append(
                     BakeryCollection(
                         id=c_data["id"],
                         name=c_data["name"],
                         description=c_data.get("description", ""), # Handle potentially missing description
                     )
                 )
            return collections
        except Exception as e:
            _LOGGER.error(f"Error fetching collections: {e}")
            # Depending on desired behavior, could return empty list or raise
            raise # Raising for now, as listing collections seems fundamental 