"""Logging utilities for OnePass AudioClean ingest."""
from __future__ import annotations

import logging
from typing import Optional


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger.

    Parameters
    ----------
    name: Optional[str]
        Logger name; defaults to module name when ``None``.

    Returns
    -------
    logging.Logger
        Logger instance with basic configuration applied.
    """

    logger = logging.getLogger(name)
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
