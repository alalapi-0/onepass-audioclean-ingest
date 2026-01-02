"""Command-line interface for OnePass AudioClean ingest."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from typing import Optional

import typer

from .config import ConfigError, load_config
from .constants import DEFAULT_AUDIO_FILENAME, DEFAULT_LOG_FILENAME, DEFAULT_META_FILENAME, INGEST_EXIT_CODES
from .convert import convert_audio_to_wav
from .deps import check_deps, determine_exit_code
from .logging_utils import get_logger
from .media import select_audio_stream
from .meta import IngestParams, MetaError, build_meta, write_meta
from .probe import ffprobe_input, ffprobe_output

app = typer.Typer(help="OnePass AudioClean ingest CLI")
logger = get_logger(__name__)


@app.command("check-deps")
def check_deps_command(
    config: Optional[str] = typer.Option(None, help="Path to config file"),
    json_output: bool = typer.Option(False, "--json", help="Output report as JSON"),
    verbose: bool = typer.Option(False, "--verbose", help="Show verbose details"),
) -> None:
    """Check local dependencies (ffmpeg/ffprobe)."""

    if config:
        logger.debug("Config path provided but unused in check-deps: %s", config)

    report = check_deps()
    exit_code = determine_exit_code(report)

    if json_output:
        indent = 2 if verbose else None
        typer.echo(json.dumps(report.to_dict(), ensure_ascii=False, indent=indent))
        raise typer.Exit(code=exit_code)

    summary_status = "OK" if report.ok else "FAIL"
    typer.echo(f"check-deps: {summary_status}")

    ffmpeg_info = report.tools.get("ffmpeg")
    ffprobe_info = report.tools.get("ffprobe")

    def _fmt_tool(info: Optional[object], name: str) -> str:
        if info is None:
            return f"{name}: not found"
        if hasattr(info, "path"):
            version_str = f" (version: {getattr(info, 'version', '')})" if getattr(info, "version", None) else ""
            return f"{name}: {getattr(info, 'path', '')}{version_str}"
        return f"{name}: unknown"

    typer.echo(_fmt_tool(ffmpeg_info, "ffmpeg"))
    typer.echo(_fmt_tool(ffprobe_info, "ffprobe"))

    capability_lines = []
    for key, supported in report.capabilities.items():
        capability_lines.append(f"  - {key}: {'yes' if supported else 'no'}")
    typer.echo("capabilities:")
    for line in capability_lines:
        typer.echo(line)

    if verbose:
        typer.echo("errors:")
        if report.errors:
            for err in report.errors:
                hint = f" (hint: {err['hint']})" if err.get("hint") else ""
                typer.echo(f"  - {err['code']}: {err['message']}{hint}")
        else:
            typer.echo("  - none")
        typer.echo("platform:")
        for key, value in report.platform.items():
            typer.echo(f"  - {key}: {value}")

    for err in report.errors:
        hint = f" (hint: {err['hint']})" if err.get("hint") else ""
        typer.echo(f"ERROR: {err['message']}{hint}", err=True)

    raise typer.Exit(code=exit_code)


@app.command()
def ingest(
    input_path: Optional[str] = typer.Argument(None, help="Path to input audio file"),
    out: str = typer.Option(..., "--out", help="Workdir for outputs"),
    config: Optional[str] = typer.Option(None, help="Path to config file"),
    sample_rate: Optional[int] = typer.Option(None, "--sample-rate", help="Target sample rate"),
    channels: Optional[int] = typer.Option(None, "--channels", help="Target channels"),
    bit_depth: Optional[int] = typer.Option(None, "--bit-depth", help="Bit depth (only 16 supported)"),
    normalize: Optional[bool] = typer.Option(None, "--normalize/--no-normalize", help="Enable loudness normalization"),
    audio_stream_index: Optional[int] = typer.Option(None, "--audio-stream-index", help="Audio stream index to extract"),
    audio_language: Optional[str] = typer.Option(
        None, "--audio-language", help="Preferred audio language tag (e.g. eng, jpn)"
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing outputs"),
    json_output: bool = typer.Option(False, "--json", help="Print meta.json content"),
) -> None:
    """Ingest and normalize audio inputs (single-file to WAV)."""

    if input_path is None:
        typer.echo("Input path is required", err=True)
        raise typer.Exit(code=INGEST_EXIT_CODES["INPUT_INVALID"])

    try:
        config_data = load_config(Path(config)) if config else load_config()
    except ConfigError as exc:
        typer.echo(f"Failed to load config: {exc}", err=True)
        raise typer.Exit(code=INGEST_EXIT_CODES["INVALID_PARAMS"])

    params = IngestParams.from_config(config_data)

    if sample_rate is not None:
        params.sample_rate = int(sample_rate)
    if channels is not None:
        params.channels = int(channels)
    if bit_depth is not None:
        params.bit_depth = int(bit_depth)
    if normalize is not None:
        params.normalize = bool(normalize)
    if params.normalize and not params.normalize_mode:
        params.normalize_mode = "loudnorm=I=-16:LRA=11:TP=-1.5"
    if not params.normalize:
        params.normalize_mode = None

    if audio_stream_index is not None:
        params.audio_stream_index = int(audio_stream_index)
    if audio_language is not None:
        params.audio_language = audio_language

    errors: list[MetaError] = []
    if params.bit_depth != 16:
        errors.append(
            MetaError(
                code="invalid_params",
                message="Only 16-bit PCM output is supported in R4",
                hint="Use --bit-depth 16",
            )
        )
        params.bit_depth = 16

    input_path_obj = Path(input_path)
    workdir = Path(out)

    try:
        workdir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem failure
        typer.echo(f"Failed to create workdir {workdir}: {exc}", err=True)
        raise typer.Exit(code=INGEST_EXIT_CODES["OUTPUT_NOT_WRITABLE"])

    audio_out = workdir / DEFAULT_AUDIO_FILENAME
    meta_path = workdir / DEFAULT_META_FILENAME
    log_path = workdir / DEFAULT_LOG_FILENAME

    if workdir.exists() and not overwrite:
        if audio_out.exists() or meta_path.exists() or log_path.exists():
            typer.echo("Workdir already contains outputs; use --overwrite to replace.", err=True)
            raise typer.Exit(code=INGEST_EXIT_CODES["OUTPUT_NOT_WRITABLE"])

    deps_report = check_deps()
    deps_errors = [
        MetaError(code=e.get("code", "deps_error"), message=e.get("message", ""), hint=e.get("hint"))
        for e in deps_report.errors
    ]
    errors.extend(deps_errors)

    probe_result = ffprobe_input(input_path_obj)
    errors.extend(probe_result.errors)

    selected_stream = None
    selection_errors: list[MetaError] = []
    selection_warnings: list[dict] = []
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

    actual_audio = None
    convert_rc: Optional[int] = None

    deps_exit = determine_exit_code(deps_report)
    if deps_exit != 0:
        meta_obj = build_meta(input_path_obj, workdir, params, deps_report, probe_obj, errors, actual_audio)
        write_meta(meta_obj, meta_path)
        if json_output:
            typer.echo(json.dumps(meta_obj, ensure_ascii=False, sort_keys=True, indent=2))
        raise typer.Exit(code=INGEST_EXIT_CODES["DEPS_MISSING"])

    if errors and any(err.code == "invalid_params" for err in errors):
        meta_obj = build_meta(input_path_obj, workdir, params, deps_report, probe_obj, errors, actual_audio)
        write_meta(meta_obj, meta_path)
        if json_output:
            typer.echo(json.dumps(meta_obj, ensure_ascii=False, sort_keys=True, indent=2))
        raise typer.Exit(code=INGEST_EXIT_CODES["INVALID_PARAMS"])

    if not input_path_obj.exists():
        errors.append(
            MetaError(
                code="input_not_found",
                message=f"Input file not found: {input_path_obj}",
                hint="Check the path and try again.",
            )
        )
        meta_obj = build_meta(input_path_obj, workdir, params, deps_report, probe_obj, errors, actual_audio)
        write_meta(meta_obj, meta_path)
        if json_output:
            typer.echo(json.dumps(meta_obj, ensure_ascii=False, sort_keys=True, indent=2))
        raise typer.Exit(code=INGEST_EXIT_CODES["INPUT_INVALID"])

    stream_error_codes = {"no_audio_stream", "invalid_audio_stream_index", "audio_language_not_found"}
    if any(err.code in stream_error_codes for err in errors):
        exit_code = INGEST_EXIT_CODES["INVALID_STREAM_SELECTION"]
        if any(err.code == "no_audio_stream" for err in errors):
            exit_code = INGEST_EXIT_CODES["NO_SUPPORTED_STREAM"]
        meta_obj = build_meta(input_path_obj, workdir, params, deps_report, probe_obj, errors, actual_audio)
        write_meta(meta_obj, meta_path)
        if json_output:
            typer.echo(json.dumps(meta_obj, ensure_ascii=False, sort_keys=True, indent=2))
        raise typer.Exit(code=exit_code)

    ffmpeg_path = deps_report.tools.get("ffmpeg").path if deps_report.tools.get("ffmpeg") else shutil.which("ffmpeg")
    selected_index = selected_stream.get("index") if isinstance(selected_stream, dict) else None
    convert_result = convert_audio_to_wav(
        input_path_obj, audio_out, params, log_path, ffmpeg_path, overwrite, audio_stream_index=selected_index
    )
    convert_rc = convert_result.returncode

    if convert_result.returncode != 0 or not audio_out.exists():
        errors.append(
            MetaError(
                code="convert_failed",
                message=f"ffmpeg conversion failed (code={convert_result.returncode})",
                detail={"stderr": convert_result.stderr},
            )
        )
        meta_obj = build_meta(input_path_obj, workdir, params, deps_report, probe_obj, errors, actual_audio)
        write_meta(meta_obj, meta_path)
        if json_output:
            typer.echo(json.dumps(meta_obj, ensure_ascii=False, sort_keys=True, indent=2))
        raise typer.Exit(code=INGEST_EXIT_CODES["CONVERT_FAILED"])

    output_probe, output_probe_errors = ffprobe_output(audio_out)
    errors.extend(output_probe_errors)
    actual_audio = output_probe
    probe_obj["output_ffprobe"] = output_probe

    if actual_audio is not None and actual_audio.get("bit_depth") is None:
        actual_audio["bit_depth"] = params.bit_depth

    meta_obj = build_meta(input_path_obj, workdir, params, deps_report, probe_obj, errors, actual_audio)
    write_meta(meta_obj, meta_path)

    if json_output:
        typer.echo(json.dumps(meta_obj, ensure_ascii=False, sort_keys=True, indent=2))

    if output_probe_errors:
        raise typer.Exit(code=INGEST_EXIT_CODES["PROBE_FAILED"])

    raise typer.Exit(code=convert_rc if convert_rc is not None else INGEST_EXIT_CODES["SUCCESS"])


@app.command()
def meta(
    input_path: str = typer.Argument(..., help="Path to input audio file"),
    out: str = typer.Option(..., "--out", help="Workdir for meta.json"),
    config: Optional[str] = typer.Option(None, help="Path to config file"),
    json_output: bool = typer.Option(False, "--json", help="Print meta.json content"),
) -> None:
    """Generate meta.json without performing conversion."""

    try:
        config_data = load_config(Path(config)) if config else load_config()
    except ConfigError as exc:
        typer.echo(f"Failed to load config: {exc}", err=True)
        raise typer.Exit(code=1)

    params = IngestParams.from_config(config_data)
    workdir = Path(out)

    try:
        workdir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - filesystem failure
        typer.echo(f"Failed to create workdir {workdir}: {exc}", err=True)
        raise typer.Exit(code=1)

    deps_report = check_deps()
    errors = [MetaError(code=e.get("code", "deps_error"), message=e.get("message", ""), hint=e.get("hint")) for e in deps_report.errors]

    probe_result = ffprobe_input(Path(input_path))
    errors.extend(probe_result.errors)

    probe_obj = {"input_ffprobe": probe_result.input_ffprobe, "warnings": probe_result.warnings, "output_ffprobe": None}
    meta_obj = build_meta(Path(input_path), workdir, params, deps_report, probe_obj, errors, actual_audio=None)

    meta_path = workdir / DEFAULT_META_FILENAME
    write_meta(meta_obj, meta_path)

    if json_output:
        typer.echo(json.dumps(meta_obj, ensure_ascii=False, sort_keys=True, indent=2))

    if errors:
        typer.echo("meta.json generated with recorded errors; see errors section.", err=False)

    raise typer.Exit(code=0)


def main(argv: Optional[list[str]] = None) -> int:
    """Entrypoint for console script."""

    argv = argv if argv is not None else sys.argv[1:]
    app(prog_name="onepass-ingest", args=list(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
