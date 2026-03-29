from __future__ import annotations

from pathlib import Path

from prosperity.corpus.loaders.local_markdown import load_markdown_documents
from prosperity.corpus.schemas import IngestedDocument, SourceType


def load_official_documents(root: Path) -> list[IngestedDocument]:
    if not root.exists():
        return []
    return load_markdown_documents(root, "mechanics_corpus", SourceType.OFFICIAL_MECHANICS)
