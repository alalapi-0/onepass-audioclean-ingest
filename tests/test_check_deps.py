"""Tests for the check-deps command.

The tests are tolerant to environments where ffmpeg/ffprobe are unavailable.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from typing import Dict, Any


def _maybe_skip_missing_tools() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        import pytest

        pytest.skip("ffmpeg/ffprobe not available in test environment", allow_module_level=True)


def test_check_deps_json_parsable() -> None:
    _maybe_skip_missing_tools()

    result = subprocess.run(
        ["onepass-ingest", "check-deps", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode in {0, 2, 3, 4}

    payload: Dict[str, Any] = json.loads(result.stdout)
    assert "ok" in payload
    assert "tools" in payload
    assert "capabilities" in payload
    assert "errors" in payload
    assert "platform" in payload

    if payload.get("ok"):
        ffmpeg = payload["tools"].get("ffmpeg")
        assert ffmpeg is not None
        assert ffmpeg.get("path")
        assert payload["capabilities"].get("pcm_s16le") is True
