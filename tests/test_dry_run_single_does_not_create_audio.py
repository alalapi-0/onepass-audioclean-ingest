import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required to generate input")


def _generate_input_wav(path: Path) -> None:
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
        text=True,
    )


def test_dry_run_single_does_not_create_audio(tmp_path: Path) -> None:
    require_ffmpeg()
    input_wav = tmp_path / "input.wav"
    _generate_input_wav(input_wav)

    workdir = tmp_path / "workdir"
    result = subprocess.run(
        [
            "onepass-ingest",
            "ingest",
            str(input_wav),
            "--out",
            str(workdir),
            "--dry-run",
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    audio_path = workdir / "audio.wav"
    log_path = workdir / "convert.log"
    meta_path = workdir / "meta.json"

    assert not audio_path.exists()
    assert not log_path.exists()
    assert meta_path.exists()

    meta = json.loads(meta_path.read_text())
    assert meta["output"]["actual_audio"] is None
    assert meta.get("execution", {}).get("ffmpeg_cmd")
    assert meta.get("execution", {}).get("planned") is True

    stdout_meta = json.loads(result.stdout)
    assert stdout_meta["execution"]["planned"] is True
