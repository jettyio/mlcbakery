import unittest
import json
import os
from unittest.mock import patch, MagicMock
import tempfile
import mlcroissant as mlc

from mlcbakery.croissant_validation import (
    validate_json,
    validate_croissant,
    validate_records,
    generate_validation_report,
    ValidationResult,
    _WAIT_TIME,
)
import func_timeout

# Assume tests/data/valid_mlcroissant.json exists relative to the project root
VALID_CROISSANT_PATH = "tests/data/valid_mlcroissant.json"
# Ensure the test data directory exists for temp file creation later
os.makedirs("tests/data", exist_ok=True)


class TestCroissantValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load valid JSON data once for reuse
        try:
            with open(VALID_CROISSANT_PATH, "r") as f:
                cls.valid_json_data = json.load(f)
        except FileNotFoundError:
            # Create a dummy file if it doesn't exist, so tests can run
            print(
                f"Warning: {VALID_CROISSANT_PATH} not found. Creating a dummy valid file for tests."
            )
            cls.valid_json_data = {
                "@context": {
                    "sc": "http://schema.org/",
                    "ml": "http://mlcommons.org/schema/",
                },
                "@type": "sc:Dataset",
                "name": "dummy-dataset",
                "description": "A dummy dataset because the original was missing.",
                "url": "http://example.com/dummy",
                "distribution": [],
                "recordSet": [],
            }
            with open(VALID_CROISSANT_PATH, "w") as f:
                json.dump(cls.valid_json_data, f, indent=2)
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {VALID_CROISSANT_PATH}.")
            cls.valid_json_data = None  # Indicate failure

    def test_validate_json_valid(self):
        result = validate_json(VALID_CROISSANT_PATH)
        self.assertTrue(result.passed)
        self.assertEqual(result.message, "The file is valid JSON.")
        self.assertIsNotNone(result.valid_json_data)
        self.assertEqual(result.valid_json_data, self.valid_json_data)

    def test_validate_json_invalid(self):
        # Create a temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as tmpfile:
            tmpfile.write('{"invalid json",}')
            tmp_path = tmpfile.name

        try:
            result = validate_json(tmp_path)
            self.assertFalse(result.passed)
            self.assertTrue("Invalid JSON format" in result.message)
            self.assertIsNone(result.valid_json_data)
        finally:
            os.remove(tmp_path)  # Clean up temp file

    def test_validate_json_file_not_found(self):
        result = validate_json("non_existent_file.json")
        self.assertFalse(result.passed)
        self.assertTrue("Error reading file" in result.message)
        self.assertTrue("No such file or directory" in result.message)
        self.assertIsNone(result.valid_json_data)

    @patch("mlcroissant.Dataset")
    def test_validate_croissant_valid(self, mock_dataset):
        # No exception raised by mlc.Dataset means valid
        mock_dataset.return_value = MagicMock()
        result = validate_croissant(self.valid_json_data)
        self.assertTrue(result.passed)
        self.assertEqual(result.message, "The dataset passes Croissant validation.")
        mock_dataset.assert_called_once_with(jsonld=self.valid_json_data)

    @patch("mlcroissant.Dataset")
    def test_validate_croissant_invalid_schema(self, mock_dataset):
        # mlc.Dataset raises ValidationError for schema issues
        mock_dataset.side_effect = mlc.ValidationError("Schema error")
        invalid_data = {"name": "missing context"}
        result = validate_croissant(invalid_data)
        self.assertFalse(result.passed)
        self.assertTrue("Validation failed: Schema error" in result.message)
        self.assertIsNotNone(result.details)

    @patch("mlcroissant.Dataset")
    def test_validate_croissant_unexpected_error(self, mock_dataset):
        # mlc.Dataset raises some other exception
        mock_dataset.side_effect = ValueError("Unexpected issue")
        data = {"name": "some data"}
        result = validate_croissant(data)
        self.assertFalse(result.passed)
        self.assertTrue(
            "Unexpected error during validation: Unexpected issue" in result.message
        )
        self.assertIsNotNone(result.details)

    @patch("mlcroissant.Dataset")
    def test_validate_records_valid(self, mock_dataset_cls):
        # Mock dataset and record generation
        mock_dataset_instance = MagicMock()
        mock_record_set = MagicMock(uuid="rs1")
        mock_dataset_instance.metadata.record_sets = [mock_record_set]
        # Simulate an iterator that yields one record then stops
        mock_records_iterator = iter([{"col1": "val1"}])
        mock_dataset_instance.records.return_value = mock_records_iterator
        mock_dataset_cls.return_value = mock_dataset_instance

        result = validate_records(self.valid_json_data)

        self.assertTrue(
            result.passed, f"Validation failed unexpectedly: {result.message}"
        )
        self.assertTrue("Record set 'rs1' passed validation." in result.message)
        mock_dataset_cls.assert_called_once_with(jsonld=self.valid_json_data)
        mock_dataset_instance.records.assert_called_once_with(record_set="rs1")

    @patch("mlcroissant.Dataset")
    def test_validate_records_no_record_sets(self, mock_dataset_cls):
        mock_dataset_instance = MagicMock()
        mock_dataset_instance.metadata.record_sets = []  # No record sets
        mock_dataset_cls.return_value = mock_dataset_instance

        result = validate_records(self.valid_json_data)
        self.assertTrue(result.passed)
        self.assertEqual(result.message, "No record sets found to validate.")
        mock_dataset_cls.assert_called_once_with(jsonld=self.valid_json_data)

    @patch(
        "func_timeout.func_timeout",
        side_effect=func_timeout.exceptions.FunctionTimedOut("Timed out"),
    )
    @patch("mlcroissant.Dataset")
    def test_validate_records_timeout(self, mock_dataset_cls, mock_func_timeout_call):
        mock_dataset_instance = MagicMock()
        mock_record_set = MagicMock(uuid="rs_timeout")
        mock_dataset_instance.metadata.record_sets = [mock_record_set]

        # Mock records to return an iterator that would hang or take too long
        # For the test, making it empty might suffice if func_timeout doesn't optimize for it,
        # but let's make it a generator that never yields to be safe.
        def hanging_iterator():
            while True:
                yield  # Should never yield, causing timeout
            # Or simpler: raise StopIteration immediately, relying on func_timeout mock
            # return iter([])

        # Let's try mocking the lambda directly within func_timeout
        # We still need dataset.records to be called though.
        mock_dataset_instance.records.return_value = iter([])  # Needs to be iterable

        # The func_timeout mock will raise the exception when called
        mock_dataset_cls.return_value = mock_dataset_instance

        result = validate_records(self.valid_json_data)

        self.assertFalse(result.passed)
        self.assertTrue(
            "Record set 'rs_timeout' generation took too long" in result.message,
            f"Unexpected message: {result.message}",
        )
        self.assertTrue(f"(>{_WAIT_TIME}s)" in result.message)
        mock_func_timeout_call.assert_called_once()  # Verify func_timeout was called

    @patch("mlcroissant.Dataset")
    def test_validate_records_generation_error(self, mock_dataset_cls):
        mock_dataset_instance = MagicMock()
        mock_record_set = MagicMock(uuid="rs_error")
        mock_dataset_instance.metadata.record_sets = [mock_record_set]

        # Create an iterator that raises an error when next() is called
        def error_iterator():
            raise ValueError("Record generation failed")
            yield  # Never reached

        mock_dataset_instance.records.return_value = error_iterator()
        mock_dataset_cls.return_value = mock_dataset_instance

        result = validate_records(self.valid_json_data)

        self.assertFalse(result.passed)
        # Check the exact error message format from the validate_records function
        expected_msg = "Record set 'rs_error' failed: Record generation failed"
        self.assertTrue(
            expected_msg in result.message,
            f"Expected substring '{expected_msg}' not found in '{result.message}'",
        )
        self.assertIsNotNone(result.details)  # Check traceback details are included

    @patch("mlcroissant.Dataset")
    def test_validate_records_unexpected_error(self, mock_dataset_cls):
        # Simulate error during Dataset instantiation or metadata access
        mock_dataset_cls.side_effect = TypeError("Unexpected dataset error")

        result = validate_records(self.valid_json_data)
        self.assertFalse(result.passed)
        self.assertTrue(
            "Unexpected error during records validation: Unexpected dataset error"
            in result.message
        )
        self.assertIsNotNone(result.details)

    def test_generate_validation_report_all_passed(self):
        results = [
            ("JSON Check", ValidationResult(passed=True, message="Valid JSON")),
            ("Schema Check", ValidationResult(passed=True, message="Schema OK")),
        ]
        filename = "test.json"
        json_data = {"key": "value"}

        report = generate_validation_report(filename, json_data, results)

        self.assertEqual(report["filename"], filename)
        self.assertTrue(report["overall_passed"])
        self.assertEqual(len(report["steps"]), 2)
        self.assertEqual(report["steps"][0]["name"], "JSON Check")
        self.assertTrue(report["steps"][0]["passed"])
        self.assertEqual(report["steps"][0]["message"], "Valid JSON")
        self.assertIsNone(report["steps"][0]["details"])
        self.assertEqual(report["steps"][1]["name"], "Schema Check")
        self.assertTrue(report["steps"][1]["passed"])
        self.assertEqual(report["json_reference"], json_data)

    def test_generate_validation_report_one_failed(self):
        results = [
            ("JSON Check", ValidationResult(passed=True, message="Valid JSON")),
            (
                "Schema Check",
                ValidationResult(
                    passed=False, message="Schema Bad", details=" Traceback..."
                ),
            ),
        ]
        filename = "test_fail.json"
        json_data = {"key": "value"}

        report = generate_validation_report(filename, json_data, results)

        self.assertEqual(report["filename"], filename)
        self.assertFalse(report["overall_passed"])
        self.assertEqual(len(report["steps"]), 2)
        self.assertEqual(report["steps"][1]["name"], "Schema Check")
        self.assertFalse(report["steps"][1]["passed"])
        self.assertEqual(report["steps"][1]["message"], "Schema Bad")
        self.assertEqual(report["steps"][1]["details"], "Traceback...")
        self.assertEqual(report["json_reference"], json_data)

    def test_generate_validation_report_no_json_data(self):
        results = [
            ("JSON Check", ValidationResult(passed=False, message="Invalid JSON")),
        ]
        filename = "bad_json.json"
        json_data = None  # e.g., from failed validate_json

        report = generate_validation_report(filename, json_data, results)

        self.assertEqual(report["filename"], filename)
        self.assertFalse(report["overall_passed"])
        self.assertEqual(len(report["steps"]), 1)
        self.assertEqual(report["steps"][0]["name"], "JSON Check")
        self.assertFalse(report["steps"][0]["passed"])
        self.assertEqual(
            report["json_reference"], "JSON could not be parsed, reference omitted"
        )


if __name__ == "__main__":
    unittest.main()
