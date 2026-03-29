from __future__ import annotations

from pathlib import Path

from prosperity.corpus.schemas import IngestedDocument, SourceType


def load_pdf_documents(root: Path, corpus_name: str, source_type: SourceType) -> list[IngestedDocument]:
    try:
        from pypdf import PdfReader
    except Exception:
        return []

    documents: list[IngestedDocument] = []
    paths = [root] if root.is_file() else list(root.rglob("*.pdf"))
    from prosperity.corpus.provenance import build_metadata
    from prosperity.corpus.search import CorpusService

    for path in paths:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
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
