from __future__ import annotations

from prosperity.dsl.mutators import jitter_parameters
from prosperity.evaluation.similarity import code_similarity, spec_similarity


def test_code_similarity_is_high_for_identical_code():
    code = "def f(x):\n    return x + 1\n"
    score = code_similarity(code, code)
    assert score["combined"] == 1.0


def test_spec_similarity_drops_for_mutated_spec(sample_spec):
    mutated = jitter_parameters(sample_spec, seed=3)
    assert spec_similarity(sample_spec, sample_spec) == 1.0
    assert spec_similarity(sample_spec, mutated) < 1.0
