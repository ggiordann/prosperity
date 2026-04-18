from __future__ import annotations

from prosperity.db import DatabaseSession, ExperimentRepository
from prosperity.orchestration.conversation import _detect_plateau, run_conversation_cycle
from prosperity.paths import RepoPaths
from prosperity.settings import AppSettings


def test_run_conversation_cycle_promotes_and_persists(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    paths = RepoPaths.discover(root)
    settings = AppSettings()
    settings.discord.enabled = False
    settings.conversation.max_candidates_per_cycle = 3
    settings.conversation.frontier_size = 2
    settings.conversation.exploit_candidates = 3
    settings.conversation.explore_candidates = 0
    settings.conversation.structural_candidates = 0
    settings.conversation.family_jump_candidates = 0
    settings.conversation.family_lab_candidates = 0
    settings.conversation.expert_builder_candidates = 0
    settings.conversation.survivor_tune_candidates = 0
    settings.conversation.promote_min_improvement = 5.0

    def fake_ingest(paths_obj, settings_obj, repo):
        return 4

    def fake_compile(paths_obj, spec):
        target = paths_obj.strategies / f"{spec.metadata.id}.py"
        target.write_text("class Trader:\n    pass\n", encoding="utf-8")
        return target

    def fake_evaluate(paths_obj, settings_obj, repo, spec, compiled_path):
        if spec.metadata.id == "conversation-round1-256418-seed":
            pnl = 100.0
        elif spec.metadata.id.startswith("conversation-microprice-seed"):
            pnl = 80.0
        elif spec.metadata.id.startswith("conversation-wall-mid-seed"):
            pnl = 70.0
        elif "v00" in spec.metadata.id:
            pnl = 120.0
        else:
            pnl = 90.0
        return {
            "decision": "promote" if pnl >= 105.0 else "reject",
            "reason": "stubbed evaluation",
            "metrics": {"total_pnl": pnl},
            "robustness": {"score": 0.8},
            "scoring": {"score": pnl / 1000.0},
            "plagiarism": {"max_score": 0.0},
            "report_path": str(paths_obj.reports / f"{spec.metadata.id}.md"),
        }

    def fake_package(paths_obj, spec, compiled_path, evaluation):
        package_dir = paths_obj.submissions / spec.metadata.id
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "submission.py").write_text(
            f"# packaged {spec.metadata.id}\nclass Trader:\n    pass\n",
            encoding="utf-8",
        )
        return package_dir

    monkeypatch.setattr("prosperity.orchestration.conversation.ingest_all", fake_ingest)
    monkeypatch.setattr("prosperity.orchestration.conversation.compile_spec_to_artifact", fake_compile)
    monkeypatch.setattr("prosperity.orchestration.conversation.evaluate_compiled_strategy", fake_evaluate)
    monkeypatch.setattr("prosperity.orchestration.conversation.package_strategy", fake_package)

    result = run_conversation_cycle(session_name="unit-test", paths=paths, settings=settings)

    assert result["decision"] == "promote"
    assert result["champion_before"] == "conversation-round1-256418-seed"
    assert result["champion_after"] != result["champion_before"]
    assert result["candidate_count"] == 3
    assert result["candidate_budget"]["exploit"] == 3
    assert result["candidate_budget"]["expert_builder"] == 0
    assert len(result["frontier"]) >= 1

    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        cycles = repo.list_recent_conversation_cycles("unit-test", limit=5)
        messages = repo.list_recent_conversation_messages("unit-test", limit=20)
        memory = repo.list_memory_notes("unit-test", limit=20)

    assert len(cycles) == 1
    assert cycles[0]["promoted_strategy_id"] == result["champion_after"]
    assert len(messages) >= 3
    assert any(row["note_kind"] == "promotion" for row in memory)
    exported = root / "current_best_algo" / "current_best_V1.py"
    assert exported.exists()
    assert f"# packaged {result['champion_after']}" in exported.read_text(encoding="utf-8")


def test_detect_plateau_activates_on_long_hold_streak():
    cycles = [
        {
            "decision": "hold",
            "champion_after": "champion-alpha",
            "best_candidate": {
                "search_bucket": "exploit",
                "family": "tutorial_submission_candidate_alpha",
                "profile": "thesis",
                "metrics": {"total_pnl": 2700.0},
                "scoring": {"score": 0.64},
            },
        }
        for _ in range(7)
    ]
    plateau = _detect_plateau(
        cycles,
        "champion-alpha",
        lookback=8,
        repeat_threshold=3,
    )
    assert plateau["active"] is True
    assert plateau["hold_streak"] == 7
