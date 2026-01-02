"""Test that video ingest records selected audio stream."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from onepass_audioclean_ingest.constants import DEFAULT_META_FILENAME
from tests.conftest import gen_video_with_audio, require_ffmpeg_ffprobe, run_cli


def test_video_ingest_records_selected_stream(tmp_path: Path) -> None:
    """Test that video ingest records selected audio stream in meta.json."""
    require_ffmpeg_ffprobe()

    # Generate video with audio
    input_video = gen_video_with_audio(tmp_path, container="mp4", duration=1.0)
    workdir = tmp_path / "workdir"
    workdir.mkdir()

    # Run ingest
    result = run_cli(
        [
            "ingest",
            str(input_video),
            "--out",
            str(workdir),
        ]
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"

    # Read meta.json
    meta_path = workdir / DEFAULT_META_FILENAME
    assert meta_path.exists(), "meta.json should exist"

    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    # Check probe.input_ffprobe.has_video
    input_ffprobe = meta.get("probe", {}).get("input_ffprobe")
    assert input_ffprobe is not None, "input_ffprobe should exist"
    assert input_ffprobe.get("has_video") is True, "has_video should be true for video input"

    # Check selected_audio_stream exists and has required fields
    selected_stream = input_ffprobe.get("selected_audio_stream")
    assert selected_stream is not None, "selected_audio_stream should exist"

    # Check required fields in selected_audio_stream
    assert "index" in selected_stream, "selected_audio_stream should have index"
    assert "codec_name" in selected_stream, "selected_audio_stream should have codec_name"
    assert "channels" in selected_stream, "selected_audio_stream should have channels"

    # Check index is integer or null
    assert isinstance(selected_stream.get("index"), (int, type(None))), "index should be int or null"

    # Check codec_name is string or null
    assert isinstance(selected_stream.get("codec_name"), (str, type(None))), "codec_name should be str or null"

    # Check channels is integer or null
    assert isinstance(selected_stream.get("channels"), (int, type(None))), "channels should be int or null"

