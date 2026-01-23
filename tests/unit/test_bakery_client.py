import unittest
from unittest.mock import patch, Mock, MagicMock
import io
import json
import tempfile
import os

import pandas as pd
import requests
import mlcroissant
from mlcbakery.bakery_client import (
    Client,
    BakeryDataset,
    BakeryCollection,
    BakeryModel,
    BakeryTask,
)

# Sample data for mocking
SAMPLE_TOKEN = "sample_bearer_token"
SAMPLE_URL = "http://fakebakery.com"
API_URL = f"{SAMPLE_URL}/api/v1"
SAMPLE_COLLECTION_NAME = "test_collection"
SAMPLE_DATASET_NAME = "test_dataset"
SAMPLE_DATASET_PATH = f"{SAMPLE_COLLECTION_NAME}/{SAMPLE_DATASET_NAME}"
SAMPLE_COLLECTION_ID = "col_123"
SAMPLE_DATASET_ID = "ds_456"
SAMPLE_MODEL_NAME = "test_model"
SAMPLE_MODEL_ID = "mod_789"
SAMPLE_TASK_NAME = "test_task"
SAMPLE_TASK_ID = "task_101"

# Load valid JSON for metadata mock once
try:
    with open("tests/data/valid_mlcroissant.json", "r") as f:
        CROISSANT_METADATA_JSON = json.load(f)
except FileNotFoundError:
    CROISSANT_METADATA_JSON = {
        "@context": "http://schema.org/",
        "@type": "Dataset",
        "name": "Fallback Croissant Test",
        "description": "Minimal fallback.",
    }
    print("Warning: tests/data/valid_mlcroissant.json not found, using fallback.")
except json.JSONDecodeError:
    raise ValueError("Error decoding tests/data/valid_mlcroissant.json")


class TestBakeryClientAuth(unittest.TestCase):
    def test_init_no_token(self):
        """Test client initialization without a token."""
        client = Client(bakery_url=SAMPLE_URL)
        self.assertEqual(client.bakery_url, API_URL)
        self.assertIsNone(client.token)

    def test_init_with_token(self):
        """Test client initialization with a token."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        self.assertEqual(client.bakery_url, API_URL)
        self.assertEqual(client.token, SAMPLE_TOKEN)

    @patch("requests.request")
    def test_request_helper_no_token(self, mock_request):
        """Test the _request helper sends no Authorization header when no token."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL)
        client._request("GET", "/some_endpoint")

        mock_request.assert_called_once()
        call_args, call_kwargs = mock_request.call_args
        self.assertNotIn("Authorization", call_kwargs.get("headers", {}))
        self.assertEqual(call_kwargs.get("url"), f"{API_URL}/some_endpoint")
        self.assertEqual(call_kwargs.get("method"), "GET")
        self.assertNotIn("auth", call_kwargs)

    @patch("requests.request")
    def test_request_helper_with_token(self, mock_request):
        """Test the _request helper sends the correct Authorization header."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        client._request("POST", "/another_endpoint", json_data={"key": "value"})

        mock_request.assert_called_once()
        call_args, call_kwargs = mock_request.call_args
        # Expect default headers plus Authorization
        expected_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {SAMPLE_TOKEN}",
        }
        self.assertEqual(call_kwargs.get("headers"), expected_headers)
        self.assertEqual(call_kwargs.get("url"), f"{API_URL}/another_endpoint")
        self.assertEqual(call_kwargs.get("method"), "POST")
        self.assertEqual(call_kwargs.get("json"), {"key": "value"})
        self.assertNotIn("auth", call_kwargs)

    
    # Patch the actual requests.request call for detailed header checks
    @patch("requests.request")
    def test_push_dataset_sends_token(self, mock_http_request):
        """Test push_dataset sends the correct Authorization header via requests.request."""
        # Mock responses for each HTTP call made by push_dataset
        mock_get_collections_resp = Mock(spec=requests.Response)
        mock_get_collections_resp.json.return_value = [
            {
                "id": SAMPLE_COLLECTION_ID,
                "name": SAMPLE_COLLECTION_NAME,
                "description": "",
            }
        ]
        mock_create_dataset_resp = Mock(spec=requests.Response)
        mock_create_dataset_resp.json.return_value = {
            "id": SAMPLE_DATASET_ID,
            "name": SAMPLE_DATASET_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
        }
        mock_save_preview_resp = Mock(spec=requests.Response)
        mock_get_dataset_final_resp = Mock(spec=requests.Response)
        mock_get_dataset_final_resp.json.return_value = {
            "id": SAMPLE_DATASET_ID,
            "name": SAMPLE_DATASET_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "dataset_metadata": CROISSANT_METADATA_JSON,
            "format": "parquet",
            "data_path": "s3://bucket/data.parquet",
            "long_description": "A test dataset.",
        }
        mock_get_preview_resp = Mock(spec=requests.Response)
        df = pd.DataFrame({"col1": [1], "col2": [2]})
        buf = io.BytesIO()
        df.to_parquet(buf)
        buf.seek(0)
        mock_get_preview_resp.content = buf.read()
        mock_get_preview_resp.status_code = 200

        # HTTP 404 Error mock for get_dataset_by_name first call
        mock_http_404 = requests.exceptions.HTTPError(response=Mock(status_code=404))

        # Configure the side_effect for requests.request
        def http_request_side_effect(*args, **kwargs):
            method = kwargs.get("method")
            url = kwargs.get("url")
            print(f"Mock HTTP Request: {method} {url}")  # Debug print

            # Assert headers are correct on every call
            # Expect default headers plus Authorization
            expected_headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {SAMPLE_TOKEN}",
            }
            # For file uploads (PUT preview), Content-Type might be different or absent
            # The requests library might handle this automatically for multipart/form-data
            actual_headers = kwargs.get("headers")
            files = kwargs.get("files")
            if method == "PUT" and "/preview" in url and files:
                # Don't strictly check Content-Type for file uploads
                self.assertIn("Authorization", actual_headers)
                self.assertEqual(
                    actual_headers.get("Authorization"),
                    expected_headers["Authorization"],
                )
                # Accept might still be present
                # self.assertEqual(actual_headers.get("Accept"), expected_headers["Accept"])
            else:
                self.assertEqual(
                    actual_headers,
                    expected_headers,
                    f"Header mismatch for {method} {url}",
                )

            self.assertNotIn("auth", kwargs, f"Auth param used for {method} {url}")

            # Determine response based on URL and method
            if method == "GET" and url == f"{API_URL}/collections":
                print("  -> Responding for GET /collections (list all)")
                return mock_get_collections_resp
            elif method == "GET" and url == f"{API_URL}/collections/{SAMPLE_COLLECTION_NAME}":
                print(f"  -> Simulating 404 for GET {url}")
                mock_404_response = Mock(spec=requests.Response)
                mock_404_response.status_code = 404
                mock_404_response.raise_for_status.side_effect = mock_http_404
                return mock_404_response
            elif (
                method == "GET"
                and url
                == f"{API_URL}/datasets/{SAMPLE_COLLECTION_NAME}/{SAMPLE_DATASET_NAME}"
            ):
                if http_request_side_effect.get_dataset_call_count == 0:
                    http_request_side_effect.get_dataset_call_count += 1
                    print("  -> Simulating 404 for GET dataset")
                    # Simulate raise_for_status behavior for 404
                    mock_404_response = Mock(spec=requests.Response)
                    mock_404_response.status_code = 404
                    mock_404_response.raise_for_status.side_effect = mock_http_404
                    return mock_404_response
                else:
                    print("  -> Responding for final GET dataset")
                    return mock_get_dataset_final_resp
            elif method == "POST" and url == f"{API_URL}/datasets/{SAMPLE_COLLECTION_NAME}":
                print("  -> Responding for POST /datasets")
                return mock_create_dataset_resp
            elif method == "PUT" and "/preview" in url:
                print("  -> Responding for PUT preview")
                return mock_save_preview_resp
            elif "/preview" in url:
                print("  -> Responding for GET preview")
                return mock_get_preview_resp
            elif method == "POST" and url == f"{API_URL}/collections/":
                print("  -> Responding for POST /collections (create)")
                # Return a mock response for collection creation
                mock_create_collection_resp = Mock(spec=requests.Response)
                mock_create_collection_resp.json.return_value = {
                    "id": SAMPLE_COLLECTION_ID,
                    "name": SAMPLE_COLLECTION_NAME,
                    "description": "",
                }
                return mock_create_collection_resp
            # Add other endpoints if needed by push_dataset internal logic (e.g., PATCH metadata?)
            else:
                print(f"  -> Unexpected HTTP request: {method} {url}")
                raise ValueError(f"Unhandled mock HTTP request: {method} {url}")

        http_request_side_effect.get_dataset_call_count = 0

        mock_http_request.side_effect = http_request_side_effect

        # Initialize client with token
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)

        mock_metadata = MagicMock(spec=mlcroissant.Dataset)
        mock_metadata.jsonld = CROISSANT_METADATA_JSON
        preview_bytes = b"dummy parquet data"

        # Call the method under test
        result_dataset = client.push_dataset(
            dataset_path=SAMPLE_DATASET_PATH,
            data_path="s3://bucket/data.parquet",
            format="parquet",
            metadata=mock_metadata,
            preview=preview_bytes,
            long_description="A test dataset.",
        )

        # Assertions on the result
        self.assertIsInstance(result_dataset, BakeryDataset)
        self.assertEqual(result_dataset.id, SAMPLE_DATASET_ID)
        self.assertEqual(result_dataset.name, SAMPLE_DATASET_NAME)
        # ... add other relevant assertions on the result_dataset fields ...

        # Verify requests.request was called multiple times
        self.assertGreater(mock_http_request.call_count, 2)
        # Header/auth checks are now inside the side_effect


class TestCollectionOperations(unittest.TestCase):
    """Tests for collection-related operations."""

    @patch("requests.request")
    def test_get_collection_by_name_success(self, mock_request):
        """Test successful retrieval of a collection by name."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "Test description",
            "auth_org_id": "org_123",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        collection = client.get_collection_by_name(SAMPLE_COLLECTION_NAME)

        self.assertIsInstance(collection, BakeryCollection)
        self.assertEqual(collection.id, SAMPLE_COLLECTION_ID)
        self.assertEqual(collection.name, SAMPLE_COLLECTION_NAME)
        self.assertEqual(collection.description, "Test description")
        self.assertEqual(collection.auth_org_id, "org_123")

    @patch("requests.request")
    def test_get_collection_by_name_not_found(self, mock_request):
        """Test get_collection_by_name raises exception when not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(Exception) as context:
            client.get_collection_by_name("nonexistent")
        self.assertIn("Failed to get collection", str(context.exception))

    @patch("requests.request")
    def test_create_collection_success(self, mock_request):
        """Test successful collection creation."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "New collection",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        collection = client.create_collection(SAMPLE_COLLECTION_NAME, "New collection")

        self.assertIsInstance(collection, BakeryCollection)
        self.assertEqual(collection.name, SAMPLE_COLLECTION_NAME)
        self.assertEqual(collection.description, "New collection")

        # Verify the request was made correctly
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["method"], "POST")
        self.assertIn("/collections/", call_kwargs["url"])
        self.assertEqual(call_kwargs["json"]["name"], SAMPLE_COLLECTION_NAME)

    @patch("requests.request")
    def test_get_collections_success(self, mock_request):
        """Test listing all collections."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {"id": "col_1", "name": "collection_1", "description": "First", "auth_org_id": "org_1"},
            {"id": "col_2", "name": "collection_2", "description": "Second", "auth_org_id": "org_2"},
        ]
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        collections = client.get_collections()

        self.assertEqual(len(collections), 2)
        self.assertIsInstance(collections[0], BakeryCollection)
        self.assertEqual(collections[0].name, "collection_1")
        self.assertEqual(collections[1].name, "collection_2")

    @patch("requests.request")
    def test_get_collection_storage_info_success(self, mock_request):
        """Test getting collection storage info."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "Test",
            "storage_info": {"bucket": "my-bucket"},
            "storage_provider": "gcp",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        collection = client.get_collection_storage_info(SAMPLE_COLLECTION_NAME)

        self.assertEqual(collection.storage_provider, "gcp")
        self.assertEqual(collection.storage_info["bucket"], "my-bucket")

    @patch("requests.request")
    def test_get_collection_storage_info_not_found(self, mock_request):
        """Test get_collection_storage_info raises ValueError when not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.get_collection_storage_info("nonexistent")
        self.assertIn("not found", str(context.exception))

    @patch("requests.request")
    def test_update_collection_storage_info_success(self, mock_request):
        """Test updating collection storage info."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "Test",
            "storage_info": {"bucket": "new-bucket"},
            "storage_provider": "aws",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        collection = client.update_collection_storage_info(
            SAMPLE_COLLECTION_NAME,
            storage_info={"bucket": "new-bucket"},
            storage_provider="aws",
        )

        self.assertEqual(collection.storage_provider, "aws")
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["method"], "PATCH")

    def test_update_collection_storage_info_no_params(self):
        """Test update_collection_storage_info raises ValueError when no params."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.update_collection_storage_info(SAMPLE_COLLECTION_NAME)
        self.assertIn("At least one of", str(context.exception))

    @patch("requests.request")
    def test_find_or_create_by_collection_name_existing(self, mock_request):
        """Test find_or_create returns existing collection."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "Existing",
            "auth_org_id": "",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        collection = client.find_or_create_by_collection_name(SAMPLE_COLLECTION_NAME)

        self.assertEqual(collection.name, SAMPLE_COLLECTION_NAME)
        # Should only call GET, not POST
        self.assertEqual(mock_request.call_count, 1)


class TestDatasetOperations(unittest.TestCase):
    """Tests for dataset-related operations."""

    @patch("requests.request")
    def test_get_dataset_by_name_success(self, mock_request):
        """Test successful retrieval of a dataset by name."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_DATASET_ID,
            "name": SAMPLE_DATASET_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "format": "parquet",
            "data_path": "/data/path",
            "long_description": "A test dataset",
            "metadata_version": "1.0.0",
            "asset_origin": "test",
            "created_at": "2024-01-01T00:00:00Z",
            "dataset_metadata": None,
        }
        # Mock preview response (404 - no preview)
        mock_preview_response = Mock(spec=requests.Response)
        mock_preview_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_preview_response.status_code = 404

        mock_request.side_effect = [mock_response, mock_preview_response]

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        dataset = client.get_dataset_by_name(SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME)

        self.assertIsInstance(dataset, BakeryDataset)
        self.assertEqual(dataset.id, SAMPLE_DATASET_ID)
        self.assertEqual(dataset.name, SAMPLE_DATASET_NAME)
        self.assertEqual(dataset.format, "parquet")
        self.assertEqual(dataset.collection_name, SAMPLE_COLLECTION_NAME)

    @patch("requests.request")
    def test_get_dataset_by_name_not_found(self, mock_request):
        """Test get_dataset_by_name returns None when not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError(response=Mock(status_code=404))
        mock_response.raise_for_status.side_effect = http_error
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        dataset = client.get_dataset_by_name(SAMPLE_COLLECTION_NAME, "nonexistent")

        self.assertIsNone(dataset)

    @patch("requests.request")
    def test_create_dataset_success(self, mock_request):
        """Test successful dataset creation."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_DATASET_ID,
            "name": SAMPLE_DATASET_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "format": "csv",
            "data_path": "/data",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        dataset = client.create_dataset(
            SAMPLE_COLLECTION_NAME,
            SAMPLE_DATASET_NAME,
            {"format": "csv", "data_path": "/data"},
        )

        self.assertIsInstance(dataset, BakeryDataset)
        self.assertEqual(dataset.name, SAMPLE_DATASET_NAME)
        self.assertEqual(dataset.format, "csv")

    @patch("requests.request")
    def test_update_dataset_success(self, mock_request):
        """Test successful dataset update."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_DATASET_ID,
            "name": SAMPLE_DATASET_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "format": "parquet",
            "data_path": "/new/path",
            "long_description": "Updated description",
            "metadata_version": "2.0.0",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        dataset = client.update_dataset(
            SAMPLE_COLLECTION_NAME,
            SAMPLE_DATASET_NAME,
            {"format": "parquet", "long_description": "Updated description"},
        )

        self.assertEqual(dataset.format, "parquet")
        self.assertEqual(dataset.long_description, "Updated description")
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["method"], "PUT")

    @patch("requests.request")
    def test_get_preview_success(self, mock_request):
        """Test successful preview retrieval."""
        df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
        buf = io.BytesIO()
        df.to_parquet(buf)
        buf.seek(0)

        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.content = buf.read()
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        preview = client.get_preview(SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME)

        self.assertIsInstance(preview, pd.DataFrame)
        self.assertEqual(list(preview.columns), ["col1", "col2"])
        self.assertEqual(len(preview), 2)

    @patch("requests.request")
    def test_get_preview_not_found(self, mock_request):
        """Test get_preview returns None when not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        preview = client.get_preview(SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME)

        self.assertIsNone(preview)

    @patch("requests.request")
    def test_save_preview_success(self, mock_request):
        """Test successful preview save."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        preview_bytes = b"fake parquet data"
        client.save_preview(SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME, preview_bytes)

        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["method"], "PUT")
        self.assertIn("files", call_kwargs)

    @patch("requests.request")
    def test_save_metadata_success(self, mock_request):
        """Test successful metadata save."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        metadata = {"@context": "http://schema.org/", "@type": "Dataset"}
        client.save_metadata(SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME, metadata)

        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["method"], "PATCH")
        self.assertEqual(call_kwargs["json"], metadata)

    @patch("requests.request")
    def test_get_datasets_by_collection_success(self, mock_request):
        """Test listing datasets in a collection."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {"id": "ds_1", "name": "dataset_1", "collection_id": SAMPLE_COLLECTION_ID, "format": "csv"},
            {"id": "ds_2", "name": "dataset_2", "collection_id": SAMPLE_COLLECTION_ID, "format": "parquet"},
        ]
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        datasets = client.get_datasets_by_collection(SAMPLE_COLLECTION_NAME)

        self.assertEqual(len(datasets), 2)
        self.assertIsInstance(datasets[0], BakeryDataset)
        self.assertEqual(datasets[0].name, "dataset_1")

    @patch("requests.request")
    def test_get_datasets_by_collection_not_found(self, mock_request):
        """Test get_datasets_by_collection returns empty list when not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        datasets = client.get_datasets_by_collection("nonexistent")

        self.assertEqual(datasets, [])

    def test_push_dataset_invalid_path(self):
        """Test push_dataset raises ValueError for invalid path format."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.push_dataset(
                dataset_path="invalid_path_no_slash",
                data_path="/data",
                format="csv",
                metadata={},
            )
        self.assertIn("collection_name/dataset_name", str(context.exception))


class TestSearchOperations(unittest.TestCase):
    """Tests for search operations."""

    @patch("requests.request")
    def test_search_datasets_success(self, mock_request):
        """Test successful dataset search."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "hits": [
                {"document": {"id": "ds_1", "name": "matching_dataset"}},
                {"document": {"id": "ds_2", "name": "another_match"}},
            ]
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        results = client.search_datasets("matching", limit=10)

        self.assertEqual(len(results), 2)
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["params"]["q"], "matching")
        self.assertEqual(call_kwargs["params"]["limit"], 10)

    @patch("requests.request")
    def test_search_datasets_error_returns_empty(self, mock_request):
        """Test search_datasets returns empty list on error."""
        mock_request.side_effect = requests.exceptions.RequestException("Network error")

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        results = client.search_datasets("query")

        self.assertEqual(results, [])

    @patch("requests.request")
    def test_search_models_success(self, mock_request):
        """Test successful model search."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "hits": [
                {"document": {"id": "mod_1", "name": "matching_model"}},
            ]
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        results = client.search_models("matching")

        self.assertEqual(len(results), 1)


class TestModelOperations(unittest.TestCase):
    """Tests for model-related operations."""

    @patch("requests.request")
    def test_get_model_by_name_success(self, mock_request):
        """Test successful retrieval of a model by name."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_MODEL_ID,
            "name": SAMPLE_MODEL_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "model_path": "/models/test.pkl",
            "metadata_version": "1.0.0",
            "model_metadata": {"framework": "sklearn"},
            "asset_origin": "training",
            "long_description": "A test model",
            "model_attributes": {"accuracy": 0.95},
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        model = client.get_model_by_name(SAMPLE_COLLECTION_NAME, SAMPLE_MODEL_NAME)

        self.assertIsInstance(model, BakeryModel)
        self.assertEqual(model.id, SAMPLE_MODEL_ID)
        self.assertEqual(model.name, SAMPLE_MODEL_NAME)
        self.assertEqual(model.model_path, "/models/test.pkl")
        self.assertEqual(model.model_attributes["accuracy"], 0.95)

    @patch("requests.request")
    def test_get_model_by_name_not_found(self, mock_request):
        """Test get_model_by_name returns None when not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        model = client.get_model_by_name(SAMPLE_COLLECTION_NAME, "nonexistent")

        self.assertIsNone(model)

    @patch("requests.request")
    def test_create_model_success(self, mock_request):
        """Test successful model creation."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_MODEL_ID,
            "name": SAMPLE_MODEL_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "model_path": "/models/new.pkl",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        model = client.create_model(
            SAMPLE_COLLECTION_NAME,
            SAMPLE_MODEL_NAME,
            {"model_path": "/models/new.pkl"},
        )

        self.assertIsInstance(model, BakeryModel)
        self.assertEqual(model.name, SAMPLE_MODEL_NAME)

    def test_create_model_missing_model_path(self):
        """Test create_model raises ValueError when model_path is missing."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.create_model(SAMPLE_COLLECTION_NAME, SAMPLE_MODEL_NAME, {})
        self.assertIn("model_path is required", str(context.exception))

    @patch("requests.request")
    def test_update_model_success(self, mock_request):
        """Test successful model update."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_MODEL_ID,
            "name": SAMPLE_MODEL_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "model_path": "/models/updated.pkl",
            "long_description": "Updated model",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        model = client.update_model(
            SAMPLE_MODEL_ID,
            {"model_path": "/models/updated.pkl", "long_description": "Updated model"},
        )

        self.assertEqual(model.model_path, "/models/updated.pkl")
        self.assertEqual(model.long_description, "Updated model")

    def test_push_model_invalid_identifier(self):
        """Test push_model raises ValueError for invalid identifier format."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.push_model(
                model_identifier="invalid_no_slash",
                model_physical_path="/models/test.pkl",
            )
        self.assertIn("collection_name/model_name", str(context.exception))


class TestTaskOperations(unittest.TestCase):
    """Tests for task-related operations."""

    @patch("requests.request")
    def test_get_task_by_name_success(self, mock_request):
        """Test successful retrieval of a task by name."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_TASK_ID,
            "name": SAMPLE_TASK_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "workflow": {"steps": [{"name": "step1"}]},
            "version": "1.0.0",
            "description": "A test task",
            "entity_type": "task",
            "asset_origin": "manual",
            "created_at": "2024-01-01T00:00:00Z",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        task = client.get_task_by_name(SAMPLE_COLLECTION_NAME, SAMPLE_TASK_NAME)

        self.assertIsInstance(task, BakeryTask)
        self.assertEqual(task.id, SAMPLE_TASK_ID)
        self.assertEqual(task.name, SAMPLE_TASK_NAME)
        self.assertEqual(task.workflow["steps"][0]["name"], "step1")

    @patch("requests.request")
    def test_get_task_by_name_not_found(self, mock_request):
        """Test get_task_by_name returns None when not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        task = client.get_task_by_name(SAMPLE_COLLECTION_NAME, "nonexistent")

        self.assertIsNone(task)

    @patch("requests.request")
    def test_create_task_success(self, mock_request):
        """Test successful task creation."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_TASK_ID,
            "name": SAMPLE_TASK_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "workflow": {"steps": []},
            "version": "1.0.0",
            "description": "New task",
            "entity_type": "task",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        task = client.create_task(
            SAMPLE_COLLECTION_NAME,
            SAMPLE_TASK_NAME,
            workflow={"steps": []},
            version="1.0.0",
            description="New task",
        )

        self.assertIsInstance(task, BakeryTask)
        self.assertEqual(task.name, SAMPLE_TASK_NAME)
        self.assertEqual(task.version, "1.0.0")

    @patch("requests.request")
    def test_update_task_success(self, mock_request):
        """Test successful task update."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": SAMPLE_TASK_ID,
            "name": SAMPLE_TASK_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "workflow": {"steps": [{"name": "updated_step"}]},
            "version": "2.0.0",
            "description": "Updated task",
            "entity_type": "task",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        task = client.update_task(
            SAMPLE_TASK_ID,
            {"workflow": {"steps": [{"name": "updated_step"}]}, "version": "2.0.0"},
        )

        self.assertEqual(task.version, "2.0.0")
        self.assertEqual(task.workflow["steps"][0]["name"], "updated_step")

    @patch("requests.request")
    def test_list_tasks_success(self, mock_request):
        """Test listing all tasks."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {"id": "t_1", "name": "task_1", "collection_id": "c_1", "workflow": {}, "entity_type": "task"},
            {"id": "t_2", "name": "task_2", "collection_id": "c_2", "workflow": {}, "entity_type": "task"},
        ]
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        tasks = client.list_tasks(skip=0, limit=50)

        self.assertEqual(len(tasks), 2)
        self.assertIsInstance(tasks[0], BakeryTask)
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["params"]["skip"], 0)
        self.assertEqual(call_kwargs["params"]["limit"], 50)

    @patch("requests.request")
    def test_search_tasks_success(self, mock_request):
        """Test searching tasks."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {"id": "t_1", "name": "matching_task"},
        ]
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        results = client.search_tasks("matching", limit=20)

        self.assertEqual(len(results), 1)
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["params"]["q"], "matching")

    @patch("requests.request")
    def test_delete_task_success(self, mock_request):
        """Test successful task deletion."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 204
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        client.delete_task(SAMPLE_TASK_ID)

        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["method"], "DELETE")
        self.assertIn(SAMPLE_TASK_ID, call_kwargs["url"])

    def test_push_task_invalid_identifier(self):
        """Test push_task raises ValueError for invalid identifier format."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.push_task(
                task_identifier="invalid_no_slash",
                workflow={"steps": []},
            )
        self.assertIn("collection_name/task_name", str(context.exception))


class TestEntityRelationships(unittest.TestCase):
    """Tests for entity relationship operations."""

    @patch("requests.request")
    def test_create_entity_relationship_success(self, mock_request):
        """Test successful entity relationship creation."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": "rel_123",
            "target_entity_str": "dataset/coll/ds1",
            "source_entity_str": "dataset/coll/ds0",
            "activity_name": "generated",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.create_entity_relationship(
            target_entity_str="dataset/coll/ds1",
            activity_name="generated",
            source_entity_str="dataset/coll/ds0",
        )

        self.assertEqual(result["id"], "rel_123")
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["method"], "POST")
        self.assertEqual(call_kwargs["json"]["activity_name"], "generated")

    @patch("requests.request")
    def test_create_entity_relationship_no_source(self, mock_request):
        """Test entity relationship creation without source entity."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "id": "rel_124",
            "target_entity_str": "dataset/coll/ds1",
            "activity_name": "imported",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.create_entity_relationship(
            target_entity_str="dataset/coll/ds1",
            activity_name="imported",
        )

        call_kwargs = mock_request.call_args[1]
        self.assertNotIn("source_entity_str", call_kwargs["json"])

    @patch("requests.request")
    def test_get_upstream_entities_success(self, mock_request):
        """Test successful retrieval of upstream entities."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {"entity_type": "dataset", "name": "parent_ds", "collection_name": "coll"},
        ]
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.get_upstream_entities("dataset", SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "parent_ds")

    @patch("requests.request")
    def test_get_upstream_entities_not_found(self, mock_request):
        """Test get_upstream_entities returns None when not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.get_upstream_entities("dataset", SAMPLE_COLLECTION_NAME, "nonexistent")

        self.assertIsNone(result)


class TestValidation(unittest.TestCase):
    """Tests for validation operations."""

    @patch("requests.request")
    def test_validate_croissant_dataset_with_dict(self, mock_request):
        """Test validation with dictionary input."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "overall_passed": True,
            "errors": [],
            "warnings": [],
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.validate_croissant_dataset(CROISSANT_METADATA_JSON)

        self.assertTrue(result["overall_passed"])
        call_kwargs = mock_request.call_args[1]
        self.assertEqual(call_kwargs["method"], "POST")
        self.assertIn("files", call_kwargs)

    @patch("requests.request")
    def test_validate_croissant_dataset_with_mlc_dataset(self, mock_request):
        """Test validation with mlcroissant.Dataset input."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "overall_passed": False,
            "errors": ["Missing required field"],
            "warnings": [],
        }
        mock_request.return_value = mock_response

        mock_dataset = MagicMock(spec=mlcroissant.Dataset)
        mock_dataset.jsonld = CROISSANT_METADATA_JSON

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.validate_croissant_dataset(mock_dataset)

        self.assertFalse(result["overall_passed"])
        self.assertEqual(len(result["errors"]), 1)


class TestDataUploadDownload(unittest.TestCase):
    """Tests for data upload and download operations."""

    @patch("requests.request")
    def test_upload_dataset_data_success(self, mock_request):
        """Test successful dataset data upload."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "filename": "data.tar.gz",
            "size": 1024,
            "path": "gs://bucket/data.tar.gz",
        }
        mock_request.return_value = mock_response

        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp.write(b"fake tar data")
            tmp_path = tmp.name

        try:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            result = client.upload_dataset_data(
                SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME, tmp_path
            )

            self.assertEqual(result["filename"], "data.tar.gz")
            call_kwargs = mock_request.call_args[1]
            self.assertEqual(call_kwargs["method"], "POST")
            self.assertIn("files", call_kwargs)
        finally:
            os.unlink(tmp_path)

    @patch("requests.request")
    def test_upload_dataset_data_not_found(self, mock_request):
        """Test upload_dataset_data raises ValueError when dataset not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp.write(b"fake tar data")
            tmp_path = tmp.name

        try:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.upload_dataset_data(SAMPLE_COLLECTION_NAME, "nonexistent", tmp_path)
            self.assertIn("not found", str(context.exception))
        finally:
            os.unlink(tmp_path)

    @patch("requests.request")
    def test_get_dataset_data_download_url_success(self, mock_request):
        """Test getting dataset data download URL."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = {
            "download_url": "https://storage.example.com/signed-url",
        }
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        url = client.get_dataset_data_download_url(
            SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME, file_number=1
        )

        self.assertEqual(url, "https://storage.example.com/signed-url")

    @patch("requests.request")
    def test_download_dataset_data_success(self, mock_request):
        """Test downloading dataset data."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Disposition": 'attachment; filename="data.tar.gz"'}
        mock_response.iter_content = Mock(return_value=[b"chunk1", b"chunk2"])
        mock_request.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "downloaded.tar.gz")
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            result_path = client.download_dataset_data(
                SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME, output_path=output_path
            )

            self.assertEqual(result_path, output_path)
            self.assertTrue(os.path.exists(output_path))
            with open(output_path, "rb") as f:
                content = f.read()
            self.assertEqual(content, b"chunk1chunk2")


class TestPrepareDataset(unittest.TestCase):
    """Tests for prepare_dataset and related local operations."""

    def test_prepare_dataset_creates_manifest(self):
        """Test prepare_dataset creates .manifest.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            result = client.prepare_dataset(
                dataset_path=tmpdir,
                dataset_name=SAMPLE_DATASET_NAME,
                collection_name=SAMPLE_COLLECTION_NAME,
            )

            manifest_path = os.path.join(tmpdir, ".manifest.json")
            self.assertTrue(os.path.exists(manifest_path))

            with open(manifest_path, "r") as f:
                manifest = json.load(f)

            self.assertEqual(manifest["properties"]["name"], SAMPLE_DATASET_NAME)
            self.assertEqual(manifest["properties"]["collection_name"], SAMPLE_COLLECTION_NAME)
            self.assertEqual(manifest["properties"]["type"], "dataset")

    def test_prepare_dataset_creates_readme(self):
        """Test prepare_dataset creates README.md if not exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            client.prepare_dataset(
                dataset_path=tmpdir,
                dataset_name=SAMPLE_DATASET_NAME,
                collection_name=SAMPLE_COLLECTION_NAME,
            )

            readme_path = os.path.join(tmpdir, "README.md")
            self.assertTrue(os.path.exists(readme_path))

            with open(readme_path, "r") as f:
                content = f.read()
            self.assertIn(SAMPLE_DATASET_NAME, content)

    def test_prepare_dataset_creates_metadata(self):
        """Test prepare_dataset creates metadata.json if not exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            client.prepare_dataset(
                dataset_path=tmpdir,
                dataset_name=SAMPLE_DATASET_NAME,
                collection_name=SAMPLE_COLLECTION_NAME,
            )

            metadata_path = os.path.join(tmpdir, "metadata.json")
            self.assertTrue(os.path.exists(metadata_path))

            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            self.assertEqual(metadata["@type"], "sc:Dataset")
            self.assertEqual(metadata["name"], SAMPLE_DATASET_NAME)

    def test_prepare_dataset_nonexistent_path(self):
        """Test prepare_dataset raises ValueError for nonexistent path."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.prepare_dataset(
                dataset_path="/nonexistent/path",
                dataset_name=SAMPLE_DATASET_NAME,
                collection_name=SAMPLE_COLLECTION_NAME,
            )
        self.assertIn("doesn't exist", str(context.exception))

    def test_prepare_dataset_file_not_directory(self):
        """Test prepare_dataset raises ValueError when path is a file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

        try:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.prepare_dataset(
                    dataset_path=tmp_path,
                    dataset_name=SAMPLE_DATASET_NAME,
                    collection_name=SAMPLE_COLLECTION_NAME,
                )
            self.assertIn("not a directory", str(context.exception))
        finally:
            os.unlink(tmp_path)


class TestDuplicateDataset(unittest.TestCase):
    """Tests for duplicate_dataset operation."""

    def test_duplicate_dataset_success(self):
        """Test successful dataset duplication."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source dataset
            source_dir = os.path.join(tmpdir, "source")
            os.makedirs(source_dir)

            manifest = {
                "properties": {
                    "name": "original",
                    "collection_name": "source_coll",
                    "type": "dataset",
                },
                "parents": [],
                "assets": {"metadata": "metadata.json"},
            }
            with open(os.path.join(source_dir, ".manifest.json"), "w") as f:
                json.dump(manifest, f)

            # Create a dummy file
            with open(os.path.join(source_dir, "data.txt"), "w") as f:
                f.write("test data")

            dest_dir = os.path.join(tmpdir, "dest")

            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            result = client.duplicate_dataset(
                source_path=source_dir,
                dest_path=dest_dir,
                params={"properties": {"name": "duplicate", "collection_name": "dest_coll"}},
            )

            # Check destination exists
            self.assertTrue(os.path.exists(dest_dir))
            self.assertTrue(os.path.exists(os.path.join(dest_dir, "data.txt")))

            # Check manifest was updated
            self.assertEqual(result["properties"]["name"], "duplicate")
            self.assertEqual(result["properties"]["collection_name"], "dest_coll")

            # Check parent lineage was set
            self.assertEqual(len(result["parents"]), 1)
            self.assertEqual(result["parents"][0]["generated"], "dataset/source_coll/original")

    def test_duplicate_dataset_source_not_exists(self):
        """Test duplicate_dataset raises ValueError when source doesn't exist."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.duplicate_dataset(
                source_path="/nonexistent",
                dest_path="/dest",
                params={},
            )
        self.assertIn("doesn't exist", str(context.exception))

    def test_duplicate_dataset_dest_exists(self):
        """Test duplicate_dataset raises ValueError when destination exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)
            os.makedirs(dest_dir)

            # Create manifest in source
            with open(os.path.join(source_dir, ".manifest.json"), "w") as f:
                json.dump({"properties": {"name": "test", "collection_name": "coll", "type": "dataset"}}, f)

            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.duplicate_dataset(
                    source_path=source_dir,
                    dest_path=dest_dir,
                    params={},
                )
            self.assertIn("already exists", str(context.exception))

    def test_duplicate_dataset_no_manifest(self):
        """Test duplicate_dataset raises ValueError when source has no manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "source")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(source_dir)

            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.duplicate_dataset(
                    source_path=source_dir,
                    dest_path=dest_dir,
                    params={},
                )
            self.assertIn("no .manifest.json", str(context.exception))


class TestRequestErrorHandling(unittest.TestCase):
    """Tests for request error handling."""

    @patch("requests.request")
    def test_request_network_error(self, mock_request):
        """Test _request raises on network error."""
        mock_request.side_effect = requests.exceptions.ConnectionError("Network unreachable")

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(requests.exceptions.ConnectionError):
            client._request("GET", "/test")

    @patch("requests.request")
    def test_request_timeout(self, mock_request):
        """Test _request raises on timeout."""
        mock_request.side_effect = requests.exceptions.Timeout("Request timed out")

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(requests.exceptions.Timeout):
            client._request("GET", "/test")

    @patch("requests.request")
    def test_request_http_error_propagates(self, mock_request):
        """Test _request propagates HTTP errors."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error", response=mock_response
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(requests.exceptions.HTTPError):
            client._request("GET", "/test")


class TestPushModelFlow(unittest.TestCase):
    """Tests for the full push_model flow."""

    @patch("requests.request")
    def test_push_model_create_new(self, mock_request):
        """Test push_model creates a new model when it doesn't exist."""
        # Mock responses for: get_collection, get_model (404), create_model, get_model (final)
        mock_collection_resp = Mock(spec=requests.Response)
        mock_collection_resp.raise_for_status = Mock()
        mock_collection_resp.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "",
            "auth_org_id": "",
        }

        mock_404_resp = Mock(spec=requests.Response)
        mock_404_resp.status_code = 404
        mock_404_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )

        mock_create_resp = Mock(spec=requests.Response)
        mock_create_resp.raise_for_status = Mock()
        mock_create_resp.json.return_value = {
            "id": SAMPLE_MODEL_ID,
            "name": SAMPLE_MODEL_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "model_path": "/models/new.pkl",
        }

        mock_final_get_resp = Mock(spec=requests.Response)
        mock_final_get_resp.raise_for_status = Mock()
        mock_final_get_resp.json.return_value = {
            "id": SAMPLE_MODEL_ID,
            "name": SAMPLE_MODEL_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "model_path": "/models/new.pkl",
            "metadata_version": "1.0.0",
        }

        mock_request.side_effect = [
            mock_collection_resp,  # get_collection_by_name
            mock_404_resp,  # get_model_by_name (not found)
            mock_create_resp,  # create_model
            mock_final_get_resp,  # get_model_by_name (final)
        ]

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.push_model(
            model_identifier=f"{SAMPLE_COLLECTION_NAME}/{SAMPLE_MODEL_NAME}",
            model_physical_path="/models/new.pkl",
            metadata_version="1.0.0",
        )

        self.assertIsInstance(result, BakeryModel)
        self.assertEqual(result.name, SAMPLE_MODEL_NAME)
        self.assertEqual(mock_request.call_count, 4)

    @patch("requests.request")
    def test_push_model_update_existing(self, mock_request):
        """Test push_model updates an existing model."""
        mock_collection_resp = Mock(spec=requests.Response)
        mock_collection_resp.raise_for_status = Mock()
        mock_collection_resp.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "",
            "auth_org_id": "",
        }

        mock_existing_resp = Mock(spec=requests.Response)
        mock_existing_resp.raise_for_status = Mock()
        mock_existing_resp.json.return_value = {
            "id": SAMPLE_MODEL_ID,
            "name": SAMPLE_MODEL_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "model_path": "/models/old.pkl",
        }

        mock_update_resp = Mock(spec=requests.Response)
        mock_update_resp.raise_for_status = Mock()
        mock_update_resp.json.return_value = {
            "id": SAMPLE_MODEL_ID,
            "name": SAMPLE_MODEL_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "model_path": "/models/updated.pkl",
        }

        mock_final_resp = Mock(spec=requests.Response)
        mock_final_resp.raise_for_status = Mock()
        mock_final_resp.json.return_value = {
            "id": SAMPLE_MODEL_ID,
            "name": SAMPLE_MODEL_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "model_path": "/models/updated.pkl",
        }

        mock_request.side_effect = [
            mock_collection_resp,
            mock_existing_resp,  # get_model_by_name (exists)
            mock_update_resp,  # update_model
            mock_final_resp,  # get_model_by_name (final)
        ]

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.push_model(
            model_identifier=f"{SAMPLE_COLLECTION_NAME}/{SAMPLE_MODEL_NAME}",
            model_physical_path="/models/updated.pkl",
        )

        self.assertEqual(result.model_path, "/models/updated.pkl")


class TestPushTaskFlow(unittest.TestCase):
    """Tests for the full push_task flow."""

    @patch("requests.request")
    def test_push_task_create_new(self, mock_request):
        """Test push_task creates a new task when it doesn't exist."""
        mock_collection_resp = Mock(spec=requests.Response)
        mock_collection_resp.raise_for_status = Mock()
        mock_collection_resp.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "",
            "auth_org_id": "",
        }

        mock_404_resp = Mock(spec=requests.Response)
        mock_404_resp.status_code = 404
        mock_404_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )

        mock_create_resp = Mock(spec=requests.Response)
        mock_create_resp.raise_for_status = Mock()
        mock_create_resp.json.return_value = {
            "id": SAMPLE_TASK_ID,
            "name": SAMPLE_TASK_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "workflow": {"steps": []},
            "entity_type": "task",
        }

        mock_final_resp = Mock(spec=requests.Response)
        mock_final_resp.raise_for_status = Mock()
        mock_final_resp.json.return_value = {
            "id": SAMPLE_TASK_ID,
            "name": SAMPLE_TASK_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "workflow": {"steps": []},
            "entity_type": "task",
            "version": "1.0.0",
        }

        mock_request.side_effect = [
            mock_collection_resp,
            mock_404_resp,  # get_task_by_name (not found)
            mock_create_resp,  # create_task
            mock_final_resp,  # get_task_by_name (final)
        ]

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.push_task(
            task_identifier=f"{SAMPLE_COLLECTION_NAME}/{SAMPLE_TASK_NAME}",
            workflow={"steps": []},
            version="1.0.0",
        )

        self.assertIsInstance(result, BakeryTask)
        self.assertEqual(result.name, SAMPLE_TASK_NAME)

    @patch("requests.request")
    def test_push_task_update_existing(self, mock_request):
        """Test push_task updates an existing task."""
        mock_collection_resp = Mock(spec=requests.Response)
        mock_collection_resp.raise_for_status = Mock()
        mock_collection_resp.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "",
            "auth_org_id": "",
        }

        mock_existing_resp = Mock(spec=requests.Response)
        mock_existing_resp.raise_for_status = Mock()
        mock_existing_resp.json.return_value = {
            "id": SAMPLE_TASK_ID,
            "name": SAMPLE_TASK_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "workflow": {"steps": []},
            "entity_type": "task",
        }

        mock_update_resp = Mock(spec=requests.Response)
        mock_update_resp.raise_for_status = Mock()
        mock_update_resp.json.return_value = {
            "id": SAMPLE_TASK_ID,
            "name": SAMPLE_TASK_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "workflow": {"steps": [{"name": "step1"}]},
            "entity_type": "task",
        }

        mock_final_resp = Mock(spec=requests.Response)
        mock_final_resp.raise_for_status = Mock()
        mock_final_resp.json.return_value = {
            "id": SAMPLE_TASK_ID,
            "name": SAMPLE_TASK_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "workflow": {"steps": [{"name": "step1"}]},
            "entity_type": "task",
        }

        mock_request.side_effect = [
            mock_collection_resp,
            mock_existing_resp,
            mock_update_resp,
            mock_final_resp,
        ]

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.push_task(
            task_identifier=f"{SAMPLE_COLLECTION_NAME}/{SAMPLE_TASK_NAME}",
            workflow={"steps": [{"name": "step1"}]},
        )

        self.assertEqual(result.workflow["steps"][0]["name"], "step1")


class TestUpdateDatasetData(unittest.TestCase):
    """Tests for update_dataset_data operation."""

    @patch("requests.request")
    def test_update_dataset_data_success(self, mock_request):
        """Test successful update of dataset data."""
        # First call: get_dataset_by_name
        mock_get_resp = Mock(spec=requests.Response)
        mock_get_resp.raise_for_status = Mock()
        mock_get_resp.json.return_value = {
            "id": SAMPLE_DATASET_ID,
            "name": SAMPLE_DATASET_NAME,
            "collection_id": SAMPLE_COLLECTION_ID,
            "dataset_metadata": None,
        }

        # Second call: preview (404)
        mock_preview_resp = Mock(spec=requests.Response)
        mock_preview_resp.status_code = 404
        mock_preview_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )

        # Third call: upload_dataset_data
        mock_upload_resp = Mock(spec=requests.Response)
        mock_upload_resp.raise_for_status = Mock()
        mock_upload_resp.json.return_value = {
            "filename": "data.tar.gz",
            "size": 1024,
        }

        mock_request.side_effect = [mock_get_resp, mock_preview_resp, mock_upload_resp]

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp.write(b"fake tar data")
            tmp_path = tmp.name

        try:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            result = client.update_dataset_data(
                SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME, tmp_path
            )
            self.assertEqual(result["filename"], "data.tar.gz")
        finally:
            os.unlink(tmp_path)

    @patch("requests.request")
    def test_update_dataset_data_not_found(self, mock_request):
        """Test update_dataset_data raises ValueError when dataset not found."""
        mock_get_resp = Mock(spec=requests.Response)
        mock_get_resp.status_code = 404
        mock_get_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_get_resp

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp.write(b"fake tar data")
            tmp_path = tmp.name

        try:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.update_dataset_data(SAMPLE_COLLECTION_NAME, "nonexistent", tmp_path)
            self.assertIn("not found", str(context.exception))
        finally:
            os.unlink(tmp_path)


class TestDownloadDatasetDataEdgeCases(unittest.TestCase):
    """Tests for download_dataset_data edge cases."""

    @patch("requests.request")
    def test_download_without_content_disposition(self, mock_request):
        """Test download when Content-Disposition header is missing."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.status_code = 200
        mock_response.headers = {}  # No Content-Disposition
        mock_response.iter_content = Mock(return_value=[b"data"])
        mock_request.return_value = mock_response

        with tempfile.TemporaryDirectory() as tmpdir:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            result_path = client.download_dataset_data(
                SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME
            )

            # Should use default filename
            self.assertIn(SAMPLE_COLLECTION_NAME, result_path)
            self.assertIn(SAMPLE_DATASET_NAME, result_path)

    @patch("requests.request")
    def test_download_not_found(self, mock_request):
        """Test download raises ValueError when dataset not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.download_dataset_data(SAMPLE_COLLECTION_NAME, "nonexistent")
        self.assertIn("not found", str(context.exception))

    @patch("requests.request")
    def test_download_no_storage_config(self, mock_request):
        """Test download raises ValueError when no storage config."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=400)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.download_dataset_data(SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME)
        self.assertIn("storage configuration", str(context.exception))


class TestGetDownloadUrlEdgeCases(unittest.TestCase):
    """Tests for get_dataset_data_download_url edge cases."""

    @patch("requests.request")
    def test_get_download_url_not_found(self, mock_request):
        """Test get_download_url raises ValueError when dataset not found."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.get_dataset_data_download_url(SAMPLE_COLLECTION_NAME, "nonexistent", 1)
        self.assertIn("not found", str(context.exception))

    @patch("requests.request")
    def test_get_download_url_no_storage(self, mock_request):
        """Test get_download_url raises ValueError when no storage config."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=400)
        )
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.get_dataset_data_download_url(SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME, 1)
        self.assertIn("storage configuration", str(context.exception))


class TestUploadDatasetDataEdgeCases(unittest.TestCase):
    """Tests for upload_dataset_data edge cases."""

    @patch("requests.request")
    def test_upload_no_storage_config(self, mock_request):
        """Test upload raises ValueError when no storage config."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=400)
        )
        mock_request.return_value = mock_response

        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp.write(b"fake tar data")
            tmp_path = tmp.name

        try:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.upload_dataset_data(SAMPLE_COLLECTION_NAME, SAMPLE_DATASET_NAME, tmp_path)
            self.assertIn("storage configuration", str(context.exception))
        finally:
            os.unlink(tmp_path)


class TestFindOrCreateCollection(unittest.TestCase):
    """Tests for find_or_create_by_collection_name operation."""

    @patch("requests.request")
    def test_find_or_create_creates_when_not_exists(self, mock_request):
        """Test find_or_create creates collection when it doesn't exist."""
        # First call: get_collection_by_name fails
        mock_get_resp = Mock(spec=requests.Response)
        mock_get_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=Mock(status_code=404)
        )

        # Second call: create_collection succeeds
        mock_create_resp = Mock(spec=requests.Response)
        mock_create_resp.raise_for_status = Mock()
        mock_create_resp.json.return_value = {
            "id": SAMPLE_COLLECTION_ID,
            "name": SAMPLE_COLLECTION_NAME,
            "description": "",
        }

        mock_request.side_effect = [mock_get_resp, mock_create_resp]

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client.find_or_create_by_collection_name(SAMPLE_COLLECTION_NAME)

        self.assertEqual(result.name, SAMPLE_COLLECTION_NAME)
        self.assertEqual(mock_request.call_count, 2)


class TestGetDefaultAgentId(unittest.TestCase):
    """Tests for _get_default_agent_id operation."""

    @patch("requests.request")
    def test_get_default_agent_found(self, mock_request):
        """Test getting default agent when it exists."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {"id": 1, "name": "other_agent"},
            {"id": 2, "name": f"{SAMPLE_COLLECTION_NAME} Owner"},
        ]
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client._get_default_agent_id(SAMPLE_COLLECTION_NAME)

        self.assertEqual(result, 2)

    @patch("requests.request")
    def test_get_default_agent_not_found(self, mock_request):
        """Test getting default agent when it doesn't exist."""
        mock_response = Mock(spec=requests.Response)
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = [
            {"id": 1, "name": "other_agent"},
        ]
        mock_request.return_value = mock_response

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client._get_default_agent_id(SAMPLE_COLLECTION_NAME)

        self.assertIsNone(result)

    @patch("requests.request")
    def test_get_default_agent_error(self, mock_request):
        """Test getting default agent handles errors gracefully."""
        mock_request.side_effect = requests.exceptions.RequestException("Error")

        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        result = client._get_default_agent_id(SAMPLE_COLLECTION_NAME)

        self.assertIsNone(result)


class TestSaveToBakery(unittest.TestCase):
    """Tests for save_to_bakery operation."""

    @patch("requests.request")
    def test_save_to_bakery_success(self, mock_request):
        """Test saving a prepared dataset to bakery."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create manifest
            manifest = {
                "properties": {
                    "name": SAMPLE_DATASET_NAME,
                    "collection_name": SAMPLE_COLLECTION_NAME,
                    "type": "dataset",
                    "origin": "test",
                    "metadata_version": "1.0.0",
                },
                "parents": [],
                "assets": {
                    "metadata": "metadata.json",
                    "long_description": "README.md",
                },
            }
            with open(os.path.join(tmpdir, ".manifest.json"), "w") as f:
                json.dump(manifest, f)

            # Create metadata.json with valid Croissant format
            metadata = CROISSANT_METADATA_JSON.copy()
            metadata["name"] = SAMPLE_DATASET_NAME
            with open(os.path.join(tmpdir, "metadata.json"), "w") as f:
                json.dump(metadata, f)

            # Create README.md
            with open(os.path.join(tmpdir, "README.md"), "w") as f:
                f.write("# Test Dataset")

            # Mock responses
            mock_collection_resp = Mock(spec=requests.Response)
            mock_collection_resp.raise_for_status = Mock()
            mock_collection_resp.json.return_value = {
                "id": SAMPLE_COLLECTION_ID,
                "name": SAMPLE_COLLECTION_NAME,
                "description": "",
                "auth_org_id": "",
            }

            mock_404_resp = Mock(spec=requests.Response)
            mock_404_resp.status_code = 404
            mock_404_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=Mock(status_code=404)
            )

            mock_create_resp = Mock(spec=requests.Response)
            mock_create_resp.raise_for_status = Mock()
            mock_create_resp.json.return_value = {
                "id": SAMPLE_DATASET_ID,
                "name": SAMPLE_DATASET_NAME,
                "collection_id": SAMPLE_COLLECTION_ID,
            }

            mock_final_resp = Mock(spec=requests.Response)
            mock_final_resp.raise_for_status = Mock()
            mock_final_resp.json.return_value = {
                "id": SAMPLE_DATASET_ID,
                "name": SAMPLE_DATASET_NAME,
                "collection_id": SAMPLE_COLLECTION_ID,
                "dataset_metadata": metadata,
            }

            mock_preview_404 = Mock(spec=requests.Response)
            mock_preview_404.status_code = 404
            mock_preview_404.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=Mock(status_code=404)
            )

            mock_request.side_effect = [
                mock_collection_resp,  # get_collection_by_name
                mock_404_resp,  # get_dataset_by_name (not found)
                mock_create_resp,  # create_dataset
                mock_final_resp,  # get_dataset_by_name (final) in push_dataset
                mock_preview_404,  # get_preview (not found)
            ]

            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            result = client.save_to_bakery(tmpdir)

            self.assertIsInstance(result, BakeryDataset)
            self.assertEqual(result.name, SAMPLE_DATASET_NAME)

    def test_save_to_bakery_no_manifest(self):
        """Test save_to_bakery raises ValueError when no manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.save_to_bakery(tmpdir)
            self.assertIn("no .manifest.json", str(context.exception))

    def test_save_to_bakery_missing_properties(self):
        """Test save_to_bakery raises ValueError when properties missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {"assets": {}}
            with open(os.path.join(tmpdir, ".manifest.json"), "w") as f:
                json.dump(manifest, f)

            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.save_to_bakery(tmpdir)
            self.assertIn("Missing 'properties'", str(context.exception))

    def test_save_to_bakery_missing_name(self):
        """Test save_to_bakery raises ValueError when name is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = {"properties": {"collection_name": "test"}}
            with open(os.path.join(tmpdir, ".manifest.json"), "w") as f:
                json.dump(manifest, f)

            client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
            with self.assertRaises(ValueError) as context:
                client.save_to_bakery(tmpdir)
            self.assertIn("Missing required properties", str(context.exception))

    def test_save_to_bakery_nonexistent_path(self):
        """Test save_to_bakery raises ValueError for nonexistent path."""
        client = Client(bakery_url=SAMPLE_URL, token=SAMPLE_TOKEN)
        with self.assertRaises(ValueError) as context:
            client.save_to_bakery("/nonexistent/path")
        self.assertIn("doesn't exist", str(context.exception))


if __name__ == "__main__":
    unittest.main()
