import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_ffmpeg():
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe required for ingest tests")


def _run_ingest(input_path: Path, workdir: Path, extra_args: list[str] | None = None) -> dict:
    args = ["onepass-ingest", "ingest", str(input_path), "--out", str(workdir)]
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    meta_path = workdir / "meta.json"
    assert meta_path.exists()
    return json.loads(meta_path.read_text())


def test_ingest_video_stream_index_selection(tmp_path: Path) -> None:
    require_ffmpeg()

    input_video = tmp_path / "input.mkv"
    workdir_auto = tmp_path / "workdir_auto"
    workdir_forced = tmp_path / "workdir_forced"

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
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880:duration=1",
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-map",
            "2:a",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-shortest",
            str(input_video),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    meta_auto = _run_ingest(input_video, workdir_auto)
    auto_selected = meta_auto["probe"]["input_ffprobe"]["selected_audio_stream"]
    streams = meta_auto["probe"]["input_ffprobe"]["audio_streams"]
    assert len(streams) >= 2
    assert auto_selected is not None

    alternative_stream = streams[0]["index"] if streams[0]["index"] != auto_selected["index"] else streams[1]["index"]

    meta_forced = _run_ingest(input_video, workdir_forced, ["--audio-stream-index", str(alternative_stream)])
    forced_selected = meta_forced["probe"]["input_ffprobe"]["selected_audio_stream"]
    assert forced_selected is not None
    assert forced_selected["index"] == alternative_stream
