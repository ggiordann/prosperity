from __future__ import annotations

import logging
from pathlib import Path

from prosperity.utils import ensure_dir


def configure_logging(log_level: str = "INFO", log_dir: Path | None = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_dir is not None:
        ensure_dir(log_dir)
        handlers.append(logging.FileHandler(log_dir / "platform.log"))
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
