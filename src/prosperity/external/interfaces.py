from __future__ import annotations

from pathlib import Path
from typing import Protocol


class SubmissionAdapter(Protocol):
    def package(self, strategy_id: str, source_path: Path, metadata: dict, explanation: str) -> Path: ...
