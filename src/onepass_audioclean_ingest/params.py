"""Parameter handling utilities for ingest configuration merging."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import ConfigError, load_custom_config, load_default_config

NORMALIZE_MODE = "loudnorm_r7_v1"
NORMALIZE_FILTERGRAPH = "loudnorm=I=-16:LRA=11:TP=-1.5:linear=true:print_format=summary"
NORMALIZE_CONFIG: Dict[str, Any] = {
    "filtergraph": NORMALIZE_FILTERGRAPH,
    "mode": NORMALIZE_MODE,
    "notes": "Single-pass EBU R128 loudnorm with fixed parameters; no measurement pass.",
}


@dataclass
class IngestParams:
    """Normalized ingestion parameters used across meta generation."""

    sample_rate: int = 16000
    channels: int = 1
    bit_depth: int = 16
    normalize: bool = False
    normalize_mode: Optional[str] = None
    normalize_config: Optional[Dict[str, Any]] = None
    ffmpeg_extra_args: List[str] = field(default_factory=list)
    audio_stream_index: Optional[int] = None
    audio_language: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_rate": int(self.sample_rate),
            "channels": int(self.channels),
            "bit_depth": int(self.bit_depth),
            "normalize": bool(self.normalize),
            "normalize_mode": self.normalize_mode,
            "normalize_config": self.normalize_config,
            "ffmpeg_extra_args": list(self.ffmpeg_extra_args),
            "audio_stream_index": self.audio_stream_index,
            "audio_language": self.audio_language,
        }


def _params_from_dict(config: Dict[str, Any]) -> IngestParams:
    extra_args = config.get("ffmpeg_extra_args", [])
    if extra_args is None:
        extra_args = []
    return IngestParams(
        sample_rate=int(config.get("sample_rate", IngestParams.sample_rate)),
        channels=int(config.get("channels", IngestParams.channels)),
        bit_depth=int(config.get("bit_depth", IngestParams.bit_depth)),
        normalize=bool(config.get("normalize", IngestParams.normalize)),
        normalize_mode=config.get("normalize_mode"),
        normalize_config=config.get("normalize_config"),
        ffmpeg_extra_args=list(extra_args),
        audio_stream_index=config.get("audio_stream_index"),
        audio_language=config.get("audio_language"),
    )


def load_default_params() -> Tuple[IngestParams, Dict[str, str]]:
    """Load params from the default configuration file."""

    default_cfg = load_default_config()
    params = _params_from_dict(default_cfg)
    sources = {key: "default" for key in params.to_dict().keys()}
    return params, sources


def load_config_params(config_path: Optional[Path | str]) -> Optional[IngestParams]:
    """Load params from a user-provided config path if present."""

    if config_path is None:
        return None
    path_obj = Path(config_path)
    if not path_obj.exists():
        raise ConfigError(f"Config path does not exist: {path_obj}")
    override_cfg = load_custom_config(path_obj)
    if override_cfg is None:
        return None
    return _params_from_dict(override_cfg)


def merge_params(
    default_params: IngestParams,
    config_params: Optional[IngestParams],
    cli_overrides: Dict[str, Any],
) -> Tuple[IngestParams, Dict[str, str]]:
    """Merge params with precedence cli > config > default, tracking sources."""

    merged = IngestParams()
    sources: Dict[str, str] = {}
    sentinel = object()
    for field_name in merged.to_dict().keys():
        cli_value = cli_overrides.get(field_name, sentinel)
        if cli_value is not sentinel:
            value = cli_value
            source = "cli"
        elif config_params is not None and getattr(config_params, field_name) is not None:
            value = getattr(config_params, field_name)
            source = "config"
        else:
            value = getattr(default_params, field_name)
            source = "default"
        setattr(merged, field_name, value)
        sources[field_name] = source

    if merged.normalize:
        merged.normalize_mode = NORMALIZE_MODE
        merged.normalize_config = NORMALIZE_CONFIG
        sources["normalize_mode"] = sources.get("normalize", "default")
        sources["normalize_config"] = sources.get("normalize", "default")
    else:
        merged.normalize_mode = None
        merged.normalize_config = None
        sources["normalize_mode"] = sources.get("normalize_mode", sources.get("normalize", "default"))
        sources["normalize_config"] = sources.get("normalize_config", sources.get("normalize", "default"))

    return merged, sources


def params_digest(params: IngestParams) -> str:
    serialized = json.dumps(params.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
