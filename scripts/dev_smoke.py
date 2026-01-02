#!/usr/bin/env python3
"""Quick smoke test for local development.

This script runs a minimal ingest workflow to verify the installation works.
It does not require network access and uses ffmpeg to generate test media.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from onepass_audioclean_ingest.subprocess_utils import run_cmd


def check_deps() -> bool:
    """Check if dependencies are available."""
    print("Checking dependencies...")
    result = subprocess.run(
        ["onepass-ingest", "check-deps", "--json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("ERROR: check-deps failed")
        print(result.stderr)
        return False

    try:
        report = json.loads(result.stdout)
        if not report.get("ok", False):
            print("WARNING: Dependencies check reported issues")
            for err in report.get("errors", []):
                print(f"  - {err.get('code')}: {err.get('message')}")
            return False
    except json.JSONDecodeError:
        print("ERROR: Failed to parse check-deps output")
        return False

    print("Dependencies OK")
    return True


def gen_test_audio(tmp_path: Path) -> Path:
    """Generate a 1-second test MP3 using ffmpeg."""
    print("Generating test audio...")
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        print("ERROR: ffmpeg not found")
        sys.exit(1)

    output_path = tmp_path / "smoke_test.mp3"
    cmd = [
        ffmpeg_path,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(output_path),
    ]

    result = run_cmd(cmd, timeout_sec=30)
    if result.returncode != 0:
        print(f"ERROR: Failed to generate test audio: {result.stderr}")
        sys.exit(1)

    print(f"Generated: {output_path}")
    return output_path


def run_ingest(input_path: Path, out_dir: Path) -> bool:
    """Run ingest on the test audio."""
    print("Running ingest...")
    out_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "onepass-ingest",
            "ingest",
            str(input_path),
            "--out",
            str(out_dir),
            "--no-normalize",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"ERROR: Ingest failed: {result.stderr}")
        return False

    print(f"Ingest completed: {out_dir}")
    return True


def print_summary(out_dir: Path) -> None:
    """Print summary of generated files."""
    print("\n=== Summary ===")
    meta_path = out_dir / "meta.json"
    audio_path = out_dir / "audio.wav"

    if meta_path.exists():
        with meta_path.open("r", encoding="utf-8") as f:
            meta = json.load(f)
        print(f"meta.json: {meta_path}")
        print(f"  schema_version: {meta.get('schema_version')}")
        print(f"  input.path: {meta.get('input', {}).get('path')}")
        print(f"  params.sample_rate: {meta.get('params', {}).get('sample_rate')}")
        print(f"  params.channels: {meta.get('params', {}).get('channels')}")
        print(f"  errors: {len(meta.get('errors', []))}")
        print(f"  warnings: {len(meta.get('warnings', []))}")
    else:
        print("WARNING: meta.json not found")

    if audio_path.exists():
        size = audio_path.stat().st_size
        print(f"audio.wav: {audio_path} ({size} bytes)")
    else:
        print("WARNING: audio.wav not found")

    print("\nOutput files:")
    for f in sorted(out_dir.iterdir()):
        if f.is_file():
            size = f.stat().st_size
            print(f"  {f.name} ({size} bytes)")


def main() -> int:
    """Main entry point."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        out_dir = Path("out") / "smoke_workdir"

        if not check_deps():
            return 1

        audio_path = gen_test_audio(tmp_path)

        if not run_ingest(audio_path, out_dir):
            return 1

        print_summary(out_dir)

    print("\nSmoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

