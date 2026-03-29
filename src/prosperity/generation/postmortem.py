from __future__ import annotations

from prosperity.dsl.schema import StrategySpec


def write_postmortem(spec: StrategySpec, failure_reason: str, stage: str) -> str:
    return (
        f"# Postmortem: {spec.metadata.name}\n\n"
        f"- Strategy id: `{spec.metadata.id}`\n"
        f"- Stage: `{stage}`\n"
        f"- Failure reason: {failure_reason}\n"
        f"- Family: `{spec.metadata.family}`\n"
        f"- Expected edge: {spec.expected_edge.target_inefficiency}\n"
        f"- Next step: mutate parameters or simplify execution before retrying.\n"
    )
