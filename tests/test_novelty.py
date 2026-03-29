from __future__ import annotations

from prosperity.dsl.mutators import jitter_parameters
from prosperity.evaluation.novelty import novelty_score


def test_novelty_score_reduces_when_behavior_and_spec_are_similar(sample_spec):
    mutated = jitter_parameters(sample_spec, seed=1)
    score = novelty_score(mutated, [sample_spec], behavior_similarity_scores=[0.9])
    assert 0.0 <= score < 0.5
