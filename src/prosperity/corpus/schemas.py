from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    OFFICIAL_MECHANICS = "OFFICIAL_MECHANICS"
    INTERNAL_CODE = "INTERNAL_CODE"
    INTERNAL_RESULTS = "INTERNAL_RESULTS"
    PUBLIC_IDEA = "PUBLIC_IDEA"
    PUBLIC_CODE_REFERENCE = "PUBLIC_CODE_REFERENCE"
    MANUAL_NOTES = "MANUAL_NOTES"


class SourceMetadata(BaseModel):
    source_type: SourceType
    source_uri_or_path: str
    fetched_at: str
    trust_level: float
    allowed_for_codegen: bool
    allowed_for_mechanics: bool
    allowed_for_strategy_hypotheses: bool
    license_note: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class IngestedDocument(BaseModel):
    document_id: str
    title: str
    content: str
    corpus_name: str
    metadata: SourceMetadata
    embedding: list[float] = Field(default_factory=list)


class SearchHit(BaseModel):
    document_id: str
    corpus_name: str
    title: str
    score: float
    snippet: str
    metadata: SourceMetadata
