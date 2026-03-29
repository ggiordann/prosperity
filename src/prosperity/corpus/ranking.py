from __future__ import annotations

from prosperity.corpus.schemas import SearchHit


def rerank_hits(hits: list[SearchHit]) -> list[SearchHit]:
    return sorted(
        hits,
        key=lambda hit: (hit.score * hit.metadata.trust_level, hit.metadata.fetched_at),
        reverse=True,
    )
