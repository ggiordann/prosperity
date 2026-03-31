from __future__ import annotations

from prosperity.generation.expert_builder import build_expert_candidates
from prosperity.generation.family_registry import build_family_spec


def test_build_expert_candidates_creates_codex_families():
    champion = build_family_spec("tutorial_submission_candidate_alpha", role="test")
    alternate = build_family_spec("tutorial_pressure_momentum", role="test")
    champion_entry = {
        "strategy_id": champion.metadata.id,
        "family": champion.metadata.family,
        "spec": champion,
    }
    frontier_entries = [
        champion_entry,
        {
            "strategy_id": alternate.metadata.id,
            "family": alternate.metadata.family,
            "spec": alternate,
        },
    ]
    candidates = build_expert_candidates(
        champion_entry,
        frontier_entries,
        memory_notes=[{"content": "plateau and slippage in passive queue fills"}],
        iteration=7,
        count=3,
        plateau_mode=True,
    )
    assert len(candidates) == 3
    assert all(candidate["bucket"] == "expert_builder" for candidate in candidates)
    assert all(candidate["spec"].metadata.family.startswith("codex_") for candidate in candidates)
    assert any(candidate["spec"].metadata.family == "codex_frontier_splice_engine" for candidate in candidates)
