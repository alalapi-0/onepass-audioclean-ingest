import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe required for ingest tests")


def test_ingest_convert_mp3_to_wav(tmp_path: Path) -> None:
    require_ffmpeg()

    input_mp3 = tmp_path / "input.mp3"
    workdir = tmp_path / "workdir"

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-q:a",
            "4",
            str(input_mp3),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        ["onepass-ingest", "ingest", str(input_mp3), "--out", str(workdir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    output_wav = workdir / "audio.wav"
    assert output_wav.exists()
    assert output_wav.stat().st_size > 0

    probe = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(output_wav),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    probe_json = json.loads(probe.stdout)
    audio_stream = next(s for s in probe_json.get("streams", []) if s.get("codec_type") == "audio")
    assert int(audio_stream.get("sample_rate")) == 16000
    assert int(audio_stream.get("channels")) == 1
    assert "pcm_s16le" in audio_stream.get("codec_name", "")

    meta_path = workdir / "meta.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta.get("schema_version") == "meta.v1"
    assert meta.get("errors") in ([], None) or len(meta.get("errors", [])) == 0
    actual_audio = meta["output"]["actual_audio"]
    assert actual_audio["sample_rate"] == 16000
    assert actual_audio["channels"] == 1

    log_path = workdir / "convert.log"
    assert log_path.exists()
    log_text = log_path.read_text()
    assert "ffmpeg" in log_text
    assert "pcm_s16le" in log_text
