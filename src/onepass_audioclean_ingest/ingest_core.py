"""Core ingest routine shared by CLI and batch execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import shutil
from pathlib import Path
from typing import List, Optional

from .constants import (
    DEFAULT_AUDIO_FILENAME,
    DEFAULT_LOG_FILENAME,
    DEFAULT_META_FILENAME,
    INGEST_EXIT_CODES,
)
from .convert import ConvertResult, build_ffmpeg_command, convert_audio_to_wav
from .deps import DepsReport, check_deps, determine_exit_code
from .media import select_audio_stream
from .meta import MetaError, build_meta, write_meta
from .params import IngestParams, params_digest
from .probe import ffprobe_input, ffprobe_output


@dataclass
class IngestResult:
    """Structured ingest response for a single input."""

    input_path: Path
    workdir: Path
    audio_path: Path
    meta_path: Path
    log_path: Path
    exit_code: int
    status: str
    errors: List[MetaError] = field(default_factory=list)
    message: str = ""
    selected_stream: Optional[dict] = None
    convert_result: Optional[ConvertResult] = None
    probe: Optional[dict] = None
    params: Optional[IngestParams] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    @property
    def duration_ms(self) -> Optional[int]:
        if self.started_at and self.ended_at:
            return int((self.ended_at - self.started_at).total_seconds() * 1000)
        return None


def _extend_errors_from_deps(report: DepsReport) -> List[MetaError]:
    return [
        MetaError(code=e.get("code", "deps_error"), message=e.get("message", ""), hint=e.get("hint"))
        for e in report.errors
    ]


def ingest_one(
    input_path: Path,
    workdir: Path,
    params: IngestParams,
    overwrite: bool,
    deps_report: Optional[DepsReport] = None,
    output_work_id: Optional[str] = None,
    output_work_key: Optional[str] = None,
    params_sources: Optional[dict] = None,
    dry_run: bool = False,
) -> IngestResult:
    """Run ingest for a single input and always emit ``meta.json``."""

    started_at = datetime.utcnow()
    errors: List[MetaError] = []

    audio_out = workdir / DEFAULT_AUDIO_FILENAME
    meta_path = workdir / DEFAULT_META_FILENAME
    log_path = workdir / DEFAULT_LOG_FILENAME

    try:
        workdir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem failure
        errors.append(
            MetaError(
                code="output_not_writable",
                message=f"Failed to create workdir {workdir}: {exc}",
            )
        )
        deps = deps_report or check_deps()
        meta_obj = build_meta(
            input_path,
            workdir,
            params,
            deps,
            probe=None,
            errors=errors,
            actual_audio=None,
            output_work_id=output_work_id,
            output_work_key=output_work_key,
        )
        write_meta(meta_obj, meta_path)
        ended = datetime.utcnow()
        return IngestResult(
            input_path=input_path,
            workdir=workdir,
            audio_path=audio_out,
            meta_path=meta_path,
            log_path=log_path,
            exit_code=INGEST_EXIT_CODES["OUTPUT_NOT_WRITABLE"],
            status="failed",
            errors=errors,
            message=errors[-1].message,
            started_at=started_at,
            ended_at=ended,
            params=params,
        )

    if workdir.exists() and not overwrite:
        if audio_out.exists() or meta_path.exists() or log_path.exists():
            errors.append(
                MetaError(
                    code="output_exists",
                    message="Workdir already contains outputs; use --overwrite to replace.",
                )
            )
            meta_obj = build_meta(
                input_path,
                workdir,
                params,
                deps_report or check_deps(),
                probe=None,
                errors=errors,
                actual_audio=None,
                output_work_id=output_work_id,
                output_work_key=output_work_key,
            )
            write_meta(meta_obj, meta_path)
            ended = datetime.utcnow()
            return IngestResult(
                input_path=input_path,
                workdir=workdir,
                audio_path=audio_out,
                meta_path=meta_path,
                log_path=log_path,
                exit_code=INGEST_EXIT_CODES["OUTPUT_NOT_WRITABLE"],
                status="failed",
                errors=errors,
                message=errors[-1].message,
                started_at=started_at,
                ended_at=ended,
                params=params,
            )

    deps_report = deps_report or check_deps()
    errors.extend(_extend_errors_from_deps(deps_report))

    probe_result = ffprobe_input(input_path)
    errors.extend(probe_result.errors)

    selected_stream = None
    selection_errors: List[MetaError] = []
    selection_warnings: List[dict] = []
    if probe_result.input_ffprobe is not None:
        selected_stream, selection_errors, selection_warnings = select_audio_stream(
            probe_result.input_ffprobe,
            preferred_index=params.audio_stream_index,
            preferred_language=params.audio_language,
        )
        probe_result.input_ffprobe["selected_audio_stream"] = selected_stream

    errors.extend(selection_errors)

    probe_obj = {
        "input_ffprobe": probe_result.input_ffprobe,
        "warnings": probe_result.warnings + selection_warnings,
        "output_ffprobe": None,
    }

    if params.bit_depth != 16:
        errors.append(
            MetaError(
                code="invalid_params",
                message="Only 16-bit PCM output is supported in R4",
                hint="Use --bit-depth 16",
            )
        )
        params.bit_depth = 16

    exit_code: int = INGEST_EXIT_CODES["SUCCESS"]
    convert_result: Optional[ConvertResult] = None
    actual_audio = None
    ffmpeg_cmd: Optional[List[str]] = None
    ffmpeg_filtergraph: Optional[str] = None

    deps_exit = determine_exit_code(deps_report)
    if deps_exit != 0:
        exit_code = INGEST_EXIT_CODES["DEPS_MISSING"]
    elif not input_path.exists():
        errors.append(
            MetaError(
                code="input_not_found",
                message=f"Input file not found: {input_path}",
                hint="Check the path and try again.",
            )
        )
        exit_code = INGEST_EXIT_CODES["INPUT_INVALID"]
    elif any(err.code == "invalid_params" for err in errors):
        exit_code = INGEST_EXIT_CODES["INVALID_PARAMS"]
    else:
        stream_error_codes = {"no_audio_stream", "invalid_audio_stream_index", "audio_language_not_found"}
        if any(err.code in stream_error_codes for err in errors):
            exit_code = INGEST_EXIT_CODES["INVALID_STREAM_SELECTION"]
            if any(err.code == "no_audio_stream" for err in errors):
                exit_code = INGEST_EXIT_CODES["NO_SUPPORTED_STREAM"]
        else:
            ffmpeg_path = (
                deps_report.tools.get("ffmpeg").path if deps_report.tools.get("ffmpeg") else shutil.which("ffmpeg")
            )
            selected_index = selected_stream.get("index") if isinstance(selected_stream, dict) else None
            ffmpeg_cmd, ffmpeg_filtergraph = build_ffmpeg_command(
                input_path,
                audio_out,
                params,
                ffmpeg_path,
                overwrite,
                audio_stream_index=selected_index,
            )
            if not dry_run:
                convert_result = convert_audio_to_wav(
                    input_path,
                    audio_out,
                    params,
                    log_path,
                    ffmpeg_path,
                    overwrite,
                    audio_stream_index=selected_index,
                )
                if convert_result.returncode != 0 or not audio_out.exists():
                    errors.append(
                        MetaError(
                            code="convert_failed",
                            message=f"ffmpeg conversion failed (code={convert_result.returncode})",
                            detail={"stderr": convert_result.stderr},
                        )
                    )
                    exit_code = INGEST_EXIT_CODES["CONVERT_FAILED"]
                else:
                    output_probe, output_probe_errors = ffprobe_output(audio_out)
                    errors.extend(output_probe_errors)
                    actual_audio = output_probe
                    probe_obj["output_ffprobe"] = output_probe
                    if actual_audio is not None and actual_audio.get("bit_depth") is None:
                        actual_audio["bit_depth"] = params.bit_depth
                    if output_probe_errors:
                        exit_code = INGEST_EXIT_CODES["PROBE_FAILED"]

    params_digest_val = params_digest(params)
    execution_obj = {
        "ffmpeg_cmd": ffmpeg_cmd,
        "ffmpeg_filtergraph": ffmpeg_filtergraph,
        "planned": dry_run,
    }

    meta_obj = build_meta(
        input_path,
        workdir,
        params,
        deps_report,
        probe_obj,
        errors,
        actual_audio,
        output_work_id=output_work_id,
        output_work_key=output_work_key,
        params_sources=params_sources,
        execution=execution_obj,
        params_digest=params_digest_val,
        planned=dry_run,
    )
    write_meta(meta_obj, meta_path)

    ended_at = datetime.utcnow()
    if dry_run and exit_code == INGEST_EXIT_CODES["SUCCESS"]:
        status = "planned"
        message = "planned"
    else:
        status = "success" if exit_code == INGEST_EXIT_CODES["SUCCESS"] else "failed"
        message = "ok" if status == "success" else (errors[-1].message if errors else "failed")

    return IngestResult(
        input_path=input_path,
        workdir=workdir,
        audio_path=audio_out,
        meta_path=meta_path,
        log_path=log_path,
        exit_code=exit_code,
        status=status,
        errors=errors,
        message=message,
        selected_stream=selected_stream,
        convert_result=convert_result,
        probe=probe_obj,
        params=params,
        started_at=started_at,
        ended_at=ended_at,
    )

