from __future__ import annotations

from prosperity.dsl.crossover import crossover_specs
from prosperity.dsl.mutators import jitter_parameters, simplify_spec
from prosperity.dsl.validators import validate_spec


def test_validate_spec_accepts_family_registry_spec(sample_spec):
    assert validate_spec(sample_spec) == []


def test_validate_spec_rejects_invalid_bounds(sample_spec):
    sample_spec.parameter_space[0].lower = 10
    sample_spec.parameter_space[0].upper = 5
    errors = validate_spec(sample_spec)
    assert any("Invalid bounds" in error for error in errors)


def test_jitter_parameters_tracks_parent_and_changes_id(sample_spec):
    mutated = jitter_parameters(sample_spec, seed=7)
    assert mutated.metadata.id.endswith("-mut")
    assert sample_spec.metadata.id in mutated.metadata.parent_ids


def test_simplify_spec_reduces_layers(sample_spec):
    simplified = simplify_spec(sample_spec)
    assert len(simplified.execution_policy.market_making.layers) <= 2
    assert sample_spec.metadata.id in simplified.metadata.parent_ids


def test_crossover_specs_combines_expected_sections(sample_spec):
    other = jitter_parameters(sample_spec, seed=9)
    child = crossover_specs(sample_spec, other)
    assert child.metadata.parent_ids == [sample_spec.metadata.id, other.metadata.id]
    assert child.signal_models == other.signal_models
    assert child.risk_policy == sample_spec.risk_policy
