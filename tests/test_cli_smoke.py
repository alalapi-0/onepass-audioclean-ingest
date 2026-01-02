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
    result = subprocess.run(
        ["python", "-m", "onepass_audioclean_ingest.cli", "check-deps", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode in {0, 2, 3, 4}
    assert result.stdout

    ingest_result = subprocess.run(
        ["python", "-m", "onepass_audioclean_ingest.cli", "ingest"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert ingest_result.returncode == 0
    assert "Not implemented" in ingest_result.stdout
