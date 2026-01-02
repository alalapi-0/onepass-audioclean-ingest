"""Unified error model and error code constants for OnePass AudioClean ingest."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# Error codes (string constants)
class ErrorCode:
    """Error code constants for structured error reporting."""

    # Dependency errors
    DEPS_MISSING = "deps_missing"
    DEPS_BROKEN = "deps_broken"
    DEPS_INSUFFICIENT = "deps_insufficient"

    # Input errors
    INPUT_NOT_FOUND = "input_not_found"
    INPUT_INVALID = "input_invalid"
    INPUT_UNSUPPORTED = "input_unsupported"

    # Output errors
    OUTPUT_NOT_WRITABLE = "output_not_writable"
    OVERWRITE_CONFLICT = "overwrite_conflict"

    # Parameter errors
    INVALID_PARAMS = "invalid_params"

    # Probe errors
    PROBE_FAILED = "probe_failed"

    # Conversion errors
    CONVERT_FAILED = "convert_failed"
    NO_AUDIO_STREAM = "no_audio_stream"
    INVALID_STREAM_SELECTION = "invalid_stream_selection"

    # Internal errors
    INTERNAL_ERROR = "internal_error"


# Exit codes (int constants)
class ExitCode:
    """Exit code constants for CLI and batch processing."""

    SUCCESS = 0
    PARTIAL_FAILED = 1  # Batch: some files failed
    GENERAL_FAILED = 1  # Single file: general failure
    DEPS_MISSING = 2
    INPUT_NOT_FOUND = 10
    OUTPUT_NOT_WRITABLE = 11
    OVERWRITE_CONFLICT = 12
    INVALID_PARAMS = 13
    PROBE_FAILED = 20  # Only when probe is required and cannot continue
    CONVERT_FAILED = 21
    NO_AUDIO_STREAM = 22
    INVALID_STREAM_SELECTION = 22  # Same as no_audio_stream for compatibility
    INTERNAL_ERROR = 99


# Mapping from error code to exit code
ERROR_TO_EXIT_CODE: Dict[str, int] = {
    ErrorCode.DEPS_MISSING: ExitCode.DEPS_MISSING,
    ErrorCode.DEPS_BROKEN: ExitCode.DEPS_MISSING,  # Treat as deps_missing
    ErrorCode.DEPS_INSUFFICIENT: ExitCode.DEPS_MISSING,
    ErrorCode.INPUT_NOT_FOUND: ExitCode.INPUT_NOT_FOUND,
    ErrorCode.INPUT_INVALID: ExitCode.INPUT_NOT_FOUND,
    ErrorCode.INPUT_UNSUPPORTED: ExitCode.INPUT_NOT_FOUND,
    ErrorCode.OUTPUT_NOT_WRITABLE: ExitCode.OUTPUT_NOT_WRITABLE,
    ErrorCode.OVERWRITE_CONFLICT: ExitCode.OVERWRITE_CONFLICT,
    ErrorCode.INVALID_PARAMS: ExitCode.INVALID_PARAMS,
    ErrorCode.PROBE_FAILED: ExitCode.PROBE_FAILED,
    ErrorCode.CONVERT_FAILED: ExitCode.CONVERT_FAILED,
    ErrorCode.NO_AUDIO_STREAM: ExitCode.NO_AUDIO_STREAM,
    ErrorCode.INVALID_STREAM_SELECTION: ExitCode.INVALID_STREAM_SELECTION,
    ErrorCode.INTERNAL_ERROR: ExitCode.INTERNAL_ERROR,
}


@dataclass
class IngestError:
    """Structured error entry for meta.json and manifest.jsonl."""

    code: str
    message: str
    hint: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"code": self.code, "message": self.message}
        if self.hint is not None:
            result["hint"] = self.hint
        if self.detail is not None:
            result["detail"] = self.detail
        return result

    def to_meta_error(self) -> Dict[str, Any]:
        """Convert to meta.json error format."""
        return self.to_dict()

    def to_manifest_error(self) -> Tuple[str, str]:
        """Convert to manifest.jsonl format: (code, short_message)."""
        return (self.code, self.message[:200])  # Truncate long messages


def safe_detail(obj: Any, max_len: int = 2000) -> Optional[Dict[str, Any]]:
    """Create a safe detail dictionary, truncating long strings.

    Parameters
    ----------
    obj: Any
        Object to convert to detail dict. If dict, truncates string values.
    max_len: int
        Maximum length for string values in detail.

    Returns
    -------
    Optional[Dict[str, Any]]
        Detail dictionary with truncated strings, or None if obj is None.
    """
    if obj is None:
        return None

    if isinstance(obj, dict):
        result: Dict[str, Any] = {}
        for key, value in obj.items():
            if isinstance(value, str):
                if len(value) > max_len:
                    result[key] = value[:max_len] + f"... (truncated, original length: {len(value)})"
                else:
                    result[key] = value
            else:
                result[key] = value
        return result

    if isinstance(obj, str):
        if len(obj) > max_len:
            return {"message": obj[:max_len] + f"... (truncated, original length: {len(obj)})"}
        return {"message": obj}

    return {"data": str(obj)[:max_len]}


def summarize_errors(errors: List[IngestError]) -> Tuple[List[str], List[str]]:
    """Extract error codes and messages from a list of errors.

    Parameters
    ----------
    errors: List[IngestError]
        List of error objects.

    Returns
    -------
    Tuple[List[str], List[str]]
        (error_codes, error_messages) where messages are truncated to 200 chars.
    """
    codes = [err.code for err in errors]
    messages = [err.message[:200] for err in errors]
    return (codes, messages)


def determine_exit_code_from_errors(errors: List[IngestError]) -> int:
    """Determine exit code from a list of errors.

    Parameters
    ----------
    errors: List[IngestError]
        List of error objects.

    Returns
    -------
    int
        Exit code based on error priorities.
    """
    if not errors:
        return ExitCode.SUCCESS

    # Priority order: deps > internal > input > output > params > probe > convert > stream
    error_codes = {err.code for err in errors}

    if ErrorCode.DEPS_MISSING in error_codes or ErrorCode.DEPS_BROKEN in error_codes or ErrorCode.DEPS_INSUFFICIENT in error_codes:
        return ExitCode.DEPS_MISSING

    if ErrorCode.INTERNAL_ERROR in error_codes:
        return ExitCode.INTERNAL_ERROR

    if ErrorCode.INPUT_NOT_FOUND in error_codes or ErrorCode.INPUT_INVALID in error_codes or ErrorCode.INPUT_UNSUPPORTED in error_codes:
        return ExitCode.INPUT_NOT_FOUND

    if ErrorCode.OUTPUT_NOT_WRITABLE in error_codes:
        return ExitCode.OUTPUT_NOT_WRITABLE

    if ErrorCode.OVERWRITE_CONFLICT in error_codes:
        return ExitCode.OVERWRITE_CONFLICT

    if ErrorCode.INVALID_PARAMS in error_codes:
        return ExitCode.INVALID_PARAMS

    if ErrorCode.PROBE_FAILED in error_codes:
        return ExitCode.PROBE_FAILED

    if ErrorCode.CONVERT_FAILED in error_codes:
        return ExitCode.CONVERT_FAILED

    if ErrorCode.NO_AUDIO_STREAM in error_codes or ErrorCode.INVALID_STREAM_SELECTION in error_codes:
        return ExitCode.NO_AUDIO_STREAM

    # Default to general failure
    return ExitCode.GENERAL_FAILED

