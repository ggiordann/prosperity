from __future__ import annotations

from typing import Callable

from prosperity.dsl.schema import StrategySpec
from prosperity.generation.anti_consensus import select_underexplored_family
from prosperity.generation.family_registry import FAMILY_BUILDERS


def generate_candidate_specs(
    existing_families: list[str],
    crowded_motifs: list[str] | None = None,
    count: int = 2,
) -> list[StrategySpec]:
    crowded = crowded_motifs or []
    families = list(FAMILY_BUILDERS.keys())
    selected: list[StrategySpec] = []
    for index in range(count):
        family = families[index] if index < len(families) else select_underexplored_family(existing_families, crowded)
        builder: Callable[..., StrategySpec] = FAMILY_BUILDERS[family]
        selected.append(builder())
    return selected
