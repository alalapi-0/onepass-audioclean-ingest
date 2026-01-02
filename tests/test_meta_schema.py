import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from onepass_audioclean_ingest.cli import app
from onepass_audioclean_ingest.constants import DEFAULT_META_FILENAME
from onepass_audioclean_ingest.subprocess_utils import run_cmd


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")
def test_meta_command_generates_schema(tmp_path: Path) -> None:
    input_path = tmp_path / "tone.wav"
    workdir = tmp_path / "work"

    cmd = [
        shutil.which("ffmpeg"),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=1000:duration=1",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(input_path),
    ]
    result = run_cmd(cmd)
    assert result.returncode == 0

    runner = CliRunner()
    result = runner.invoke(app, ["meta", str(input_path), "--out", str(workdir)])
    assert result.exit_code == 0

    meta_path = workdir / DEFAULT_META_FILENAME
    assert meta_path.exists()

    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta.get("schema_version") == "meta.v1"
    assert "params" in meta
    assert "output" in meta
    assert "errors" in meta
    assert "stable_fields" in meta
