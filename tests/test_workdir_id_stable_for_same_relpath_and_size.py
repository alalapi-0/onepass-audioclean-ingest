"""Test that workdir ID is stable for same relpath and size."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from onepass_audioclean_ingest.constants import MANIFEST_PLAN_SCHEMA_VERSION
from tests.conftest import gen_sine_audio, require_ffmpeg_ffprobe, run_cli


def test_workdir_id_stable_for_same_relpath_and_size(tmp_path: Path) -> None:
    """Test that workdir ID is stable for same relpath and file size."""
    require_ffmpeg_ffprobe()

    # Create input directory
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root1 = tmp_path / "out1"
    out_root2 = tmp_path / "out2"

    # Create a single file
    audio_file = gen_sine_audio(input_dir, ext="mp3", duration=1.0)
    # Rename to a.mp3
    (input_dir / "test_audio.mp3").rename(input_dir / "a.mp3")

    # First dry-run
    result1 = run_cli(
        [
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root1),
            "--dry-run",
            "--manifest-name",
            "manifest1.jsonl",
        ]
    )
    assert result1.returncode == 0, f"First dry-run failed: {result1.stderr}"

    # Second dry-run (same input, different manifest name)
    result2 = run_cli(
        [
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root2),
            "--dry-run",
            "--manifest-name",
            "manifest2.jsonl",
        ]
    )
    assert result2.returncode == 0, f"Second dry-run failed: {result2.stderr}"

    # Read both manifests
    manifest1_path = out_root1 / "manifest1.plan.jsonl"
    manifest2_path = out_root2 / "manifest2.plan.jsonl"

    assert manifest1_path.exists(), "First manifest should exist"
    assert manifest2_path.exists(), "Second manifest should exist"

    # Extract work_id from both
    line1 = manifest1_path.read_text(encoding="utf-8").strip().splitlines()[0]
    line2 = manifest2_path.read_text(encoding="utf-8").strip().splitlines()[0]

    record1 = json.loads(line1)
    record2 = json.loads(line2)

    assert record1.get("schema_version") == MANIFEST_PLAN_SCHEMA_VERSION
    assert record2.get("schema_version") == MANIFEST_PLAN_SCHEMA_VERSION

    work_id1 = record1["output"]["work_id"]
    work_id2 = record2["output"]["work_id"]

    assert work_id1 is not None, "work_id should not be None"
    assert work_id2 is not None, "work_id should not be None"
    assert work_id1 == work_id2, f"work_id should be stable: {work_id1} != {work_id2}"

    # Also check work_key is the same
    work_key1 = record1["output"]["work_key"]
    work_key2 = record2["output"]["work_key"]

    assert work_key1 == work_key2, f"work_key should be stable: {work_key1} != {work_key2}"

