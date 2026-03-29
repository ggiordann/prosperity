from __future__ import annotations

import json

from prosperity.dsl.schema import StrategySpec


def normalize_spec(spec: StrategySpec) -> dict:
    payload = spec.model_dump(mode="json")
    payload["fair_value_models"] = sorted(
        payload["fair_value_models"], key=lambda item: (item["kind"], item.get("weight", 0.0))
    )
    payload["signal_models"] = sorted(
        payload["signal_models"], key=lambda item: (item["kind"], item["name"])
    )
    return payload


def normalized_spec_json(spec: StrategySpec) -> str:
    return json.dumps(normalize_spec(spec), sort_keys=True, separators=(",", ":"))
