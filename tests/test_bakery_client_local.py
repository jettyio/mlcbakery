import json
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

import mlcroissant as mlc
from mlcbakery.bakery_client import Client, BakeryDataset


class TestBakeryClientLocal(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test datasets
        self.test_dir = tempfile.mkdtemp()
        self.client = Client("http://test.bakery.com")

        # Create test dataset structure
        self.source_dataset_path = os.path.join(self.test_dir, "source_dataset")
        os.makedirs(self.source_dataset_path)
        
        # Create a data file
        self.data_dir = os.path.join(self.source_dataset_path, "data")
        os.makedirs(self.data_dir)
        with open(os.path.join(self.data_dir, "data.csv"), "w") as f:
            f.write("id,value\n1,test")
        
        # Create a README
        with open(os.path.join(self.source_dataset_path, "README.md"), "w") as f:
            f.write("# Test Dataset\nThis is a test dataset.")
        
        # Create a sample Croissant metadata file
        self.metadata_content = {
            "@context": "http://schema.org/",
            "@type": "Dataset",
            "name": "Test Dataset", 
            "description": "A test dataset for unit tests"
        }
        with open(os.path.join(self.source_dataset_path, "metadata.json"), "w") as f:
            json.dump(self.metadata_content, f)

    def tearDown(self):
        # Clean up the temporary directory
        shutil.rmtree(self.test_dir)

    def test_prepare_dataset(self):
        """Test creating a .manifest.json file for a dataset."""
        params = {
            "properties": {
                "type": "dataset",
                "name": "test_dataset",
                "collection_name": "test_collection",
                "origin": "test.com",
                "metadata_version": "1.0.0",
            },
            "parents": [
                {
                    "generated_by": None,
                    "attributed_to": "test@example.com"
                }
            ],
            "assets": {
                "long_description": "README.md",
                "metadata": "metadata.json"
            }
        }
        
        result = self.client.prepare_dataset(self.source_dataset_path, params)
        
        # Check that .manifest.json was created
        bakery_file = os.path.join(self.source_dataset_path, ".manifest.json")
        self.assertTrue(os.path.exists(bakery_file))
        
        # Check that the content is correct
        with open(bakery_file, "r") as f:
            content = json.load(f)
        self.assertEqual(content, params)
        self.assertEqual(result, params)

    def test_duplicate_dataset(self):
        """Test duplicating a dataset."""
        # First prepare the source dataset
        source_params = {
            "properties": {
                "type": "dataset",
                "name": "source_dataset",
                "collection_name": "test_collection",
                "origin": "test.com",
                "metadata_version": "1.0.0",
            },
            "parents": [
                {
                    "generated_by": None,
                    "attributed_to": "original@example.com"
                }
            ],
            "assets": {
                "long_description": "README.md",
                "metadata": "metadata.json"
            }
        }
        self.client.prepare_dataset(self.source_dataset_path, source_params)
        
        # Now duplicate it
        dest_dataset_path = os.path.join(self.test_dir, "duplicate_dataset")
        update_params = {
            "properties": {
                "name": "duplicate_dataset"
            }
        }
        attributed_to = "duplicator@example.com"
        
        result = self.client.duplicate_dataset(
            self.source_dataset_path, 
            dest_dataset_path, 
            update_params, 
            attributed_to
        )
        
        # Check that destination was created
        self.assertTrue(os.path.exists(dest_dataset_path))
        
        # Check that .manifest.json exists in destination
        dest_bakery_file = os.path.join(dest_dataset_path, ".manifest.json")
        self.assertTrue(os.path.exists(dest_bakery_file))
        
        # Check that data file was copied
        self.assertTrue(os.path.exists(os.path.join(dest_dataset_path, "data", "data.csv")))
        
        # Check the content of .manifest.json
        with open(dest_bakery_file, "r") as f:
            content = json.load(f)
        
        # Check that name was updated
        self.assertEqual(content["properties"]["name"], "duplicate_dataset")
        
        # Check that the parent record was added correctly
        self.assertEqual(len(content["parents"]), 1)
        self.assertEqual(content["parents"][0]["generated_by"], "dataset/test_collection/source_dataset")
        self.assertEqual(content["parents"][0]["attributed_to"], "duplicator@example.com")

    @patch("mlcbakery.bakery_client.Client.push_dataset")
    def test_save_to_bakery_without_data_upload(self, mock_push_dataset):
        """Test saving a dataset to the bakery API without uploading data."""
        # Prepare the mock return value for push_dataset
        mock_dataset = BakeryDataset(
            id="test_id",
            name="test_dataset",
            collection_id="test_collection_id"
        )
        mock_push_dataset.return_value = mock_dataset
        
        # Prepare the dataset
        params = {
            "properties": {
                "type": "dataset",
                "name": "test_dataset",
                "collection_name": "test_collection",
                "origin": "test.com",
                "metadata_version": "1.0.0",
            },
            "assets": {
                "long_description": "README.md",
                "metadata": "metadata.json"
            }
        }
        self.client.prepare_dataset(self.source_dataset_path, params)
        
        # Mock the mlcroissant.Dataset
        with patch("mlcroissant.Dataset") as mock_mlc_dataset:
            mock_mlc_dataset.return_value = MagicMock()
            
            # Call save_to_bakery
            result = self.client.save_to_bakery(self.source_dataset_path, upload_data=False)
            
            # Check that push_dataset was called with the right arguments
            mock_push_dataset.assert_called_once()
            call_args = mock_push_dataset.call_args[1]
            self.assertEqual(call_args["dataset_path"], "test_collection/test_dataset")
            self.assertEqual(call_args["metadata_version"], "1.0.0")
            self.assertIsNone(call_args["data_file_path"])
            
            # Check the result
            self.assertEqual(result, mock_dataset)

    @patch("mlcbakery.bakery_client.Client.push_dataset")
    def test_save_to_bakery_with_data_upload(self, mock_push_dataset):
        """Test saving a dataset to the bakery API with data upload."""
        # Prepare the mock return value for push_dataset
        mock_dataset = BakeryDataset(
            id="test_id",
            name="test_dataset",
            collection_id="test_collection_id"
        )
        mock_push_dataset.return_value = mock_dataset
        
        # Prepare the dataset
        params = {
            "properties": {
                "type": "dataset",
                "name": "test_dataset",
                "collection_name": "test_collection",
                "origin": "test.com",
                "metadata_version": "1.0.0",
            },
            "assets": {
                "long_description": "README.md",
                "metadata": "metadata.json"
            }
        }
        self.client.prepare_dataset(self.source_dataset_path, params)
        
        # Mock the mlcroissant.Dataset
        with patch("mlcroissant.Dataset") as mock_mlc_dataset:
            mock_mlc_dataset.return_value = MagicMock()
            
            # Call save_to_bakery with upload_data=True
            result = self.client.save_to_bakery(self.source_dataset_path, upload_data=True)
            
            # Check that push_dataset was called with the right arguments
            mock_push_dataset.assert_called_once()
            call_args = mock_push_dataset.call_args[1]
            self.assertEqual(call_args["dataset_path"], "test_collection/test_dataset")
            self.assertEqual(call_args["metadata_version"], "1.0.0")
            
            # data_file_path should be set to a temporary file path
            self.assertIsNotNone(call_args["data_file_path"])
            
            # Check the result
            self.assertEqual(result, mock_dataset)


if __name__ == "__main__":
    unittest.main()