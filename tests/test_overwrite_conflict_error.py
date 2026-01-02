"""Test overwrite conflict error handling."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe required for ingest tests")


def _make_tone(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_overwrite_conflict_error(tmp_path: Path) -> None:
    """Test that overwrite conflict is properly recorded in meta.json."""
    require_ffmpeg()

    input_audio = tmp_path / "input.wav"
    _make_tone(input_audio)
    workdir = tmp_path / "workdir"

    # First ingest should succeed
    result1 = subprocess.run(
        ["onepass-ingest", "ingest", str(input_audio), "--out", str(workdir)],
        text=True,
        capture_output=True,
    )
    assert result1.returncode == 0
    assert (workdir / "audio.wav").exists()
    assert (workdir / "meta.json").exists()

    # Get convert.log size before second attempt
    convert_log = workdir / "convert.log"
    log_size_before = convert_log.stat().st_size if convert_log.exists() else 0

    # Second ingest without overwrite should fail with overwrite_conflict
    result2 = subprocess.run(
        ["onepass-ingest", "ingest", str(input_audio), "--out", str(workdir)],
        text=True,
        capture_output=True,
    )

    # Should exit with overwrite_conflict code (12)
    assert result2.returncode == 12

    # meta.json should exist and contain overwrite_conflict error
    meta_path = workdir / "meta.json"
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    errors = meta.get("errors", [])
    assert len(errors) > 0
    assert errors[0]["code"] == "overwrite_conflict"

    # convert.log should still exist (not overwritten or at least file exists)
    assert convert_log.exists()

