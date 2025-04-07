import dataclasses
import io
import json
import requests
import mlcroissant
import logging  

import pandas as pd

_LOGGER = logging.getLogger(__name__)

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

class BakeryClient:
    def __init__(self, bakery_url: str = "http://localhost:8000"):
        self.bakery_url = bakery_url + "/api/v1"

    def find_or_create_by_collection_name(
        self, collection_name: str
    ) -> BakeryCollection:
        """Get a collection by collection name and create it if it doesn't exist."""
        collection_url = f"{self.bakery_url}/collections"
        response = requests.get(collection_url)
        collections = [
            BakeryCollection(
                id=c["id"],
                name=c["name"],
                description=c["description"],
            )
            for c in response.json()
        ]

        for collection in collections:
            if collection.name == collection_name:
                return collection

        # If collection doesn't exist, create it
        response = requests.post(
            collection_url, json={"name": collection_name, "description": ""}
        )
        if response.status_code != 200:
            raise Exception(
                f"Failed to create collection {collection_name}: {response.text}"
            )
        json_response = response.json()
        return BakeryCollection(
            id=json_response["id"],
            name=json_response["name"],
            description=json_response["description"],
        )

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
        collection_name = dataset_path.split("/")[0]
        dataset_name = dataset_path.split("/")[1]
        collection = self.find_or_create_by_collection_name(collection_name)

        # find the dataset in the collection
        dataset = self.get_dataset_by_name(collection_name, dataset_name)
        if dataset:
            # put the dataset:
            dataset = self.update_dataset(
                dataset.id,
                {
                    "name": dataset_name,
                    "collection_id": collection.id,
                    "dataset_metadata": metadata.jsonld,
                    "data_path": data_path,
                    "format": format,
                },
            )
        else:
            # create the dataset:
            print(
                f"Creating dataset {dataset_name} in collection {collection_name} with {collection.id}"
            )
            dataset = self.create_dataset(
                collection.id,
                dataset_name,
                {
                    "dataset_metadata": metadata.jsonld,
                    "data_path": data_path,
                    "format": format,
                    "long_description": long_description,
                },
            )
        # update the preview:
        self.save_preview(dataset.id, preview)
        return self.get_dataset_by_name(collection_name, dataset_name)

    def get_dataset_by_name(
        self, collection_name: str, dataset_name: str
    ) -> BakeryDataset | None:
        """Get a dataset by name in a collection if it exists."""
        dataset_url = f"{self.bakery_url}/datasets/{collection_name}/{dataset_name}"
        response = requests.get(dataset_url)
        if response.status_code != 200:
            return None
        dataset_response = response.json()

        json_str = dataset_response["dataset_metadata"]
        metadata = None
        if json_str and "@context" in json_str:
            metadata = mlcroissant.Dataset(jsonld=json_str)

        preview = self.get_preview(dataset_response["id"])
        _LOGGER.info(dataset_response.keys())
        return BakeryDataset(
            id=dataset_response["id"],
            name=dataset_response["name"],
            collection_id=dataset_response["collection_id"],
            metadata=metadata,
            preview=preview,
            metadata_version=dataset_response.get("metadata_version", ""),
            format=dataset_response.get("format", ""),
            created_at=dataset_response.get("created_at", ""),
            data_path=dataset_response.get("data_path", ""),
            long_description=dataset_response.get("long_description", ""),
        )

    def get_preview(self, dataset_id: str) -> pd.DataFrame:
        """Get a preview for a dataset."""
        preview_url = f"{self.bakery_url}/datasets/{dataset_id}/preview"
        response = requests.get(preview_url)
        if response.status_code != 200:
            return None
        return pd.read_parquet(io.BytesIO(response.content))

    def create_dataset(
        self, collection_id: str, dataset_name: str, params: dict = dict()
    ) -> BakeryDataset:
        """Create a dataset in a collection."""
        dataset_url = f"{self.bakery_url}/datasets"
        response = requests.post(
            dataset_url,
            json={
                "name": dataset_name,
                "collection_id": collection_id,
                "entity_type": "dataset",
                **params,
            },
        )
        json_response = response.json()
        if "id" not in json_response:
            raise Exception(
                f"Failed to create dataset {dataset_name} in collection {collection_id}: {json_response}"
            )
        return BakeryDataset(
            id=json_response["id"],
            name=json_response["name"],
            collection_id=json_response["collection_id"],
        )

    def update_dataset(self, dataset_id: str, params: dict):
        """Update a dataset."""
        metadata_url = f"{self.bakery_url}/datasets/{dataset_id}"
        response = requests.put(metadata_url, json=params)
        if response.status_code != 200:
            raise Exception(
                f"Failed to update metadata to dataset {dataset_id}: {response.text}"
            )
        json_response = response.json()
        return BakeryDataset(
            id=json_response["id"],
            name=json_response["name"],
            collection_id=json_response["collection_id"],
        )

    def save_metadata(self, dataset_id: str, metadata: dict):
        """Save metadata to a dataset."""
        metadata_url = f"{self.bakery_url}/datasets/{dataset_id}/metadata"
        response = requests.patch(metadata_url, json=metadata)
        if response.status_code != 200:
            raise Exception(
                f"Failed to save metadata to dataset {dataset_id}: {response.text}"
            )

    def save_preview(self, dataset_id: str, preview: bytes):
        """Save a preview to a dataset."""
        preview_url = f"{self.bakery_url}/datasets/{dataset_id}/preview"
        files = {"preview": ("preview.parquet", preview, "application/parquet")}
        response = requests.put(preview_url, files=files)
        if response.status_code != 200:
            raise Exception(
                f"Failed to save preview to dataset {dataset_id}: {response.text}"
            )

    def fork_dataset(
        self,
        origin: BakeryDataset,
        destination: str,
        data_path: str,
        format: str,
        metadata: mlcroissant.Dataset,
        preview: bytes,
    ):
        """Fork a dataset."""
        forked_dataset = self.push_dataset(
            destination, data_path, format, metadata, preview
        )
        # define an activity
        activity_url = f"{self.bakery_url}/activities"

        response = requests.post(
            activity_url,
            json={
                "name": "Forked Dataset",
                "input_entity_ids": [origin.id],
                "output_entity_id": forked_dataset.id,
            },
        )
        print(response.json())
        return forked_dataset

    def get_upstream_entities(self, collection_name: str, dataset_name: str):
        """Get the upstream entities for a dataset."""
        activity_url = (
            f"{self.bakery_url}/datasets/{collection_name}/{dataset_name}/upstream"
        )
        response = requests.get(activity_url)
        if response.status_code != 200:
            return None
        return response.json()

    def get_datasets_by_collection(self, collection_name: str):
        """Get all datasets for a collection."""
        collection_url = f"{self.bakery_url}/collections/{collection_name}/datasets"
        response = requests.get(collection_url)
        return response.json()

    def get_collections(self):
        """Get all collections."""
        collection_url = f"{self.bakery_url}/collections"
        response = requests.get(collection_url)
        return response.json()
