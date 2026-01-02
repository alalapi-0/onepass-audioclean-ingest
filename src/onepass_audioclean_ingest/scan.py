"""Input directory scanner for batch ingest."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Set


IGNORED_NAMES = {"__MACOSX", ".DS_Store"}


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _should_ignore(path: Path) -> bool:
    name = path.name
    return name in IGNORED_NAMES or _is_hidden(path)


def _ext_set(exts: Iterable[str]) -> Set[str]:
    return {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in exts}


def scan_inputs(root: Path, recursive: bool, exts: Set[str]) -> List[Path]:
    """Collect input files under ``root`` following stability rules."""

    normalized_exts = _ext_set(exts)
    root = root.resolve()
    inputs: List[Path] = []

    if recursive:
        iterator = root.rglob("*")
    else:
        iterator = root.glob("*")

    for path in iterator:
        if path.is_dir():
            if _should_ignore(path):
                continue
            continue
        if _should_ignore(path):
            continue
        if not path.suffix:
            continue
        if path.suffix.lower() not in normalized_exts:
            continue
        inputs.append(path)

    inputs.sort(key=lambda p: str(p.relative_to(root).as_posix()))
    return inputs

