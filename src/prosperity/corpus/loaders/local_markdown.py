from __future__ import annotations

from pathlib import Path

from prosperity.corpus.provenance import build_metadata
from prosperity.corpus.schemas import IngestedDocument, SourceType
from prosperity.corpus.search import CorpusService
from prosperity.utils import read_text


def load_markdown_documents(root: Path, corpus_name: str, source_type: SourceType) -> list[IngestedDocument]:
    documents: list[IngestedDocument] = []
    paths = [root] if root.is_file() else list(root.rglob("*.md"))
    for path in paths:
        content = read_text(path)
        metadata = build_metadata(source_type, str(path))
        documents.append(
            IngestedDocument(
                document_id=CorpusService.document_id(path.stem, content),
                title=path.name,
                content=content,
                corpus_name=corpus_name,
                metadata=metadata,
            )
        )
    return documents
