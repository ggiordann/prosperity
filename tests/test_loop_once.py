from __future__ import annotations

from pathlib import Path

from prosperity.orchestration.loop import run_loop_once
from prosperity.paths import RepoPaths
from prosperity.settings import AppSettings


def test_run_loop_once_executes_pipeline_with_stubbed_dependencies(tmp_path, monkeypatch, sample_spec):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    paths = RepoPaths.discover(root)

    def fake_compile(paths_obj, spec):
        path = paths_obj.strategies / f"{spec.metadata.id}.py"
        path.write_text("class Trader:\n    pass\n", encoding="utf-8")
        return path

    def fake_package(paths_obj, spec, compiled_path, evaluation):
        package_dir = paths_obj.submissions / spec.metadata.id
        package_dir.mkdir(parents=True, exist_ok=True)
        return package_dir

    monkeypatch.setattr("prosperity.orchestration.loop.RepoPaths.discover", lambda: paths)
    monkeypatch.setattr("prosperity.orchestration.loop.load_settings", lambda paths: AppSettings())
    monkeypatch.setattr("prosperity.orchestration.loop.ingest_all", lambda paths, settings, repo: 5)
    monkeypatch.setattr("prosperity.orchestration.loop.generate_specs", lambda repo: [sample_spec])
    monkeypatch.setattr("prosperity.orchestration.loop.compile_spec_to_artifact", fake_compile)
    monkeypatch.setattr(
        "prosperity.orchestration.loop.evaluate_compiled_strategy",
        lambda paths, settings, repo, spec, compiled: {
            "decision": "promote",
            "reason": "ok",
            "metrics": {"total_pnl": 1234.0},
            "robustness": {"score": 0.8},
            "scoring": {"score": 0.9},
            "plagiarism": {"max_score": 0.0},
            "report_path": str(paths.reports / "report.md"),
        },
    )
    monkeypatch.setattr("prosperity.orchestration.loop.package_strategy", fake_package)
    monkeypatch.setattr("prosperity.orchestration.loop.persist_strategy_record", lambda *args, **kwargs: None)
    monkeypatch.setattr("prosperity.orchestration.loop.write_failure_postmortem", lambda *args, **kwargs: Path("noop"))

    result = run_loop_once()
    assert result["ingested_documents"] == 5
    assert result["candidate_count"] == 1
    assert result["outcomes"][0]["decision"] == "promote"
