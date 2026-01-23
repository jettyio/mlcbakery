"""Unit tests for mlcbakery.storage.gcp module."""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open

from mlcbakery.storage.gcp import (
    create_gcs_client,
    get_next_file_number,
    upload_file_to_gcs,
    generate_download_signed_url,
    extract_bucket_info,
)


class TestCreateGcsClient:
    """Tests for create_gcs_client function."""

    def test_create_client_with_test_credentials(self):
        """Test that test credentials bypass real authentication."""
        storage_info = {
            "private_key": "test-private-key",
            "type": "service_account",
        }

        with patch("mlcbakery.storage.gcp.storage.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = create_gcs_client(storage_info)

            # Should call Client() without credentials for test mode
            mock_client_class.assert_called_once_with()
            assert result == mock_client

    def test_create_client_with_real_credentials(self):
        """Test creating client with real service account credentials."""
        storage_info = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "key-id",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----\n",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "123456789",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }

        with patch("mlcbakery.storage.gcp.storage.Client") as mock_client_class, \
             patch("mlcbakery.storage.gcp.service_account.Credentials.from_service_account_file") as mock_creds, \
             patch("mlcbakery.storage.gcp.os.unlink") as mock_unlink:
            mock_credentials = MagicMock()
            mock_creds.return_value = mock_credentials
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client

            result = create_gcs_client(storage_info)

            # Should create credentials from temp file
            mock_creds.assert_called_once()
            call_args = mock_creds.call_args
            assert call_args[1]["scopes"] == ["https://www.googleapis.com/auth/cloud-platform"]

            # Should create client with credentials
            mock_client_class.assert_called_once_with(credentials=mock_credentials)

            # Should clean up temp file
            mock_unlink.assert_called_once()

            assert result == mock_client

    def test_create_client_with_invalid_credentials_raises_value_error(self):
        """Test that invalid credentials raise ValueError."""
        storage_info = {
            "type": "service_account",
            "private_key": "invalid-key-format",
        }

        with patch("mlcbakery.storage.gcp.service_account.Credentials.from_service_account_file") as mock_creds:
            mock_creds.side_effect = Exception("Invalid credentials format")

            with pytest.raises(ValueError) as exc_info:
                create_gcs_client(storage_info)

            assert "Invalid GCP credentials" in str(exc_info.value)

    def test_create_client_cleans_up_temp_file_on_error(self):
        """Test that temp file is cleaned up even when an error occurs."""
        storage_info = {
            "type": "service_account",
            "private_key": "some-key",
            "project_id": "test-project",
        }

        temp_file_path = None

        with patch("mlcbakery.storage.gcp.service_account.Credentials.from_service_account_file") as mock_creds, \
             patch("mlcbakery.storage.gcp.os.unlink") as mock_unlink, \
             patch("mlcbakery.storage.gcp.os.path.exists", return_value=True):
            mock_creds.side_effect = Exception("Credential error")

            with pytest.raises(ValueError):
                create_gcs_client(storage_info)

            # Should attempt to clean up temp file
            mock_unlink.assert_called()


class TestGetNextFileNumber:
    """Tests for get_next_file_number function."""

    def test_returns_zero_when_no_files_exist(self):
        """Test that 0 is returned when no files exist in the bucket."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.list_blobs.return_value = []

        result = get_next_file_number("test-bucket", "mlcbakery/collection/dataset/", mock_client)

        assert result == 0
        mock_client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.list_blobs.assert_called_once_with(prefix="mlcbakery/collection/dataset/")

    def test_returns_next_number_after_existing_files(self):
        """Test that the next sequential number is returned."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        # Create mock blobs with file names
        mock_blob1 = MagicMock()
        mock_blob1.name = "mlcbakery/collection/dataset/data.000000.tar.gz"
        mock_blob2 = MagicMock()
        mock_blob2.name = "mlcbakery/collection/dataset/data.000001.tar.gz"
        mock_blob3 = MagicMock()
        mock_blob3.name = "mlcbakery/collection/dataset/data.000002.tar.gz"

        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]

        result = get_next_file_number("test-bucket", "mlcbakery/collection/dataset/", mock_client)

        assert result == 3

    def test_handles_non_sequential_file_numbers(self):
        """Test that max + 1 is returned even with gaps in numbering."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        mock_blob1 = MagicMock()
        mock_blob1.name = "mlcbakery/collection/dataset/data.000000.tar.gz"
        mock_blob2 = MagicMock()
        mock_blob2.name = "mlcbakery/collection/dataset/data.000005.tar.gz"
        mock_blob3 = MagicMock()
        mock_blob3.name = "mlcbakery/collection/dataset/data.000010.tar.gz"

        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3]

        result = get_next_file_number("test-bucket", "mlcbakery/collection/dataset/", mock_client)

        assert result == 11

    def test_ignores_non_matching_files(self):
        """Test that files not matching data.NNNNNN.tar.gz are ignored."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        mock_blob1 = MagicMock()
        mock_blob1.name = "mlcbakery/collection/dataset/data.000000.tar.gz"
        mock_blob2 = MagicMock()
        mock_blob2.name = "mlcbakery/collection/dataset/readme.md"
        mock_blob3 = MagicMock()
        mock_blob3.name = "mlcbakery/collection/dataset/metadata.json"
        mock_blob4 = MagicMock()
        mock_blob4.name = "mlcbakery/collection/dataset/data.invalid.tar.gz"

        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2, mock_blob3, mock_blob4]

        result = get_next_file_number("test-bucket", "mlcbakery/collection/dataset/", mock_client)

        assert result == 1

    def test_returns_zero_when_only_non_matching_files_exist(self):
        """Test that 0 is returned when only non-matching files exist."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        mock_blob1 = MagicMock()
        mock_blob1.name = "mlcbakery/collection/dataset/readme.md"
        mock_blob2 = MagicMock()
        mock_blob2.name = "mlcbakery/collection/dataset/metadata.json"

        mock_bucket.list_blobs.return_value = [mock_blob1, mock_blob2]

        result = get_next_file_number("test-bucket", "mlcbakery/collection/dataset/", mock_client)

        assert result == 0

    def test_returns_zero_on_exception(self):
        """Test that 0 is returned when an exception occurs."""
        mock_client = MagicMock()
        mock_client.bucket.side_effect = Exception("Connection error")

        result = get_next_file_number("test-bucket", "mlcbakery/collection/dataset/", mock_client)

        assert result == 0

    def test_handles_large_file_numbers(self):
        """Test handling of large file numbers."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_client.bucket.return_value = mock_bucket

        mock_blob = MagicMock()
        mock_blob.name = "mlcbakery/collection/dataset/data.999999.tar.gz"

        mock_bucket.list_blobs.return_value = [mock_blob]

        result = get_next_file_number("test-bucket", "mlcbakery/collection/dataset/", mock_client)

        assert result == 1000000


class TestUploadFileToGcs:
    """Tests for upload_file_to_gcs function."""

    def test_successful_upload(self):
        """Test successful file upload."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.name = "mlcbakery/collection/dataset/data.000000.tar.gz"

        data = b"test file content"
        destination_path = "mlcbakery/collection/dataset/data.000000.tar.gz"

        result = upload_file_to_gcs("test-bucket", data, destination_path, mock_client)

        mock_client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with(destination_path)
        mock_blob.upload_from_string.assert_called_once_with(data)
        assert result == mock_blob.name

    def test_upload_with_empty_data(self):
        """Test uploading empty data."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.name = "test/path.tar.gz"

        result = upload_file_to_gcs("test-bucket", b"", "test/path.tar.gz", mock_client)

        mock_blob.upload_from_string.assert_called_once_with(b"")
        assert result == "test/path.tar.gz"

    def test_upload_raises_exception_on_failure(self):
        """Test that upload failures raise an exception."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.upload_from_string.side_effect = Exception("Upload failed")

        with pytest.raises(Exception) as exc_info:
            upload_file_to_gcs("test-bucket", b"data", "path.tar.gz", mock_client)

        assert "Upload failed" in str(exc_info.value)

    def test_upload_large_data(self):
        """Test uploading large data."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.name = "path.tar.gz"

        # 10MB of data
        large_data = b"x" * (10 * 1024 * 1024)

        result = upload_file_to_gcs("test-bucket", large_data, "path.tar.gz", mock_client)

        mock_blob.upload_from_string.assert_called_once_with(large_data)
        assert result == "path.tar.gz"


class TestGenerateDownloadSignedUrl:
    """Tests for generate_download_signed_url function."""

    def test_generate_signed_url_default_expiration(self):
        """Test generating signed URL with default expiration."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"

        result = generate_download_signed_url(
            "test-bucket",
            "mlcbakery/collection/dataset/data.000000.tar.gz",
            mock_client
        )

        mock_client.bucket.assert_called_once_with("test-bucket")
        mock_bucket.blob.assert_called_once_with("mlcbakery/collection/dataset/data.000000.tar.gz")
        mock_blob.generate_signed_url.assert_called_once_with(
            version="v4",
            expiration=3600,
            method="GET"
        )
        assert result == "https://storage.googleapis.com/signed-url"

    def test_generate_signed_url_custom_expiration(self):
        """Test generating signed URL with custom expiration."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.return_value = "https://storage.googleapis.com/signed-url"

        result = generate_download_signed_url(
            "test-bucket",
            "path/to/file.tar.gz",
            mock_client,
            expiration=7200
        )

        mock_blob.generate_signed_url.assert_called_once_with(
            version="v4",
            expiration=7200,
            method="GET"
        )

    def test_generate_signed_url_raises_exception_on_failure(self):
        """Test that signed URL generation failure raises exception."""
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.generate_signed_url.side_effect = Exception("Signing failed")

        with pytest.raises(Exception) as exc_info:
            generate_download_signed_url("test-bucket", "path.tar.gz", mock_client)

        assert "Signing failed" in str(exc_info.value)


class TestExtractBucketInfo:
    """Tests for extract_bucket_info function."""

    def test_extract_bucket_name_only(self):
        """Test extracting just bucket name when no prefix provided."""
        storage_info = {"bucket": "my-test-bucket"}

        bucket_name, path_prefix = extract_bucket_info(storage_info)

        assert bucket_name == "my-test-bucket"
        assert path_prefix == ""

    def test_extract_bucket_name_and_prefix(self):
        """Test extracting bucket name and path prefix."""
        storage_info = {
            "bucket": "my-test-bucket",
            "path_prefix": "mlcbakery/datasets"
        }

        bucket_name, path_prefix = extract_bucket_info(storage_info)

        assert bucket_name == "my-test-bucket"
        assert path_prefix == "mlcbakery/datasets"

    def test_missing_bucket_raises_value_error(self):
        """Test that missing bucket field raises ValueError."""
        storage_info = {"path_prefix": "some/prefix"}

        with pytest.raises(ValueError) as exc_info:
            extract_bucket_info(storage_info)

        assert "bucket" in str(exc_info.value).lower()

    def test_empty_storage_info_raises_value_error(self):
        """Test that empty storage info raises ValueError."""
        with pytest.raises(ValueError):
            extract_bucket_info({})

    def test_extract_with_additional_fields(self):
        """Test that additional fields are ignored."""
        storage_info = {
            "bucket": "my-bucket",
            "path_prefix": "prefix",
            "type": "service_account",
            "project_id": "test-project",
            "extra_field": "ignored"
        }

        bucket_name, path_prefix = extract_bucket_info(storage_info)

        assert bucket_name == "my-bucket"
        assert path_prefix == "prefix"

    def test_extract_with_none_path_prefix(self):
        """Test handling when path_prefix is explicitly None."""
        storage_info = {
            "bucket": "my-bucket",
            "path_prefix": None
        }

        bucket_name, path_prefix = extract_bucket_info(storage_info)

        assert bucket_name == "my-bucket"
        # get() with default "" returns None if key exists with None value
        assert path_prefix is None
