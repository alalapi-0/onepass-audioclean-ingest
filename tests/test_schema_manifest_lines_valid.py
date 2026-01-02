"""Test manifest.jsonl schema validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from onepass_audioclean_ingest.constants import DEFAULT_MANIFEST_NAME
from tests.conftest import gen_sine_audio, require_ffmpeg_ffprobe, run_cli


def test_schema_manifest_lines_valid(tmp_path: Path) -> None:
    """Test that manifest.jsonl has valid schema and required fields."""
    require_ffmpeg_ffprobe()

    # Generate test directory with 2 files
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root = tmp_path / "out"

    gen_sine_audio(input_dir, ext="mp3", duration=0.5)
    gen_sine_audio(input_dir, ext="wav", duration=0.5)

    # Run batch ingest
    result = run_cli(
        [
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root),
            "--recursive",
        ]
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    # Read manifest.jsonl
    manifest_path = out_root / DEFAULT_MANIFEST_NAME
    assert manifest_path.exists(), "manifest.jsonl should exist"

    lines = manifest_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2, "Should have at least 2 entries"

    # Validate each line
    for line_num, line in enumerate(lines, 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Line {line_num} is not valid JSON: {exc}")

        # Check schema_version
        assert record.get("schema_version") == "manifest.v1", f"Line {line_num}: schema_version should be manifest.v1"

        # Check required fields
        required_fields = [
            "input",
            "output",
            "status",
            "exit_code",
            "started_at",
            "ended_at",
            "duration_ms",
        ]
        for field in required_fields:
            assert field in record, f"Line {line_num}: Required field '{field}' missing"

        # Check input structure
        assert "path" in record["input"]
        assert "relpath" in record["input"]
        assert "ext" in record["input"]
        assert "size_bytes" in record["input"]

        # Check output structure
        assert "workdir" in record["output"]
        assert "audio_wav" in record["output"]
        assert "meta_json" in record["output"]

        # Check status is valid
        assert record["status"] in ["success", "failed", "planned"], f"Line {line_num}: Invalid status"

        # Check exit_code is integer or null
        assert isinstance(record["exit_code"], (int, type(None))), f"Line {line_num}: exit_code should be int or null"

        # Check timestamps are strings
        assert isinstance(record["started_at"], str), f"Line {line_num}: started_at should be string"
        assert isinstance(record["ended_at"], str), f"Line {line_num}: ended_at should be string"

        # Check duration_ms is integer
        assert isinstance(record["duration_ms"], int), f"Line {line_num}: duration_ms should be integer"

