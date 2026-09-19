"""Structured logging for AI-Trader."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"


def setup_logging(level: str = "INFO", log_file: str | Path | None = None) -> None:
    """Configure root logger with console + rotating file handlers."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    console = RichHandler(rich_tracebacks=True, show_time=True, markup=False)
    console.setLevel(level.upper())
    root.addHandler(console)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FORMAT))
        fh.setLevel(level.upper())
        root.addHandler(fh)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)