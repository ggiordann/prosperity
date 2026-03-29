from __future__ import annotations

import json
import re
from pathlib import Path

from prosperity.corpus.provenance import build_metadata
from prosperity.corpus.schemas import IngestedDocument, SourceType
from prosperity.corpus.search import CorpusService
from prosperity.utils import ensure_dir, read_text, slugify

MOTIF_KEYWORDS = {
    "market_making": [r"market making", r"maker", r"order book"],
    "mean_reversion": [r"mean reversion", r"z-score", r"spread"],
    "momentum": [r"momentum", r"trend"],
    "arbitrage": [r"arbitrage", r"basket", r"conversion"],
    "options": [r"black-scholes", r"implied vol", r"option"],
    "dashboard": [r"dashboard", r"visualizer"],
    "backtester": [r"backtester", r"simulation"],
}


def _extract_motifs(text: str) -> list[str]:
    lowered = text.lower()
    motifs = []
    for motif, patterns in MOTIF_KEYWORDS.items():
        if any(re.search(pattern, lowered) for pattern in patterns):
            motifs.append(motif)
    return motifs


def load_research_repo_documents(root: Path, output_dir: Path) -> list[IngestedDocument]:
    documents: list[IngestedDocument] = []
    ensure_dir(output_dir)
    if not root.exists():
        return documents

    for repo_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        readme = repo_dir / "README.md"
        readme_text = read_text(readme) if readme.exists() else ""
        python_files = sorted(path.name for path in repo_dir.rglob("*.py"))
        motifs = _extract_motifs(readme_text + "\n" + "\n".join(python_files))
        summary = {
            "repo": repo_dir.name,
            "motifs": motifs,
            "readme_excerpt": readme_text[:2000],
            "python_file_count": len(python_files),
            "notable_files": python_files[:25],
        }
        summary_path = output_dir / f"{slugify(repo_dir.name)}.json"
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        metadata = build_metadata(
            SourceType.PUBLIC_IDEA,
            str(repo_dir),
            repo_name=repo_dir.name,
            motifs=motifs,
        )
        documents.append(
            IngestedDocument(
                document_id=CorpusService.document_id(repo_dir.name, json.dumps(summary, sort_keys=True)),
                title=repo_dir.name,
                content=json.dumps(summary, indent=2, sort_keys=True),
                corpus_name="public_ideas_corpus",
                metadata=metadata,
            )
        )
    return documents
