from __future__ import annotations

import copy
from typing import Any

from prosperity.dsl.schema import ParameterDef, StrategySpec
from prosperity.generation.family_registry import build_family_spec


def _find_parameter(spec: StrategySpec, name: str) -> ParameterDef | None:
    for parameter in spec.parameter_space:
        if parameter.name == name:
            return parameter
    return None


def _set_parameter(spec: StrategySpec, name: str, value: float) -> None:
    parameter = _find_parameter(spec, name)
    if parameter is None:
        return
    parameter.default = max(parameter.lower, min(parameter.upper, value))


def _shift_parameter(spec: StrategySpec, name: str, direction: str, strength: float = 1.0) -> None:
    parameter = _find_parameter(spec, name)
    if parameter is None:
        return
    span = parameter.upper - parameter.lower
    delta = span * parameter.mutation_scale * strength
    sign = 1.0 if direction == "up" else -1.0
    parameter.default = max(parameter.lower, min(parameter.upper, parameter.default + sign * delta))


def _apply_builder_variation(spec: StrategySpec, iteration: int, index: int) -> None:
    profiles = [
        ("reservation_bias", "up", 0.4),
        ("signal_scale", "up", 0.6),
        ("layer_offset_scale", "down", 0.4),
        ("layer_size_scale", "up", 0.4),
        ("taking_min_edge", "down", 0.4),
        ("inventory_skew", "up", 0.5),
    ]
    name, direction, strength = profiles[(iteration + index) % len(profiles)]
    _shift_parameter(spec, name, direction, strength)
    secondary = profiles[(iteration + index + 2) % len(profiles)]
    _shift_parameter(spec, secondary[0], secondary[1], secondary[2] * 0.6)


def _merge_parameter_spaces(left: list[ParameterDef], right: list[ParameterDef]) -> list[ParameterDef]:
    merged: dict[str, ParameterDef] = {}
    for parameter in left + right:
        merged[parameter.name] = copy.deepcopy(parameter)
    return list(merged.values())


def _blend_specs(
    base: StrategySpec,
    *,
    fair_from: StrategySpec | None = None,
    signal_from: StrategySpec | None = None,
    execution_from: StrategySpec | None = None,
    risk_from: StrategySpec | None = None,
    parameter_sources: list[StrategySpec] | None = None,
) -> StrategySpec:
    blended = copy.deepcopy(base)
    if fair_from is not None:
        blended.fair_value_models = copy.deepcopy(fair_from.fair_value_models)
    if signal_from is not None:
        blended.signal_models = copy.deepcopy(signal_from.signal_models)
    if execution_from is not None:
        blended.execution_policy = copy.deepcopy(execution_from.execution_policy)
    if risk_from is not None:
        blended.risk_policy = copy.deepcopy(risk_from.risk_policy)

    sources = [base]
    for source in parameter_sources or []:
        sources.append(source)
    merged = list(blended.parameter_space)
    for source in sources:
        merged = _merge_parameter_spaces(merged, source.parameter_space)
    blended.parameter_space = merged
    return blended


def _memory_text(memory_notes: list[dict[str, Any]]) -> str:
    return " ".join(str(note.get("content", "")) for note in memory_notes[:10]).lower()


def _alternate_frontier_specs(
    champion_entry: dict[str, Any],
    frontier_entries: list[dict[str, Any]],
) -> list[StrategySpec]:
    champion_id = champion_entry["strategy_id"]
    alternates: list[StrategySpec] = []
    for entry in frontier_entries:
        if entry["strategy_id"] == champion_id:
            continue
        spec = entry.get("spec")
        if isinstance(spec, StrategySpec):
            alternates.append(spec)
    return alternates


def _best_alternate_family(
    champion_entry: dict[str, Any],
    frontier_entries: list[dict[str, Any]],
    *,
    fallback_family: str,
) -> StrategySpec:
    for entry in frontier_entries:
        if entry["strategy_id"] == champion_entry["strategy_id"]:
            continue
        spec = entry.get("spec")
        if isinstance(spec, StrategySpec):
            return spec
    return build_family_spec(fallback_family, role="codex_expert_builder")


def _rename_candidate(
    spec: StrategySpec,
    *,
    family_name: str,
    profile: str,
    iteration: int,
    source_family: str,
    notes: str,
) -> StrategySpec:
    spec.metadata.family = family_name
    spec.metadata.name = f"Codex {profile.replace('_', ' ').title()} cycle {iteration}"
    spec.metadata.parent_ids = list(dict.fromkeys(spec.metadata.parent_ids))
    spec.metadata.created_by_role = "codex_expert_builder"
    spec.metadata.confidence_notes = (
        f"Codex-authored algorithm builder archetype `{profile}`. "
        f"Built from source family `{source_family}`. {notes}"
    )
    return spec


def _passive_alpha_barbell(
    champion_spec: StrategySpec,
    memory_text: str,
    iteration: int,
) -> StrategySpec:
    passive = build_family_spec("tutorial_passive_queue_reversion", role="codex_expert_builder")
    blended = _blend_specs(
        champion_spec,
        fair_from=champion_spec,
        signal_from=champion_spec,
        execution_from=passive,
        risk_from=passive,
        parameter_sources=[passive],
    )
    _shift_parameter(blended, "tomato_filter_volume", "up", 1.2)
    _shift_parameter(blended, "quote_aggression", "down", 1.3)
    _shift_parameter(blended, "take_extra", "up", 0.9)
    _shift_parameter(blended, "clear_width", "up", 0.8)
    _shift_parameter(blended, "inventory_skew", "up", 0.9)
    _shift_parameter(blended, "second_imb_weight", "up", 0.5)
    if "slippage" in memory_text or "fragile" in memory_text:
        _shift_parameter(blended, "taking_min_edge", "up", 0.7)
    return _rename_candidate(
        blended,
        family_name="codex_passive_alpha_barbell",
        profile="passive_alpha_barbell",
        iteration=iteration,
        source_family=champion_spec.metadata.family,
        notes="Keeps the champion alpha but forces a much more patient passive execution shell.",
    )


def _latent_gap_hybrid(
    champion_spec: StrategySpec,
    iteration: int,
) -> StrategySpec:
    latent = build_family_spec("tutorial_latent_book_reversion", role="codex_expert_builder")
    gap = build_family_spec("tutorial_gap_repricing", role="codex_expert_builder")
    blended = _blend_specs(
        latent,
        signal_from=gap,
        execution_from=champion_spec,
        risk_from=latent,
        parameter_sources=[champion_spec, gap],
    )
    _shift_parameter(blended, "gap_push_weight", "up", 0.8)
    _shift_parameter(blended, "lag2_fade_weight", "down", 0.5)
    _shift_parameter(blended, "taking_min_edge", "down", 0.3)
    _shift_parameter(blended, "signal_scale", "up", 0.5)
    return _rename_candidate(
        blended,
        family_name="codex_latent_gap_hybrid",
        profile="latent_gap_hybrid",
        iteration=iteration,
        source_family=champion_spec.metadata.family,
        notes="Combines a slower latent fair with gap repricing to push the search away from pure local alpha overlays.",
    )


def _guarded_momentum_breakout(
    champion_spec: StrategySpec,
    memory_text: str,
    iteration: int,
) -> StrategySpec:
    momentum = build_family_spec("tutorial_pressure_momentum", role="codex_expert_builder")
    passive = build_family_spec("tutorial_passive_queue_reversion", role="codex_expert_builder")
    blended = _blend_specs(
        momentum,
        fair_from=momentum,
        signal_from=momentum,
        execution_from=momentum,
        risk_from=passive,
        parameter_sources=[passive, champion_spec],
    )
    _shift_parameter(blended, "momentum_drive_weight", "up", 0.6)
    _shift_parameter(blended, "level_two_pressure_weight", "up", 0.4)
    _shift_parameter(blended, "taking_min_edge", "up", 0.8)
    _shift_parameter(blended, "taking_max_size", "down", 0.8)
    _shift_parameter(blended, "inventory_skew", "up", 0.6)
    if "drawdown" in memory_text or "inventory" in memory_text:
        _shift_parameter(blended, "clear_width", "up", 0.6)
    return _rename_candidate(
        blended,
        family_name="codex_guarded_momentum_breakout",
        profile="guarded_momentum_breakout",
        iteration=iteration,
        source_family=champion_spec.metadata.family,
        notes="Introduces a genuinely directional family but wraps it with tighter inventory discipline to avoid runaway trend chasing.",
    )


def _micro_queue_blend(
    champion_spec: StrategySpec,
    iteration: int,
) -> StrategySpec:
    micro = build_family_spec("tutorial_microprice_reversion", role="codex_expert_builder")
    passive = build_family_spec("tutorial_passive_queue_reversion", role="codex_expert_builder")
    blended = _blend_specs(
        micro,
        fair_from=micro,
        signal_from=micro,
        execution_from=passive,
        risk_from=champion_spec,
        parameter_sources=[champion_spec, passive],
    )
    _shift_parameter(blended, "micro_reversion_weight", "down", 0.6)
    _shift_parameter(blended, "lag1_fade_weight", "down", 0.4)
    _shift_parameter(blended, "taking_min_edge", "up", 0.9)
    _shift_parameter(blended, "quote_aggression", "down", 1.0)
    _shift_parameter(blended, "layer_offset_scale", "up", 0.5)
    return _rename_candidate(
        blended,
        family_name="codex_micro_queue_blend",
        profile="micro_queue_blend",
        iteration=iteration,
        source_family=champion_spec.metadata.family,
        notes="Pairs fast microprice reversion with slow queue-priority execution to create a different fill profile.",
    )


def _breakout_gap_barbell(
    champion_spec: StrategySpec,
    iteration: int,
) -> StrategySpec:
    gap = build_family_spec("tutorial_gap_repricing", role="codex_expert_builder")
    momentum = build_family_spec("tutorial_pressure_momentum", role="codex_expert_builder")
    blended = _blend_specs(
        gap,
        fair_from=gap,
        signal_from=gap,
        execution_from=momentum,
        risk_from=champion_spec,
        parameter_sources=[champion_spec, momentum],
    )
    _shift_parameter(blended, "gap_push_weight", "up", 0.9)
    _shift_parameter(blended, "lag2_fade_weight", "up", 0.3)
    _shift_parameter(blended, "micro_gap_weight", "down", 0.2)
    _shift_parameter(blended, "signal_scale", "up", 0.4)
    _shift_parameter(blended, "taking_min_edge", "down", 0.2)
    return _rename_candidate(
        blended,
        family_name="codex_breakout_gap_barbell",
        profile="breakout_gap_barbell",
        iteration=iteration,
        source_family=champion_spec.metadata.family,
        notes="Uses gap-driven asymmetry with a more one-sided breakout execution shell to test a non-consensus path.",
    )


def _frontier_splice_engine(
    champion_entry: dict[str, Any],
    frontier_entries: list[dict[str, Any]],
    memory_text: str,
    iteration: int,
) -> StrategySpec:
    champion_spec = champion_entry["spec"]
    alternate = _best_alternate_family(
        champion_entry,
        frontier_entries,
        fallback_family="tutorial_pressure_momentum",
    )
    blended = _blend_specs(
        champion_spec,
        fair_from=alternate,
        signal_from=alternate,
        execution_from=champion_spec,
        risk_from=champion_spec,
        parameter_sources=[alternate, champion_spec],
    )
    _shift_parameter(blended, "signal_scale", "up", 0.9)
    _shift_parameter(blended, "reservation_bias", "up", 0.5)
    _shift_parameter(blended, "layer_size_scale", "down", 0.4)
    _shift_parameter(blended, "taking_max_size", "up", 0.6)
    if "passive" in memory_text or "underperform" in memory_text:
        _shift_parameter(blended, "quote_aggression", "up", 0.8)
        _shift_parameter(blended, "taking_min_edge", "down", 0.4)
    if blended.execution_policy.market_making.params is not None:
        blended.execution_policy.market_making.params["style"] = "signal_skew"
    return _rename_candidate(
        blended,
        family_name="codex_frontier_splice_engine",
        profile="frontier_splice_engine",
        iteration=iteration,
        source_family=alternate.metadata.family,
        notes="Steals fair-value and signal identity from the best non-champion family while keeping a proven execution shell.",
    )


def _volatility_regime_hunter(
    champion_spec: StrategySpec,
    iteration: int,
) -> StrategySpec:
    momentum = build_family_spec("tutorial_pressure_momentum", role="codex_expert_builder")
    latent = build_family_spec("tutorial_latent_book_reversion", role="codex_expert_builder")
    blended = _blend_specs(
        latent,
        fair_from=latent,
        signal_from=momentum,
        execution_from=momentum,
        risk_from=latent,
        parameter_sources=[latent, momentum],
    )
    _set_parameter(blended, "reservation_bias", 0.35)
    _shift_parameter(blended, "signal_scale", "up", 1.0)
    _shift_parameter(blended, "taking_min_edge", "down", 0.5)
    _shift_parameter(blended, "taking_max_size", "up", 0.9)
    _shift_parameter(blended, "layer_offset_scale", "down", 0.3)
    _shift_parameter(blended, "layer_size_scale", "up", 0.4)
    if blended.execution_policy.taking.params is not None:
        blended.execution_policy.taking.params["style"] = "breakout"
    if blended.execution_policy.market_making.params is not None:
        blended.execution_policy.market_making.params["style"] = "one_sided"
    return _rename_candidate(
        blended,
        family_name="codex_volatility_regime_hunter",
        profile="volatility_regime_hunter",
        iteration=iteration,
        source_family=champion_spec.metadata.family,
        notes="Leans into volatility-gated directional bursts rather than defaulting to fade-heavy tutorial behavior.",
    )


def _asymmetric_repricing_engine(
    champion_spec: StrategySpec,
    frontier_entries: list[dict[str, Any]],
    iteration: int,
) -> StrategySpec:
    alternate = _best_alternate_family(
        {"strategy_id": champion_spec.metadata.id, "spec": champion_spec},
        frontier_entries,
        fallback_family="tutorial_gap_repricing",
    )
    gap = build_family_spec("tutorial_gap_repricing", role="codex_expert_builder")
    blended = _blend_specs(
        gap,
        fair_from=alternate,
        signal_from=gap,
        execution_from=alternate,
        risk_from=champion_spec,
        parameter_sources=[champion_spec, alternate, gap],
    )
    _set_parameter(blended, "reservation_bias", -0.15)
    _shift_parameter(blended, "gap_push_weight", "up", 1.1)
    _shift_parameter(blended, "signal_scale", "up", 0.8)
    _shift_parameter(blended, "quote_aggression", "up", 0.7)
    _shift_parameter(blended, "take_extra", "down", 0.7)
    _shift_parameter(blended, "layer_offset_scale", "down", 0.5)
    if blended.execution_policy.market_making.params is not None:
        blended.execution_policy.market_making.params["style"] = "signal_skew"
    return _rename_candidate(
        blended,
        family_name="codex_asymmetric_repricing_engine",
        profile="asymmetric_repricing_engine",
        iteration=iteration,
        source_family=alternate.metadata.family,
        notes="Pushes a more asymmetric repricing engine with stronger reservation-price skew and faster quote relocation.",
    )


def _inventory_pressure_rotor(
    champion_spec: StrategySpec,
    memory_text: str,
    iteration: int,
) -> StrategySpec:
    passive = build_family_spec("tutorial_passive_queue_reversion", role="codex_expert_builder")
    momentum = build_family_spec("tutorial_pressure_momentum", role="codex_expert_builder")
    blended = _blend_specs(
        champion_spec,
        fair_from=champion_spec,
        signal_from=momentum,
        execution_from=champion_spec,
        risk_from=passive,
        parameter_sources=[champion_spec, momentum, passive],
    )
    _shift_parameter(blended, "inventory_skew", "up", 1.4)
    _shift_parameter(blended, "clear_width", "up", 1.1)
    _shift_parameter(blended, "signal_scale", "up", 0.6)
    _shift_parameter(blended, "taking_max_size", "down", 0.4)
    _shift_parameter(blended, "layer_size_scale", "down", 0.5)
    if "stale" in memory_text or "queue" in memory_text:
        _shift_parameter(blended, "quote_aggression", "up", 0.5)
    return _rename_candidate(
        blended,
        family_name="codex_inventory_pressure_rotor",
        profile="inventory_pressure_rotor",
        iteration=iteration,
        source_family=champion_spec.metadata.family,
        notes="Rotates away from pure static inventory rules and makes inventory pressure itself part of the directional search.",
    )


def build_expert_candidates(
    champion_entry: dict[str, Any],
    frontier_entries: list[dict[str, Any]],
    memory_notes: list[dict[str, Any]],
    iteration: int,
    count: int,
    *,
    plateau_mode: bool = False,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    champion_spec = champion_entry["spec"]
    memory_text = _memory_text(memory_notes)
    alternate_specs = _alternate_frontier_specs(champion_entry, frontier_entries)
    builders = [
        lambda spec, notes, cycle: _frontier_splice_engine(champion_entry, frontier_entries, notes, cycle),
        lambda spec, notes, cycle: _volatility_regime_hunter(spec, cycle),
        lambda spec, notes, cycle: _asymmetric_repricing_engine(spec, frontier_entries, cycle),
        lambda spec, notes, cycle: _guarded_momentum_breakout(spec, notes, cycle),
        lambda spec, notes, cycle: _inventory_pressure_rotor(spec, notes, cycle),
        lambda spec, notes, cycle: _latent_gap_hybrid(spec, cycle),
        lambda spec, notes, cycle: _micro_queue_blend(spec, cycle),
        lambda spec, notes, cycle: _breakout_gap_barbell(spec, cycle),
        lambda spec, notes, cycle: _passive_alpha_barbell(spec, notes, cycle),
    ]
    if plateau_mode or alternate_specs:
        builders = [
            lambda spec, notes, cycle: _frontier_splice_engine(champion_entry, frontier_entries, notes, cycle),
            lambda spec, notes, cycle: _asymmetric_repricing_engine(spec, frontier_entries, cycle),
            lambda spec, notes, cycle: _volatility_regime_hunter(spec, cycle),
            lambda spec, notes, cycle: _guarded_momentum_breakout(spec, notes, cycle),
            lambda spec, notes, cycle: _breakout_gap_barbell(spec, cycle),
            lambda spec, notes, cycle: _inventory_pressure_rotor(spec, notes, cycle),
            lambda spec, notes, cycle: _latent_gap_hybrid(spec, cycle),
            lambda spec, notes, cycle: _micro_queue_blend(spec, cycle),
            lambda spec, notes, cycle: _passive_alpha_barbell(spec, notes, cycle),
        ]

    candidates: list[dict[str, Any]] = []
    rotation = iteration % len(builders)
    ordered_builders = builders[rotation:] + builders[:rotation]
    for index in range(min(count, len(ordered_builders))):
        builder = ordered_builders[index]
        spec = builder(champion_spec, memory_text, iteration)
        _apply_builder_variation(spec, iteration, index)
        spec.metadata.id = (
            f"{spec.metadata.family}-{champion_spec.metadata.id[-8:]}-c{iteration:03d}-x{index:02d}"
        )
        spec.metadata.parent_ids = list(dict.fromkeys(champion_spec.metadata.parent_ids + [champion_spec.metadata.id]))
        candidates.append(
            {
                "spec": spec,
                "bucket": "expert_builder",
                "origin_family": champion_spec.metadata.family,
                "origin_strategy_id": champion_spec.metadata.id,
                "profile": spec.metadata.family,
            }
        )
    return candidates
