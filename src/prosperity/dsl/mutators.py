from __future__ import annotations

import copy
import random

from prosperity.dsl.schema import ParameterDef, StrategySpec


def _find_parameter(spec: StrategySpec, name: str) -> ParameterDef | None:
    for parameter in spec.parameter_space:
        if parameter.name == name:
            return parameter
    return None


def _shift_parameter(spec: StrategySpec, name: str, direction: str, strength: float = 1.0) -> None:
    parameter = _find_parameter(spec, name)
    if parameter is None:
        return
    span = parameter.upper - parameter.lower
    delta = span * parameter.mutation_scale * strength
    sign = 1.0 if direction == "up" else -1.0
    parameter.default = max(
        parameter.lower,
        min(parameter.upper, parameter.default + sign * delta),
    )


def jitter_parameters(spec: StrategySpec, seed: int | None = None) -> StrategySpec:
    rng = random.Random(seed)
    mutated = copy.deepcopy(spec)
    for parameter in mutated.parameter_space:
        span = parameter.upper - parameter.lower
        delta = span * parameter.mutation_scale
        parameter.default = max(
            parameter.lower,
            min(parameter.upper, parameter.default + rng.uniform(-delta, delta)),
        )
    mutated.metadata.parent_ids = list(dict.fromkeys(mutated.metadata.parent_ids + [spec.metadata.id]))
    mutated.metadata.id = f"{spec.metadata.id}-mut"
    mutated.metadata.name = f"{spec.metadata.name} mutation"
    return mutated


def simplify_spec(spec: StrategySpec) -> StrategySpec:
    mutated = copy.deepcopy(spec)
    if len(mutated.signal_models) > 1:
        mutated.signal_models = mutated.signal_models[:1]
    if len(mutated.execution_policy.market_making.layers) > 2:
        mutated.execution_policy.market_making.layers = mutated.execution_policy.market_making.layers[:2]
    mutated.metadata.id = f"{spec.metadata.id}-simple"
    mutated.metadata.name = f"{spec.metadata.name} simplified"
    mutated.metadata.parent_ids = list(dict.fromkeys(mutated.metadata.parent_ids + [spec.metadata.id]))
    return mutated


def apply_structural_profile(spec: StrategySpec, profile: str) -> StrategySpec:
    mutated = copy.deepcopy(spec)
    profile_name = profile.lower()

    if profile_name == "low_turnover":
        for name, direction, strength in [
            ("tomato_filter_volume", "up", 1.8),
            ("tomato_take_width", "up", 1.2),
            ("take_extra", "up", 1.2),
            ("quote_aggression", "down", 1.4),
            ("fair_alpha_scale", "down", 0.9),
            ("clear_width", "up", 0.8),
        ]:
            _shift_parameter(mutated, name, direction, strength)
        mutated.execution_policy.taking.min_edge += 0.5
        mutated.execution_policy.taking.max_size = max(4, int(mutated.execution_policy.taking.max_size * 0.8))
    elif profile_name == "inventory_hardening":
        for name, direction, strength in [
            ("inventory_skew", "up", 1.5),
            ("clear_width", "up", 1.0),
            ("take_extra", "up", 0.8),
            ("quote_aggression", "down", 0.8),
        ]:
            _shift_parameter(mutated, name, direction, strength)
        mutated.risk_policy.dynamic_inventory_aversion += 0.15
        mutated.execution_policy.market_making.inventory_skew += 0.15
    elif profile_name == "signal_rotation":
        for name, direction, strength in [
            ("second_imb_weight", "down", 1.2),
            ("gap_weight", "up", 1.2),
            ("ret1_weight", "up", 1.0),
            ("micro_weight", "up", 0.8),
            ("ret3_weight", "up", 1.0),
        ]:
            _shift_parameter(mutated, name, direction, strength)
        if len(mutated.signal_models) > 1:
            mutated.signal_models = mutated.signal_models[1:] + mutated.signal_models[:1]
    elif profile_name == "aggressive_repricing":
        for name, direction, strength in [
            ("tomato_filter_volume", "down", 1.6),
            ("tomato_take_width", "down", 1.4),
            ("quote_aggression", "up", 1.2),
            ("fair_alpha_scale", "up", 1.1),
            ("take_extra", "down", 1.2),
        ]:
            _shift_parameter(mutated, name, direction, strength)
        mutated.execution_policy.taking.max_size = max(8, int(mutated.execution_policy.taking.max_size * 1.1))
    else:
        return simplify_spec(mutated)

    mutated.metadata.id = f"{spec.metadata.id}-{profile_name}"
    mutated.metadata.name = f"{spec.metadata.name} {profile_name}"
    mutated.metadata.parent_ids = list(dict.fromkeys(mutated.metadata.parent_ids + [spec.metadata.id]))
    mutated.metadata.created_by_role = "structural_mutator"
    return mutated
