import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from onepass_audioclean_ingest.cli import app
from onepass_audioclean_ingest.constants import DEFAULT_META_FILENAME
from onepass_audioclean_ingest.subprocess_utils import run_cmd


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not available")
@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="ffprobe not available")
def test_probe_fields_present(tmp_path: Path) -> None:
    input_path = tmp_path / "tone.mp3"
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
        "sine=frequency=440:duration=1",
        "-q:a",
        "9",
        str(input_path),
    ]
    result = run_cmd(cmd)
    assert result.returncode == 0

    runner = CliRunner()
    result = runner.invoke(app, ["meta", str(input_path), "--out", str(workdir)])
    assert result.exit_code == 0

    meta_path = workdir / DEFAULT_META_FILENAME
    with meta_path.open("r", encoding="utf-8") as f:
        meta = json.load(f)

    probe = meta.get("probe", {})
    ffprobe_info = probe.get("input_ffprobe")
    assert ffprobe_info is not None
    assert any(
        key in ffprobe_info and ffprobe_info.get(key) is not None
        for key in ("duration", "channels", "sample_rate")
    )
