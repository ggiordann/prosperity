from __future__ import annotations

from pathlib import Path

from prosperity.quant.models import QuantState
from prosperity.utils import json_dumps


def load_quant_state(path: Path) -> QuantState:
    if not path.exists():
        return QuantState()
    return QuantState.model_validate_json(path.read_text(encoding="utf-8"))


def save_quant_state(path: Path, state: QuantState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_dumps(state.model_dump(mode="json")), encoding="utf-8")

