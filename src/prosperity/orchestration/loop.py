from __future__ import annotations

from prosperity.db import DatabaseSession, ExperimentRepository
from prosperity.orchestration.jobs import (
    compile_spec_to_artifact,
    evaluate_compiled_strategy,
    generate_specs,
    ingest_all,
    package_strategy,
    persist_strategy_record,
    write_failure_postmortem,
)
from prosperity.orchestration.locks import file_lock
from prosperity.paths import RepoPaths
from prosperity.settings import load_settings


def _with_repo(paths: RepoPaths, callback):
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        return callback(repo)


def run_loop_once() -> dict:
    paths = RepoPaths.discover()
    settings = load_settings(paths)
    lock_path = paths.caches / "loop.lock"
    with file_lock(lock_path):
        ingested = _with_repo(paths, lambda repo: ingest_all(paths, settings, repo))
        specs = _with_repo(paths, generate_specs)
        outcomes = []
        for spec in specs:
            try:
                compiled = compile_spec_to_artifact(paths, spec)
                _with_repo(paths, lambda repo, spec=spec, compiled=compiled: persist_strategy_record(repo, spec, compiled, stage="compiled"))
                evaluation = _with_repo(
                    paths,
                    lambda repo, spec=spec, compiled=compiled: evaluate_compiled_strategy(paths, settings, repo, spec, compiled),
                )
                if evaluation["decision"] == "promote":
                    package_dir = package_strategy(paths, spec, compiled, evaluation)
                    _with_repo(
                        paths,
                        lambda repo, spec=spec, compiled=compiled, package_dir=package_dir: persist_strategy_record(
                            repo,
                            spec,
                            compiled,
                            stage="packaged",
                            notes=str(package_dir),
                        ),
                    )
                else:
                    write_failure_postmortem(paths, spec, evaluation["reason"], "evaluation")
                    _with_repo(
                        paths,
                        lambda repo, spec=spec, compiled=compiled, evaluation=evaluation: persist_strategy_record(
                            repo,
                            spec,
                            compiled,
                            stage="blocked",
                            notes=evaluation["reason"],
                        ),
                    )
                outcomes.append({"strategy_id": spec.metadata.id, **evaluation})
            except Exception as exc:
                write_failure_postmortem(paths, spec, str(exc), "loop")
                _with_repo(
                    paths,
                    lambda repo, spec=spec, exc=exc: persist_strategy_record(
                        repo,
                        spec,
                        paths.strategies / f"{spec.metadata.id}.py",
                        stage="blocked",
                        notes=str(exc),
                    ),
                )
                outcomes.append({"strategy_id": spec.metadata.id, "decision": "error", "reason": str(exc)})
        return {"ingested_documents": ingested, "candidate_count": len(specs), "outcomes": outcomes}
