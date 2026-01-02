"""Utilities for running subprocess commands with consistent decoding."""
from __future__ import annotations

from dataclasses import dataclass
import subprocess
import time
from typing import List


@dataclass
class CmdResult:
    """Normalized result of a subprocess invocation."""

    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int


class CommandTimeout(RuntimeError):
    """Raised when a subprocess exceeds the allowed timeout."""

    def __init__(self, cmd: List[str], timeout_sec: int, duration_ms: int) -> None:
        message = f"Command timed out after {timeout_sec}s: {' '.join(cmd)}"
        super().__init__(message)
        self.cmd = cmd
        self.timeout_sec = timeout_sec
        self.duration_ms = duration_ms


def run_cmd(cmd: List[str], timeout_sec: int = 30) -> CmdResult:
    """Run a command and return a normalized :class:`CmdResult`.

    Text output is decoded as UTF-8 with replacement to handle locale differences.
    A timeout raises :class:`CommandTimeout` so callers can map it to domain errors.
    """

    start = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout_sec,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        return CmdResult(
            cmd=list(cmd),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired:
        duration_ms = int((time.monotonic() - start) * 1000)
        raise CommandTimeout(list(cmd), timeout_sec=timeout_sec, duration_ms=duration_ms)
