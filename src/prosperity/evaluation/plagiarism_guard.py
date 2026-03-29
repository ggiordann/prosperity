from __future__ import annotations

import json
from pathlib import Path

from prosperity.evaluation.similarity import code_similarity
from prosperity.utils import ensure_dir, read_text


def scan_public_code_similarity(candidate_code: str, research_root: Path, cache_dir: Path) -> dict:
    ensure_dir(cache_dir)
    results = []
    for path in research_root.rglob("*.py"):
        try:
            reference = read_text(path)
        except Exception:
            continue
        similarity = code_similarity(candidate_code, reference)
        results.append(
            {
                "path": str(path),
                "score": similarity["combined"],
                "token_jaccard": similarity["token_jaccard"],
                "ast_similarity": similarity["ast_similarity"],
            }
        )
    results.sort(key=lambda item: item["score"], reverse=True)
    payload = {
        "max_score": results[0]["score"] if results else 0.0,
        "nearest": results[:10],
    }
    (cache_dir / "plagiarism_scan.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
