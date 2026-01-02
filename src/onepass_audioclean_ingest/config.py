"""Configuration loading utilities for OnePass AudioClean ingest."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"


class ConfigError(Exception):
    """Raised when configuration loading fails."""


def load_default_config() -> Dict[str, Any]:
    """Load the default ingestion configuration.

    Returns
    -------
    Dict[str, Any]
        Parsed configuration dictionary.

    Raises
    ------
    ConfigError
        If the default configuration file is missing or cannot be parsed.
    """

    if not DEFAULT_CONFIG_PATH.exists():
        raise ConfigError(f"Default config not found at {DEFAULT_CONFIG_PATH}")

    try:
        with DEFAULT_CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Failed to parse YAML: {exc}") from exc
    return config


def load_config(config_path: Path | None = None) -> Dict[str, Any]:
    """Load configuration from a provided path or the default path.

    Parameters
    ----------
    config_path : Path | None
        Optional path to a configuration file overriding the default.

    Returns
    -------
    Dict[str, Any]
        Parsed configuration dictionary.
    """

    path = config_path or DEFAULT_CONFIG_PATH
    if path != DEFAULT_CONFIG_PATH and not path.exists():
        raise ConfigError(f"Config path does not exist: {path}")

    base = load_default_config()
    if path == DEFAULT_CONFIG_PATH:
        return base

    override = _load_custom_config(path)
    merged = {**base, **(override or {})}
    return merged


def _load_custom_config(path: Path) -> Dict[str, Any]:
    """Load configuration from a custom path (YAML only for R1)."""

    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - defensive
        raise ConfigError(f"Failed to parse YAML: {exc}") from exc
