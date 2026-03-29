from __future__ import annotations

from pathlib import Path

from prosperity.corpus.loaders.local_markdown import load_markdown_documents
from prosperity.corpus.schemas import SourceType


def load_reddit_exports(root: Path):
    if not root.exists():
        return []
    return load_markdown_documents(root, "public_ideas_corpus", SourceType.PUBLIC_IDEA)
