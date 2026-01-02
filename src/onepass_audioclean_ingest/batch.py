"""Batch ingest executor and manifest writer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .constants import (
    DEFAULT_AUDIO_FILENAME,
    DEFAULT_LOG_FILENAME,
    DEFAULT_MANIFEST_NAME,
    DEFAULT_META_FILENAME,
    INGEST_EXIT_CODES,
    MANIFEST_SCHEMA_VERSION,
    MANIFEST_PLAN_SCHEMA_VERSION,
    SUPPORTED_MEDIA_EXTENSIONS,
)
from .deps import check_deps, determine_exit_code
from .errors import ErrorCode, ExitCode, IngestError, summarize_errors
from .ingest_core import ingest_one
from .logging_utils import get_logger
from .params import IngestParams, params_digest
from .scan import scan_inputs


logger = get_logger(__name__)


@dataclass
class BatchOptions:
    params: IngestParams
    params_sources: Optional[dict] = None
    overwrite: bool = False
    recursive: bool = True
    exts: Optional[Iterable[str]] = None
    continue_on_error: bool = True
    manifest_name: str = DEFAULT_MANIFEST_NAME
    dry_run: bool = False
    log_file: Optional[Path] = None


@dataclass
class BatchResult:
    exit_code: int
    processed: int
    succeeded: int
    failed: int
    manifest_path: Optional[Path]


def safe_stem(name: str, max_len: int = 60) -> str:
    safe_chars = [ch if ch.isalnum() or ch in {".", "_", "-"} else "_" for ch in name]
    safe = "".join(safe_chars)
    return safe[:max_len] if len(safe) > max_len else safe


def compute_work_id(input_path: Path, input_root: Optional[Path] = None, size_bytes: Optional[int] = None) -> Tuple[str, str]:
    root = input_root.resolve() if input_root else None
    rel = input_path.relative_to(root) if root else Path(input_path.name)
    rel_key = rel.as_posix()
    actual_size = size_bytes
    if actual_size is None and input_path.exists():
        actual_size = input_path.stat().st_size
    size_token = actual_size if actual_size is not None else 0
    work_key = f"{rel_key}\n{size_token}"
    digest = hashlib.sha256(work_key.encode("utf-8")).hexdigest()[:12]
    return work_key, digest


def _manifest_line(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True)


def _params_digest(params: IngestParams) -> str:
    return params_digest(params)


def _error_summary(errors: Iterable[object]) -> str:
    messages: List[str] = []
    for err in errors:
        message = getattr(err, "message", None) or getattr(err, "get", lambda key, default=None: None)("message")
        if message:
            messages.append(str(message))
    return "; ".join(messages)


def _make_manifest_path(out_root: Path, manifest_name: str, dry_run: bool) -> Path:
    if dry_run:
        stem = manifest_name
        if stem.endswith(".jsonl"):
            stem = stem[:-6]
        return out_root / f"{stem}.plan.jsonl"
    return out_root / manifest_name


def run_batch(input_dir: Path, out_root: Path, options: BatchOptions) -> BatchResult:
    input_dir = input_dir.resolve()
    out_root = out_root.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    exts = set(options.exts) if options.exts else set(SUPPORTED_MEDIA_EXTENSIONS)
    manifest_path = _make_manifest_path(out_root, options.manifest_name, options.dry_run)

    # Check deps at the start - if missing, exit early with code 2
    deps_report = check_deps()
    deps_exit = determine_exit_code(deps_report)
    if deps_exit != 0:
        logger.error("Dependencies check failed, cannot proceed with batch ingest")
        # Write a minimal manifest entry if possible
        try:
            with manifest_path.open("w", encoding="utf-8", newline="\n") as f:
                record = {
                    "schema_version": MANIFEST_SCHEMA_VERSION,
                    "status": "failed",
                    "exit_code": deps_exit,
                    "error_codes": ["deps_missing"],
                    "error_messages": ["Dependencies (ffmpeg/ffprobe) are missing or broken"],
                    "message": "Batch ingest aborted due to missing dependencies",
                    "input": {"path": str(input_dir), "relpath": ".", "ext": "", "size_bytes": 0},
                    "output": {"workdir": str(out_root), "work_id": None, "work_key": None},
                    "started_at": datetime.utcnow().isoformat() + "Z",
                    "ended_at": datetime.utcnow().isoformat() + "Z",
                    "duration_ms": 0,
                }
                f.write(_manifest_line(record) + "\n")
        except Exception:  # pragma: no cover
            pass
        return BatchResult(exit_code=deps_exit, processed=0, succeeded=0, failed=0, manifest_path=manifest_path)

    files = scan_inputs(input_dir, recursive=options.recursive, exts=exts)
    if not files:
        logger.info("No inputs found under %s", input_dir)

    manifest_handle = manifest_path.open("w", encoding="utf-8", newline="\n")

    processed = 0
    succeeded = 0
    failed = 0
    exit_code = 0

    for path in files:
        processed += 1
        relpath = path.relative_to(input_dir).as_posix()
        size_bytes = path.stat().st_size if path.exists() else 0
        work_key, work_id = compute_work_id(path, input_root=input_dir, size_bytes=size_bytes)
        workdir_name = f"{safe_stem(path.stem)}__{work_id}"
        workdir = out_root / workdir_name
        started = datetime.utcnow()

        if options.dry_run:
            ended = datetime.utcnow()
            # Generate output filename based on input filename
            audio_filename = f"{path.stem}.wav"
            record = {
                "schema_version": MANIFEST_PLAN_SCHEMA_VERSION,
                "status": "planned",
                "exit_code": None,
                "error_codes": [],
                "message": "planned",
                "errors_summary": "",
                "input": {
                    "path": str(path),
                    "relpath": relpath,
                    "ext": path.suffix.lower(),
                    "size_bytes": size_bytes,
                },
                "output": {
                    "workdir": str(workdir),
                    "work_id": work_id,
                    "work_key": work_key,
                    "audio_wav": str(workdir / audio_filename),
                    "meta_json": str(workdir / DEFAULT_META_FILENAME),
                    "convert_log": str(workdir / DEFAULT_LOG_FILENAME),
                },
                "started_at": started.isoformat() + "Z",
                "ended_at": ended.isoformat() + "Z",
                "duration_ms": int((ended - started).total_seconds() * 1000),
                "params_digest": _params_digest(options.params),
            }
            manifest_handle.write(_manifest_line(record) + "\n")
            manifest_handle.flush()
            continue

        try:
            result = ingest_one(
                path,
                workdir,
                params=options.params,
                params_sources=options.params_sources,
                overwrite=options.overwrite,
                deps_report=deps_report,
                output_work_id=work_id,
                output_work_key=work_key,
            )
        except Exception as exc:  # pragma: no cover - defensive
            ended = datetime.utcnow()
            failed += 1
            exit_code = ExitCode.PARTIAL_FAILED
            error_codes, error_messages = summarize_errors(
                [IngestError(code=ErrorCode.INTERNAL_ERROR, message=f"Unhandled error: {exc}")]
            )
            record = {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "status": "failed",
                "exit_code": ExitCode.INTERNAL_ERROR,
                "error_codes": error_codes,
                "error_messages": error_messages,
                "warning_codes": [],
                "warning_messages": [],
                "message": f"Unhandled error: {exc}",
                "errors_summary": str(exc)[:200],
                "input": {
                    "path": str(path),
                    "relpath": relpath,
                    "ext": path.suffix.lower(),
                    "size_bytes": size_bytes,
                },
                "output": {
                    "workdir": str(workdir),
                    "work_id": work_id,
                    "work_key": work_key,
                    "audio_wav": str(workdir / f"{path.stem}.wav"),
                    "meta_json": str(workdir / DEFAULT_META_FILENAME),
                    "convert_log": str(workdir / DEFAULT_LOG_FILENAME),
                },
                "started_at": started.isoformat() + "Z",
                "ended_at": ended.isoformat() + "Z",
                "duration_ms": int((ended - started).total_seconds() * 1000),
                "params_digest": _params_digest(options.params),
            }
            manifest_handle.write(_manifest_line(record) + "\n")
            manifest_handle.flush()
            if not options.continue_on_error:
                break
            continue

        ended = result.ended_at or datetime.utcnow()
        status = result.status
        error_codes, error_messages = summarize_errors(result.errors)
        warning_codes, warning_messages = summarize_errors(result.warnings)
        if status != "success":
            failed += 1
            exit_code = ExitCode.PARTIAL_FAILED
        else:
            succeeded += 1

        # Determine meta_json path
        meta_json_path = str(result.meta_path) if result.meta_path.exists() else None

        record = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "status": status,
            "exit_code": result.exit_code,
            "error_codes": error_codes,
            "error_messages": error_messages,
            "warning_codes": warning_codes,
            "warning_messages": warning_messages,
            "message": result.message,
            "errors_summary": "; ".join(error_messages) if error_messages else "",
            "input": {
                "path": str(path),
                "relpath": relpath,
                "ext": path.suffix.lower(),
                "size_bytes": size_bytes,
            },
            "output": {
                "workdir": str(workdir),
                "work_id": work_id,
                "work_key": work_key,
                "audio_wav": str(result.audio_path) if result.audio_path else str(workdir / f"{path.stem}.wav"),
                "meta_json": str(workdir / DEFAULT_META_FILENAME),
                "convert_log": str(workdir / DEFAULT_LOG_FILENAME),
            },
            "meta_json_path": meta_json_path,
            "log_file": str(options.log_file) if options.log_file else None,
            "started_at": (result.started_at or started).isoformat() + "Z",
            "ended_at": ended.isoformat() + "Z",
            "duration_ms": result.duration_ms or int((ended - started).total_seconds() * 1000),
            "params_digest": _params_digest(options.params),
        }
        manifest_handle.write(_manifest_line(record) + "\n")
        manifest_handle.flush()

        if status != "success" and not options.continue_on_error:
            break

    manifest_handle.close()

    # Final exit code: 0 if all succeeded, 1 if any failed, 2 if deps missing (already handled)
    final_exit_code = ExitCode.SUCCESS if failed == 0 else ExitCode.PARTIAL_FAILED

    return BatchResult(
        exit_code=final_exit_code,
        processed=processed,
        succeeded=succeeded,
        failed=failed,
        manifest_path=manifest_path,
    )

