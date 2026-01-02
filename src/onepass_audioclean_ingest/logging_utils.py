"""Logging utilities for OnePass AudioClean ingest."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


_LOGGER_SETUP = False
_ROOT_LOGGER_NAME = "onepass_audioclean_ingest"


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None) -> logging.Logger:
    """Setup root logger with console and optional file handlers.

    Parameters
    ----------
    verbose: bool
        If True, set level to DEBUG; otherwise INFO.
    log_file: Optional[Path]
        If provided, add a file handler to write logs to this path.

    Returns
    -------
    logging.Logger
        Root logger instance.
    """
    global _LOGGER_SETUP

    root_logger = logging.getLogger(_ROOT_LOGGER_NAME)
    root_logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Clear existing handlers if reconfiguring
    if _LOGGER_SETUP:
        root_logger.handlers.clear()

    # Console handler (always present)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # File handler (if log_file provided)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # File always gets DEBUG level
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    root_logger.propagate = False
    _LOGGER_SETUP = True
    return root_logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger.

    If logging has not been setup, creates a basic console logger.
    Otherwise, returns a child logger of the root logger.

    Parameters
    ----------
    name: Optional[str]
        Logger name; defaults to module name when ``None``.
        If name starts with _ROOT_LOGGER_NAME, it becomes a child logger.

    Returns
    -------
    logging.Logger
        Logger instance with basic configuration applied.
    """
    if not _LOGGER_SETUP:
        # Fallback: create a basic logger if setup_logging hasn't been called
        logger = logging.getLogger(name or _ROOT_LOGGER_NAME)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        return logger

    # Use root logger or create child logger
    if name is None:
        return logging.getLogger(_ROOT_LOGGER_NAME)

    # If name starts with root logger name, use it as-is; otherwise make it a child
    if name.startswith(_ROOT_LOGGER_NAME):
        return logging.getLogger(name)

    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
