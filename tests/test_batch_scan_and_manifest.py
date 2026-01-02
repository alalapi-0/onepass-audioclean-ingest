import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe required for ingest tests")


def _make_tone(path: Path, fmt: str) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
    ]
    if fmt == "mp4":
        cmd.extend(["-c:a", "aac"])
    cmd.append(str(path))
    subprocess.run(cmd, check=True, capture_output=True)


def test_batch_scan_and_manifest(tmp_path: Path) -> None:
    require_ffmpeg()

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root = tmp_path / "out"

    _make_tone(input_dir / "a.mp3", "mp3")
    _make_tone(input_dir / "b.wav", "wav")
    _make_tone(input_dir / "c.mp4", "mp4")

    result = subprocess.run(
        [
            "onepass-ingest",
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root),
            "--recursive",
        ],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr

    manifest = out_root / "manifest.jsonl"
    assert manifest.exists()
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 3

    for line in lines:
        record = json.loads(line)
        assert record["schema_version"] == "manifest.v1"
        workdir = Path(record["output"]["workdir"])
        assert workdir.exists()
        if record["status"] == "success":
            audio = Path(record["output"]["audio_wav"])
            meta = Path(record["output"]["meta_json"])
            log = Path(record["output"]["convert_log"])
            assert audio.exists()
            assert meta.exists()
            assert log.exists()

