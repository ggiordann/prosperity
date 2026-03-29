from __future__ import annotations

import json
from pathlib import Path

from prosperity.dsl.schema import StrategySpec
from prosperity.dsl.validators import validate_spec


def _load_template(template_path: Path) -> str:
    return template_path.read_text(encoding="utf-8")


def render_strategy_module(spec: StrategySpec, template_path: Path) -> str:
    errors = validate_spec(spec)
    if errors:
        raise ValueError(f"Invalid StrategySpec: {errors}")
    template = _load_template(template_path)
    return template.replace("__SPEC_JSON__", json.dumps(spec.model_dump(mode="json"), sort_keys=True))


def compile_strategy_module(spec: StrategySpec, output_path: Path, template_path: Path) -> Path:
    code = render_strategy_module(spec, template_path)
    output_path.write_text(code, encoding="utf-8")
    return output_path
