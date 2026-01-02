import json
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


def test_continue_on_error_defaults(tmp_path: Path) -> None:
    require_ffmpeg()

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root = tmp_path / "out"

    good = input_dir / "good.wav"
    _make_tone(good)
    bad = input_dir / "bad.mp3"
    bad.write_text("not an audio file", encoding="utf-8")

    result = subprocess.run(
        ["onepass-ingest", "ingest", str(input_dir), "--out-root", str(out_root)],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1

    manifest = out_root / "manifest.jsonl"
    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    statuses = {rec["status"] for rec in records}
    assert "failed" in statuses and "success" in statuses


def test_fail_fast_stops_early(tmp_path: Path) -> None:
    require_ffmpeg()

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root = tmp_path / "out"

    first_bad = input_dir / "00_bad.mp3"
    first_bad.write_text("corrupt", encoding="utf-8")
    second_good = input_dir / "01_good.wav"
    _make_tone(second_good)

    result = subprocess.run(
        [
            "onepass-ingest",
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root),
            "--fail-fast",
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 1

    manifest = out_root / "manifest.jsonl"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert 1 <= len(lines) <= 2
    records = [json.loads(line) for line in lines]
    assert records[0]["status"] == "failed"
