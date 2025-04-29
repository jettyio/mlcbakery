# from https://github.com/mlcommons/croissant/blob/main/health/croissant-validator-neurips/hf-gradio-app/validation.py
import json
import traceback
import mlcroissant as mlc
import func_timeout
import dataclasses

_WAIT_TIME = 5 * 60  # seconds

@dataclasses.dataclass(frozen=True)
class ValidationResult:
    """Represents the result of a validation step."""
    passed: bool
    message: str
    details: str | None = None
    valid_json_data: dict | None = None

def validate_json(file_path: str) -> ValidationResult:
    """Validate that the file is proper JSON."""
    try:
        with open(file_path, 'r') as f:
            json_data = json.load(f)
        return ValidationResult(passed=True, message="The file is valid JSON.", valid_json_data=json_data)
    except json.JSONDecodeError as e:
        error_message = f"Invalid JSON format: {str(e)}"
        return ValidationResult(passed=False, message=error_message)
    except Exception as e:
        error_message = f"Error reading file: {str(e)}"
        return ValidationResult(passed=False, message=error_message)

def validate_croissant(json_data: dict) -> ValidationResult:
    """Validate that the JSON follows Croissant schema."""
    try:
        _ = mlc.Dataset(jsonld=json_data)  # Instantiate to validate
        return ValidationResult(passed=True, message="The dataset passes Croissant validation.")
    except mlc.ValidationError as e:
        error_details = traceback.format_exc()
        error_message = f"Validation failed: {str(e)}"
        return ValidationResult(passed=False, message=error_message, details=error_details)
    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"Unexpected error during validation: {str(e)}"
        return ValidationResult(passed=False, message=error_message, details=error_details)

def validate_records(json_data: dict) -> ValidationResult:
    """Validate that records can be generated within the time limit."""
    try:
        dataset = mlc.Dataset(jsonld=json_data)
        record_sets = dataset.metadata.record_sets

        if not record_sets:
            return ValidationResult(passed=True, message="No record sets found to validate.")

        results = []

        for record_set in record_sets:
            try:
                records = dataset.records(record_set=record_set.uuid)
                _ = func_timeout(_WAIT_TIME, lambda: next(iter(records)))
                results.append(f"Record set '{record_set.uuid}' passed validation.")
            except func_timeout.exceptions.FunctionTimedOut:
                error_message = f"Record set '{record_set.uuid}' generation took too long (>{_WAIT_TIME}s)"
                return ValidationResult(passed=False, message=error_message)
            except Exception as e:
                error_details = traceback.format_exc()
                error_message = f"Record set '{record_set.uuid}' failed: {str(e)}"
                return ValidationResult(passed=False, message=error_message, details=error_details)

        return ValidationResult(passed=True, message="\n".join(results))
    except Exception as e:
        error_details = traceback.format_exc()
        error_message = f"Unexpected error during records validation: {str(e)}"
        return ValidationResult(passed=False, message=error_message, details=error_details)

def generate_validation_report(filename: str, json_data: dict | None, results: list[tuple[str, ValidationResult]]) -> dict:
    """Generate a structured validation report as a dictionary."""
    report_steps = []
    overall_passed = True
    for test_name, result in results:
        step_report = {
            "name": test_name,
            "passed": result.passed,
            "message": result.message.strip(),
            "details": result.details.strip() if result.details else None,
        }
        report_steps.append(step_report)
        if not result.passed:
            overall_passed = False

    # Format JSON reference
    if json_data:
        # Keep the original JSON data, let the caller decide on formatting if needed
        json_reference = json_data
    else:
        json_reference = "JSON could not be parsed, reference omitted"

    report = {
        "filename": filename,
        "overall_passed": overall_passed,
        "steps": report_steps,
        "json_reference": json_reference
    }

    return report