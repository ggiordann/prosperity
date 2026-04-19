from __future__ import annotations

import re
from pathlib import Path

from prosperity.autoresearch.models import ExperimentRecipe
from prosperity.utils import sha256_text, slugify


def recipe_pool() -> list[ExperimentRecipe]:
    """Structural and parameter experiments the loop can run without touching the evaluator."""
    return [
        ExperimentRecipe(
            name="pepper_slope_gate_light",
            kind="structural",
            description="Stop adding pepper exposure when the learned drift is too weak.",
            changes={
                "constants": {
                    "PEPPER_HORIZON": 2200.0,
                    "PEPPER_TAKE_EDGE": 6,
                    "PEPPER_PASSIVE_SIZE": 48,
                    "PEPPER_REVERSION_WEIGHT": 0.035,
                },
                "slope_gate": 0.00018,
            },
        ),
        ExperimentRecipe(
            name="pepper_slope_gate_strict",
            kind="structural",
            description="Require a stronger positive drift before pepper accumulation.",
            changes={
                "constants": {
                    "PEPPER_HORIZON": 1500.0,
                    "PEPPER_TAKE_EDGE": 4,
                    "PEPPER_PASSIVE_SIZE": 32,
                    "PEPPER_REVERSION_WEIGHT": 0.050,
                },
                "slope_gate": 0.00035,
            },
        ),
        ExperimentRecipe(
            name="pepper_position_cap_40",
            kind="risk_structure",
            description="Cut max pepper inventory so public-trend dependence cannot dominate.",
            changes={
                "constants": {
                    "PEPPER_HORIZON": 1800.0,
                    "PEPPER_TAKE_EDGE": 5,
                    "PEPPER_PASSIVE_SIZE": 40,
                    "PEPPER_REVERSION_WEIGHT": 0.055,
                },
                "pepper_cap": 40,
            },
        ),
        ExperimentRecipe(
            name="pepper_drawdown_guard",
            kind="structural",
            description="Track pepper peak mid and flatten when trend drawdown appears.",
            changes={
                "constants": {
                    "PEPPER_HORIZON": 2600.0,
                    "PEPPER_TAKE_EDGE": 6,
                    "PEPPER_PASSIVE_SIZE": 40,
                    "PEPPER_REVERSION_WEIGHT": 0.040,
                },
                "drawdown_guard": 45.0,
            },
        ),
        ExperimentRecipe(
            name="ash_heavier_market_maker",
            kind="family_shift",
            description="Lean more on ash spread/reversion while reducing pepper fill dependence.",
            changes={
                "constants": {
                    "ASH_SKEW": 0.18,
                    "ASH_PASSIVE_SIZE": 64,
                    "ASH_LONG_MA_WEIGHT": 0.08,
                    "PEPPER_HORIZON": 1400.0,
                    "PEPPER_TAKE_EDGE": 3,
                    "PEPPER_PASSIVE_SIZE": 24,
                    "PEPPER_REVERSION_WEIGHT": 0.060,
                },
                "pepper_cap": 36,
            },
        ),
        ExperimentRecipe(
            name="pepper_reversion_dominant",
            kind="family_shift",
            description="Turn pepper from pure drift capture into slower trend plus reversion.",
            changes={
                "constants": {
                    "PEPPER_SLOPE_ALPHA": 0.18,
                    "PEPPER_HORIZON": 1200.0,
                    "PEPPER_TAKE_EDGE": 3,
                    "PEPPER_PASSIVE_SIZE": 28,
                    "PEPPER_REVERSION_WEIGHT": 0.085,
                },
                "slope_gate": 0.00012,
            },
        ),
        ExperimentRecipe(
            name="pepper_public_trend_ablation",
            kind="control",
            description="Ablate most pepper trend exposure to measure non-drift robustness.",
            changes={
                "constants": {
                    "PEPPER_HORIZON": 350.0,
                    "PEPPER_TAKE_EDGE": 1,
                    "PEPPER_PASSIVE_SIZE": 12,
                    "PEPPER_REVERSION_WEIGHT": 0.100,
                },
                "pepper_cap": 20,
            },
        ),
        ExperimentRecipe(
            name="ash_only_control",
            kind="control",
            description="Disable pepper and retain ash to expose how much score is public drift.",
            changes={
                "constants": {
                    "ASH_SKEW": 0.16,
                    "ASH_PASSIVE_SIZE": 64,
                    "PEPPER_HORIZON": 0.0,
                    "PEPPER_TAKE_EDGE": -9999,
                    "PEPPER_PASSIVE_SIZE": 0,
                },
                "pepper_cap": 0,
            },
        ),
    ]


def select_recipes(iteration: int, count: int) -> list[ExperimentRecipe]:
    pool = recipe_pool()
    if count <= 0:
        return []
    start = ((iteration - 1) * count) % len(pool)
    selected = [pool[(start + offset) % len(pool)] for offset in range(min(count, len(pool)))]
    if count <= len(selected):
        return selected
    extra = []
    for idx in range(count - len(selected)):
        base = pool[(start + idx) % len(pool)]
        extra.append(
            ExperimentRecipe(
                name=f"{base.name}_wide_{idx + 1}",
                kind=base.kind,
                description=f"Wider variant of {base.description}",
                changes=_widen_changes(base.changes, 1.0 + 0.08 * (idx + 1)),
            )
        )
    return [*selected, *extra]


def materialize_candidate(source: Path, target_dir: Path, recipe: ExperimentRecipe) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    text = source.read_text(encoding="utf-8")
    mutated = apply_recipe(text, recipe)
    digest = sha256_text(mutated)[:8]
    path = target_dir / f"{slugify(recipe.name)}-{digest}.py"
    path.write_text(mutated, encoding="utf-8")
    return path


def apply_recipe(text: str, recipe: ExperimentRecipe) -> str:
    out = text
    constants = recipe.changes.get("constants", {})
    if isinstance(constants, dict):
        for name, value in constants.items():
            out = _replace_constant(out, str(name), value)
    pepper_cap = recipe.changes.get("pepper_cap")
    if pepper_cap is not None:
        out = _apply_pepper_cap(out, int(pepper_cap))
    slope_gate = recipe.changes.get("slope_gate")
    if slope_gate is not None:
        out = _apply_slope_gate(out, float(slope_gate))
    drawdown_guard = recipe.changes.get("drawdown_guard")
    if drawdown_guard is not None:
        out = _apply_drawdown_guard(out, float(drawdown_guard))
    return _stamp_recipe(out, recipe)


def _replace_constant(text: str, name: str, value: object) -> str:
    formatted = repr(value)
    pattern = re.compile(rf"^(\s*{re.escape(name)}\s*:\s*[^=]+?=\s*).*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(rf"\g<1>{formatted}", text, count=1)
    return text


def _apply_pepper_cap(text: str, cap: int) -> str:
    text = _ensure_class_constant(text, "PEPPER_MAX_POSITION", cap)
    return text.replace(
        '        limit = self.POSITION_LIMITS[product]\n        position = state.position.get(product, 0)\n',
        '        limit = min(self.POSITION_LIMITS[product], self.PEPPER_MAX_POSITION)\n        position = state.position.get(product, 0)\n',
        1,
    )


def _apply_slope_gate(text: str, gate: float) -> str:
    text = _ensure_class_constant(text, "PEPPER_SLOPE_GATE", gate)
    needle = "        fair_value = trend_fair - reversion_drag\n"
    block = (
        "        fair_value = trend_fair - reversion_drag\n"
        "        if slope < self.PEPPER_SLOPE_GATE:\n"
        "            # Gate only pauses new exposure; liquidation is handled by separate risk recipes.\n"
        "            return orders\n"
    )
    if "PEPPER_SLOPE_GATE" in text and needle in text and "if slope < self.PEPPER_SLOPE_GATE" not in text:
        return text.replace(needle, block, 1)
    return text


def _apply_drawdown_guard(text: str, threshold: float) -> str:
    text = _ensure_class_constant(text, "PEPPER_DRAWDOWN_STOP", threshold)
    mid_needle = "        if mid is None:\n            return orders\n\n"
    mid_block = (
        "        if mid is None:\n"
        "            return orders\n"
        "        peak_mid = max(float(memory.get(\"pep_peak_mid\", mid)), mid)\n"
        "        memory[\"pep_peak_mid\"] = peak_mid\n\n"
    )
    if "pep_peak_mid" not in text and mid_needle in text:
        text = text.replace(mid_needle, mid_block, 1)
    fair_needle = "        fair_value = trend_fair - reversion_drag\n"
    fair_block = (
        "        fair_value = trend_fair - reversion_drag\n"
        "        if peak_mid - mid > self.PEPPER_DRAWDOWN_STOP:\n"
        "            if position > 0 and best_bid is not None:\n"
        "                qty = min(position, max(1, self.PEPPER_PASSIVE_SIZE))\n"
        "                orders.append(Order(product, best_bid, -qty))\n"
        "            return orders\n"
    )
    if "PEPPER_DRAWDOWN_STOP" in text and fair_needle in text and "peak_mid - mid > self.PEPPER_DRAWDOWN_STOP" not in text:
        text = text.replace(fair_needle, fair_block, 1)
    return text


def _ensure_class_constant(text: str, name: str, value: object) -> str:
    if re.search(rf"^\s*{re.escape(name)}\s*:", text, flags=re.MULTILINE):
        return _replace_constant(text, name, value)
    anchor = re.search(r"^(\s*PEPPER_REVERSION_WEIGHT\s*:\s*[^=]+?=\s*.*)$", text, flags=re.MULTILINE)
    if not anchor:
        return text
    annotation = "int" if isinstance(value, int) else "float"
    insert_at = anchor.end()
    return f"{text[:insert_at]}\n    {name}: {annotation} = {repr(value)}{text[insert_at:]}"


def _stamp_recipe(text: str, recipe: ExperimentRecipe) -> str:
    stamp = f"# autoresearch_recipe: {recipe.name} ({recipe.kind})\n"
    if "autoresearch_recipe:" in text:
        return text
    return f"{stamp}{text}"


def _widen_changes(changes: dict[str, object], factor: float) -> dict[str, object]:
    widened: dict[str, object] = {}
    for key, value in changes.items():
        if isinstance(value, dict):
            widened[key] = {
                nested_key: _scale_value(nested_value, factor)
                for nested_key, nested_value in value.items()
            }
        else:
            widened[key] = _scale_value(value, factor)
    return widened


def _scale_value(value: object, factor: float) -> object:
    if isinstance(value, float):
        return round(value * factor, 6)
    if isinstance(value, int):
        return max(0, int(round(value * factor)))
    return value
