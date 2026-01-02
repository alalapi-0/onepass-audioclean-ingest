"""Metadata schema helpers for OnePass AudioClean ingest."""
from __future__ import annotations

import hashlib
import json
import shlex
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
import platform
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jsonschema import Draft202012Validator

from .constants import (
    DEFAULT_AUDIO_FILENAME,
    DEFAULT_LOG_FILENAME,
    DEFAULT_META_FILENAME,
)
from .deps import DepsReport
from .params import IngestParams


@dataclass
class MetaError:
    """Structured error entry for meta.json."""

    code: str
    message: str
    hint: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _repo_version() -> Optional[str]:
    try:
        return version("onepass-audioclean-ingest")
    except PackageNotFoundError:
        return None


def _input_info(input_path: Path, errors: List[MetaError]) -> Dict[str, Any]:
    abspath = str(input_path.resolve())
    ext = input_path.suffix
    size_bytes = 0
    mtime_epoch: Optional[float] = None

    if input_path.exists():
        stat = input_path.stat()
        size_bytes = stat.st_size
        mtime_epoch = stat.st_mtime
    else:
        errors.append(
            MetaError(
                code="input_missing",
                message=f"Input file not found: {input_path}",
                hint="Ensure the input path is correct before ingestion.",
            )
        )

    return {
        "path": str(input_path),
        "abspath": abspath,
        "size_bytes": int(size_bytes),
        "mtime_epoch": mtime_epoch,
        "sha256": None,
        "ext": ext,
    }


def _tooling(report: DepsReport) -> Dict[str, Any]:
    ffmpeg_info = asdict(report.tools.get("ffmpeg")) if report.tools.get("ffmpeg") else None
    ffprobe_info = asdict(report.tools.get("ffprobe")) if report.tools.get("ffprobe") else None
    return {
        "ffmpeg": ffmpeg_info,
        "ffprobe": ffprobe_info,
        "python": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "executable": sys.executable,
        },
    }


def _stable_fields() -> Dict[str, Any]:
    core_fields = [
        "schema_version",
        "pipeline.repo",
        "input.path",
        "input.size_bytes",
        "input.ext",
        "params.sample_rate",
        "params.channels",
        "params.bit_depth",
        "params.normalize",
        "params.normalize_mode",
        "params.normalize_config",
        "params.ffmpeg_extra_args",
        "params.audio_stream_index",
        "params.audio_language",
        "params_sources.sample_rate",
        "params_sources.channels",
        "params_sources.bit_depth",
        "params_sources.normalize",
        "params_sources.normalize_mode",
        "params_sources.normalize_config",
        "params_sources.ffmpeg_extra_args",
        "params_sources.audio_stream_index",
        "params_sources.audio_language",
        "output.workdir",
        "output.work_id",
        "output.work_key",
        "output.audio_wav",
        "output.meta_json",
        "output.convert_log",
        "output.expected_audio.codec",
        "output.expected_audio.sample_rate",
        "output.expected_audio.channels",
        "output.expected_audio.bit_depth",
    ]
    non_core_fields = [
        "created_at",
        "pipeline.repo_version",
        "input.abspath",
        "input.mtime_epoch",
        "input.sha256",
        "tooling.python",
        "probe.warnings",
        "probe.output_ffprobe",
        "output.actual_audio",
        "errors",
        "execution",
    ]
    notes = (
        "Core fields drive reproducibility (paths within workdir, params, expected_audio). "
        "Non-core fields may change across runs or machines (timestamps, absolute paths, platform). "
        "Actual audio attributes are captured to validate the conversion but are derived from ffprobe and may vary slightly across ffmpeg builds. "
        "output.work_id/work_key track the deterministic workdir naming based on path+size in batch runs. "
        "Enabling normalize changes the waveform; reproducibility depends on using the same ffmpeg build and fixed loudnorm parameters."
    )
    return {"core": core_fields, "non_core": non_core_fields, "notes": notes}


def _cmd_digest(cmd: Optional[List[str]], filtergraph: Optional[str]) -> Optional[str]:
    if cmd is None:
        return None
    payload = {"cmd": cmd, "filtergraph": filtergraph}
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _cmd_str(cmd: Optional[List[str]]) -> Optional[str]:
    if cmd is None:
        return None
    return " ".join(shlex.quote(part) for part in cmd)


def build_meta(
    input_path: Path,
    workdir: Path,
    params: IngestParams,
    tooling: DepsReport,
    probe: Optional[Dict[str, Any]],
    errors: List[MetaError],
    actual_audio: Optional[Dict[str, Any]] = None,
    output_work_id: Optional[str] = None,
    output_work_key: Optional[str] = None,
    params_sources: Optional[Dict[str, str]] = None,
    execution: Optional[Dict[str, Any]] = None,
    params_digest: Optional[str] = None,
    cmd_digest: Optional[str] = None,
    planned: bool = False,
) -> Dict[str, Any]:
    """Assemble the meta dictionary adhering to the v1 schema."""

    input_obj = _input_info(input_path, errors)
    schema_version = "meta.v1"
    pipeline = {"repo": "onepass-audioclean-ingest", "repo_version": _repo_version()}

    probe_obj = probe if probe is not None else {"input_ffprobe": None, "warnings": [], "output_ffprobe": None}

    output_obj = {
        "workdir": str(workdir),
        "work_id": output_work_id,
        "work_key": output_work_key,
        "audio_wav": DEFAULT_AUDIO_FILENAME,
        "meta_json": DEFAULT_META_FILENAME,
        "convert_log": DEFAULT_LOG_FILENAME,
        "expected_audio": {
            "codec": "pcm_s16le",
            "sample_rate": params.sample_rate,
            "channels": params.channels,
            "bit_depth": params.bit_depth,
        },
        "actual_audio": actual_audio,
    }
    params_dict = params.to_dict()
    params_digest = params_digest or hashlib.sha256(
        json.dumps(params_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    execution_obj = execution or {
        "ffmpeg_cmd": None,
        "ffmpeg_cmd_str": None,
        "ffmpeg_filtergraph": None,
        "cmd_digest": _cmd_digest(None, None) if cmd_digest is None else cmd_digest,
        "planned": planned,
    }
    execution_obj["cmd_digest"] = execution_obj.get("cmd_digest") or _cmd_digest(
        execution_obj.get("ffmpeg_cmd"), execution_obj.get("ffmpeg_filtergraph")
    )
    execution_obj["ffmpeg_cmd_str"] = execution_obj.get("ffmpeg_cmd_str") or _cmd_str(execution_obj.get("ffmpeg_cmd"))
    execution_obj["planned"] = planned or execution_obj.get("planned", False)

    meta = {
        "schema_version": schema_version,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "pipeline": pipeline,
        "input": input_obj,
        "params": params_dict,
        "params_sources": params_sources,
        "tooling": _tooling(tooling),
        "probe": probe_obj,
        "output": output_obj,
        "execution": execution_obj,
        "integrity": {"meta_sha256": None, "output_audio_sha256": None, "params_digest": params_digest},
        "errors": [err.to_dict() for err in errors],
        "stable_fields": _stable_fields(),
    }
    return meta


def write_meta(meta: Dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")


def validate_meta(meta: Dict[str, Any], schema_path: Path) -> Tuple[bool, List[str]]:
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)
    validator = Draft202012Validator(schema)
    errors = [error.message for error in validator.iter_errors(meta)]
    return len(errors) == 0, errors
