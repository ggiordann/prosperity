from __future__ import annotations

from prosperity.dsl.normalization import normalized_spec_json
from prosperity.dsl.schema import StrategySpec
from prosperity.utils import sha256_text


def spec_hash(spec: StrategySpec) -> str:
    return sha256_text(normalized_spec_json(spec))
