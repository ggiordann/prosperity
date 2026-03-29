from __future__ import annotations

from prosperity.corpus.chunking import chunk_text
from prosperity.corpus.provenance import build_metadata
from prosperity.corpus.schemas import SourceType


def test_chunk_text_creates_overlapping_chunks():
    chunks = chunk_text("a" * 2500, chunk_size=1000, overlap=100)
    assert len(chunks) == 3
    assert len(chunks[0]) == 1000
    assert chunks[0][-100:] == chunks[1][:100]


def test_build_metadata_applies_public_code_policy():
    metadata = build_metadata(SourceType.PUBLIC_CODE_REFERENCE, "demo://repo")
    assert metadata.allowed_for_codegen is False
    assert metadata.allowed_for_strategy_hypotheses is True
