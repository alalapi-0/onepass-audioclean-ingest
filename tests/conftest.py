"""Pytest fixtures and helpers for OnePass AudioClean ingest tests."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import pytest

from onepass_audioclean_ingest.subprocess_utils import run_cmd


def has_ffmpeg() -> bool:
    """Check if ffmpeg is available in PATH."""
    return shutil.which("ffmpeg") is not None


def has_ffprobe() -> bool:
    """Check if ffprobe is available in PATH."""
    return shutil.which("ffprobe") is not None


def require_ffmpeg_ffprobe() -> None:
    """Skip test if ffmpeg or ffprobe is not available."""
    if not has_ffmpeg() or not has_ffprobe():
        pytest.skip("ffmpeg/ffprobe required for this test")


@pytest.fixture
def ffmpeg_available() -> bool:
    """Fixture that returns True if ffmpeg is available."""
    return has_ffmpeg()


@pytest.fixture
def ffprobe_available() -> bool:
    """Fixture that returns True if ffprobe is available."""
    return has_ffprobe()


def run_cli(args: list[str], timeout_sec: int = 60) -> subprocess.CompletedProcess:
    """Run the CLI command and return CompletedProcess.

    Parameters
    ----------
    args: list[str]
        CLI arguments (without 'onepass-ingest')
    timeout_sec: int
        Timeout in seconds

    Returns
    -------
    subprocess.CompletedProcess
        Completed process result
    """
    cmd = ["onepass-ingest"] + args
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    return result


def gen_sine_audio(
    tmp_path: Path,
    ext: str = "mp3",
    duration: float = 1.0,
    freq: int = 440,
    sample_rate: int = 16000,
    channels: int = 1,
) -> Path:
    """Generate a sine wave audio file using ffmpeg.

    Parameters
    ----------
    tmp_path: Path
        Temporary directory path
    ext: str
        Output extension (mp3, wav, etc.)
    duration: float
        Duration in seconds
    freq: int
        Frequency in Hz
    sample_rate: int
        Sample rate
    channels: int
        Number of channels

    Returns
    -------
    Path
        Path to generated audio file
    """
    require_ffmpeg_ffprobe()
    output_path = tmp_path / f"test_audio.{ext}"
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found")

    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency={freq}:duration={duration}",
        "-ar",
        str(sample_rate),
        "-ac",
        str(channels),
    ]

    # Add codec for non-wav formats
    if ext == "mp3":
        cmd.extend(["-c:a", "libmp3lame", "-b:a", "128k"])
    elif ext == "m4a":
        cmd.extend(["-c:a", "aac", "-b:a", "128k"])

    cmd.append(str(output_path))

    result = run_cmd(cmd, timeout_sec=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return output_path


def gen_video_with_audio(
    tmp_path: Path,
    container: str = "mp4",
    duration: float = 1.0,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
) -> Path:
    """Generate a video file with audio track using ffmpeg.

    Parameters
    ----------
    tmp_path: Path
        Temporary directory path
    container: str
        Container format (mp4, mkv, mov)
    duration: float
        Duration in seconds
    video_codec: str
        Video codec
    audio_codec: str
        Audio codec

    Returns
    -------
    Path
        Path to generated video file
    """
    require_ffmpeg_ffprobe()
    output_path = tmp_path / f"test_video.{container}"
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found")

    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=duration={duration}:size=320x240:rate=1",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration}",
        "-c:v",
        video_codec,
        "-c:a",
        audio_codec,
        "-shortest",
        str(output_path),
    ]

    result = run_cmd(cmd, timeout_sec=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return output_path


def gen_container_with_two_audio_streams(
    tmp_path: Path,
    container: str = "mkv",
    duration: float = 1.0,
) -> Path:
    """Generate a container with two audio streams using ffmpeg.

    Parameters
    ----------
    tmp_path: Path
        Temporary directory path
    container: str
        Container format (mkv, mp4)
    duration: float
        Duration in seconds

    Returns
    -------
    Path
        Path to generated container file
    """
    require_ffmpeg_ffprobe()
    output_path = tmp_path / f"test_multi_audio.{container}"
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        raise RuntimeError("ffmpeg not found")

    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration}",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=880:duration={duration}",
        "-map",
        "0:a",
        "-c:a:0",
        "aac",
        "-b:a:0",
        "128k",
        "-map",
        "1:a",
        "-c:a:1",
        "aac",
        "-b:a:1",
        "128k",
        str(output_path),
    ]

    result = run_cmd(cmd, timeout_sec=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    return output_path


def ffprobe_summary(path: Path) -> dict:
    """Read audio/video file summary using ffprobe.

    Parameters
    ----------
    path: Path
        Path to media file

    Returns
    -------
    dict
        Summary with keys: sample_rate, channels, codec_name, duration
    """
    require_ffmpeg_ffprobe()
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        raise RuntimeError("ffprobe not found")

    cmd = [
        ffprobe_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    result = run_cmd(cmd, timeout_sec=30)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe output is not valid JSON: {exc}") from exc

    # Extract audio stream info
    audio_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    format_info = data.get("format", {})

    summary = {
        "sample_rate": None,
        "channels": None,
        "codec_name": None,
        "duration": None,
    }

    if audio_stream:
        summary["sample_rate"] = audio_stream.get("sample_rate")
        if summary["sample_rate"]:
            try:
                summary["sample_rate"] = int(summary["sample_rate"])
            except (ValueError, TypeError):
                pass

        summary["channels"] = audio_stream.get("channels")
        if summary["channels"]:
            try:
                summary["channels"] = int(summary["channels"])
            except (ValueError, TypeError):
                pass

        summary["codec_name"] = audio_stream.get("codec_name")

    if format_info.get("duration"):
        try:
            summary["duration"] = float(format_info["duration"])
        except (ValueError, TypeError):
            pass

    return summary

