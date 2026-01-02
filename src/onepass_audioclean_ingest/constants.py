"""Constants and path conventions for OnePass AudioClean ingest."""
from __future__ import annotations

from pathlib import Path

DEFAULT_OUTPUT_ROOT = Path("out")
DEFAULT_AUDIO_FILENAME = "audio.wav"
DEFAULT_META_FILENAME = "meta.json"
DEFAULT_LOG_FILENAME = "convert.log"
DEFAULT_MANIFEST_NAME = "manifest.jsonl"

# Placeholder for future schema directory (e.g., meta.json schema)
SCHEMAS_DIR = Path(__file__).parent / "schemas"

# Default supported extensions for scanning (case-insensitive)
SUPPORTED_MEDIA_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
    ".aac",
    ".mp4",
    ".mkv",
    ".mov",
}

MANIFEST_SCHEMA_VERSION = "manifest.v1"

# Error codes for CLI exit status
ERROR_CODES = {
    "OK": 0,
    "DEPS_MISSING": 2,
    "DEPS_BROKEN": 3,
    "DEPS_INSUFFICIENT": 4,
}

INGEST_EXIT_CODES = {
    "SUCCESS": 0,
    "DEPS_MISSING": 2,
    "INPUT_INVALID": 10,
    "NO_SUPPORTED_STREAM": 12,
    "INVALID_STREAM_SELECTION": 13,
    "OUTPUT_NOT_WRITABLE": 11,
    "CONVERT_FAILED": 20,
    "PROBE_FAILED": 21,
    "INVALID_PARAMS": 30,
}
