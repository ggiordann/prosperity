from __future__ import annotations

from datetime import datetime, timezone
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
    if normalized == "promote":
        return 0x2ECC71
    if normalized == "shadow_promote":
        return 0x3498DB
    if normalized == "hold":
        return 0xF39C12
    return 0x95A5A6


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
    if not settings.discord.enabled:
        return {"status": "skipped", "reason": "discord notifications disabled"}
    if not settings.discord.channel_id:
        return {"status": "skipped", "reason": "discord channel_id missing"}
    if not settings.discord.bot_token:
        return {"status": "skipped", "reason": "discord bot_token missing"}

    payload = build_cycle_summary_payload(cycle_summary, settings)
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
