import json
import shutil
import subprocess
from pathlib import Path

import pytest

from onepass_audioclean_ingest.batch import compute_work_id, safe_stem


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required to generate input")


def _generate_input_wav(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.5",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_dry_run_batch_writes_plan_manifest(tmp_path: Path) -> None:
    require_ffmpeg()

    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    files = [input_dir / "a.wav", input_dir / "b.wav"]
    for f in files:
        _generate_input_wav(f)

    out_root = tmp_path / "out_root"
    result = subprocess.run(
        ["onepass-ingest", "ingest", str(input_dir), "--out-root", str(out_root), "--dry-run"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    manifest_path = out_root / "manifest.plan.jsonl"
    assert manifest_path.exists()
    lines = manifest_path.read_text().strip().splitlines()
    assert len(lines) == len(files)

    for line, source in zip(lines, files):
        record = json.loads(line)
        assert record["status"] == "planned"
        assert record["schema_version"] == "manifest.plan.v1"
        work_key, work_id = compute_work_id(source, input_root=input_dir, size_bytes=source.stat().st_size)
        expected_workdir = out_root / f"{safe_stem(source.stem)}__{work_id}"
        assert record["output"]["workdir"] == str(expected_workdir)
        audio_path = Path(record["output"]["audio_wav"])
        assert not audio_path.exists()
