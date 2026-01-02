"""Test batch processing with bad inputs continues and records failures."""
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


def test_batch_bad_input_records_failure_and_continues(tmp_path: Path) -> None:
    """Test that batch processing continues on bad input and records failures in manifest."""
    require_ffmpeg()

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root = tmp_path / "out"

    # Create a good audio file
    good = input_dir / "good.mp3"
    _make_tone(good)

    # Create a bad file (not audio)
    bad = input_dir / "bad.mp3"
    bad.write_text("not an audio file", encoding="utf-8")

    result = subprocess.run(
        ["onepass-ingest", "ingest", str(input_dir), "--out-root", str(out_root)],
        text=True,
        capture_output=True,
    )

    # Should exit with code 1 (partial failure)
    assert result.returncode == 1

    # Check manifest exists
    manifest = out_root / "manifest.jsonl"
    assert manifest.exists()

    # Parse manifest
    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]

    # Should have 2 records
    assert len(records) == 2

    # Find good and bad records
    good_record = next((r for r in records if "good" in r["input"]["relpath"]), None)
    bad_record = next((r for r in records if "bad" in r["input"]["relpath"]), None)

    assert good_record is not None
    assert bad_record is not None

    # Good record should be success
    assert good_record["status"] == "success"
    assert good_record["exit_code"] == 0
    assert len(good_record.get("error_codes", [])) == 0

    # Bad record should be failed
    assert bad_record["status"] == "failed"
    assert bad_record["exit_code"] != 0
    assert len(bad_record.get("error_codes", [])) > 0

    # Bad record should have convert_failed or input_invalid error
    error_codes = bad_record.get("error_codes", [])
    assert any(code in ["convert_failed", "input_invalid", "probe_failed"] for code in error_codes)

    # Good workdir should have audio.wav
    good_workdir = Path(good_record["output"]["workdir"])
    assert (good_workdir / "audio.wav").exists()
    assert (good_workdir / "meta.json").exists()

