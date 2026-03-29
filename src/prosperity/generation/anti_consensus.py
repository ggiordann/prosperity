from __future__ import annotations

from collections import Counter

from prosperity.generation.family_registry import FAMILY_BUILDERS


def select_underexplored_family(existing_families: list[str], crowded_motifs: list[str]) -> str:
    counts = Counter(existing_families)
    candidates = []
    for family in FAMILY_BUILDERS:
        penalty = counts.get(family, 0)
        if "wall_mid" in crowded_motifs and "wall_mid" in family:
            penalty += 2
        candidates.append((penalty, family))
    candidates.sort()
    return candidates[0][1]
