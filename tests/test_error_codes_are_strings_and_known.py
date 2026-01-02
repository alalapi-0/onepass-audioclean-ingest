"""Test that error codes are strings and belong to known set."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from onepass_audioclean_ingest.constants import DEFAULT_MANIFEST_NAME, DEFAULT_META_FILENAME, KNOWN_ERROR_CODES
from tests.conftest import require_ffmpeg_ffprobe, run_cli


def test_error_codes_are_strings_and_known(tmp_path: Path) -> None:
    """Test that error codes in meta.json and manifest are strings and known."""
    require_ffmpeg_ffprobe()

    # Create a bad input (non-existent file)
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    bad_file = input_dir / "nonexistent.mp3"
    out_root = tmp_path / "out"

    # Run batch ingest (should fail for nonexistent file)
    result = run_cli(
        [
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root),
            "--recursive",
        ]
    )
    # Exit code might be 0 or 1 depending on continue-on-error behavior
    # We just need to check the manifest

    # Read manifest
    manifest_path = out_root / DEFAULT_MANIFEST_NAME
    if not manifest_path.exists():
        pytest.skip("Manifest not created (might be due to no files found)")

    lines = manifest_path.read_text(encoding="utf-8").strip().splitlines()
    if not lines:
        pytest.skip("Manifest is empty")

    # Check manifest error codes
    for line in lines:
        record = json.loads(line)
        error_codes = record.get("error_codes", [])
        assert isinstance(error_codes, list), "error_codes should be a list"

        for code in error_codes:
            assert isinstance(code, str), f"Error code should be string: {code}"
            assert code in KNOWN_ERROR_CODES, f"Unknown error code: {code}"

        # Also check warning_codes if present
        warning_codes = record.get("warning_codes", [])
        if warning_codes:
            assert isinstance(warning_codes, list), "warning_codes should be a list"
            for code in warning_codes:
                assert isinstance(code, str), f"Warning code should be string: {code}"
                # Warning codes might be different, but should still be strings

    # Also test with a real file that might have errors
    # Create a valid file and ingest it
    from tests.conftest import gen_sine_audio  # noqa: F401

    valid_file = gen_sine_audio(input_dir, ext="mp3", duration=0.5)
    workdir = tmp_path / "workdir"
    workdir.mkdir()

    result = run_cli(
        [
            "ingest",
            str(valid_file),
            "--out",
            str(workdir),
        ]
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    # Check meta.json error codes
    meta_path = workdir / DEFAULT_META_FILENAME
    assert meta_path.exists(), "meta.json should exist"

    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    errors = meta.get("errors", [])
    assert isinstance(errors, list), "errors should be a list"

    for error in errors:
        code = error.get("code")
        assert isinstance(code, str), f"Error code should be string: {code}"
        assert code in KNOWN_ERROR_CODES, f"Unknown error code: {code}"

    warnings = meta.get("warnings", [])
    assert isinstance(warnings, list), "warnings should be a list"

    for warning in warnings:
        code = warning.get("code")
        if code:
            assert isinstance(code, str), f"Warning code should be string: {code}"

