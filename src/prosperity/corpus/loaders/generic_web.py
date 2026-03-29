from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from prosperity.corpus.provenance import build_metadata
from prosperity.corpus.schemas import IngestedDocument, SourceType
from prosperity.corpus.search import CorpusService


def load_web_document(url: str, corpus_name: str, source_type: SourceType) -> IngestedDocument:
    response = httpx.get(url, timeout=20.0)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text("\n", strip=True)
    metadata = build_metadata(source_type, url)
    return IngestedDocument(
        document_id=CorpusService.document_id("web", text),
        title=url,
        content=text,
        corpus_name=corpus_name,
        metadata=metadata,
    )
