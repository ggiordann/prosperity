from __future__ import annotations

import shutil
import time
from pathlib import Path
from uuid import uuid4

from prosperity.backtester.runner import BacktesterRunner
from prosperity.external.discord_notifier import send_quant_summary_message
from prosperity.paths import RepoPaths
from prosperity.quant.alpha_miner import mine_alpha_signals
from prosperity.quant.budget import allocate_quant_budget
from prosperity.quant.git_scout import scout_git_commits
from prosperity.quant.models import (
    AlphaSignal,
    QuantCycleSummary,
    StrategyEvaluation,
    StrategyIdea,
)
from prosperity.quant.state import load_quant_state, save_quant_state
from prosperity.quant.strategy_builder import build_alpha_strategy_files
from prosperity.quant.team import evaluate_strategy_file, extract_strategy_idea, is_strategy_file
from prosperity.settings import AppSettings, load_settings
from prosperity.utils import json_dumps, utcnow_iso


def _resolve_path(root: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path


def _state_path(paths: RepoPaths, settings: AppSettings) -> Path:
    return _resolve_path(paths.root, settings.quant.state_path) or (paths.data / "quant" / "state.json")


def _report_dir(paths: RepoPaths, settings: AppSettings) -> Path:
    return _resolve_path(paths.root, settings.quant.report_dir) or (paths.reports / "quant")


def _find_latest_current_best(paths: RepoPaths) -> Path | None:
    current_best_dir = paths.root / "current_best_algo"
    if not current_best_dir.exists():
        return None
    candidates = sorted(current_best_dir.glob("current_best_V*.py"))
    for candidate in reversed(candidates):
        if is_strategy_file(candidate):
            return candidate
    return None


def _find_champion_path(paths: RepoPaths, settings: AppSettings) -> Path | None:
    configured = _resolve_path(paths.root, settings.quant.champion_strategy_path)
    if configured and configured.exists():
        return configured
    latest_current_best = _find_latest_current_best(paths)
    if latest_current_best is not None:
        return latest_current_best
    seed = _resolve_path(paths.root, settings.conversation.seed_strategy_path)
    if seed and seed.exists():
        return seed
    return None


def _feature_matches_tags(signal: AlphaSignal, ideas: list[StrategyIdea]) -> bool:
    feature = signal.feature.lower()
    for idea in ideas:
        tags = set(idea.tags)
        if "imbalance" in tags and "imbalance" in feature:
            return True
        if "microprice" in tags and "micro" in feature:
            return True
        if "ema" in tags and "ema" in feature:
            return True
        if "spread" in tags and "spread" in feature:
            return True
        if "momentum" in tags and "momentum" in feature:
            return True
        if "mean_reversion" in tags and ("fade" in feature or "reversion" in feature):
            return True
    return False


def _select_git_variant_signals(
    signals: list[AlphaSignal],
    ideas: list[StrategyIdea],
    count: int,
) -> list[AlphaSignal]:
    if count <= 0 or not ideas:
        return []
    matched = [signal for signal in signals if _feature_matches_tags(signal, ideas)]
    if len(matched) >= count:
        return matched[:count]
    seen = {(signal.product, signal.feature, signal.horizon) for signal in matched}
    for signal in signals:
        key = (signal.product, signal.feature, signal.horizon)
        if key not in seen:
            matched.append(signal)
            seen.add(key)
        if len(matched) >= count:
            break
    return matched[:count]


def _best_evaluation(evaluations: list[StrategyEvaluation]) -> StrategyEvaluation | None:
    ok = [evaluation for evaluation in evaluations if evaluation.status == "ok" and evaluation.total_pnl is not None]
    if not ok:
        return None
    return max(ok, key=lambda evaluation: float(evaluation.total_pnl or 0.0))


def _next_current_best_version(paths: RepoPaths) -> int:
    export_dir = paths.root / "current_best_algo"
    export_dir.mkdir(parents=True, exist_ok=True)
    versions: list[int] = []
    for candidate in export_dir.glob("current_best_V*.py"):
        suffix = candidate.stem.removeprefix("current_best_V")
        if suffix.isdigit():
            versions.append(int(suffix))
    return (max(versions) + 1) if versions else 1


def _promote_if_allowed(paths: RepoPaths, settings: AppSettings, best: StrategyEvaluation, champion: StrategyEvaluation | None) -> str | None:
    if not settings.quant.auto_promote:
        return None
    if best.status != "ok" or best.total_pnl is None:
        return None
    champion_pnl = float(champion.total_pnl or 0.0) if champion and champion.total_pnl is not None else 0.0
    if best.total_pnl < champion_pnl + settings.quant.promote_min_improvement:
        return None
    source = Path(best.path)
    if not source.exists():
        return None
    version = _next_current_best_version(paths)
    target = paths.root / "current_best_algo" / f"current_best_V{version}.py"
    shutil.copy2(source, target)
    return str(target)


def _write_report(paths: RepoPaths, settings: AppSettings, summary: QuantCycleSummary, promoted_path: str | None) -> Path:
    report_dir = _report_dir(paths, settings)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / f"{summary.cycle_id}.json"
    json_path.write_text(json_dumps(summary.model_dump(mode="json")), encoding="utf-8")
    md_path = report_dir / f"{summary.cycle_id}.md"
    lines = [
        f"# Quant Cycle {summary.iteration}",
        "",
        f"- Dataset: `{summary.dataset}`",
        f"- Decision: `{summary.decision}`",
        f"- Reason: {summary.reason}",
        f"- Git commits considered: {len(summary.git.commits)}",
        f"- Git strategy files considered: {len(summary.git.candidate_strategy_files)}",
        f"- Rows analyzed: {summary.alpha.rows_analyzed}",
        "",
        "## Budget",
        "",
        f"- Git: {summary.budget.git_fraction:.2f}",
        f"- Raw alpha: {summary.budget.raw_alpha_fraction:.2f}",
        f"- Champion: {summary.budget.champion_fraction:.2f}",
        f"- Structural: {summary.budget.structural_fraction:.2f}",
        f"- Reason: {summary.budget.reason}",
        "",
        "## Top Alpha Signals",
        "",
    ]
    for signal in summary.alpha.top_signals[:8]:
        lines.append(
            f"- `{signal.product}` `{signal.feature}` h={signal.horizon}: "
            f"corr={signal.correlation:.4f}, acc={signal.directional_accuracy:.3f}, score={signal.score:.4f}"
        )
    lines.extend(["", "## Evaluations", ""])
    for evaluation in [*(summary.team_evaluations), *(summary.generated_evaluations)]:
        pnl = "n/a" if evaluation.total_pnl is None else f"{evaluation.total_pnl:.2f}"
        lines.append(f"- `{evaluation.source}` `{Path(evaluation.path).name}`: {evaluation.status}, pnl={pnl}")
    if promoted_path:
        lines.extend(["", f"Promoted to `{promoted_path}`."])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md_path


def run_quant_cycle(
    *,
    paths: RepoPaths | None = None,
    settings: AppSettings | None = None,
    fetch_git: bool | None = None,
    run_backtests: bool = True,
    promote: bool | None = None,
) -> dict:
    resolved_paths = paths or RepoPaths.discover()
    resolved_settings = settings or load_settings(resolved_paths)
    if promote is not None:
        resolved_settings.quant.auto_promote = promote

    state_path = _state_path(resolved_paths, resolved_settings)
    state = load_quant_state(state_path)
    cycle_id = f"quant-{uuid4().hex[:10]}"
    iteration = state.completed_cycles + 1
    should_fetch = resolved_settings.quant.fetch_remote if fetch_git is None else fetch_git

    git = scout_git_commits(
        resolved_paths.root,
        last_seen_sha=state.last_git_sha,
        fetch_remote=should_fetch,
        initial_scan_commits=resolved_settings.quant.initial_git_scan_commits,
        max_files=resolved_settings.quant.max_changed_files_per_cycle,
    )
    budget = allocate_quant_budget(resolved_settings, git)
    alpha = mine_alpha_signals(
        resolved_paths,
        resolved_settings,
        horizons=resolved_settings.quant.alpha_horizons,
        top_n=resolved_settings.quant.top_alpha_features,
    )

    runner = BacktesterRunner(resolved_paths, resolved_settings)
    team_ideas: list[StrategyIdea] = []
    team_evaluations: list[StrategyEvaluation] = []
    for rel_path in git.candidate_strategy_files[: budget.direct_git_tests]:
        path = resolved_paths.root / rel_path
        if path.exists() and is_strategy_file(path):
            team_ideas.append(extract_strategy_idea(path))
            if run_backtests:
                team_evaluations.append(evaluate_strategy_file(runner, resolved_settings, path, source="git_direct"))

    generated_evaluations: list[StrategyEvaluation] = []
    if run_backtests:
        alpha_files = build_alpha_strategy_files(
            resolved_paths,
            resolved_settings,
            cycle_id=f"{cycle_id}-alpha",
            signals=alpha.top_signals,
            count=budget.alpha_strategy_tests,
        )
        for path in alpha_files:
            generated_evaluations.append(evaluate_strategy_file(runner, resolved_settings, path, source="alpha_generated"))

        git_variant_signals = _select_git_variant_signals(alpha.top_signals, team_ideas, budget.git_variant_tests)
        git_variant_files = build_alpha_strategy_files(
            resolved_paths,
            resolved_settings,
            cycle_id=f"{cycle_id}-git",
            signals=git_variant_signals,
            count=len(git_variant_signals),
        )
        for path in git_variant_files:
            generated_evaluations.append(evaluate_strategy_file(runner, resolved_settings, path, source="git_variant"))

    champion_path = _find_champion_path(resolved_paths, resolved_settings)
    champion = None
    if champion_path is not None and run_backtests:
        champion = evaluate_strategy_file(runner, resolved_settings, champion_path, source="champion")

    best_candidate = _best_evaluation([*team_evaluations, *generated_evaluations])
    decision = "hold"
    reason = "No generated or teammate candidate beat the champion gate."
    promoted_path = None
    if best_candidate is not None:
        champion_pnl = float(champion.total_pnl or 0.0) if champion and champion.total_pnl is not None else 0.0
        if best_candidate.total_pnl is not None and best_candidate.total_pnl >= champion_pnl + resolved_settings.quant.promote_min_improvement:
            decision = "promote_ready"
            reason = f"{best_candidate.strategy_id} beat champion by {best_candidate.total_pnl - champion_pnl:.2f}."
            promoted_path = _promote_if_allowed(resolved_paths, resolved_settings, best_candidate, champion)
            if promoted_path:
                decision = "promote"
                reason += f" Exported to {promoted_path}."

    placeholder_report = str(_report_dir(resolved_paths, resolved_settings) / f"{cycle_id}.md")
    summary = QuantCycleSummary(
        cycle_id=cycle_id,
        session_name=resolved_settings.quant.session_name,
        iteration=iteration,
        dataset=resolved_settings.backtester.default_dataset,
        git=git,
        budget=budget,
        alpha=alpha,
        team_ideas=team_ideas,
        team_evaluations=team_evaluations,
        generated_evaluations=generated_evaluations,
        champion=champion,
        best_candidate=best_candidate,
        decision=decision,
        reason=reason,
        report_path=placeholder_report,
        created_at=utcnow_iso(),
    )
    report_path = _write_report(resolved_paths, resolved_settings, summary, promoted_path)
    summary.report_path = str(report_path)
    summary.discord = send_quant_summary_message(summary.model_dump(mode="json"), resolved_settings)
    (report_path.with_suffix(".json")).write_text(json_dumps(summary.model_dump(mode="json")), encoding="utf-8")

    state.completed_cycles = iteration
    state.last_git_sha = git.target_sha or state.last_git_sha
    if best_candidate and best_candidate.status == "ok":
        state.accepted_ideas.append(
            {
                "cycle_id": cycle_id,
                "strategy_id": best_candidate.strategy_id,
                "pnl": best_candidate.total_pnl,
                "decision": decision,
                "created_at": summary.created_at,
            }
        )
        state.accepted_ideas = state.accepted_ideas[-50:]
    save_quant_state(state_path, state)
    return summary.model_dump(mode="json")


def run_quant_loop(
    *,
    cycles: int | None,
    sleep_seconds: int,
    fetch_git: bool | None = None,
    promote: bool | None = None,
) -> None:
    completed = 0
    while cycles is None or completed < cycles:
        print(json_dumps(run_quant_cycle(fetch_git=fetch_git, promote=promote)))
        completed += 1
        if cycles is not None and completed >= cycles:
            break
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)
