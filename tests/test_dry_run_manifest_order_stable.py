"""Test that dry-run manifest order is stable across runs."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from onepass_audioclean_ingest.constants import DEFAULT_MANIFEST_NAME, MANIFEST_PLAN_SCHEMA_VERSION
from tests.conftest import gen_sine_audio, require_ffmpeg_ffprobe, run_cli


def test_dry_run_manifest_order_stable(tmp_path: Path) -> None:
    """Test that dry-run manifest order is stable (dictionary order)."""
    require_ffmpeg_ffprobe()

    # Create input directory with files in non-alphabetical order
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root1 = tmp_path / "out1"
    out_root2 = tmp_path / "out2"

    # Create files in non-alphabetical order: b, a, c
    gen_sine_audio(input_dir, ext="mp3", duration=0.5)
    # Rename to create b.mp3, a.mp3, c.mp3
    (input_dir / "test_audio.mp3").rename(input_dir / "b.mp3")
    gen_sine_audio(input_dir, ext="mp3", duration=0.5)
    (input_dir / "test_audio.mp3").rename(input_dir / "a.mp3")
    gen_sine_audio(input_dir, ext="mp3", duration=0.5)
    (input_dir / "test_audio.mp3").rename(input_dir / "c.mp3")

    # First dry-run
    result1 = run_cli(
        [
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root1),
            "--dry-run",
        ]
    )
    assert result1.returncode == 0, f"First dry-run failed: {result1.stderr}"

    # Second dry-run (different out_root)
    result2 = run_cli(
        [
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root2),
            "--dry-run",
        ]
    )
    assert result2.returncode == 0, f"Second dry-run failed: {result2.stderr}"

    # Read both manifests
    manifest1_path = out_root1 / "manifest.plan.jsonl"
    manifest2_path = out_root2 / "manifest.plan.jsonl"

    assert manifest1_path.exists(), "First manifest should exist"
    assert manifest2_path.exists(), "Second manifest should exist"

    lines1 = manifest1_path.read_text(encoding="utf-8").strip().splitlines()
    lines2 = manifest2_path.read_text(encoding="utf-8").strip().splitlines()

    assert len(lines1) == 3, "Should have 3 entries"
    assert len(lines2) == 3, "Should have 3 entries"

    # Extract relpaths from both manifests
    relpaths1 = []
    relpaths2 = []
    for line in lines1:
        record = json.loads(line)
        assert record.get("schema_version") == MANIFEST_PLAN_SCHEMA_VERSION
        assert record.get("status") == "planned"
        relpaths1.append(record["input"]["relpath"])

    for line in lines2:
        record = json.loads(line)
        assert record.get("schema_version") == MANIFEST_PLAN_SCHEMA_VERSION
        assert record.get("status") == "planned"
        relpaths2.append(record["input"]["relpath"])

    # Check order is identical
    assert relpaths1 == relpaths2, "Manifest order should be stable across runs"

    # Check order is dictionary order (a, b, c)
    assert relpaths1 == ["a.mp3", "b.mp3", "c.mp3"], "Order should be dictionary order"

