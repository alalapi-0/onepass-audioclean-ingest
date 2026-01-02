"""FFprobe helpers for extracting lightweight media information."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logging_utils import get_logger
from .meta import MetaError
from .subprocess_utils import CommandTimeout, run_cmd

logger = get_logger(__name__)


@dataclass
class ProbeResult:
    input_ffprobe: Optional[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    errors: List[MetaError]


def ffprobe_input(path: Path, timeout_sec: int = 30) -> ProbeResult:
    """Run ffprobe on an input file and return selected fields."""

    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        error = MetaError(
            code="probe_missing",
            message="ffprobe not found in PATH",
            hint="Install ffprobe or ensure it is available in PATH.",
        )
        return ProbeResult(input_ffprobe=None, warnings=[], errors=[error])

    try:
        result = run_cmd(
            [
                ffprobe_path,
                "-hide_banner",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            timeout_sec=timeout_sec,
        )
    except CommandTimeout as exc:
        error = MetaError(
            code="probe_timeout",
            message=f"ffprobe timed out after {exc.timeout_sec}s",
            hint="Retry with a smaller file or adjust timeout.",
        )
        return ProbeResult(input_ffprobe=None, warnings=[], errors=[error])

    if result.returncode != 0:
        error = MetaError(
            code="probe_failed",
            message=f"ffprobe returned {result.returncode}",
            detail={"stderr": result.stderr},
        )
        return ProbeResult(input_ffprobe=None, warnings=[], errors=[error])

    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        error = MetaError(
            code="probe_parse_error",
            message="Failed to parse ffprobe JSON output",
            detail={"error": str(exc)},
        )
        return ProbeResult(input_ffprobe=None, warnings=[], errors=[error])

    audio_stream = None
    for stream in parsed.get("streams", []):
        if stream.get("codec_type") == "audio":
            audio_stream = stream
            break

    format_section = parsed.get("format", {}) if isinstance(parsed, dict) else {}

    def _to_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _to_float(value: Any) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    probe_summary = {
        "duration": _to_float(format_section.get("duration")),
        "sample_rate": _to_int(audio_stream.get("sample_rate")) if audio_stream else None,
        "channels": _to_int(audio_stream.get("channels")) if audio_stream else None,
        "codec_name": audio_stream.get("codec_name") if audio_stream else None,
        "format_name": format_section.get("format_name"),
        "bit_rate": _to_int(format_section.get("bit_rate")),
    }

    warnings: List[Dict[str, Any]] = []
    if not audio_stream:
        warnings.append(
            {
                "code": "probe_no_audio_stream",
                "message": "No audio stream detected in input",
                "detail": None,
            }
        )

    return ProbeResult(input_ffprobe=probe_summary, warnings=warnings, errors=[])
