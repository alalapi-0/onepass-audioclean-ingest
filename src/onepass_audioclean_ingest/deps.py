"""Dependency detection helpers for ffmpeg/ffprobe.

This module performs lightweight capability probing without triggering any
network access. Detection is best-effort and aims to be stable across
platforms by relying on text parsing rather than running media conversions.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
import platform
import re
import shutil
from typing import Dict, List, Optional

from .constants import ERROR_CODES
from .subprocess_utils import CmdResult, CommandTimeout, run_cmd


FFMPEG_MIN_CAPABILITIES = {
    "pcm_s16le": "pcm_s16le",  # encoder name for 16-bit PCM
    "decode_mp3": "mp3",
    "decode_aac": "aac",
    "decode_flac": "flac",
    "decode_opus": "opus",
}


@dataclass
class ToolInfo:
    """Information about a detected tool binary."""

    name: str
    path: str
    version_raw: str
    version: Optional[str]
    build: Dict[str, str] = field(default_factory=dict)
    detection: Optional[CmdResult] = None


@dataclass
class DepsReport:
    """Structured report for dependency checks."""

    ok: bool
    tools: Dict[str, Optional[ToolInfo]]
    capabilities: Dict[str, bool]
    errors: List[Dict[str, Optional[str]]]
    warnings: List[Dict[str, str]]
    created_at: str
    platform: Dict[str, str]

    def to_dict(self) -> Dict[str, object]:
        """Convert to plain dict, expanding dataclasses for JSON serialization."""

        return asdict(self)


def _parse_version(output: str, tool_name: str) -> Optional[str]:
    """Extract a version token from ``<tool> -version`` output.

    Common patterns include::
        ffmpeg version 7.0.2 Copyright (c) ...
        ffprobe version 6.0-essentials_build-www.gyan.dev ...
    """

    for line in output.splitlines():
        if line.strip():
            match = re.search(r"version\s+([\w.\-]+)", line)
            if match:
                return match.group(1)
            break
    # Fallback: look for the tool name followed by whitespace and a version-like token
    match = re.search(rf"{re.escape(tool_name)}\s+([\w.\-]+)", output)
    return match.group(1) if match else None


def _parse_build_info(output: str) -> Dict[str, str]:
    """Parse build configuration from version output.

    The goal is to surface useful hints (e.g., configuration flags) without
    being brittle. Keys are kept minimal and ordering is not significant.
    """

    build: Dict[str, str] = {}
    for line in output.splitlines():
        if line.lower().startswith("configuration"):
            # Example: configuration: --enable-gpl --enable-version3 ...
            build["configuration"] = line.split(":", 1)[-1].strip()
        elif "built" in line.lower() and "gcc" in line.lower():
            build.setdefault("compiler", line.strip())
    return build


def detect_ffmpeg(timeout_sec: int = 10) -> Optional[ToolInfo]:
    """Locate and inspect ``ffmpeg``.

    Returns ``None`` if the binary is not found via ``shutil.which``.
    """

    path = shutil.which("ffmpeg")
    if not path:
        return None

    detection = run_cmd([path, "-version"], timeout_sec=timeout_sec)
    version_raw = detection.stdout.strip() or detection.stderr.strip()
    version = _parse_version(version_raw, "ffmpeg")
    build = _parse_build_info(version_raw)
    return ToolInfo(
        name="ffmpeg",
        path=path,
        version_raw=version_raw,
        version=version,
        build=build,
        detection=detection,
    )


def detect_ffprobe(timeout_sec: int = 10) -> Optional[ToolInfo]:
    """Locate and inspect ``ffprobe``.

    Returns ``None`` if the binary is not found via ``shutil.which``.
    """

    path = shutil.which("ffprobe")
    if not path:
        return None

    detection = run_cmd([path, "-version"], timeout_sec=timeout_sec)
    version_raw = detection.stdout.strip() or detection.stderr.strip()
    version = _parse_version(version_raw, "ffprobe")
    build = _parse_build_info(version_raw)
    return ToolInfo(
        name="ffprobe",
        path=path,
        version_raw=version_raw,
        version=version,
        build=build,
        detection=detection,
    )


def _detect_capabilities(ffmpeg_path: str, timeout_sec: int = 15) -> tuple[Dict[str, bool], Optional[str]]:
    """Probe ffmpeg encoders/decoders for minimal ingest requirements.

    Output formats vary across platforms. We match by substring on each
    capability token and interpret any occurrence as support. For example,
    encoder lists often include ``pcm_s16le`` as ``EA.. pcm_s16le" while decoder
    lists include tags like ``A.... mp3``. Substring matching keeps the check
    tolerant to whitespace and flag columns.
    """

    capabilities: Dict[str, bool] = {key: False for key in FFMPEG_MIN_CAPABILITIES}

    try:
        encoders = run_cmd([ffmpeg_path, "-hide_banner", "-encoders"], timeout_sec=timeout_sec)
        encoder_output = encoders.stdout.lower()
    except CommandTimeout:
        return capabilities, "ffmpeg -encoders timed out"

    if encoders.returncode == 0:
        if FFMPEG_MIN_CAPABILITIES["pcm_s16le"].lower() in encoder_output:
            capabilities["pcm_s16le"] = True
    else:
        return capabilities, "ffmpeg -encoders returned non-zero exit code"

    try:
        decoders = run_cmd([ffmpeg_path, "-hide_banner", "-decoders"], timeout_sec=timeout_sec)
        decoder_output = decoders.stdout.lower()
    except CommandTimeout:
        return capabilities, "ffmpeg -decoders timed out"

    if decoders.returncode == 0:
        for key, token in FFMPEG_MIN_CAPABILITIES.items():
            if key == "pcm_s16le":
                continue
            if re.search(rf"\b{re.escape(token.lower())}\b", decoder_output):
                capabilities[key] = True
    else:
        return capabilities, "ffmpeg -decoders returned non-zero exit code"

    return capabilities, None


def _platform_info() -> Dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
    }


def _build_error(code: str, message: str, hint: Optional[str] = None) -> Dict[str, Optional[str]]:
    return {"code": code, "message": message, "hint": hint}


def determine_exit_code(report: DepsReport) -> int:
    """Map a dependency report to an exit code.

    Priority is: missing > broken > insufficient > ok. This keeps automation
    behavior predictable.
    """

    error_codes = {item.get("code") for item in report.errors}
    if "deps_missing" in error_codes:
        return ERROR_CODES.get("DEPS_MISSING", 2)
    if "deps_broken" in error_codes:
        return ERROR_CODES.get("DEPS_BROKEN", 3)
    if "deps_insufficient" in error_codes:
        return ERROR_CODES.get("DEPS_INSUFFICIENT", 4)
    return ERROR_CODES.get("OK", 0)


def check_deps() -> DepsReport:
    """Run dependency checks and return a structured report."""

    errors: List[Dict[str, Optional[str]]] = []
    warnings: List[Dict[str, str]] = []
    capabilities: Dict[str, bool] = {key: False for key in FFMPEG_MIN_CAPABILITIES}

    ffmpeg_info: Optional[ToolInfo]
    ffprobe_info: Optional[ToolInfo]

    try:
        ffmpeg_info = detect_ffmpeg()
    except CommandTimeout as exc:
        ffmpeg_info = None
        errors.append(
            _build_error(
                "deps_broken",
                f"ffmpeg timed out after {exc.timeout_sec}s",
                hint="Check ffmpeg installation or reduce wrapper timeout.",
            )
        )
    except Exception as exc:  # pragma: no cover - defensive
        ffmpeg_info = None
        errors.append(_build_error("deps_broken", f"ffmpeg detection failed: {exc}", hint=None))

    try:
        ffprobe_info = detect_ffprobe()
    except CommandTimeout as exc:
        ffprobe_info = None
        errors.append(
            _build_error(
                "deps_broken",
                f"ffprobe timed out after {exc.timeout_sec}s",
                hint="Check ffprobe installation or reduce wrapper timeout.",
            )
        )
    except Exception as exc:  # pragma: no cover - defensive
        ffprobe_info = None
        errors.append(_build_error("deps_broken", f"ffprobe detection failed: {exc}", hint=None))

    tools: Dict[str, Optional[ToolInfo]] = {"ffmpeg": ffmpeg_info, "ffprobe": ffprobe_info}

    if ffmpeg_info is None:
        errors.append(
            _build_error(
                "deps_missing",
                "ffmpeg not found in PATH",
                hint="Install ffmpeg and ensure it is available in PATH.",
            )
        )
    elif ffmpeg_info.detection and ffmpeg_info.detection.returncode != 0:
        errors.append(
            _build_error(
                "deps_broken",
                f"ffmpeg returned non-zero exit code: {ffmpeg_info.detection.returncode}",
                hint="Reinstall or rebuild ffmpeg.",
            )
        )
    else:
        capabilities, cap_error = _detect_capabilities(ffmpeg_info.path)
        if cap_error:
            errors.append(
                _build_error(
                    "deps_broken",
                    cap_error,
                    hint="Inspect ffmpeg build or permissions.",
                )
            )

    if ffprobe_info is None:
        errors.append(
            _build_error(
                "deps_missing",
                "ffprobe not found in PATH",
                hint="Install ffmpeg (usually includes ffprobe) and ensure PATH is set.",
            )
        )
    elif ffprobe_info.detection and ffprobe_info.detection.returncode != 0:
        errors.append(
            _build_error(
                "deps_broken",
                f"ffprobe returned non-zero exit code: {ffprobe_info.detection.returncode}",
                hint="Reinstall or rebuild ffmpeg/ffprobe.",
            )
        )

    if not capabilities.get("pcm_s16le", False) and ffmpeg_info is not None:
        errors.append(
            _build_error(
                "deps_insufficient",
                "ffmpeg missing pcm_s16le encoder support",
                hint="Ensure ffmpeg is built with PCM encoders enabled.",
            )
        )

    ok = len(errors) == 0

    created_at = datetime.utcnow().isoformat() + "Z"

    report = DepsReport(
        ok=ok,
        tools=tools,
        capabilities=capabilities,
        errors=errors,
        warnings=warnings,
        created_at=created_at,
        platform=_platform_info(),
    )

    # Finalize ok flag in case capability errors were appended
    report.ok = determine_exit_code(report) == ERROR_CODES.get("OK", 0)
    return report
