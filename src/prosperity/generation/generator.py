from __future__ import annotations

from prosperity.generation.anti_consensus import select_underexplored_family
from prosperity.generation.family_registry import FAMILY_BUILDERS


def generate_candidate_specs(
    existing_families: list[str],
    crowded_motifs: list[str] | None = None,
    count: int = 2,
) -> list:
    crowded = crowded_motifs or []
    families = list(FAMILY_BUILDERS.keys())
    selected = []
    for index in range(count):
        family = families[index] if index < len(families) else select_underexplored_family(existing_families, crowded)
        selected.append(FAMILY_BUILDERS[family]())
    return selected
