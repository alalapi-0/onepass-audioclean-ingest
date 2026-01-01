"""Smoke tests for the CLI."""
from __future__ import annotations

import subprocess


def test_cli_help() -> None:
    result = subprocess.run(
        ["python", "-m", "onepass_audioclean_ingest.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "OnePass AudioClean ingest" in result.stdout


def test_cli_subcommands() -> None:
    for command in (["check-deps"], ["ingest"]):
        result = subprocess.run(
            ["python", "-m", "onepass_audioclean_ingest.cli", *command],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Not implemented in R1" in result.stdout
