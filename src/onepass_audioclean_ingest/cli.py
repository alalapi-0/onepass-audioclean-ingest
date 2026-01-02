"""Command-line interface for OnePass AudioClean ingest."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Optional, Set

import typer

from .batch import BatchOptions, run_batch, compute_work_id
from .config import ConfigError
from .constants import DEFAULT_INGEST_LOG_NAME, DEFAULT_MANIFEST_NAME, DEFAULT_META_FILENAME, INGEST_EXIT_CODES, SUPPORTED_MEDIA_EXTENSIONS
from .deps import check_deps, determine_exit_code
from .ingest_core import ingest_one
from .logging_utils import get_logger, setup_logging
from .params import IngestParams, load_config_params, load_default_params, merge_params
from .meta import MetaError, build_meta, write_meta
from .probe import ffprobe_input

app = typer.Typer(help="OnePass AudioClean ingest CLI")
logger = get_logger(__name__)


@app.command("check-deps")
def check_deps_command(
    config: Optional[str] = typer.Option(None, help="Path to config file"),
    json_output: bool = typer.Option(False, "--json", help="Output report as JSON"),
    verbose: bool = typer.Option(False, "--verbose", help="Show verbose details"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file"),
) -> None:
    """Check local dependencies (ffmpeg/ffprobe)."""

    setup_logging(verbose=verbose, log_file=Path(log_file) if log_file else None)

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
    input_path: Optional[str] = typer.Argument(None, help="Path to input file or directory"),
    out: Optional[str] = typer.Option(None, "--out", help="Workdir for single-file outputs"),
    out_root: Optional[str] = typer.Option(None, "--out-root", help="Output root when ingesting a directory"),
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
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Recursively scan directories"),
    ext: Optional[str] = typer.Option(None, "--ext", help="Comma-separated extension whitelist for directory mode"),
    continue_on_error: bool = typer.Option(True, "--continue-on-error/--fail-fast", help="Keep running on failures"),
    manifest_name: str = typer.Option(DEFAULT_MANIFEST_NAME, "--manifest-name", help="Manifest filename for batch mode"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan batch outputs without converting"),
    json_output: bool = typer.Option(False, "--json", help="Print meta.json content (single file)"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose (DEBUG) logging"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to global log file (batch mode defaults to <out-root>/ingest.log)"),
) -> None:
    """Ingest a single file or a directory of media."""

    if input_path is None:
        typer.echo("Input path is required", err=True)
        raise typer.Exit(code=INGEST_EXIT_CODES["INPUT_INVALID"])

    input_path_obj = Path(input_path)
    is_dir_mode = input_path_obj.is_dir() or out_root is not None

    # Setup logging: determine log file path
    log_file_path: Optional[Path] = None
    if log_file:
        log_file_path = Path(log_file)
    elif is_dir_mode and out_root:
        # Default log file for batch mode
        log_file_path = Path(out_root) / DEFAULT_INGEST_LOG_NAME

    setup_logging(verbose=verbose, log_file=log_file_path)

    try:
        default_params, _default_sources = load_default_params()
        config_params = load_config_params(Path(config)) if config else None
    except ConfigError as exc:
        typer.echo(f"Failed to load config: {exc}", err=True)
        raise typer.Exit(code=INGEST_EXIT_CODES["INVALID_PARAMS"])

    cli_overrides: dict[str, Optional[str | int | bool]] = {}
    if sample_rate is not None:
        cli_overrides["sample_rate"] = int(sample_rate)
    if channels is not None:
        cli_overrides["channels"] = int(channels)
    if bit_depth is not None:
        cli_overrides["bit_depth"] = int(bit_depth)
    if normalize is not None:
        cli_overrides["normalize"] = bool(normalize)
    if audio_stream_index is not None:
        cli_overrides["audio_stream_index"] = int(audio_stream_index)
    if audio_language is not None:
        cli_overrides["audio_language"] = audio_language

    params, params_sources = merge_params(default_params, config_params, cli_overrides)

    def _parse_ext(value: Optional[str]) -> Set[str]:
        if value is None:
            return SUPPORTED_MEDIA_EXTENSIONS
        parsed = {item.strip().lower() for item in value.split(",") if item.strip()}
        return {f".{e}" if not e.startswith(".") else e for e in parsed}

    if is_dir_mode:
        if out is not None:
            typer.echo("--out cannot be combined with directory input; use --out-root.", err=True)
            raise typer.Exit(code=INGEST_EXIT_CODES["INVALID_PARAMS"])
        if out_root is None:
            typer.echo("--out-root is required for directory ingest", err=True)
            raise typer.Exit(code=INGEST_EXIT_CODES["INVALID_PARAMS"])
        if not input_path_obj.exists() or not input_path_obj.is_dir():
            typer.echo("Input directory does not exist", err=True)
            raise typer.Exit(code=INGEST_EXIT_CODES["INPUT_INVALID"])

        options = BatchOptions(
            params=params,
            params_sources=params_sources,
            overwrite=overwrite,
            recursive=recursive,
            exts=_parse_ext(ext),
            continue_on_error=continue_on_error,
            manifest_name=manifest_name,
            dry_run=dry_run,
            log_file=log_file_path,
        )
        result = run_batch(input_path_obj, Path(out_root), options)
        raise typer.Exit(code=result.exit_code)

    if out_root is not None:
        typer.echo("--out-root can only be used with directory ingest", err=True)
        raise typer.Exit(code=INGEST_EXIT_CODES["INVALID_PARAMS"])
    if out is None:
        typer.echo("--out is required for single-file ingest", err=True)
        raise typer.Exit(code=INGEST_EXIT_CODES["INVALID_PARAMS"])

    workdir = Path(out)
    size_bytes = input_path_obj.stat().st_size if input_path_obj.exists() else None
    work_key, work_id = compute_work_id(input_path_obj, size_bytes=size_bytes)

    result = ingest_one(
        input_path_obj,
        workdir,
        params,
        overwrite,
        params_sources=params_sources,
        output_work_id=work_id,
        output_work_key=work_key,
        dry_run=dry_run,
    )

    if json_output:
        try:
            meta_content = json.loads(result.meta_path.read_text(encoding="utf-8"))
            typer.echo(json.dumps(meta_content, ensure_ascii=False, sort_keys=True, indent=2))
        except OSError:
            typer.echo("Failed to read generated meta.json", err=True)

    raise typer.Exit(code=result.exit_code)


@app.command()
def meta(
    input_path: str = typer.Argument(..., help="Path to input audio file"),
    out: str = typer.Option(..., "--out", help="Workdir for meta.json"),
    config: Optional[str] = typer.Option(None, help="Path to config file"),
    json_output: bool = typer.Option(False, "--json", help="Print meta.json content"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose (DEBUG) logging"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Path to log file"),
) -> None:
    """Generate meta.json without performing conversion."""

    setup_logging(verbose=verbose, log_file=Path(log_file) if log_file else None)

    try:
        default_params, _default_sources = load_default_params()
        config_params = load_config_params(Path(config)) if config else None
        params, params_sources = merge_params(default_params, config_params, {})
    except ConfigError as exc:
        typer.echo(f"Failed to load config: {exc}", err=True)
        raise typer.Exit(code=1)
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
    meta_obj = build_meta(
        Path(input_path),
        workdir,
        params,
        deps_report,
        probe_obj,
        errors,
        actual_audio=None,
        params_sources=params_sources,
        planned=True,
    )

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
