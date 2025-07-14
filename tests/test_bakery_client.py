import unittest
from unittest.mock import patch, Mock, MagicMock
import io
import json

import pandas as pd
import requests
import mlcroissant
from mlcbakery.bakery_client import Client, BakeryDataset, BakeryCollection

# Sample data for mocking
SAMPLE_TOKEN = "sample_bearer_token"
SAMPLE_URL = "http://fakebakery.com"
API_URL = f"{SAMPLE_URL}/api/v1"
SAMPLE_COLLECTION_NAME = "test_collection"
SAMPLE_DATASET_NAME = "test_dataset"
SAMPLE_DATASET_PATH = f"{SAMPLE_COLLECTION_NAME}/{SAMPLE_DATASET_NAME}"
SAMPLE_COLLECTION_ID = "col_123"
SAMPLE_DATASET_ID = "ds_456"

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
            elif method == "POST" and url == f"{API_URL}/datasets/":
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


if __name__ == "__main__":
    unittest.main()
