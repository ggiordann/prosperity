from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType

from prosperity.utils import ensure_dir, utcnow_iso

fcntl: ModuleType | None
try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


def _write_lock_metadata(path: Path, handle) -> None:
    payload = {
        "pid": os.getpid(),
        "path": str(path),
        "acquired_at": utcnow_iso(),
    }
    handle.seek(0)
    handle.truncate()
    handle.write(json.dumps(payload, sort_keys=True))
    handle.flush()


@contextmanager
def file_lock(path: Path):
    ensure_dir(path.parent)
    if fcntl is None:  # pragma: no cover
        try:
            with path.open("x", encoding="utf-8") as handle:
                _write_lock_metadata(path, handle)
        except FileExistsError as exc:
            raise RuntimeError(f"Lock already held: {path}") from exc
        try:
            yield
        finally:
            if path.exists():
                path.unlink()
        return

    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Lock already held: {path}") from exc
        _write_lock_metadata(path, handle)
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            path.unlink(missing_ok=True)
