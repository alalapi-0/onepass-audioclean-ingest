"""Audio conversion helpers for ingest."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import shutil
from pathlib import Path
from typing import List, Optional

from .meta import IngestParams
from .subprocess_utils import CmdResult, CommandTimeout, run_cmd


@dataclass
class ConvertResult:
    """Structured result of an ffmpeg conversion."""

    cmd: List[str]
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    output_size_bytes: Optional[int]


def _write_log(log_path: Path, input_path: Path, output_path: Path, cmd: List[str], result: CmdResult) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"timestamp: {datetime.utcnow().isoformat()}Z\n")
        handle.write(f"input: {input_path}\n")
        handle.write(f"output: {output_path}\n")
        handle.write("command:\n")
        handle.write("  " + " ".join(cmd) + "\n")
        handle.write("stdout:\n")
        handle.write(result.stdout)
        if not result.stdout.endswith("\n"):
            handle.write("\n")
        handle.write("stderr:\n")
        handle.write(result.stderr)
        if not result.stderr.endswith("\n"):
            handle.write("\n")


def convert_audio_to_wav(
    input_path: Path,
    output_wav: Path,
    params: IngestParams,
    log_path: Path,
    ffmpeg_path: Optional[str],
    overwrite: bool,
    audio_stream_index: Optional[int] = None,
) -> ConvertResult:
    """Convert an input audio file to deterministic PCM s16le WAV.

    The command aims to maximize reproducibility by disabling metadata,
    using bitexact flags and fixing sample rate/channels/bit depth.
    """

    ffmpeg_bin = ffmpeg_path or shutil.which("ffmpeg") or "ffmpeg"
    cmd: List[str] = [ffmpeg_bin, "-hide_banner"]
    cmd.append("-y" if overwrite else "-n")
    cmd.extend(["-i", str(input_path)])

    if audio_stream_index is not None:
        cmd.extend(["-map", f"0:{audio_stream_index}"])

    cmd.extend(["-vn", "-ar", str(params.sample_rate), "-ac", str(params.channels)])

    filtergraph = None
    if params.normalize:
        filtergraph = params.normalize_mode or "loudnorm=I=-16:LRA=11:TP=-1.5"
        cmd.extend(["-af", filtergraph])

    cmd.extend(
        [
            "-c:a",
            "pcm_s16le",
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
        ]
    )

    if params.ffmpeg_extra_args:
        cmd.extend(params.ffmpeg_extra_args)

    cmd.append(str(output_wav))

    try:
        result = run_cmd(cmd, timeout_sec=180)
    except CommandTimeout as exc:
        timeout_result = CmdResult(cmd=list(exc.cmd), returncode=-1, stdout="", stderr=str(exc), duration_ms=exc.duration_ms)
        _write_log(log_path, input_path, output_wav, cmd, timeout_result)
        return ConvertResult(cmd=list(cmd), returncode=-1, stdout="", stderr=str(exc), duration_ms=exc.duration_ms, output_size_bytes=None)
    except OSError as exc:
        failed = CmdResult(cmd=list(cmd), returncode=-1, stdout="", stderr=str(exc), duration_ms=0)
        _write_log(log_path, input_path, output_wav, cmd, failed)
        return ConvertResult(cmd=list(cmd), returncode=-1, stdout="", stderr=str(exc), duration_ms=0, output_size_bytes=None)

    _write_log(log_path, input_path, output_wav, cmd, result)

    output_size = output_wav.stat().st_size if output_wav.exists() else None
    return ConvertResult(
        cmd=list(cmd),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
        output_size_bytes=output_size,
    )
