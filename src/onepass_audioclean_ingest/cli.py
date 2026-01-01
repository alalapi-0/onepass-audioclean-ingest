"""Command-line interface for OnePass AudioClean ingest."""
from __future__ import annotations

import sys
from typing import Optional

import typer

from . import __version__
from .logging_utils import get_logger

app = typer.Typer(help="OnePass AudioClean ingest CLI (R1 placeholder)")
logger = get_logger(__name__)


@app.command("check-deps")
def check_deps(config: Optional[str] = typer.Option(None, help="Path to config file")) -> None:
    """Check local dependencies (ffmpeg/ffprobe). R1 placeholder only."""

    typer.echo("check-deps: Not implemented in R1")
    if config:
        logger.debug("Config path provided but unused in R1: %s", config)


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


def main(argv: Optional[list[str]] = None) -> int:
    """Entrypoint for console script."""

    argv = argv if argv is not None else sys.argv[1:]
    app(prog_name="onepass-ingest", args=list(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
