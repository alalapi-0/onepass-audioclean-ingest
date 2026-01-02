import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe required for ingest tests")


def generate_wav(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:duration=1",
            "-ar",
            "8000",
            "-ac",
            "1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_ingest_overwrite_behavior(tmp_path: Path) -> None:
    require_ffmpeg()

    input_wav = tmp_path / "input.wav"
    generate_wav(input_wav)

    workdir = tmp_path / "workdir"

    first = subprocess.run(
        ["onepass-ingest", "ingest", str(input_wav), "--out", str(workdir)],
        capture_output=True,
        text=True,
    )
    assert first.returncode == 0, first.stderr

    meta_path = workdir / "meta.json"
    first_meta = json.loads(meta_path.read_text())

    second = subprocess.run(
        ["onepass-ingest", "ingest", str(input_wav), "--out", str(workdir)],
        capture_output=True,
        text=True,
    )
    assert second.returncode != 0

    third = subprocess.run(
        ["onepass-ingest", "ingest", str(input_wav), "--out", str(workdir), "--overwrite"],
        capture_output=True,
        text=True,
    )
    assert third.returncode == 0, third.stderr

    refreshed_meta = json.loads(meta_path.read_text())
    assert refreshed_meta["created_at"] != first_meta["created_at"]
