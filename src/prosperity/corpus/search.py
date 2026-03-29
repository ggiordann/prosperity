from __future__ import annotations

from prosperity.corpus.embeddings import EmbeddingProvider, cosine_similarity
from prosperity.corpus.ranking import rerank_hits
from prosperity.corpus.schemas import IngestedDocument, SearchHit
from prosperity.db import ExperimentRepository
from prosperity.db.models import DocumentRecord
from prosperity.utils import sha256_text


class CorpusService:
    def __init__(self, repository: ExperimentRepository, embedder: EmbeddingProvider):
        self.repository = repository
        self.embedder = embedder

    def upsert_documents(self, documents: list[IngestedDocument]) -> None:
        for document in documents:
            self.repository.upsert_document(
                DocumentRecord(
                    document_id=document.document_id,
                    corpus_name=document.corpus_name,
                    title=document.title,
                    content=document.content,
                    metadata=document.metadata.model_dump(),
                    embedding=document.embedding or self.embedder.embed_text(document.content),
                    created_at=document.metadata.fetched_at,
                )
            )

    def search(
        self,
        query: str,
        corpus_names: set[str] | None = None,
        top_k: int = 5,
    ) -> list[SearchHit]:
        rows = self.repository.connection.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ).fetchall()
        query_embedding = self.embedder.embed_text(query)
        hits: list[SearchHit] = []
        for row in rows:
            if corpus_names and row["corpus_name"] not in corpus_names:
                continue
            metadata = row["metadata_json"]
            hit = SearchHit.model_validate(
                {
                    "document_id": row["document_id"],
                    "corpus_name": row["corpus_name"],
                    "title": row["title"],
                    "score": cosine_similarity(query_embedding, __import__("json").loads(row["embedding_json"])),
                    "snippet": row["content"][:240],
                    "metadata": __import__("json").loads(metadata),
                }
            )
            hits.append(hit)
        return rerank_hits(hits)[:top_k]

    @staticmethod
    def document_id(prefix: str, text: str) -> str:
        return f"{prefix}-{sha256_text(text)[:16]}"
