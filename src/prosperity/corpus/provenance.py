from __future__ import annotations

from typing import TypedDict

from prosperity.corpus.schemas import SourceMetadata, SourceType
from prosperity.utils import utcnow_iso


class PolicyConfig(TypedDict):
    trust_level: float
    allowed_for_codegen: bool
    allowed_for_mechanics: bool
    allowed_for_strategy_hypotheses: bool


DEFAULT_POLICY: dict[SourceType, PolicyConfig] = {
    SourceType.OFFICIAL_MECHANICS: dict(
        trust_level=1.0,
        allowed_for_codegen=True,
        allowed_for_mechanics=True,
        allowed_for_strategy_hypotheses=True,
    ),
    SourceType.INTERNAL_CODE: dict(
        trust_level=1.0,
        allowed_for_codegen=True,
        allowed_for_mechanics=True,
        allowed_for_strategy_hypotheses=True,
    ),
    SourceType.INTERNAL_RESULTS: dict(
        trust_level=1.0,
        allowed_for_codegen=True,
        allowed_for_mechanics=True,
        allowed_for_strategy_hypotheses=True,
    ),
    SourceType.PUBLIC_IDEA: dict(
        trust_level=0.45,
        allowed_for_codegen=False,
        allowed_for_mechanics=False,
        allowed_for_strategy_hypotheses=True,
    ),
    SourceType.PUBLIC_CODE_REFERENCE: dict(
        trust_level=0.20,
        allowed_for_codegen=False,
        allowed_for_mechanics=False,
        allowed_for_strategy_hypotheses=True,
    ),
    SourceType.MANUAL_NOTES: dict(
        trust_level=0.80,
        allowed_for_codegen=True,
        allowed_for_mechanics=True,
        allowed_for_strategy_hypotheses=True,
    ),
}


def build_metadata(source_type: SourceType, source_uri_or_path: str, **extra) -> SourceMetadata:
    policy = DEFAULT_POLICY[source_type]
    return SourceMetadata(
        source_type=source_type,
        source_uri_or_path=source_uri_or_path,
        fetched_at=utcnow_iso(),
        trust_level=policy["trust_level"],
        allowed_for_codegen=policy["allowed_for_codegen"],
        allowed_for_mechanics=policy["allowed_for_mechanics"],
        allowed_for_strategy_hypotheses=policy["allowed_for_strategy_hypotheses"],
        license_note=extra.pop("license_note", None),
        extra=extra,
    )
