from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from prosperity.settings import AppSettings


def _fmt_number(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return str(value)
    return f"{value:.1f}"


def _fmt_delta(value: float) -> str:
    return f"{value:+.1f}"


def _decision_color(decision: str) -> int:
    normalized = decision.lower()
    if normalized in {"promote", "promote_ready"}:
        return 0x2ECC71
    if normalized == "shadow_promote":
        return 0x3498DB
    if normalized == "hold":
        return 0xF39C12
    return 0x95A5A6


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _short_path(value: str | None) -> str:
    if not value:
        return "unknown"
    return Path(value).name or value


def _cycle_stats(cycle_summary: dict[str, Any], settings: AppSettings) -> dict[str, str]:
    best_candidate = cycle_summary.get("best_candidate", {})
    best_metrics = best_candidate.get("metrics", {})
    best_scoring = best_candidate.get("scoring", {})
    best_robustness = best_candidate.get("robustness", {})
    best_validation = best_candidate.get("validation", {})
    strategist = cycle_summary.get("strategist", {})
    champion_pnl = float(cycle_summary.get("champion_pnl", 0.0))
    champion_validation_score = float(cycle_summary.get("champion_validation_score", 0.0))
    best_pnl = float(best_metrics.get("total_pnl", 0.0))
    pnl_delta = best_pnl - champion_pnl
    llm_status = cycle_summary.get("llm_status", {})
    llm_mode = llm_status.get("mode")
    if not llm_mode:
        llm_mode = "live" if settings.llm.allow_live_requests and settings.openai_api_key else "off"
    llm_budget = ""
    if llm_status:
        llm_budget = (
            f" (${llm_status.get('remaining_usd', 0.0):.2f} left / "
            f"${llm_status.get('daily_budget_usd', 0.0):.2f})"
        )
    discord_mode = "enabled" if settings.discord.enabled else "disabled"
    per_product = best_metrics.get("per_product_pnl", {})
    emr = _fmt_number(per_product.get("EMR", {}).get("SUB"))
    tom = _fmt_number(per_product.get("TOM", {}).get("SUB"))
    candidate_budget = cycle_summary.get("candidate_budget", {})
    bucket_counts = cycle_summary.get("candidate_bucket_counts", {})
    family_lab_profiles = cycle_summary.get("family_lab_profiles_tried", [])
    expert_profiles = cycle_summary.get("expert_builder_profiles_tried", [])
    family_jump_profiles = cycle_summary.get("family_jump_profiles_tried", [])
    plateau = cycle_summary.get("plateau_state", {})
    recent_performance = cycle_summary.get("recent_performance", {})
    bucket_scores = recent_performance.get("bucket_scores", {})
    family_lab_line = ", ".join(f"`{profile}`" for profile in family_lab_profiles[:4]) if family_lab_profiles else "`none`"
    expert_line = ", ".join(f"`{profile}`" for profile in expert_profiles[:4]) if expert_profiles else "`none`"
    family_jump_line = ", ".join(f"`{profile}`" for profile in family_jump_profiles[:4]) if family_jump_profiles else "`none`"
    adaptive_line = ", ".join(
        f"`{bucket}:{score:.2f}`"
        for bucket, score in sorted(bucket_scores.items(), key=lambda item: item[1], reverse=True)[:4]
    ) or "`none`"

    return {
        "strategy": strategist.get("thesis", "no strategist thesis recorded."),
        "pnl_compare": (
            f"candidate `{best_candidate.get('strategy_id', 'unknown')}`: `{_fmt_number(best_pnl)}`\n"
            f"champion `{cycle_summary.get('champion_before', 'unknown')}`: `{_fmt_number(champion_pnl)}`\n"
            f"delta: `{_fmt_delta(pnl_delta)}`\n"
            f"validation: `{best_validation.get('score', 0.0):.3f}` vs champ `{champion_validation_score:.3f}`"
        ),
        "stats": (
            f"trades: `{_fmt_number(best_metrics.get('own_trade_count'))}`\n"
            f"emr: `{emr}` | tom: `{tom}`\n"
            f"robustness: `{best_robustness.get('score', 0.0):.3f}`\n"
            f"validation: `{best_validation.get('score', 0.0):.3f}`\n"
            f"score: `{best_scoring.get('score', 0.0):.3f}`\n"
            f"plagiarism: `{best_candidate.get('plagiarism', {}).get('max_score', 0.0):.3f}`\n"
            f"candidates: `{cycle_summary.get('candidate_count', 0)}`\n"
            f"screened/full: `{cycle_summary.get('screened_candidate_count', 0)} / {cycle_summary.get('full_evaluation_count', 0)}`\n"
            f"search: `x{candidate_budget.get('exploit', 0)} e{candidate_budget.get('explore', 0)} "
            f"s{candidate_budget.get('structural', 0)} j{candidate_budget.get('family_jump', 0)} "
            f"l{candidate_budget.get('family_lab', 0)} b{candidate_budget.get('expert_builder', 0)} "
            f"t{candidate_budget.get('survivor_tune', 0)}`\n"
            f"dedupe blocked: `{cycle_summary.get('duplicates_blocked', 0)}`\n"
            f"eval mix: `exp {bucket_counts.get('exploit', 0)} | exr {bucket_counts.get('explore', 0)} | "
            f"str {bucket_counts.get('structural', 0)} | jump {bucket_counts.get('family_jump', 0)} | "
            f"lab {bucket_counts.get('family_lab', 0)} | builder {bucket_counts.get('expert_builder', 0)}`"
        ),
        "algo_search": (
            f"adaptive frontier:\n{adaptive_line}\n"
            f"family lab:\n{family_lab_line}\n"
            f"expert builder:\n{expert_line}\n"
            f"family jumps:\n{family_jump_line}"
        ),
        "health": (
            f"db: `ok`\n"
            f"backtester: `ok`\n"
            f"llm: `{llm_mode}{llm_budget}`\n"
            f"discord: `{discord_mode}`\n"
            f"ingested: `{cycle_summary.get('ingested_documents', 0)}`\n"
            f"plateau: `{'on' if plateau.get('active') else 'off'}`"
        ),
    }


def render_cycle_summary_message(cycle_summary: dict[str, Any], settings: AppSettings) -> str:
    stats = _cycle_stats(cycle_summary, settings)
    decision = str(cycle_summary.get("decision", "unknown")).upper()
    return "\n".join(
        [
            f"loop {cycle_summary.get('iteration')} | session `{cycle_summary.get('session_name')}` | decision `{decision}`",
            f"strategy: {stats['strategy']}",
            f"pnl:\n{stats['pnl_compare']}",
            f"stats:\n{stats['stats']}",
            f"health:\n{stats['health']}",
        ]
    )


def build_cycle_summary_payload(cycle_summary: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    stats = _cycle_stats(cycle_summary, settings)
    decision = str(cycle_summary.get("decision", "unknown")).upper()
    best_candidate = cycle_summary.get("best_candidate", {})
    reason = str(cycle_summary.get("reason", ""))
    mention_user_id = settings.discord.promote_ping_user_id
    should_ping = str(cycle_summary.get("decision", "")).lower() == "promote" and bool(mention_user_id)
    content = f"<@{mention_user_id}>" if should_ping and mention_user_id else None
    allowed_mentions: dict[str, list[str]] = {"parse": []}
    if should_ping and mention_user_id:
        allowed_mentions = {"users": [mention_user_id]}
    embed = {
        "title": f"prosperity loop #{cycle_summary.get('iteration')}",
        "description": (
            f"session `{cycle_summary.get('session_name')}`\n"
            f"decision `{decision}`\n"
            f"best candidate `{best_candidate.get('strategy_id', 'unknown')}`"
        ),
        "color": _decision_color(str(cycle_summary.get("decision", "unknown"))),
        "fields": [
            {
                "name": "strategy",
                "value": stats["strategy"][:1024],
                "inline": False,
            },
            {
                "name": "pnl vs champion",
                "value": stats["pnl_compare"][:1024],
                "inline": True,
            },
            {
                "name": "stats",
                "value": stats["stats"][:1024],
                "inline": True,
            },
            {
                "name": "algo search",
                "value": stats["algo_search"][:1024],
                "inline": True,
            },
            {
                "name": "system health",
                "value": stats["health"][:1024],
                "inline": True,
            },
            {
                "name": "reason",
                "value": reason[:1024] if reason else "no additional reason recorded",
                "inline": False,
            },
        ],
        "footer": {
            "text": f"champion: {cycle_summary.get('champion_before', 'unknown')} -> {cycle_summary.get('champion_after', 'unknown')}",
        },
        "timestamp": _now_iso(),
    }
    return {
        "content": content,
        "embeds": [embed],
        "allowed_mentions": allowed_mentions,
    }


def send_cycle_summary_message(cycle_summary: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    return _send_payload(build_cycle_summary_payload(cycle_summary, settings), settings)


def _quant_eval_line(evaluation: dict[str, Any] | None) -> str:
    if not evaluation:
        return "`none`"
    pnl = _fmt_number(evaluation.get("total_pnl"))
    trades = _fmt_number(evaluation.get("own_trade_count"))
    return f"`{_short_path(evaluation.get('path'))}`\npnl: `{pnl}`\ntrades: `{trades}`"


def _quant_delta(best_candidate: dict[str, Any] | None, champion: dict[str, Any] | None) -> float | None:
    if not best_candidate or not champion:
        return None
    best_pnl = best_candidate.get("total_pnl")
    champion_pnl = champion.get("total_pnl")
    if best_pnl is None or champion_pnl is None:
        return None
    return float(best_pnl) - float(champion_pnl)


def _quant_stats(summary: dict[str, Any], settings: AppSettings) -> dict[str, str]:
    alpha = summary.get("alpha", {})
    top_signals = alpha.get("top_signals", [])
    top_signal = top_signals[0] if top_signals else {}
    budget = summary.get("budget", {})
    git = summary.get("git", {})
    champion = summary.get("champion")
    best_candidate = summary.get("best_candidate")
    delta = _quant_delta(best_candidate, champion)
    discord_mode = "enabled" if settings.discord.enabled else "disabled"
    git_error = git.get("error")
    git_status = "ok" if not git_error else f"error: {git_error}"

    alpha_line = "no alpha signal recorded"
    if top_signal:
        alpha_line = (
            f"`{top_signal.get('product', 'unknown')}` `{top_signal.get('feature', 'unknown')}` "
            f"h=`{top_signal.get('horizon', 'n/a')}`\n"
            f"corr: `{float(top_signal.get('correlation', 0.0)):.4f}` | "
            f"acc: `{float(top_signal.get('directional_accuracy', 0.0)):.3f}` | "
            f"score: `{float(top_signal.get('score', 0.0)):.4f}`"
        )

    best_line = _quant_eval_line(best_candidate)
    champion_line = _quant_eval_line(champion)
    champion_path = champion.get("path") if isinstance(champion, dict) else None
    champion_origin = "round1-derived seed" if champion_path and "round1" in champion_path.lower() else "round2/native or configured"
    delta_line = "n/a" if delta is None else _fmt_delta(delta)

    return {
        "champion": f"{champion_line}\norigin: `{champion_origin}`\ndataset: `{summary.get('dataset', 'unknown')}`",
        "pnl_compare": f"candidate:\n{best_line}\nchampion pnl delta: `{delta_line}`",
        "alpha": alpha_line,
        "search": (
            f"git commits: `{len(git.get('commits', []))}`\n"
            f"git strategy files: `{len(git.get('candidate_strategy_files', []))}`\n"
            f"budget git/raw/champ/struct: "
            f"`{float(budget.get('git_fraction', 0.0)):.2f}/"
            f"{float(budget.get('raw_alpha_fraction', 0.0)):.2f}/"
            f"{float(budget.get('champion_fraction', 0.0)):.2f}/"
            f"{float(budget.get('structural_fraction', 0.0)):.2f}`\n"
            f"tests git direct/variant/alpha: "
            f"`{budget.get('direct_git_tests', 0)}/"
            f"{budget.get('git_variant_tests', 0)}/"
            f"{budget.get('alpha_strategy_tests', 0)}`"
        ),
        "health": (
            f"db: `ok`\n"
            f"backtester: `ok`\n"
            f"git: `{git_status}`\n"
            f"discord: `{discord_mode}`\n"
            f"rows analyzed: `{alpha.get('rows_analyzed', 0)}`\n"
            f"report: `{_short_path(summary.get('report_path'))}`"
        ),
    }


def render_quant_summary_message(summary: dict[str, Any], settings: AppSettings) -> str:
    stats = _quant_stats(summary, settings)
    decision = str(summary.get("decision", "unknown")).upper()
    return "\n".join(
        [
            f"quant loop {summary.get('iteration')} | session `{summary.get('session_name')}` | decision `{decision}`",
            f"dataset: `{summary.get('dataset')}`",
            f"champion:\n{stats['champion']}",
            f"candidate:\n{stats['pnl_compare']}",
            f"alpha:\n{stats['alpha']}",
            f"health:\n{stats['health']}",
        ]
    )


def build_quant_summary_payload(summary: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    stats = _quant_stats(summary, settings)
    decision = str(summary.get("decision", "unknown")).upper()
    reason = str(summary.get("reason", ""))
    mention_user_id = settings.discord.promote_ping_user_id
    should_ping = str(summary.get("decision", "")).lower() == "promote" and bool(mention_user_id)
    content = f"<@{mention_user_id}>" if should_ping and mention_user_id else None
    allowed_mentions: dict[str, list[str]] = {"parse": []}
    if should_ping and mention_user_id:
        allowed_mentions = {"users": [mention_user_id]}

    embed = {
        "title": f"ai quant loop #{summary.get('iteration')}",
        "description": (
            f"session `{summary.get('session_name')}`\n"
            f"dataset `{summary.get('dataset')}`\n"
            f"decision `{decision}`"
        ),
        "color": _decision_color(str(summary.get("decision", "unknown"))),
        "fields": [
            {
                "name": "current champion",
                "value": stats["champion"][:1024],
                "inline": True,
            },
            {
                "name": "candidate vs champion",
                "value": stats["pnl_compare"][:1024],
                "inline": True,
            },
            {
                "name": "top alpha found",
                "value": stats["alpha"][:1024],
                "inline": False,
            },
            {
                "name": "search budget",
                "value": stats["search"][:1024],
                "inline": True,
            },
            {
                "name": "system health",
                "value": stats["health"][:1024],
                "inline": True,
            },
            {
                "name": "reason",
                "value": reason[:1024] if reason else "no additional reason recorded",
                "inline": False,
            },
        ],
        "footer": {
            "text": f"cycle: {summary.get('cycle_id', 'unknown')}",
        },
        "timestamp": _now_iso(),
    }
    return {
        "content": content,
        "embeds": [embed],
        "allowed_mentions": allowed_mentions,
    }


def send_quant_summary_message(summary: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    return _send_payload(build_quant_summary_payload(summary, settings), settings)


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + "..."


def _short_product_name(product: str) -> str:
    return (
        product.replace("ASH_COATED_OSMIUM", "ASH")
        .replace("INTARIAN_PEPPER_ROOT", "PEPPER")
        .replace("DRYLAND_FLAX", "FLAX")
        .replace("EMBER_MUSHROOM", "MUSH")
    )


def _product_pnl_line(product_pnl: dict[str, Any]) -> str:
    if not product_pnl:
        return "no product pnl"
    items = sorted(product_pnl.items(), key=lambda item: abs(float(item[1])), reverse=True)
    return " | ".join(f"{_short_product_name(product)} `{_fmt_number(float(pnl))}`" for product, pnl in items[:4])


def _research_day_line(day_score: dict[str, Any]) -> str:
    return (
        f"{day_score.get('label', 'day')} pnl `{_fmt_number(float(day_score.get('pnl', 0.0)))}` "
        f"tr `{int(day_score.get('own_trades', 0))}` "
        f"[{_product_pnl_line(day_score.get('product_pnl', {}))}]"
    )


def _research_days_line(day_scores: list[dict[str, Any]]) -> str:
    if not day_scores:
        return "`none`"
    return "\n".join(_research_day_line(day_score) for day_score in day_scores[:5])


def _research_score_line(score: dict[str, Any] | None, *, include_days: bool = False) -> str:
    if not score:
        return "`none`"
    if score.get("status") != "ok":
        return f"`error`: {str(score.get('error') or 'unknown')[:180]}"
    lines = [
        f"score: `{float(score.get('score', 0.0)):.1f}`\n"
        f"train: `{float(score.get('train_mean', 0.0)):.1f}` | "
        f"validation: `{float(score.get('validation_mean', 0.0)):.1f}`\n"
        f"stress: `{float(score.get('stress_mean', 0.0)):.1f}` | "
        f"worst: `{float(score.get('worst_day_pnl', 0.0)):.1f}`\n"
        f"trades: `{int(score.get('own_trade_count', 0))}` | "
        f"concentration: `{float(score.get('product_concentration', 0.0)):.3f}`\n"
        f"train-val gap: `{float(score.get('train_validation_gap', 0.0)):.1f}` | "
        f"stress gap: `{float(score.get('stress_gap', 0.0)):.1f}`\n"
        f"stability: `{float(score.get('stability', 0.0)):.3f}`"
    ]
    if include_days:
        lines.append(f"days:\n{_research_days_line(score.get('day_scores', []))}")
        lines.append(f"stress days:\n{_research_days_line(score.get('stress_day_scores', []))}")
    return _truncate("\n".join(lines), 1024)


def _research_delta(candidate_score: dict[str, Any] | None, champion_score: dict[str, Any] | None) -> float | None:
    if not candidate_score or not champion_score:
        return None
    if candidate_score.get("status") != "ok" or champion_score.get("status") != "ok":
        return None
    return float(candidate_score.get("score", 0.0)) - float(champion_score.get("score", 0.0))


def _research_changes_line(recipe: dict[str, Any]) -> str:
    changes = recipe.get("changes", {})
    if not changes:
        return "`none`"
    return f"`{_truncate(json.dumps(changes, sort_keys=True), 280)}`"


def _autoresearch_experiment_field(
    experiment: dict[str, Any],
    champion_score: dict[str, Any] | None,
    index: int,
) -> dict[str, Any]:
    recipe = experiment.get("recipe", {})
    score = experiment.get("score")
    delta = _research_delta(score, champion_score if isinstance(champion_score, dict) else None)
    delta_line = "`n/a`" if delta is None else f"`{_fmt_delta(delta)}`"
    value = "\n".join(
        [
            f"kind: `{recipe.get('kind', 'unknown')}` | decision: `{experiment.get('decision', 'unknown')}`",
            f"score delta vs champion: {delta_line}",
            f"path: `{_short_path(experiment.get('path'))}`",
            f"changes: {_research_changes_line(recipe)}",
            f"gate: {_truncate(str(experiment.get('reason') or 'no reason'), 180)}",
            _research_score_line(score if isinstance(score, dict) else None, include_days=True),
        ]
    )
    return {
        "name": _truncate(f"{index}. {recipe.get('name', 'unknown')}", 256),
        "value": _truncate(value, 1024),
        "inline": False,
    }


def _autoresearch_stats(summary: dict[str, Any], settings: AppSettings) -> dict[str, str]:
    best = summary.get("best_experiment") or {}
    best_score = best.get("score") if isinstance(best, dict) else None
    champion_score = summary.get("champion_score")
    recipes = summary.get("experiments", [])
    ok_count = sum(1 for experiment in recipes if (experiment.get("score") or {}).get("status") == "ok")
    delta = None
    if isinstance(best_score, dict) and isinstance(champion_score, dict):
        if best_score.get("status") == "ok" and champion_score.get("status") == "ok":
            delta = float(best_score.get("score", 0.0)) - float(champion_score.get("score", 0.0))
    delta_line = "`n/a`" if delta is None else f"`{_fmt_delta(delta)}`"
    discord_mode = "enabled" if settings.discord.enabled else "disabled"
    best_recipe = best.get("recipe", {}) if isinstance(best, dict) else {}
    best_name = best_recipe.get("name", "none") if isinstance(best_recipe, dict) else "none"
    best_kind = best_recipe.get("kind", "unknown") if isinstance(best_recipe, dict) else "unknown"
    return {
        "champion": f"`{_short_path(summary.get('champion_path'))}`\n{_research_score_line(champion_score, include_days=True)}",
        "best": (
            f"recipe: `{best_name}`\n"
            f"kind: `{best_kind}`\n"
            f"score delta: {delta_line}\n"
            f"path: `{_short_path(best.get('path') if isinstance(best, dict) else None)}`\n"
            f"{_research_score_line(best_score, include_days=True)}"
        ),
        "research": (
            f"experiments: `{len(recipes)}`\n"
            f"valid evals: `{ok_count}`\n"
            f"dataset: `{summary.get('dataset', 'unknown')}`\n"
            f"reporting: `{'files + discord' if settings.autoresearch.write_reports else 'discord-only'}`"
        ),
        "health": (
            f"db: `ok`\n"
            f"backtester: `ok`\n"
            f"discord: `{discord_mode}`\n"
            f"locked evaluator: `train/validation/stress`"
        ),
    }


def render_autoresearch_summary_message(summary: dict[str, Any], settings: AppSettings) -> str:
    stats = _autoresearch_stats(summary, settings)
    decision = str(summary.get("decision", "unknown")).upper()
    experiment_lines = [
        f"{field['name']}\n{field['value']}"
        for field in [
            _autoresearch_experiment_field(experiment, summary.get("champion_score"), idx)
            for idx, experiment in enumerate(summary.get("experiments", []), start=1)
        ]
    ]
    return "\n".join(
        [
            f"autoresearch loop {summary.get('iteration')} | session `{summary.get('session_name')}` | decision `{decision}`",
            f"champion:\n{stats['champion']}",
            f"best experiment:\n{stats['best']}",
            f"research:\n{stats['research']}",
            f"all experiments:\n{chr(10).join(experiment_lines) if experiment_lines else 'none'}",
            f"health:\n{stats['health']}",
            f"reason: {summary.get('reason', 'none')}",
        ]
    )


def build_autoresearch_summary_payload(summary: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    stats = _autoresearch_stats(summary, settings)
    decision = str(summary.get("decision", "unknown")).upper()
    reason = str(summary.get("reason", ""))
    mention_user_id = settings.discord.promote_ping_user_id
    should_ping = str(summary.get("decision", "")).lower() == "promote" and bool(mention_user_id)
    content = f"<@{mention_user_id}>" if should_ping and mention_user_id else None
    allowed_mentions: dict[str, list[str]] = {"parse": []}
    if should_ping and mention_user_id:
        allowed_mentions = {"users": [mention_user_id]}

    embeds: list[dict[str, Any]] = []
    summary_embed = {
        "title": f"autoresearch loop #{summary.get('iteration')}",
        "description": (
            f"session `{summary.get('session_name')}`\n"
            f"dataset `{summary.get('dataset')}`\n"
            f"decision `{decision}`"
        ),
        "color": _decision_color(str(summary.get("decision", "unknown"))),
        "fields": [
            {
                "name": "current champion",
                "value": stats["champion"][:1024],
                "inline": True,
            },
            {
                "name": "best experiment",
                "value": stats["best"][:1024],
                "inline": True,
            },
            {
                "name": "research run",
                "value": stats["research"][:1024],
                "inline": True,
            },
            {
                "name": "system health",
                "value": stats["health"][:1024],
                "inline": True,
            },
            {
                "name": "reason",
                "value": reason[:1024] if reason else "no additional reason recorded",
                "inline": False,
            },
        ],
        "footer": {
            "text": f"cycle: {summary.get('cycle_id', 'unknown')}",
        },
        "timestamp": _now_iso(),
    }
    embeds.append(summary_embed)

    experiment_fields = [
        _autoresearch_experiment_field(experiment, summary.get("champion_score"), index)
        for index, experiment in enumerate(summary.get("experiments", []), start=1)
    ]
    for chunk_index in range(0, len(experiment_fields), 5):
        chunk = experiment_fields[chunk_index : chunk_index + 5]
        embeds.append(
            {
                "title": f"autoresearch experiments {chunk_index + 1}-{chunk_index + len(chunk)}",
                "color": _decision_color(str(summary.get("decision", "unknown"))),
                "fields": chunk,
                "footer": {
                    "text": f"cycle: {summary.get('cycle_id', 'unknown')}",
                },
                "timestamp": _now_iso(),
            }
        )
        if len(embeds) >= 10:
            break
    if len(experiment_fields) > 45 and len(embeds) == 10:
        embeds[-1]["fields"].append(
            {
                "name": "truncated",
                "value": f"`{len(experiment_fields) - 45}` experiments omitted by Discord embed limits.",
                "inline": False,
            }
        )
    return {
        "content": content,
        "embeds": embeds,
        "allowed_mentions": allowed_mentions,
    }


def send_autoresearch_summary_message(summary: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    return _send_payload(build_autoresearch_summary_payload(summary, settings), settings)


def _send_payload(payload: dict[str, Any], settings: AppSettings) -> dict[str, Any]:
    if not settings.discord.enabled:
        return {"status": "skipped", "reason": "discord notifications disabled"}
    if not settings.discord.channel_id:
        return {"status": "skipped", "reason": "discord channel_id missing"}
    if not settings.discord.bot_token:
        return {"status": "skipped", "reason": "discord bot_token missing"}

    url = f"{settings.discord.api_base_url}/channels/{settings.discord.channel_id}/messages"
    headers = {
        "Authorization": f"Bot {settings.discord.bot_token}",
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=20.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return {"status": "error", "reason": str(exc)}
    data = response.json()
    return {
        "status": "sent",
        "message_id": data.get("id"),
        "channel_id": data.get("channel_id"),
    }
