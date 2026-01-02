"""Test meta.json schema validation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from onepass_audioclean_ingest.constants import DEFAULT_META_FILENAME
from tests.conftest import gen_sine_audio, require_ffmpeg_ffprobe, run_cli


def test_schema_meta_valid(tmp_path: Path) -> None:
    """Test that generated meta.json has valid schema and required fields."""
    require_ffmpeg_ffprobe()

    # Generate test audio
    input_audio = gen_sine_audio(tmp_path, ext="mp3", duration=1.0)
    workdir = tmp_path / "workdir"
    workdir.mkdir()

    # Run ingest (normalize off)
    result = run_cli(
        [
            "ingest",
            str(input_audio),
            "--out",
            str(workdir),
            "--no-normalize",
        ]
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    # Read meta.json
    meta_path = workdir / DEFAULT_META_FILENAME
    assert meta_path.exists(), "meta.json should exist"

    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    # Check schema_version
    assert meta.get("schema_version") == "meta.v1", "schema_version should be meta.v1"

    # Check required top-level fields
    required_fields = [
        "input",
        "params",
        "tooling",
        "probe",
        "output",
        "errors",
        "warnings",
        "stable_fields",
    ]
    for field in required_fields:
        assert field in meta, f"Required field '{field}' missing in meta.json"

    # Check input fields
    assert "path" in meta["input"]
    assert "size_bytes" in meta["input"]
    assert "ext" in meta["input"]

    # Check params fields
    assert "sample_rate" in meta["params"]
    assert "channels" in meta["params"]
    assert "bit_depth" in meta["params"]
    assert "normalize" in meta["params"]

    # Check tooling fields
    assert "ffmpeg" in meta["tooling"]
    assert "ffprobe" in meta["tooling"]
    assert "python" in meta["tooling"]

    # Check probe fields
    assert "input_ffprobe" in meta["probe"]
    assert "warnings" in meta["probe"]

    # Check output fields
    assert "workdir" in meta["output"]
    assert "audio_wav" in meta["output"]
    assert "meta_json" in meta["output"]
    assert "expected_audio" in meta["output"]

    # Check errors and warnings are arrays
    assert isinstance(meta["errors"], list)
    assert isinstance(meta["warnings"], list)

    # Check stable_fields
    assert "core" in meta["stable_fields"]
    assert "non_core" in meta["stable_fields"]
    assert isinstance(meta["stable_fields"]["core"], list)
    assert isinstance(meta["stable_fields"]["non_core"], list)

