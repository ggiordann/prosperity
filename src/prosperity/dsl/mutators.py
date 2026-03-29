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


def _merge_parameter_spaces(left: list[ParameterDef], right: list[ParameterDef]) -> list[ParameterDef]:
    merged: dict[str, ParameterDef] = {}
    for parameter in left + right:
        merged[parameter.name] = copy.deepcopy(parameter)
    return list(merged.values())


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


def family_component_mutation(spec: StrategySpec, target_family: str, component: str = "full_jump") -> StrategySpec:
    from prosperity.generation.family_registry import build_family_spec

    template = build_family_spec(target_family, role="family_mutator")
    mode = component.lower()

    if mode == "full_jump":
        mutated = copy.deepcopy(template)
        mutated.metadata.parent_ids = list(dict.fromkeys(spec.metadata.parent_ids + [spec.metadata.id]))
        mutated.metadata.confidence_notes = (
            f"Full family jump from {spec.metadata.family} into {target_family}."
        )
    else:
        mutated = copy.deepcopy(spec)
        if mode == "fair":
            mutated.fair_value_models = copy.deepcopy(template.fair_value_models)
        elif mode == "signal":
            mutated.signal_models = copy.deepcopy(template.signal_models)
        elif mode == "execution":
            mutated.execution_policy = copy.deepcopy(template.execution_policy)
        elif mode == "risk":
            mutated.risk_policy = copy.deepcopy(template.risk_policy)
        else:
            raise ValueError(f"Unsupported family mutation component: {component}")
        mutated.parameter_space = _merge_parameter_spaces(mutated.parameter_space, template.parameter_space)
        mutated.metadata.family = f"{spec.metadata.family}__{mode}__{target_family}"
        mutated.metadata.parent_ids = list(dict.fromkeys(spec.metadata.parent_ids + [spec.metadata.id]))
        mutated.metadata.confidence_notes = (
            f"Component swap `{mode}` from {target_family} into {spec.metadata.family}."
        )

    mutated.metadata.id = f"{spec.metadata.id}-{mode}-{target_family}"
    mutated.metadata.name = f"{spec.metadata.name} {mode} {target_family}"
    mutated.metadata.created_by_role = "family_mutator"
    return mutated
