import unittest
from unittest.mock import patch, MagicMock
import json

# Assuming your client is in mlcbakery.bakery_client
from mlcbakery.bakery_client import Client, BakeryModel, BakeryCollection, _LOGGER
import requests

# Disable logging for tests to keep output clean
_LOGGER.setLevel('CRITICAL')

class TestPushModel(unittest.TestCase):

    def setUp(self):
        self.client = Client(bakery_url="http://fake-bakery-url.com", token="fake-token")
        self.collection_name = "test_collection"
        self.model_name = "test_model"
        self.model_identifier = f"{self.collection_name}/{self.model_name}"
        self.model_physical_path = "/path/to/model.pkl"
        
        self.mock_collection = BakeryCollection(
            id="col_123", 
            name=self.collection_name, 
            description="A test collection"
        )

        self.base_model_data = {
            "name": self.model_name,
            "model_path": self.model_physical_path,
            "metadata_version": "1.0.0",
            "model_metadata": {"accuracy": 0.95},
            "asset_origin": "local_training",
            "long_description": "A detailed description of the test model.",
            "model_attributes": {"input_shape": [None, 224, 224, 3]}
        }

    @patch('mlcbakery.bakery_client.Client._request')
    @patch('mlcbakery.bakery_client.Client.find_or_create_by_collection_name')
    def test_push_model_create_new(self, mock_find_or_create_collection, mock_request):
        # --- MOCK SETUP ---
        mock_find_or_create_collection.return_value = self.mock_collection

        # 1. Initial get_model_by_name: _request should raise HTTPError for 404
        mock_http_error_404 = requests.exceptions.HTTPError(
            response=MagicMock(status_code=404)
        )

        # 2. create_model (POST /models)
        created_model_id = "model_abc123"
        mock_response_create = MagicMock(spec=requests.Response)
        mock_response_create.json.return_value = {
            "id": created_model_id,
            "name": self.model_name,
            "collection_id": self.mock_collection.id,
            **self.base_model_data
        }
        mock_response_create.status_code = 201 # Created

        # 3. Final get_model_by_name (after creation)
        mock_response_get_final = MagicMock(spec=requests.Response)
        mock_response_get_final.json.return_value = {
            "id": created_model_id,
            "name": self.model_name,
            "collection_id": self.mock_collection.id,
            **self.base_model_data
        }
        mock_response_get_final.status_code = 200

        # Configure _request to return these responses in order
        mock_request.side_effect = [
            mock_http_error_404,        # For initial get_model_by_name (causes it to return None)
            mock_response_create,       # For create_model
            mock_response_get_final     # For final get_model_by_name
        ]

        # --- CALL THE METHOD ---
        pushed_model = self.client.push_model(
            model_identifier=self.model_identifier,
            model_physical_path=self.model_physical_path,
            model_metadata=self.base_model_data["model_metadata"],
            asset_origin=self.base_model_data["asset_origin"],
            long_description=self.base_model_data["long_description"],
            metadata_version=self.base_model_data["metadata_version"],
            model_attributes=self.base_model_data["model_attributes"]
        )

        # --- ASSERTIONS ---
        mock_find_or_create_collection.assert_called_once_with(self.collection_name)
        
        self.assertEqual(mock_request.call_count, 3)
        
        # Call 1: Initial get_model_by_name
        args, kwargs = mock_request.call_args_list[0]
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], f"/models/{self.collection_name}/{self.model_name}")

        # Call 2: create_model (POST /models/{collection_name})
        args, kwargs = mock_request.call_args_list[1]
        self.assertEqual(args[0], "POST")
        self.assertEqual(args[1], f"/models/{self.collection_name}")
        expected_payload_create = {
            "name": self.model_name,
            "entity_type": "trained_model",
            **self.base_model_data
        }
        self.assertEqual(kwargs['json_data'], expected_payload_create)

        # Call 3: Final get_model_by_name
        args, kwargs = mock_request.call_args_list[2]
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], f"/models/{self.collection_name}/{self.model_name}")

        self.assertIsInstance(pushed_model, BakeryModel)
        self.assertEqual(pushed_model.id, created_model_id)
        self.assertEqual(pushed_model.name, self.model_name)
        self.assertEqual(pushed_model.collection_id, self.mock_collection.id)
        self.assertEqual(pushed_model.model_path, self.model_physical_path)
        self.assertEqual(pushed_model.model_metadata, self.base_model_data["model_metadata"])

    @patch('mlcbakery.bakery_client.Client._request')
    @patch('mlcbakery.bakery_client.Client.find_or_create_by_collection_name')
    def test_push_model_update_existing(self, mock_find_or_create_collection, mock_request):
        # --- MOCK SETUP ---
        mock_find_or_create_collection.return_value = self.mock_collection
        
        existing_model_id = "model_xyz789"
        initial_model_data = {
            "id": existing_model_id,
            "name": self.model_name,
            "collection_id": self.mock_collection.id,
            "model_path": "/old/path/model.v1",
            "metadata_version": "0.9.0",
            "model_metadata": {"accuracy": 0.90},
            "asset_origin": "old_source",
            "long_description": "Old description.",
            "model_attributes": {"input_shape": [None, 128, 128, 3]}
        }

        # 1. Initial get_model_by_name (returns existing model)
        mock_response_get_initial = MagicMock(spec=requests.Response)
        mock_response_get_initial.json.return_value = initial_model_data
        mock_response_get_initial.status_code = 200

        # 2. update_model (PUT /models/{model_id})
        updated_model_data_from_payload = {
            "model_path": self.model_physical_path, # New path
            "metadata_version": "1.0.0", # New version
            "model_metadata": {"accuracy": 0.98, "new_metric": True}, # Updated metadata
            "asset_origin": "new_local_training",
            "long_description": "An updated detailed description.",
            "model_attributes": {"input_shape": [None, 256, 256, 3], "classes": 10}
        }
        mock_response_update = MagicMock(spec=requests.Response)
        mock_response_update.json.return_value = { # API returns the full updated model
            "id": existing_model_id,
            "name": self.model_name,
            "collection_id": self.mock_collection.id,
            **updated_model_data_from_payload 
        }
        mock_response_update.status_code = 200

        # 3. Final get_model_by_name (after update)
        mock_response_get_final = MagicMock(spec=requests.Response)
        mock_response_get_final.json.return_value = {
            "id": existing_model_id,
            "name": self.model_name,
            "collection_id": self.mock_collection.id,
            **updated_model_data_from_payload # Reflects the update
        }
        mock_response_get_final.status_code = 200
        
        mock_request.side_effect = [
            mock_response_get_initial, # For initial get_model_by_name
            mock_response_update,      # For update_model
            mock_response_get_final    # For final get_model_by_name
        ]

        # --- CALL THE METHOD ---
        pushed_model = self.client.push_model(
            model_identifier=self.model_identifier,
            model_physical_path=updated_model_data_from_payload["model_path"],
            model_metadata=updated_model_data_from_payload["model_metadata"],
            asset_origin=updated_model_data_from_payload["asset_origin"],
            long_description=updated_model_data_from_payload["long_description"],
            metadata_version=updated_model_data_from_payload["metadata_version"],
            model_attributes=updated_model_data_from_payload["model_attributes"]
        )

        # --- ASSERTIONS ---
        mock_find_or_create_collection.assert_called_once_with(self.collection_name)
        
        self.assertEqual(mock_request.call_count, 3)

        # Call 1: Initial get_model_by_name
        args, kwargs = mock_request.call_args_list[0]
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], f"/models/{self.collection_name}/{self.model_name}")
        
        # Call 2: update_model (PUT /models/{collection_name}/{model_name})
        args, kwargs = mock_request.call_args_list[1]
        self.assertEqual(args[0], "PUT")
        self.assertEqual(args[1], f"/models/{self.collection_name}/{self.model_name}")
        # For update, only non-None values are sent
        expected_payload_update = {
            "model_path": updated_model_data_from_payload["model_path"],
            "model_metadata": updated_model_data_from_payload["model_metadata"],
            "asset_origin": updated_model_data_from_payload["asset_origin"],
            "long_description": updated_model_data_from_payload["long_description"],
            "metadata_version": updated_model_data_from_payload["metadata_version"],
            "model_attributes": updated_model_data_from_payload["model_attributes"]
        }
        self.assertEqual(kwargs['json_data'], expected_payload_update)

        # Call 3: Final get_model_by_name
        args, kwargs = mock_request.call_args_list[2]
        self.assertEqual(args[0], "GET")
        self.assertEqual(args[1], f"/models/{self.collection_name}/{self.model_name}")

        self.assertIsInstance(pushed_model, BakeryModel)
        self.assertEqual(pushed_model.id, existing_model_id)
        self.assertEqual(pushed_model.name, self.model_name)
        self.assertEqual(pushed_model.model_path, updated_model_data_from_payload["model_path"])
        self.assertEqual(pushed_model.model_metadata, updated_model_data_from_payload["model_metadata"])
        self.assertEqual(pushed_model.metadata_version, updated_model_data_from_payload["metadata_version"])

if __name__ == '__main__':
    unittest.main() 