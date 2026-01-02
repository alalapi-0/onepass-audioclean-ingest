import json
import shutil
import subprocess
from pathlib import Path

import pytest


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe required for ingest tests")


def _generate_input_mp3(path: Path) -> None:
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
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _probe_audio(path: Path) -> dict:
    probe = subprocess.run(
        [
            "ffprobe",
            "-hide_banner",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_streams",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(probe.stdout)


def test_normalize_changes_filtergraph_in_meta(tmp_path: Path) -> None:
    require_ffmpeg()
    input_mp3 = tmp_path / "input.mp3"
    _generate_input_mp3(input_mp3)

    work_off = tmp_path / "work_off"
    work_on = tmp_path / "work_on"

    result_off = subprocess.run(
        ["onepass-ingest", "ingest", str(input_mp3), "--out", str(work_off), "--no-normalize"],
        capture_output=True,
        text=True,
    )
    assert result_off.returncode == 0, result_off.stderr

    result_on = subprocess.run(
        ["onepass-ingest", "ingest", str(input_mp3), "--out", str(work_on), "--normalize"],
        capture_output=True,
        text=True,
    )
    assert result_on.returncode == 0, result_on.stderr

    meta_off = json.loads((work_off / "meta.json").read_text())
    meta_on = json.loads((work_on / "meta.json").read_text())

    assert meta_off["params"]["normalize"] is False
    assert meta_off["execution"]["ffmpeg_filtergraph"] in (None, "")

    assert meta_on["params"]["normalize"] is True
    assert "loudnorm" in (meta_on["execution"]["ffmpeg_filtergraph"] or "")
    assert meta_on["params"]["normalize_mode"] == "loudnorm_r7_v1"

    for workdir in (work_off, work_on):
        audio_path = workdir / "audio.wav"
        assert audio_path.exists()
        probe_json = _probe_audio(audio_path)
        audio_stream = next(s for s in probe_json.get("streams", []) if s.get("codec_type") == "audio")
        assert int(audio_stream.get("sample_rate")) == 16000
        assert int(audio_stream.get("channels")) == 1
        assert "pcm_s16le" in audio_stream.get("codec_name", "")
