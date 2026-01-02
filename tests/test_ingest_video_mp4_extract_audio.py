import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe required for ingest tests")


def test_ingest_video_mp4_extract_audio(tmp_path: Path) -> None:
    require_ffmpeg()

    input_mp4 = tmp_path / "input.mp4"
    workdir = tmp_path / "workdir"

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=128x128:rate=25",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(input_mp4),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        ["onepass-ingest", "ingest", str(input_mp4), "--out", str(workdir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    output_wav = workdir / "audio.wav"
    assert output_wav.exists()

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
    assert meta.get("errors") in ([], None) or len(meta.get("errors", [])) == 0
    input_ffprobe = meta["probe"]["input_ffprobe"]
    assert input_ffprobe["has_video"] is True
    assert input_ffprobe.get("selected_audio_stream", {}).get("index") is not None
