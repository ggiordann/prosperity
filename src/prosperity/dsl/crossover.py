from __future__ import annotations

import copy

from prosperity.dsl.schema import StrategySpec


def crossover_specs(left: StrategySpec, right: StrategySpec) -> StrategySpec:
    child = copy.deepcopy(left)
    child.metadata.id = f"{left.metadata.id[:8]}-{right.metadata.id[:8]}-x"
    child.metadata.name = f"{left.metadata.name} x {right.metadata.name}"
    child.metadata.parent_ids = [left.metadata.id, right.metadata.id]
    child.fair_value_models = copy.deepcopy(left.fair_value_models)
    child.signal_models = copy.deepcopy(right.signal_models)
    child.execution_policy = copy.deepcopy(right.execution_policy)
    child.risk_policy = copy.deepcopy(left.risk_policy)
    return child
