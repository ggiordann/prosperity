from __future__ import annotations

from prosperity.dsl.schema import StrategySpec


def critique_spec(spec: StrategySpec) -> dict:
    complexity = len(spec.fair_value_models) + len(spec.signal_models) + len(spec.execution_policy.market_making.layers)
    notes = []
    if complexity > 8:
        notes.append("Strategy is relatively complex and may be harder to debug.")
    if spec.explainability.crowded_motif_references:
        notes.append(f"Crowded motifs present: {', '.join(spec.explainability.crowded_motif_references)}")
    if spec.execution_policy.taking.max_size > spec.risk_policy.max_aggressive_size:
        notes.append("Taking max size exceeds risk max aggressive size.")
    return {
        "complexity": complexity,
        "notes": notes,
        "summary": " ".join(notes) if notes else "No major structural red flags detected.",
    }
