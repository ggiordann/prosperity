from __future__ import annotations

from pathlib import Path

from prosperity.utils import ensure_dir, sha256_text


class PromptCache:
    def __init__(self, root: Path):
        self.root = ensure_dir(root)

    def _path(self, key: str) -> Path:
        return self.root / f"{sha256_text(key)}.json"

    def get(self, key: str) -> str | None:
        path = self._path(key)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def set(self, key: str, value: str) -> None:
        self._path(key).write_text(value, encoding="utf-8")
