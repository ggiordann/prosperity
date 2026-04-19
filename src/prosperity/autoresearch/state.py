from __future__ import annotations

from pathlib import Path

from prosperity.autoresearch.models import AutoResearchState
from prosperity.utils import json_dumps


def load_autoresearch_state(path: Path) -> AutoResearchState:
    if not path.exists():
        return AutoResearchState()
    return AutoResearchState.model_validate_json(path.read_text(encoding="utf-8"))


def save_autoresearch_state(path: Path, state: AutoResearchState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(state.model_dump(mode="json")), encoding="utf-8")

