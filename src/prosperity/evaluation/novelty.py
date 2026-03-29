from __future__ import annotations

from prosperity.evaluation.similarity import spec_similarity


def novelty_score(candidate_spec, prior_specs: list, behavior_similarity_scores: list[float]) -> float:
    spec_novelty = 1.0
    if prior_specs:
        spec_novelty = 1.0 - max(spec_similarity(candidate_spec, prior) for prior in prior_specs)
    behavior_novelty = 1.0 - max(behavior_similarity_scores, default=0.0)
    return max(0.0, min(1.0, 0.5 * spec_novelty + 0.5 * behavior_novelty))
