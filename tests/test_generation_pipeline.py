from __future__ import annotations

from prosperity.generation.critic import critique_spec
from prosperity.generation.generator import generate_candidate_specs


def test_generate_candidate_specs_returns_requested_count():
    specs = generate_candidate_specs(existing_families=[], count=2)
    assert len(specs) == 2
    assert specs[0].metadata.id != specs[1].metadata.id


def test_critique_spec_returns_structured_notes(sample_spec):
    critique = critique_spec(sample_spec)
    assert "complexity" in critique
    assert "summary" in critique
