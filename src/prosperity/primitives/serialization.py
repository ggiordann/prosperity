from __future__ import annotations

import json
from typing import Any


def load_state(trader_data: str) -> dict[str, Any]:
    if not trader_data:
        return {}
    try:
        payload = json.loads(trader_data)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def dump_state(state: dict[str, Any]) -> str:
    return json.dumps(state, separators=(",", ":"))
