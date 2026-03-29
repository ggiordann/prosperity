from __future__ import annotations

from pathlib import Path

from prosperity.backtester.datasets import resolve_dataset_argument
from prosperity.backtester.runner import BacktesterRunner, BacktestRequest
from prosperity.compilation.spec_to_strategy import compile_strategy_module
from prosperity.corpus import CorpusService
from prosperity.corpus.embeddings import EmbeddingProvider
from prosperity.corpus.loaders import (
    load_imcdata_documents,
    load_markdown_documents,
    load_official_documents,
    load_research_repo_documents,
)
from prosperity.corpus.schemas import SourceType
from prosperity.db import ExperimentRepository
from prosperity.db.models import (
    EvaluationRecord,
    PromotionRecord,
    RunRecord,
    SimilarityRecord,
    StrategyRecord,
)
from prosperity.dsl.hashing import spec_hash
from prosperity.dsl.schema import StrategySpec
from prosperity.evaluation.diagnostics import build_diagnostics_report
from prosperity.evaluation.fingerprints import behavior_fingerprint
from prosperity.evaluation.metrics import compute_metrics
from prosperity.evaluation.novelty import novelty_score
from prosperity.evaluation.plagiarism_guard import scan_public_code_similarity
from prosperity.evaluation.promotion import promotion_decision
from prosperity.evaluation.robustness import run_robustness_suite
from prosperity.evaluation.scoring import score_candidate
from prosperity.evaluation.similarity import code_similarity, spec_similarity
from prosperity.external.manual_submission import package_manual_submission
from prosperity.generation.critic import critique_spec
from prosperity.generation.generator import generate_candidate_specs
from prosperity.generation.postmortem import write_postmortem
from prosperity.utils import json_dumps, utcnow_iso


def ingest_all(paths, settings, repository: ExperimentRepository) -> int:
    embedder = EmbeddingProvider(settings)
    corpus = CorpusService(repository, embedder)
    documents = []
    documents.extend(load_markdown_documents(paths.docs, "internal_research_corpus", SourceType.INTERNAL_CODE))
    documents.extend(load_official_documents(paths.docs))
    documents.extend(load_imcdata_documents(paths.root / "imcdata"))
    documents.extend(
        load_research_repo_documents(
            paths.research_repos,
            paths.data / "processed" / "research_repo_summaries",
        )
    )
    corpus.upsert_documents(documents)
    return len(documents)


def generate_specs(repository: ExperimentRepository) -> list[StrategySpec]:
    existing_families = [row["family"] for row in repository.list_strategies()]
    public_rows = repository.connection.execute(
        "SELECT metadata_json FROM documents WHERE corpus_name = 'public_ideas_corpus'"
    ).fetchall()
    crowded = []
    for row in public_rows:
        payload = __import__("json").loads(row["metadata_json"])
        crowded.extend(payload.get("extra", {}).get("motifs", []))
    return generate_candidate_specs(existing_families, crowded_motifs=crowded, count=2)


def compile_spec_to_artifact(paths, spec: StrategySpec) -> Path:
    template = paths.root / "src" / "prosperity" / "compilation" / "templates" / "strategy_module.py.j2"
    output_path = paths.strategies / f"{spec.metadata.id}.py"
    return compile_strategy_module(spec, output_path=output_path, template_path=template)


def evaluate_compiled_strategy(paths, settings, repository: ExperimentRepository, spec: StrategySpec, compiled_path: Path) -> dict:
    runner = BacktesterRunner(paths, settings)
    backtest_result = runner.run(
        BacktestRequest(
            trader_path=str(compiled_path),
            dataset=resolve_dataset_argument("submission"),
            products_mode=settings.backtester.default_products_mode,
        )
    )
    metrics = compute_metrics(backtest_result.summary)
    robustness = run_robustness_suite(runner, str(compiled_path), resolve_dataset_argument("submission"))
    prior_rows = repository.list_strategies()
    prior_specs = []
    similarity_records: list[SimilarityRecord] = []
    internal_similarity_scores: list[float] = []
    from prosperity.dsl.schema import StrategySpec as StrategySpecModel

    for row in prior_rows:
        try:
            prior_spec = StrategySpecModel.model_validate_json(row["spec_json"])
            prior_specs.append(prior_spec)
            score = spec_similarity(spec, prior_spec)
            internal_similarity_scores.append(score)
            similarity_records.append(
                SimilarityRecord(
                    similarity_id=f"sim-{spec.metadata.id[:8]}-{row['strategy_id'][:8]}-spec",
                    strategy_id=spec.metadata.id,
                    neighbor_id=row["strategy_id"],
                    neighbor_source="internal_strategy",
                    modality="spec",
                    score=score,
                    details_json=json_dumps({"kind": "spec_similarity"}),
                    created_at=utcnow_iso(),
                )
            )
            code_path = row["code_path"]
            if code_path and Path(code_path).exists():
                code_score = code_similarity(compiled_path.read_text(encoding="utf-8"), Path(code_path).read_text(encoding="utf-8"))["combined"]
                internal_similarity_scores.append(code_score)
                similarity_records.append(
                    SimilarityRecord(
                        similarity_id=f"sim-{spec.metadata.id[:8]}-{row['strategy_id'][:8]}-code",
                        strategy_id=spec.metadata.id,
                        neighbor_id=row["strategy_id"],
                        neighbor_source="internal_strategy",
                        modality="code",
                        score=code_score,
                        details_json=json_dumps({"kind": "code_similarity"}),
                        created_at=utcnow_iso(),
                    )
                )
        except Exception:
            continue
    novelty = novelty_score(spec, prior_specs, behavior_similarity_scores=internal_similarity_scores)
    plagiarism = scan_public_code_similarity(
        compiled_path.read_text(encoding="utf-8"),
        paths.research_repos,
        paths.caches / spec.metadata.id,
    )
    scoring = score_candidate(metrics, robustness, novelty, plagiarism_score=plagiarism["max_score"])
    decision, reason = promotion_decision(scoring["score"], plagiarism["max_score"])
    report = build_diagnostics_report(spec.metadata.name, metrics, robustness, scoring, plagiarism)
    report_path = paths.reports / f"{spec.metadata.id}.md"
    report_path.write_text(report, encoding="utf-8")

    repository.insert_run(
        RunRecord(
            run_id=backtest_result.run_id,
            strategy_id=spec.metadata.id,
            dataset_id="submission",
            trader_path=str(compiled_path),
            status="completed",
            final_pnl_total=metrics["total_pnl"],
            own_trade_count=metrics["own_trade_count"],
            tick_count=sum(row.ticks for row in backtest_result.summary.day_results),
            summary_json=backtest_result.summary.model_dump_json(indent=2),
            stdout_path=str(paths.runs / backtest_result.run_id / "stdout.txt"),
            stderr_path=str(paths.runs / backtest_result.run_id / "stderr.txt"),
            created_at=backtest_result.created_at,
        )
    )
    repository.insert_evaluation(
        EvaluationRecord(
            evaluation_id=f"eval-{spec_hash(spec)[:12]}",
            strategy_id=spec.metadata.id,
            run_id=backtest_result.run_id,
            score=scoring["score"],
            robustness_score=robustness.get("score", 0.0),
            novelty_score=novelty,
            similarity_score=max(internal_similarity_scores, default=0.0),
            plagiarism_score=plagiarism["max_score"],
            metrics_json=json_dumps(
                {
                    "metrics": metrics,
                    "robustness": robustness,
                    "scoring": scoring,
                    "plagiarism": plagiarism,
                    "behavior_fingerprint": behavior_fingerprint(backtest_result.summary),
                    "critique": critique_spec(spec),
                }
            ),
            created_at=utcnow_iso(),
        )
    )
    repository.insert_similarity_records(similarity_records)
    repository.insert_promotion(
        PromotionRecord(
            promotion_id=f"promo-{spec_hash(spec)[:12]}",
            strategy_id=spec.metadata.id,
            decision=decision,
            reason=reason,
            package_dir=None,
            created_at=utcnow_iso(),
        )
    )
    return {
        "decision": decision,
        "reason": reason,
        "metrics": metrics,
        "robustness": robustness,
        "scoring": scoring,
        "plagiarism": plagiarism,
        "report_path": str(report_path),
    }


def package_strategy(paths, spec: StrategySpec, compiled_path: Path, evaluation: dict) -> Path:
    explanation = (
        f"{spec.metadata.name}\n\n"
        f"Decision: {evaluation['decision']}\n"
        f"Reason: {evaluation['reason']}\n"
        f"Score: {evaluation['scoring']['score']}\n"
    )
    return package_manual_submission(
        paths.submissions,
        spec.metadata.id,
        compiled_path,
        metadata=spec.model_dump(mode="json"),
        explanation=explanation,
    )


def persist_strategy_record(repository: ExperimentRepository, spec: StrategySpec, compiled_path: Path, stage: str, notes: str = "") -> None:
    repository.upsert_strategy(
        StrategyRecord(
            strategy_id=spec.metadata.id,
            name=spec.metadata.name,
            family=spec.metadata.family,
            stage=stage,
            spec_json=spec.model_dump_json(indent=2),
            code_path=str(compiled_path),
            created_at=utcnow_iso(),
            notes=notes,
        )
    )


def write_failure_postmortem(paths, spec: StrategySpec, reason: str, stage: str) -> Path:
    postmortem = write_postmortem(spec, reason, stage)
    path = paths.reports / f"{spec.metadata.id}-postmortem.md"
    path.write_text(postmortem, encoding="utf-8")
    return path
