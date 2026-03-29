from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from prosperity.corpus.provenance import build_metadata
from prosperity.corpus.schemas import IngestedDocument, SourceType
from prosperity.corpus.search import CorpusService
from prosperity.utils import read_text


def load_html_documents(root: Path, corpus_name: str, source_type: SourceType) -> list[IngestedDocument]:
    documents: list[IngestedDocument] = []
    paths = [root] if root.is_file() else list(root.rglob("*.html"))
    for path in paths:
        soup = BeautifulSoup(read_text(path), "html.parser")
        text = soup.get_text("\n", strip=True)
        metadata = build_metadata(source_type, str(path))
        documents.append(
            IngestedDocument(
                document_id=CorpusService.document_id(path.stem, text),
                title=path.name,
                content=text,
                corpus_name=corpus_name,
                metadata=metadata,
            )
        )
    return documents
