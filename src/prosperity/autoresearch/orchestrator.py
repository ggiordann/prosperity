from __future__ import annotations

import shutil
import time
from pathlib import Path
from uuid import uuid4

from prosperity.autoresearch.evaluator import candidate_clears_gate, evaluate_locked_strategy
from prosperity.autoresearch.models import (
    AutoResearchCycleSummary,
    ResearchExperiment,
    ResearchScore,
)
from prosperity.autoresearch.recipes import materialize_candidate, select_recipes
from prosperity.autoresearch.state import load_autoresearch_state, save_autoresearch_state
from prosperity.backtester.runner import BacktesterRunner
from prosperity.external.discord_notifier import send_autoresearch_summary_message
from prosperity.paths import RepoPaths
from prosperity.quant.team import is_strategy_file
from prosperity.settings import AppSettings, load_settings
from prosperity.utils import ensure_dir, json_dumps, utcnow_iso


def _resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _state_path(paths: RepoPaths, settings: AppSettings) -> Path:
    return _resolve_path(paths.root, settings.autoresearch.state_path) or (paths.data / "autoresearch" / "state.json")


def _report_dir(paths: RepoPaths, settings: AppSettings) -> Path:
    return _resolve_path(paths.root, settings.autoresearch.report_dir) or (paths.reports / "autoresearch")


def _artifacts_dir(paths: RepoPaths, settings: AppSettings) -> Path:
    return _resolve_path(paths.root, settings.autoresearch.artifacts_dir) or (paths.strategies / "autoresearch")


def _find_latest_current_best(paths: RepoPaths) -> Path | None:
    current_best_dir = paths.root / "current_best_algo"
    if not current_best_dir.exists():
        return None
    candidates = sorted(current_best_dir.glob("current_best_V*.py"))
    for candidate in reversed(candidates):
        if is_strategy_file(candidate):
            return candidate
    return None


def _find_target_strategy(paths: RepoPaths, settings: AppSettings) -> Path:
    configured = _resolve_path(paths.root, settings.autoresearch.target_strategy_path)
    if configured and configured.exists() and is_strategy_file(configured):
        return configured
    latest = _find_latest_current_best(paths)
    if latest is not None:
        return latest
    seed = _resolve_path(paths.root, settings.conversation.seed_strategy_path)
    if seed and seed.exists() and is_strategy_file(seed):
        return seed
    raise RuntimeError("No valid autoresearch target strategy found.")


def _next_current_best_version(paths: RepoPaths) -> int:
    export_dir = ensure_dir(paths.root / "current_best_algo")
    versions: list[int] = []
    for candidate in export_dir.glob("current_best_V*.py"):
        suffix = candidate.stem.removeprefix("current_best_V")
        if suffix.isdigit():
            versions.append(int(suffix))
    return (max(versions) + 1) if versions else 1


def _promote_candidate(paths: RepoPaths, candidate: ResearchExperiment) -> str | None:
    source = Path(candidate.path)
    if not source.exists():
        return None
    version = _next_current_best_version(paths)
    target = paths.root / "current_best_algo" / f"current_best_V{version}.py"
    shutil.copy2(source, target)
    return str(target)


def _best_experiment(experiments: list[ResearchExperiment]) -> ResearchExperiment | None:
    ok = [experiment for experiment in experiments if experiment.score and experiment.score.status == "ok"]
    if not ok:
        return None
    return max(ok, key=lambda experiment: float(experiment.score.score if experiment.score else 0.0))


def _score_brief(score: ResearchScore | None) -> str:
    if score is None:
        return "not evaluated"
    if score.status != "ok":
        return f"error: {score.error or 'unknown'}"
    return (
        f"score={score.score:.2f}, train={score.train_mean:.2f}, "
        f"validation={score.validation_mean:.2f}, stress={score.stress_mean:.2f}, "
        f"worst={score.worst_day_pnl:.2f}, concentration={score.product_concentration:.3f}"
    )


def _write_report(
    paths: RepoPaths,
    settings: AppSettings,
    summary: AutoResearchCycleSummary,
) -> Path:
    report_dir = ensure_dir(_report_dir(paths, settings))
    json_path = report_dir / f"{summary.cycle_id}.json"
    json_path.write_text(json_dumps(summary.model_dump(mode="json")), encoding="utf-8")

    md_path = report_dir / f"{summary.cycle_id}.md"
    lines = [
        f"# AutoResearch Cycle {summary.iteration}",
        "",
        f"- Session: `{summary.session_name}`",
        f"- Dataset: `{summary.dataset}`",
        f"- Decision: `{summary.decision}`",
        f"- Reason: {summary.reason}",
        f"- Champion: `{summary.champion_path}`",
        f"- Champion score: {_score_brief(summary.champion_score)}",
        "",
        "## Experiments",
        "",
    ]
    for experiment in summary.experiments:
        lines.append(f"### {experiment.recipe.name}")
        lines.append("")
        lines.append(f"- Kind: `{experiment.recipe.kind}`")
        lines.append(f"- Description: {experiment.recipe.description}")
        lines.append(f"- Path: `{experiment.path}`")
        lines.append(f"- Status: `{experiment.status}`")
        lines.append(f"- Score: {_score_brief(experiment.score)}")
        lines.append(f"- Decision: `{experiment.decision}`")
        if experiment.reason:
            lines.append(f"- Reason: {experiment.reason}")
        lines.append("")
    if summary.promoted_path:
        lines.extend(["## Promotion", "", f"Promoted to `{summary.promoted_path}`.", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def run_autoresearch_cycle(
    *,
    paths: RepoPaths | None = None,
    settings: AppSettings | None = None,
    experiments: int | None = None,
    promote: bool | None = None,
    send_discord: bool | None = None,
) -> dict:
    resolved_paths = paths or RepoPaths.discover()
    resolved_settings = settings or load_settings(resolved_paths)
    if promote is not None:
        resolved_settings.autoresearch.auto_promote = promote
    if send_discord is not None:
        resolved_settings.autoresearch.send_discord = send_discord

    state_path = _state_path(resolved_paths, resolved_settings)
    state = load_autoresearch_state(state_path)
    iteration = state.completed_cycles + 1
    cycle_id = f"autoresearch-{uuid4().hex[:10]}"
    target = _find_target_strategy(resolved_paths, resolved_settings)
    runner = BacktesterRunner(resolved_paths, resolved_settings)
    champion_score = evaluate_locked_strategy(runner, resolved_settings, target)

    experiment_count = experiments if experiments is not None else resolved_settings.autoresearch.experiments_per_cycle
    cycle_artifacts_dir = ensure_dir(_artifacts_dir(resolved_paths, resolved_settings) / cycle_id)
    research_experiments: list[ResearchExperiment] = []
    for recipe in select_recipes(iteration, experiment_count):
        path = materialize_candidate(target, cycle_artifacts_dir, recipe)
        experiment = ResearchExperiment(
            experiment_id=f"{cycle_id}-{recipe.name}",
            recipe=recipe,
            path=str(path),
            source_path=str(target),
            status="created",
        )
        score = evaluate_locked_strategy(runner, resolved_settings, path)
        experiment.score = score
        experiment.status = score.status
        clears, reason = candidate_clears_gate(score, champion_score, resolved_settings)
        experiment.decision = "promote_ready" if clears else "hold"
        experiment.reason = reason
        research_experiments.append(experiment)

    best = _best_experiment(research_experiments)
    decision = "hold"
    reason = "No experiment cleared the locked champion gate."
    promoted_path = None
    if best and best.score:
        clears, gate_reason = candidate_clears_gate(best.score, champion_score, resolved_settings)
        if clears:
            decision = "promote_ready"
            reason = f"{best.recipe.name} cleared gate: {gate_reason}."
            if resolved_settings.autoresearch.auto_promote:
                promoted_path = _promote_candidate(resolved_paths, best)
                if promoted_path:
                    decision = "promote"
                    reason += f" Exported to {promoted_path}."
        else:
            reason = f"Best experiment {best.recipe.name} held: {gate_reason}."

    summary = AutoResearchCycleSummary(
        cycle_id=cycle_id,
        session_name=resolved_settings.autoresearch.session_name,
        iteration=iteration,
        dataset=resolved_settings.backtester.default_dataset,
        champion_path=str(target),
        champion_score=champion_score,
        experiments=research_experiments,
        best_experiment=best,
        decision=decision,
        reason=reason,
        promoted_path=promoted_path,
        report_path="discord-only",
        created_at=utcnow_iso(),
    )
    report_path: Path | None = None
    if resolved_settings.autoresearch.write_reports:
        report_path = _write_report(resolved_paths, resolved_settings, summary)
        summary.report_path = str(report_path)
    if resolved_settings.autoresearch.send_discord:
        summary.discord = send_autoresearch_summary_message(summary.model_dump(mode="json"), resolved_settings)
    else:
        summary.discord = {"status": "skipped", "reason": "autoresearch discord disabled for this run"}
    if report_path is not None:
        (report_path.with_suffix(".json")).write_text(json_dumps(summary.model_dump(mode="json")), encoding="utf-8")

    state.completed_cycles = iteration
    state.champion_path = promoted_path or str(target)
    if champion_score.status == "ok":
        state.best_score = champion_score.score
    state.archive.append(
        {
            "cycle_id": cycle_id,
            "iteration": iteration,
            "decision": decision,
            "reason": reason,
            "champion_path": str(target),
            "champion_score": champion_score.score if champion_score.status == "ok" else None,
            "best_experiment": best.recipe.name if best else None,
            "best_score": best.score.score if best and best.score and best.score.status == "ok" else None,
            "created_at": summary.created_at,
        }
    )
    state.archive = state.archive[-100:]
    save_autoresearch_state(state_path, state)
    return summary.model_dump(mode="json")


def run_autoresearch_loop(
    *,
    cycles: int | None,
    sleep_seconds: int,
    experiments: int | None = None,
    promote: bool | None = None,
    send_discord: bool | None = None,
) -> None:
    completed = 0
    while cycles is None or completed < cycles:
        print(
            json_dumps(
                run_autoresearch_cycle(
                    experiments=experiments,
                    promote=promote,
                    send_discord=send_discord,
                )
            )
        )
        completed += 1
        if cycles is not None and completed >= cycles:
            break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
