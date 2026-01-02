"""Test that log file is written in batch mode."""
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


def test_log_file_written_in_batch_default(tmp_path: Path) -> None:
    """Test that default log file is written in batch mode."""
    require_ffmpeg()

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root = tmp_path / "out"

    # Create one audio file
    audio = input_dir / "test.wav"
    _make_tone(audio)

    result = subprocess.run(
        ["onepass-ingest", "ingest", str(input_dir), "--out-root", str(out_root)],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0

    # Default log file should exist
    log_file = out_root / "ingest.log"
    assert log_file.exists()

    # Log file should contain some content
    log_content = log_file.read_text(encoding="utf-8")
    assert len(log_content) > 0

    # Should contain some keywords (loose check)
    assert any(keyword in log_content.lower() for keyword in ["ingest", "processing", "ffmpeg", "info", "debug"])


def test_log_file_written_in_batch_custom(tmp_path: Path) -> None:
    """Test that custom log file is written when specified."""
    require_ffmpeg()

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    out_root = tmp_path / "out"
    custom_log = tmp_path / "custom.log"

    # Create one audio file
    audio = input_dir / "test.wav"
    _make_tone(audio)

    result = subprocess.run(
        [
            "onepass-ingest",
            "ingest",
            str(input_dir),
            "--out-root",
            str(out_root),
            "--log-file",
            str(custom_log),
        ],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0

    # Custom log file should exist
    assert custom_log.exists()

    # Log file should contain some content
    log_content = custom_log.read_text(encoding="utf-8")
    assert len(log_content) > 0

