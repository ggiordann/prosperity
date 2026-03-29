from __future__ import annotations

import csv
from pathlib import Path

from prosperity.corpus.provenance import build_metadata
from prosperity.corpus.schemas import IngestedDocument, SourceType
from prosperity.corpus.search import CorpusService


def load_imcdata_documents(root: Path) -> list[IngestedDocument]:
    documents: list[IngestedDocument] = []
    for csv_path in sorted(root.glob("*.csv")):
        with csv_path.open(encoding="utf-8", errors="ignore") as handle:
            reader = csv.reader(handle, delimiter=";")
            rows = list(reader)
        header = rows[0] if rows else []
        sample = rows[1:6]
        text = "\n".join(
            [
                f"file: {csv_path.name}",
                f"rows: {max(0, len(rows) - 1)}",
                f"header: {header}",
                f"sample: {sample}",
            ]
        )
        metadata = build_metadata(SourceType.INTERNAL_RESULTS, str(csv_path))
        documents.append(
            IngestedDocument(
                document_id=CorpusService.document_id(csv_path.stem, text),
                title=csv_path.name,
                content=text,
                corpus_name="internal_research_corpus",
                metadata=metadata,
            )
        )
    return documents
