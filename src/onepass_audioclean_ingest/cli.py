"""Command-line interface for OnePass AudioClean ingest."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Optional

import typer

from .config import ConfigError, load_config
from .constants import DEFAULT_META_FILENAME
from .deps import check_deps, determine_exit_code
from .logging_utils import get_logger
from .meta import IngestParams, MetaError, build_meta, write_meta
from .probe import ffprobe_input

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
    config: Optional[str] = typer.Option(None, help="Path to config file"),
    output_root: Optional[str] = typer.Option(None, help="Root directory for outputs"),
) -> None:
    """Ingest and normalize audio inputs. R1 placeholder only."""

    typer.echo("ingest: Not implemented in R1")
    if any([input_path, config, output_root]):
        logger.debug(
            "Arguments provided but unused in R1: input=%s, config=%s, output_root=%s",
            input_path,
            config,
            output_root,
        )


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

    probe_obj = {"input_ffprobe": probe_result.input_ffprobe, "warnings": probe_result.warnings}
    meta_obj = build_meta(Path(input_path), workdir, params, deps_report, probe_obj, errors)

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
