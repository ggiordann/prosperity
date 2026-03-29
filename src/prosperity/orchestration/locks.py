from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from prosperity.utils import ensure_dir


@contextmanager
def file_lock(path: Path):
    ensure_dir(path.parent)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write("locked")
    except FileExistsError as exc:
        raise RuntimeError(f"Lock already held: {path}") from exc
    try:
        yield
    finally:
        if path.exists():
            path.unlink()
