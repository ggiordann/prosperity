from __future__ import annotations

import copy
import random

from prosperity.dsl.schema import StrategySpec


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
