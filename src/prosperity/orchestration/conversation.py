from __future__ import annotations

import copy
import json
import random
import re
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from prosperity.backtester.runner import BacktesterRunner
from prosperity.db import DatabaseSession, ExperimentRepository
from prosperity.db.models import (
    ConversationCycleRecord,
    ConversationMessageRecord,
    MemoryNoteRecord,
)
from prosperity.dsl.crossover import crossover_specs
from prosperity.dsl.mutators import apply_structural_profile, family_component_mutation
from prosperity.dsl.normalization import normalized_spec_json
from prosperity.dsl.schema import ParameterDef, StrategySpec
from prosperity.evaluation.promotion import champion_challenger_decision
from prosperity.evaluation.screening import quick_screen_candidate
from prosperity.external.discord_notifier import send_cycle_summary_message
from prosperity.generation.expert_builder import build_expert_candidates
from prosperity.generation.family_registry import (
    FAMILY_BUILDERS,
    build_family_spec,
)
from prosperity.llm.budget import BudgetTracker
from prosperity.llm.client import LLMClient
from prosperity.orchestration.jobs import (
    compile_spec_to_artifact,
    evaluate_compiled_strategy,
    ingest_all,
    package_strategy,
    persist_strategy_record,
)
from prosperity.orchestration.locks import file_lock
from prosperity.paths import RepoPaths
from prosperity.settings import AppSettings, load_settings
from prosperity.utils import json_dumps, read_text, slugify, utcnow_iso

PROMPT_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts"
STRATEGIST_PROMPT = PROMPT_DIR / "conversation_strategist.md"
CRITIC_PROMPT = PROMPT_DIR / "conversation_critic.md"
POSTMORTEM_PROMPT = PROMPT_DIR / "conversation_postmortem.md"
FRONTIER_SEED_SPECS = {
    "tutorial_submission_candidate_alpha": {
        "strategy_id": "conversation-submission-alpha-seed",
        "name": "Conversation Submission Alpha Seed",
    },
    "tutorial_latent_book_reversion": {
        "strategy_id": "conversation-latent-book-seed",
        "name": "Conversation Latent Book Seed",
    },
    "tutorial_wall_mid_mm": {
        "strategy_id": "conversation-wall-mid-seed",
        "name": "Conversation Wall Mid Seed",
    },
    "tutorial_microprice_reversion": {
        "strategy_id": "conversation-microprice-seed",
        "name": "Conversation Microprice Seed",
    },
    "tutorial_pressure_momentum": {
        "strategy_id": "conversation-pressure-momentum-seed",
        "name": "Conversation Pressure Momentum Seed",
    },
    "tutorial_passive_queue_reversion": {
        "strategy_id": "conversation-passive-queue-seed",
        "name": "Conversation Passive Queue Seed",
    },
    "tutorial_gap_repricing": {
        "strategy_id": "conversation-gap-repricing-seed",
        "name": "Conversation Gap Repricing Seed",
    },
    "tutorial_trade_pressure_reversion": {
        "strategy_id": "conversation-trade-pressure-seed",
        "name": "Conversation Trade Pressure Seed",
    },
    "tutorial_volatility_breakout": {
        "strategy_id": "conversation-volatility-breakout-seed",
        "name": "Conversation Volatility Breakout Seed",
    },
    "tutorial_asymmetric_queue_hybrid": {
        "strategy_id": "conversation-asymmetric-queue-seed",
        "name": "Conversation Asymmetric Queue Seed",
    },
}
STRUCTURAL_PROFILES = [
    "low_turnover",
    "inventory_hardening",
    "signal_rotation",
    "aggressive_repricing",
]


def _with_repo(paths: RepoPaths, callback):
    with DatabaseSession(paths.db_dir / "prosperity.sqlite3") as db:
        repo = ExperimentRepository(db.connection)
        return callback(repo)


def _now() -> str:
    return utcnow_iso()


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _load_prompt(path: Path) -> str:
    return read_text(path).strip()


def _allowed_parameters(spec: StrategySpec) -> list[str]:
    return [parameter.name for parameter in spec.parameter_space]


def _param_def_map(spec: StrategySpec) -> dict[str, ParameterDef]:
    return {parameter.name: parameter for parameter in spec.parameter_space}


def _merge_parameter_spaces(left: list[ParameterDef], right: list[ParameterDef]) -> list[ParameterDef]:
    merged: dict[str, ParameterDef] = {}
    for parameter in left + right:
        merged[parameter.name] = copy.deepcopy(parameter)
    return list(merged.values())


def _blend_spec_components(
    base: StrategySpec,
    *,
    fair_from: StrategySpec | None = None,
    signal_from: StrategySpec | None = None,
    execution_from: StrategySpec | None = None,
    risk_from: StrategySpec | None = None,
    parameter_sources: list[StrategySpec] | None = None,
) -> StrategySpec:
    blended = copy.deepcopy(base)
    if fair_from is not None:
        blended.fair_value_models = copy.deepcopy(fair_from.fair_value_models)
    if signal_from is not None:
        blended.signal_models = copy.deepcopy(signal_from.signal_models)
    if execution_from is not None:
        blended.execution_policy = copy.deepcopy(execution_from.execution_policy)
    if risk_from is not None:
        blended.risk_policy = copy.deepcopy(risk_from.risk_policy)

    merged = list(blended.parameter_space)
    for source in parameter_sources or []:
        merged = _merge_parameter_spaces(merged, source.parameter_space)
    blended.parameter_space = merged
    return blended


def _spec_from_row(row) -> StrategySpec:
    return StrategySpec.model_validate_json(row["spec_json"])


def _evaluation_from_row(row) -> dict:
    payload = json.loads(row["metrics_json"])
    return {
        "metrics": payload.get("metrics", {}),
        "robustness": payload.get("robustness", {}),
        "validation": payload.get("validation", {}),
        "scoring": payload.get("scoring", {}),
        "plagiarism": payload.get("plagiarism", {}),
        "behavior_fingerprint": payload.get("behavior_fingerprint", {}),
        "critique": payload.get("critique", {}),
    }


def _strategy_entry(spec: StrategySpec, compiled_path: Path, evaluation: dict) -> dict[str, Any]:
    metrics = evaluation.get("metrics", {})
    scoring = evaluation.get("scoring", {})
    validation = evaluation.get("validation", {})
    return {
        "strategy_id": spec.metadata.id,
        "family": spec.metadata.family,
        "name": spec.metadata.name,
        "spec": spec,
        "compiled_path": compiled_path,
        "evaluation": evaluation,
        "pnl": float(metrics.get("total_pnl", 0.0)),
        "validation_score": float(validation.get("score", 0.0)),
        "score": float(scoring.get("score", 0.0)),
    }


def _frontier_brief(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": entry["strategy_id"],
            "family": entry["family"],
            "pnl": entry["pnl"],
            "validation_score": entry.get("validation_score", 0.0),
            "score": entry["score"],
        }
        for entry in entries
    ]


def _next_current_best_version(paths: RepoPaths) -> int:
    export_dir = paths.root / "current_best_algo"
    export_dir.mkdir(parents=True, exist_ok=True)
    versions: list[int] = []
    for search_root in (export_dir, paths.root):
        for candidate in search_root.glob("current_best_V*.py"):
            match = re.fullmatch(r"current_best_V(\d+)\.py", candidate.name)
            if match:
                versions.append(int(match.group(1)))
    return (max(versions) + 1) if versions else 1


def _export_current_best(paths: RepoPaths, source_path: Path) -> Path:
    export_dir = paths.root / "current_best_algo"
    export_dir.mkdir(parents=True, exist_ok=True)
    version = _next_current_best_version(paths)
    target = export_dir / f"current_best_V{version}.py"
    target.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    return target


def _normalize_plan(payload: dict, allowed_parameters: list[str], max_candidates: int) -> dict:
    allowed = set(allowed_parameters)
    focus = [name for name in payload.get("focus_parameters", []) if name in allowed]
    if not focus:
        focus = [name for name in allowed_parameters if "tomato" in name or name in {"fair_alpha_scale", "gap_weight", "second_imb_weight"}][:4]
    directions = {}
    for name in focus:
        direction = str(payload.get("directions", {}).get(name, "neutral")).lower()
        if direction not in {"up", "down", "neutral"}:
            direction = "neutral"
        directions[name] = direction
    candidate_count = int(payload.get("candidate_count", max_candidates))
    candidate_count = max(2, min(max_candidates, candidate_count))
    return {
        "thesis": str(payload.get("thesis", "Probe a small local hill-climb around the current champion.")),
        "focus_parameters": focus,
        "directions": directions,
        "candidate_count": candidate_count,
        "guardrails": [str(item) for item in payload.get("guardrails", [])][:6],
        "reasoning": str(payload.get("reasoning", "")),
    }


def _heuristic_plan(
    spec: StrategySpec,
    memory_notes: list[dict],
    iteration: int,
    max_candidates: int,
    plateau_state: dict[str, Any] | None = None,
) -> dict:
    available = _allowed_parameters(spec)
    plateau_active = bool(plateau_state and plateau_state.get("active"))
    preferred_groups = [
        [
            "fair_alpha_scale",
            "second_imb_weight",
            "gap_weight",
            "ret1_weight",
            "micro_weight",
            "tomato_take_width",
        ],
        [
            "taking_min_edge",
            "inventory_skew",
            "layer_offset_scale",
            "layer_size_scale",
            "clear_width",
            "signal_scale",
        ],
    ]
    focus: list[str] = []
    for group in preferred_groups:
        focus.extend([name for name in group if name in available])
        if len(focus) >= 4:
            break
    if len(focus) < 4:
        ranked = [
            name
            for name in available
            if any(token in name for token in ("weight", "edge", "inventory", "layer", "clear", "signal", "alpha", "take"))
        ]
        focus.extend([name for name in ranked if name not in focus])
    if not focus:
        focus = available[:4]
    focus = focus[:6]
    if iteration % 3 == 0:
        focus = [name for name in focus if name not in {"fair_alpha_scale", "second_imb_weight"}]
        focus = (focus + [name for name in ["quote_aggression", "take_extra", "taking_min_edge", "clear_width"] if name in available])[:4]
    if plateau_active:
        focus = [
            name
            for name in [
                "taking_min_edge",
                "signal_scale",
                "inventory_skew",
                "layer_offset_scale",
                "layer_size_scale",
                "quote_aggression",
                "clear_width",
                "fair_alpha_scale",
            ]
            if name in available
        ][:6]
    note_text = " ".join(note["content"] for note in memory_notes[:4]).lower()
    defensive = any(token in note_text for token in ("aggressive", "inventory", "drawdown", "worse"))
    directions = {name: "neutral" for name in focus}
    for name in focus:
        if any(token in name for token in ("inventory", "clear", "edge", "offset")):
            directions[name] = "up" if defensive else "down"
        elif any(token in name for token in ("size_scale", "max_size", "aggression", "signal_scale")):
            directions[name] = "down" if defensive else "up"
        elif "weight" in name or "alpha" in name:
            directions[name] = "down" if defensive else "up"
    thesis = "Search locally around the current family edge while keeping EMERALDS stable and forcing at least some structural exploration."
    reasoning = "Use recent postmortems to alternate between more aggressive and more defensive local search while preserving room for family jumps."
    guardrails = [
        "Do not disturb EMERALDS unless the change is tiny.",
        "Keep turnover bounded and force at least one alternate-family probe.",
    ]
    candidate_count = max(3, min(max_candidates, 6))
    if plateau_active:
        thesis = (
            "Plateau detected: push budget into materially different algorithms, especially family jumps, "
            "execution shell swaps, and Codex-built hybrid archetypes."
        )
        reasoning = (
            "Repeated near-duplicate hold cycles mean the search must escape the current local basin. "
            "Prefer families with different fill profiles and signal mixes over another small TOM execution tweak."
        )
        guardrails = [
            "Spend most of the cycle on alternate families and expert-built hybrids.",
            "Avoid rebuilding the same low-edge defensive tweak that already stalled.",
        ]
        candidate_count = max(5, min(max_candidates, 8))
    return {
        "thesis": thesis,
        "focus_parameters": focus,
        "directions": directions,
        "candidate_count": candidate_count,
        "guardrails": guardrails,
        "reasoning": reasoning,
    }


def _normalize_critic(payload: dict, allowed_parameters: list[str]) -> dict:
    allowed = set(allowed_parameters)
    avoid_parameters = [name for name in payload.get("avoid_parameters", []) if name in allowed]
    stress_bias = str(payload.get("stress_bias", "balanced")).lower()
    if stress_bias not in {"more_defensive", "balanced", "more_aggressive"}:
        stress_bias = "balanced"
    return {
        "main_risks": [str(item) for item in payload.get("main_risks", [])][:6],
        "avoid_parameters": avoid_parameters,
        "guardrails": [str(item) for item in payload.get("guardrails", [])][:6],
        "stress_bias": stress_bias,
        "reasoning": str(payload.get("reasoning", "")),
    }


def _heuristic_critic(plan: dict) -> dict:
    focus = set(plan["focus_parameters"])
    avoid: list[str] = []
    risks: list[str] = []
    if {"quote_aggression", "tomato_take_width", "take_extra"} & focus:
        risks.append("Execution parameters can improve fast but often cause adverse selection when moved too far.")
    if {"fair_alpha_scale", "second_imb_weight", "gap_weight"} & focus:
        risks.append("Signal scaling can overfit the tutorial regime if the mutation is too directional.")
    if not risks:
        risks.append("Keep changes local and prefer stability over novelty spikes.")
    if "emeralds_quote_size" in focus:
        avoid.append("emeralds_quote_size")
    return {
        "main_risks": risks,
        "avoid_parameters": avoid,
        "guardrails": [
            "Keep EMERALDS mostly unchanged.",
            "Do not push more than a small fraction of the parameter range in one cycle.",
        ],
        "stress_bias": "balanced",
        "reasoning": "The current champion already has a good local edge; avoid over-rotating into high-variance execution.",
    }


def _normalize_postmortem(payload: dict) -> dict:
    result = str(payload.get("result", "flat")).lower()
    if result not in {"win", "loss", "flat"}:
        result = "flat"
    tags = [str(item) for item in payload.get("tags", [])][:6]
    return {
        "result": result,
        "lesson": str(payload.get("lesson", "")),
        "next_hint": str(payload.get("next_hint", "")),
        "tags": tags,
    }


def _heuristic_postmortem(candidate_id: str, candidate_pnl: float, champion_pnl: float) -> dict:
    if candidate_pnl > champion_pnl:
        return {
            "result": "win",
            "lesson": f"{candidate_id} improved the champion by {candidate_pnl - champion_pnl:.1f} submission PnL.",
            "next_hint": "Keep the same family and explore a narrower neighborhood around the winning parameter shifts.",
            "tags": ["promotion_candidate", "local_hill_climb"],
        }
    if candidate_pnl < champion_pnl:
        return {
            "result": "loss",
            "lesson": f"{candidate_id} underperformed the champion by {champion_pnl - candidate_pnl:.1f} submission PnL.",
            "next_hint": "Retreat toward smaller parameter moves or a more defensive execution profile.",
            "tags": ["regression", "execution_risk"],
        }
    return {
        "result": "flat",
        "lesson": f"{candidate_id} was effectively flat to the champion on submission PnL.",
        "next_hint": "Prefer a structural mutation next cycle instead of another tiny jitter.",
        "tags": ["flat", "search_plateau"],
    }


def _llm_role_json(
    settings: AppSettings,
    paths: RepoPaths,
    role: str,
    prompt_path: Path,
    context: str,
    model: str,
) -> dict | None:
    if not settings.conversation.use_llm_roles:
        return None
    if not settings.llm.allow_live_requests or not settings.openai_api_key:
        return None
    prompt = f"{_load_prompt(prompt_path)}\n\n{context}".strip()
    try:
        client = LLMClient(settings, paths.caches)
        return client.generate_json(role, prompt, model=model)
    except Exception:
        return None


def _llm_runtime_status(
    settings: AppSettings,
    paths: RepoPaths,
    strategist_plan: dict[str, Any] | None = None,
    critic_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not settings.conversation.use_llm_roles:
        return {"mode": "disabled", "spent_usd": 0.0, "remaining_usd": 0.0, "daily_budget_usd": 0.0}
    if not settings.llm.allow_live_requests or not settings.openai_api_key:
        return {"mode": "disabled", "spent_usd": 0.0, "remaining_usd": 0.0, "daily_budget_usd": settings.llm.daily_budget_usd}
    tracker = BudgetTracker(paths.caches / "llm_budget.json", settings.llm.daily_budget_usd)
    status = tracker.status()
    mode = "budget_exhausted" if status["exhausted"] else "live"
    if strategist_plan and critic_plan and (
        strategist_plan.get("source") != "llm" or critic_plan.get("source") != "llm"
    ):
        mode = "budget_exhausted" if status["exhausted"] else "fallback"
    status["mode"] = mode
    return status


def _strategist_turn(
    settings: AppSettings,
    paths: RepoPaths,
    champion_spec: StrategySpec,
    champion_eval: dict,
    frontier_entries: list[dict[str, Any]],
    candidate_budget: dict[str, int],
    memory_notes: list[dict],
    iteration: int,
    plateau_state: dict[str, Any],
    recent_performance: dict[str, dict[str, float]],
) -> dict:
    allowed = _allowed_parameters(champion_spec)
    memory_excerpt = [note["content"] for note in memory_notes[:6]]
    context = json_dumps(
        {
            "allowed_parameters": allowed,
            "champion_id": champion_spec.metadata.id,
            "champion_family": champion_spec.metadata.family,
            "champion_metrics": champion_eval.get("metrics", {}),
            "frontier": _frontier_brief(frontier_entries),
            "candidate_budget": candidate_budget,
            "recent_memory_notes": memory_excerpt,
            "iteration": iteration,
            "max_candidates": settings.conversation.max_candidates_per_cycle,
            "plateau_state": plateau_state,
            "recent_performance": recent_performance,
        }
    )
    payload = _llm_role_json(
        settings,
        paths,
        role="conversation_strategist",
        prompt_path=STRATEGIST_PROMPT,
        context=context,
        model=settings.llm.strategist_model,
    )
    if payload is None:
        plan = _heuristic_plan(
            champion_spec,
            memory_notes,
            iteration,
            settings.conversation.max_candidates_per_cycle,
            plateau_state=plateau_state,
        )
        plan["source"] = "heuristic"
        return plan
    plan = _normalize_plan(payload, allowed, settings.conversation.max_candidates_per_cycle)
    plan["source"] = "llm"
    return plan


def _critic_turn(
    settings: AppSettings,
    paths: RepoPaths,
    champion_spec: StrategySpec,
    frontier_entries: list[dict[str, Any]],
    plan: dict,
    champion_eval: dict,
    plateau_state: dict[str, Any],
    recent_performance: dict[str, dict[str, float]],
) -> dict:
    allowed = _allowed_parameters(champion_spec)
    context = json_dumps(
        {
            "allowed_parameters": allowed,
            "plan": plan,
            "frontier": _frontier_brief(frontier_entries),
            "champion_metrics": champion_eval.get("metrics", {}),
            "champion_scoring": champion_eval.get("scoring", {}),
            "plateau_state": plateau_state,
            "recent_performance": recent_performance,
        }
    )
    payload = _llm_role_json(
        settings,
        paths,
        role="conversation_critic",
        prompt_path=CRITIC_PROMPT,
        context=context,
        model=settings.llm.critic_model,
    )
    if payload is None:
        critique = _heuristic_critic(plan)
        critique["source"] = "heuristic"
        return critique
    critique = _normalize_critic(payload, allowed)
    critique["source"] = "llm"
    return critique


def _postmortem_turn(
    settings: AppSettings,
    paths: RepoPaths,
    candidate_result: dict,
    champion_pnl: float,
) -> dict:
    context = json_dumps(
        {
            "candidate_result": candidate_result,
            "champion_pnl": champion_pnl,
        }
    )
    payload = _llm_role_json(
        settings,
        paths,
        role="conversation_postmortem",
        prompt_path=POSTMORTEM_PROMPT,
        context=context,
        model=settings.llm.critic_model,
    )
    if payload is None:
        postmortem = _heuristic_postmortem(
            candidate_result["strategy_id"],
            float(candidate_result["metrics"]["total_pnl"]),
            champion_pnl,
        )
        postmortem["source"] = "heuristic"
        return postmortem
    postmortem = _normalize_postmortem(payload)
    postmortem["source"] = "llm"
    return postmortem


def _make_candidate_id(base_name: str, iteration: int, variant_index: int) -> str:
    return f"{slugify(base_name)}-c{iteration:03d}-v{variant_index:02d}-{uuid4().hex[:6]}"


def _budget_split(
    settings: AppSettings,
    requested_exploit_count: int,
    family_jump_cycle: bool,
    plateau_mode: bool,
    recent_performance: dict[str, dict[str, float]] | None = None,
) -> dict[str, int]:
    total = max(1, settings.conversation.max_candidates_per_cycle)
    available_for_other = max(0, total - 1)
    desired = {
        "explore": settings.conversation.explore_candidates,
        "structural": settings.conversation.structural_candidates,
        "family_jump": settings.conversation.family_jump_candidates,
        "family_lab": settings.conversation.family_lab_candidates,
        "expert_builder": settings.conversation.expert_builder_candidates,
        "survivor_tune": settings.conversation.survivor_tune_candidates,
    }
    if family_jump_cycle:
        desired["family_jump"] += 1
        desired["structural"] += 1
        desired["family_lab"] += 1
    if plateau_mode:
        desired["explore"] = max(desired["explore"], 1)
        desired["structural"] = max(desired["structural"], 3)
        desired["family_jump"] = max(desired["family_jump"], 3)
        desired["family_lab"] = max(desired["family_lab"], 3)
        desired["expert_builder"] = max(desired["expert_builder"], 4)
        desired["survivor_tune"] = 0
        requested_exploit_count = 1
    bucket_scores = (recent_performance or {}).get("bucket_scores", {})
    if bucket_scores and not plateau_mode:
        exploit_score = bucket_scores.get("exploit", 0.0)
        adaptive_buckets = [
            ("family_lab", bucket_scores.get("family_lab", 0.0)),
            ("expert_builder", bucket_scores.get("expert_builder", 0.0)),
            ("family_jump", bucket_scores.get("family_jump", 0.0)),
            ("structural", bucket_scores.get("structural", 0.0)),
            ("explore", bucket_scores.get("explore", 0.0)),
        ]
        adaptive_buckets.sort(key=lambda item: item[1], reverse=True)
        best_bucket, best_bucket_score = adaptive_buckets[0]
        if best_bucket != "exploit" and best_bucket_score > exploit_score + 0.05:
            desired[best_bucket] = min(total, desired[best_bucket] + 1)
            requested_exploit_count = max(1, requested_exploit_count - 1)

    allocations = {key: 0 for key in desired}
    if plateau_mode:
        order = ["expert_builder", "family_jump", "family_lab", "structural", "explore", "survivor_tune"]
    elif family_jump_cycle:
        order = ["family_jump", "family_lab", "structural", "explore", "expert_builder", "survivor_tune"]
    else:
        order = ["family_lab", "explore", "structural", "family_jump", "expert_builder", "survivor_tune"]
    remaining_other = available_for_other
    for key in order:
        allocation = min(desired[key], remaining_other)
        allocations[key] = allocation
        remaining_other -= allocation

    exploit = max(1, min(requested_exploit_count, total - sum(allocations.values())))
    leftover = total - (sum(allocations.values()) + exploit)
    if plateau_mode:
        allocations["expert_builder"] += max(0, leftover)
    elif family_jump_cycle:
        allocations["family_jump"] += max(0, leftover)
    else:
        allocations["family_lab"] += max(0, leftover)
    return {
        "total": (
            exploit
            + allocations["explore"]
            + allocations["structural"]
            + allocations["family_jump"]
            + allocations["family_lab"]
            + allocations["expert_builder"]
            + allocations["survivor_tune"]
        ),
        "exploit": exploit,
        "explore": allocations["explore"],
        "structural": allocations["structural"],
        "family_jump": allocations["family_jump"],
        "family_lab": allocations["family_lab"],
        "expert_builder": allocations["expert_builder"],
        "survivor_tune": allocations["survivor_tune"],
        "family_jump_cycle": int(family_jump_cycle),
        "plateau_mode": int(plateau_mode),
    }


def _project_plan_to_spec(
    plan: dict,
    spec: StrategySpec,
    memory_notes: list[dict],
    iteration: int,
    count: int,
) -> dict:
    allowed = set(_allowed_parameters(spec))
    focus = [name for name in plan["focus_parameters"] if name in allowed]
    directions = {name: plan["directions"].get(name, "neutral") for name in focus}
    if not focus:
        fallback = _heuristic_plan(spec, memory_notes, iteration, count)
        fallback["candidate_count"] = count
        return fallback
    projected = dict(plan)
    projected["focus_parameters"] = focus
    projected["directions"] = directions
    projected["candidate_count"] = count
    return projected


def _mutate_parameter(
    parameter: ParameterDef,
    direction: str,
    profile: str,
    rng: random.Random,
) -> float:
    span = parameter.upper - parameter.lower
    base_step = span * parameter.mutation_scale
    direction_value = {"up": 1.0, "down": -1.0, "neutral": 0.0}[direction]
    profile_multiplier = {
        "thesis": 1.00,
        "half_step": 0.55,
        "contrarian": -0.65,
        "defensive": 0.35,
        "jitter": 0.15,
    }.get(profile, 0.15)
    jitter = rng.uniform(-0.35, 0.35) * base_step
    proposed = parameter.default + direction_value * base_step * profile_multiplier + jitter
    return _clamp(proposed, parameter.lower, parameter.upper)


def _apply_profile_defaults(spec: StrategySpec, profile: str) -> None:
    parameter_map = _param_def_map(spec)
    if profile == "defensive":
        for name, direction in {
            "tomato_take_width": "up",
            "take_extra": "up",
            "quote_aggression": "down",
            "fair_alpha_scale": "down",
            "taking_min_edge": "up",
            "inventory_skew": "up",
            "layer_offset_scale": "up",
            "layer_size_scale": "down",
            "clear_width": "up",
            "signal_scale": "down",
        }.items():
            if name not in parameter_map:
                continue
            parameter = parameter_map[name]
            span = parameter.upper - parameter.lower
            step = span * parameter.mutation_scale * 0.5
            sign = 1.0 if direction == "up" else -1.0
            parameter.default = _clamp(parameter.default + sign * step, parameter.lower, parameter.upper)


def _apply_seeded_variation(spec: StrategySpec, iteration: int, salt: str) -> None:
    rng = random.Random(f"{spec.metadata.family}:{iteration}:{salt}")
    candidate_parameters = [
        "signal_scale",
        "reservation_bias",
        "layer_offset_scale",
        "layer_size_scale",
        "taking_min_edge",
        "taking_max_size",
        "inventory_skew",
        "clear_width",
        "quote_aggression",
        "take_extra",
        "fair_alpha_scale",
    ]
    selected = [name for name in candidate_parameters if name in _param_def_map(spec)]
    rng.shuffle(selected)
    for name in selected[:3]:
        parameter = _param_def_map(spec)[name]
        span = parameter.upper - parameter.lower
        jitter = rng.uniform(-0.8, 0.8) * span * parameter.mutation_scale
        parameter.default = _clamp(parameter.default + jitter, parameter.lower, parameter.upper)


def _mutate_candidates(
    champion_spec: StrategySpec,
    plan: dict,
    critique: dict,
    iteration: int,
    count: int,
    bucket: str,
) -> list[dict[str, Any]]:
    profiles = ["thesis", "half_step", "contrarian", "defensive", "jitter", "jitter"]
    focus = plan["focus_parameters"]
    avoid = set(critique["avoid_parameters"])
    directions = plan["directions"]
    candidates: list[dict[str, Any]] = []
    for index in range(count):
        profile = profiles[index % len(profiles)]
        rng = random.Random(f"{champion_spec.metadata.id}:{iteration}:{profile}:{index}")
        mutated = copy.deepcopy(champion_spec)
        for parameter in mutated.parameter_space:
            current_direction = directions.get(parameter.name, "neutral")
            if parameter.name in avoid:
                current_direction = "neutral"
            if profile == "contrarian" and parameter.name in focus:
                current_direction = {"up": "down", "down": "up", "neutral": "neutral"}[current_direction]
            if parameter.name in focus:
                parameter.default = _mutate_parameter(parameter, current_direction, profile, rng)
            else:
                span = parameter.upper - parameter.lower
                jitter = rng.uniform(-0.10, 0.10) * span * parameter.mutation_scale
                parameter.default = _clamp(parameter.default + jitter, parameter.lower, parameter.upper)
        _apply_profile_defaults(mutated, profile if critique["stress_bias"] == "more_defensive" else "jitter")
        mutated.metadata.parent_ids = list(dict.fromkeys(champion_spec.metadata.parent_ids + [champion_spec.metadata.id]))
        mutated.metadata.id = _make_candidate_id(champion_spec.metadata.name, iteration, index)
        mutated.metadata.name = f"{champion_spec.metadata.name} {profile} cycle {iteration}"
        mutated.metadata.created_by_role = "conversation_mutator"
        mutated.metadata.confidence_notes = (
            f"{plan['thesis']} | bucket={bucket} | profile={profile} | critic={'; '.join(critique['main_risks'][:2])}"
        )
        candidates.append(
            {
                "spec": mutated,
                "bucket": bucket,
                "origin_family": champion_spec.metadata.family,
                "origin_strategy_id": champion_spec.metadata.id,
                "profile": profile,
            }
        )
    return candidates


def _structural_candidates(
    champion_entry: dict[str, Any],
    frontier_entries: list[dict[str, Any]],
    iteration: int,
    count: int,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    champion_spec = champion_entry["spec"]
    candidates: list[dict[str, Any]] = []
    for index, profile in enumerate(STRUCTURAL_PROFILES):
        if len(candidates) >= count:
            break
        mutated = apply_structural_profile(champion_spec, profile)
        _apply_seeded_variation(mutated, iteration, f"structural:{profile}:{index}")
        mutated.metadata.id = _make_candidate_id(champion_spec.metadata.name, iteration, index + 50)
        mutated.metadata.name = f"{champion_spec.metadata.name} {profile} cycle {iteration}"
        mutated.metadata.confidence_notes = (
            f"structural profile={profile} | parent={champion_spec.metadata.id}"
        )
        candidates.append(
            {
                "spec": mutated,
                "bucket": "structural",
                "origin_family": champion_spec.metadata.family,
                "origin_strategy_id": champion_spec.metadata.id,
                "profile": profile,
            }
        )
    alternate_entries = [entry for entry in frontier_entries if entry["strategy_id"] != champion_entry["strategy_id"]]
    for alt_index, alternate in enumerate(alternate_entries):
        if len(candidates) >= count:
            break
        crossover = crossover_specs(alternate["spec"], champion_spec)
        _apply_seeded_variation(crossover, iteration, f"crossover:{alternate['family']}:{alt_index}")
        crossover.metadata.id = _make_candidate_id(alternate["name"], iteration, alt_index + 80)
        crossover.metadata.name = f"{alternate['name']} x {champion_spec.metadata.name} cycle {iteration}"
        crossover.metadata.created_by_role = "conversation_crossover"
        crossover.metadata.confidence_notes = (
            f"frontier crossover | left={alternate['strategy_id']} | right={champion_spec.metadata.id}"
        )
        candidates.append(
            {
                "spec": crossover,
                "bucket": "structural",
                "origin_family": alternate["family"],
                "origin_strategy_id": alternate["strategy_id"],
                "profile": "frontier_crossover",
            }
        )
    return candidates[:count]


def _family_jump_candidates(
    champion_entry: dict[str, Any],
    frontier_entries: list[dict[str, Any]],
    iteration: int,
    count: int,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    champion_spec = champion_entry["spec"]
    seen_families = {entry["family"] for entry in frontier_entries}
    family_names = [family for family in FAMILY_BUILDERS if family != champion_spec.metadata.family]
    ordered_families = [family for family in family_names if family in seen_families] + [
        family for family in family_names if family not in seen_families
    ]
    component_modes = ["full_jump", "fair", "signal", "execution", "risk"]
    candidates: list[dict[str, Any]] = []
    family_offset = iteration % max(1, len(ordered_families))
    mode_offset = iteration % len(component_modes)
    for index in range(count):
        if not ordered_families:
            break
        family_name = ordered_families[(index + family_offset) % len(ordered_families)]
        mode = component_modes[(index + mode_offset) % len(component_modes)]
        mutated = family_component_mutation(champion_spec, family_name, component=mode)
        _apply_seeded_variation(mutated, iteration, f"family_jump:{family_name}:{mode}:{index}")
        mutated.metadata.id = _make_candidate_id(f"{champion_spec.metadata.name}-{mode}-{family_name}", iteration, index + 120)
        mutated.metadata.name = f"{champion_spec.metadata.name} {mode} {family_name} cycle {iteration}"
        mutated.metadata.confidence_notes = (
            f"family jump mode={mode} | source={champion_spec.metadata.family} | target={family_name}"
        )
        candidates.append(
            {
                "spec": mutated,
                "bucket": "family_jump",
                "origin_family": champion_spec.metadata.family,
                "origin_strategy_id": champion_spec.metadata.id,
                "profile": f"{mode}:{family_name}",
            }
        )
    return candidates


def _recent_cycle_payloads(paths: RepoPaths, session_name: str, limit: int) -> list[dict[str, Any]]:
    rows = _with_repo(paths, lambda repo: repo.list_recent_conversation_cycles(session_name, limit=limit))
    payloads: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row["summary_json"])
        except Exception:
            continue
        if not payload.get("decision"):
            continue
        payloads.append(payload)
    return payloads


def _best_candidate_signature(cycle_summary: dict[str, Any]) -> tuple[Any, ...] | None:
    best_candidate = cycle_summary.get("best_candidate")
    if not isinstance(best_candidate, dict):
        return None
    metrics = best_candidate.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    return (
        best_candidate.get("search_bucket"),
        best_candidate.get("family"),
        best_candidate.get("profile"),
        round(float(metrics.get("total_pnl", 0.0)), 1),
        round(float(best_candidate.get("validation", {}).get("score", 0.0)), 3),
        round(float(best_candidate.get("scoring", {}).get("score", 0.0)), 3),
    )


def _detect_plateau(
    recent_cycles: list[dict[str, Any]],
    champion_strategy_id: str,
    lookback: int,
    repeat_threshold: int,
) -> dict[str, Any]:
    streak_window = recent_cycles[: max(lookback * 4, 24)]
    considered = recent_cycles[: max(lookback * 2, 16)]
    same_champion = [cycle for cycle in considered if cycle.get("champion_after") == champion_strategy_id]
    hold_streak = 0
    for cycle in streak_window:
        if cycle.get("decision") == "promote":
            break
        if cycle.get("champion_after") != champion_strategy_id:
            break
        hold_streak += 1

    signature_counts: dict[tuple[Any, ...], int] = {}
    top_signature: tuple[Any, ...] | None = None
    top_count = 0
    for cycle in same_champion:
        signature = _best_candidate_signature(cycle)
        if signature is None:
            continue
        signature_counts[signature] = signature_counts.get(signature, 0) + 1
        if signature_counts[signature] > top_count:
            top_count = signature_counts[signature]
            top_signature = signature

    active = hold_streak >= max(5, lookback - 1) or top_count >= repeat_threshold
    if active and top_count >= repeat_threshold and top_signature is not None:
        reason = (
            f"Repeated best-candidate pattern {top_signature[0]} / {top_signature[1]} / {top_signature[2]} "
            f"appeared {top_count} times."
        )
    elif active:
        reason = f"No promotion for {hold_streak} straight cycles on the same champion."
    else:
        reason = "Search frontier still moving."
    return {
        "active": active,
        "hold_streak": hold_streak,
        "repeat_count": top_count,
        "top_signature": list(top_signature) if top_signature is not None else None,
        "reason": reason,
    }


def _existing_strategy_signatures(paths: RepoPaths) -> set[str]:
    signatures: set[str] = set()
    rows = _with_repo(paths, lambda repo: repo.list_strategies())
    for row in rows:
        try:
            signatures.add(normalized_spec_json(_spec_from_row(row)))
        except Exception:
            continue
    return signatures


def _dedupe_candidates(
    paths: RepoPaths,
    candidate_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    seen = _existing_strategy_signatures(paths)
    unique: list[dict[str, Any]] = []
    duplicates_blocked = 0
    for entry in candidate_entries:
        signature = normalized_spec_json(entry["spec"])
        if signature in seen:
            duplicates_blocked += 1
            continue
        seen.add(signature)
        unique.append(entry)
    return unique, duplicates_blocked


def _candidate_bucket_summary(candidate_results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for candidate in candidate_results:
        bucket = str(candidate.get("search_bucket", "unknown"))
        counts[bucket] = counts.get(bucket, 0) + 1
    return counts


def _recent_search_performance(
    recent_cycles: list[dict[str, Any]],
    lookback: int,
) -> dict[str, dict[str, float]]:
    bucket_totals: dict[str, list[float]] = {}
    family_totals: dict[str, list[float]] = {}
    for cycle in recent_cycles[:lookback]:
        best_candidate = cycle.get("best_candidate")
        if not isinstance(best_candidate, dict):
            continue
        bucket = str(best_candidate.get("search_bucket", ""))
        family = str(best_candidate.get("family", ""))
        champion_pnl = float(cycle.get("champion_pnl", 0.0))
        metrics = best_candidate.get("metrics", {})
        validation = best_candidate.get("validation", {})
        scoring = best_candidate.get("scoring", {})
        candidate_pnl = float(metrics.get("total_pnl", 0.0))
        validation_score = float(validation.get("score", 0.0))
        score = float(scoring.get("score", 0.0))
        pnl_closeness = max(0.0, 1.0 - max(0.0, champion_pnl - candidate_pnl) / 400.0)
        merit = 0.55 * pnl_closeness + 0.25 * validation_score + 0.20 * score
        decision = str(cycle.get("decision", "hold"))
        if decision == "promote":
            merit += 1.0
        elif decision == "shadow_promote":
            merit += 0.6
        if bucket:
            bucket_totals.setdefault(bucket, []).append(merit)
        if family:
            family_totals.setdefault(family, []).append(merit)
    return {
        "bucket_scores": {key: sum(values) / len(values) for key, values in bucket_totals.items() if values},
        "family_scores": {key: sum(values) / len(values) for key, values in family_totals.items() if values},
    }


def _regime_day_pnls(evaluation: dict[str, Any]) -> dict[str, float]:
    validation = evaluation.get("validation", {})
    if not isinstance(validation, dict):
        return {}
    payload = validation.get("day_pnls", {})
    if not isinstance(payload, dict):
        return {}
    return {str(key): float(value) for key, value in payload.items()}


def _regime_complementarity(entry: dict[str, Any], champion_entry: dict[str, Any]) -> float:
    candidate_days = _regime_day_pnls(entry["evaluation"])
    champion_days = _regime_day_pnls(champion_entry["evaluation"])
    if not candidate_days or not champion_days:
        return 0.0
    score = 0.0
    for day, champion_pnl in champion_days.items():
        candidate_pnl = candidate_days.get(day)
        if candidate_pnl is None:
            continue
        if candidate_pnl > champion_pnl:
            score += min(1.0, (candidate_pnl - champion_pnl) / 800.0)
    return score


def _profiles_for_bucket(candidate_results: list[dict[str, Any]], bucket: str, limit: int = 6) -> list[str]:
    profiles: list[str] = []
    seen: set[str] = set()
    for candidate in candidate_results:
        if candidate.get("search_bucket") != bucket:
            continue
        profile = str(candidate.get("profile", "")).strip()
        if not profile or profile in seen:
            continue
        seen.add(profile)
        profiles.append(profile)
        if len(profiles) >= limit:
            break
    return profiles


def _explore_candidates_from_frontier(
    frontier_entries: list[dict[str, Any]],
    champion_entry: dict[str, Any],
    plan: dict,
    critique: dict,
    memory_notes: list[dict],
    iteration: int,
    count: int,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    candidates: list[dict[str, Any]] = []
    alternate_entries = [entry for entry in frontier_entries if entry["strategy_id"] != champion_entry["strategy_id"]]
    for index, entry in enumerate(alternate_entries):
        if len(candidates) >= count:
            break
        projected_plan = _project_plan_to_spec(plan, entry["spec"], memory_notes, iteration, count=1)
        mutated_batch = _mutate_candidates(
            entry["spec"],
            projected_plan,
            critique,
            iteration,
            count=1,
            bucket="explore",
        )
        if not mutated_batch:
            continue
        candidate = mutated_batch[0]
        candidate["profile"] = f"frontier_probe_{index}"
        candidates.append(candidate)
    for family_name in FRONTIER_SEED_SPECS:
        if len(candidates) >= count:
            break
        if family_name in {entry["family"] for entry in alternate_entries}:
            continue
        seed_info = FRONTIER_SEED_SPECS[family_name]
        seed_spec = _build_seed_spec(
            family_name,
            strategy_id=f"{str(seed_info['strategy_id'])}-temp",
            name=f"{str(seed_info['name'])} Explore",
        )
        projected_plan = _project_plan_to_spec(plan, seed_spec, memory_notes, iteration, count=1)
        mutated_batch = _mutate_candidates(
            seed_spec,
            projected_plan,
            critique,
            iteration,
            count=1,
            bucket="explore",
        )
        if mutated_batch:
            candidates.append(mutated_batch[0])
    return candidates[:count]


def _family_lab_candidates(
    champion_entry: dict[str, Any],
    frontier_entries: list[dict[str, Any]],
    plan: dict,
    critique: dict,
    memory_notes: list[dict],
    iteration: int,
    count: int,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    champion_spec = champion_entry["spec"]
    alternate_entries = [entry for entry in frontier_entries if entry["strategy_id"] != champion_entry["strategy_id"]]
    candidates: list[dict[str, Any]] = []
    for index, entry in enumerate(alternate_entries):
        if len(candidates) >= count:
            break
        family_spec = entry["spec"]
        profile_index = (iteration + index) % 3
        if profile_index == 0:
            projected_plan = _project_plan_to_spec(plan, family_spec, memory_notes, iteration, count=1)
            tuned_batch = _mutate_candidates(
                family_spec,
                projected_plan,
                critique,
                iteration,
                count=1,
                bucket="family_lab",
            )
            if not tuned_batch:
                continue
            tuned_batch[0]["profile"] = f"family_lab_local:{entry['family']}"
            candidates.append(tuned_batch[0])
            continue

        if profile_index == 1:
            hybrid = _blend_spec_components(
                champion_spec,
                fair_from=family_spec,
                signal_from=family_spec,
                execution_from=champion_spec,
                risk_from=family_spec,
                parameter_sources=[champion_spec, family_spec],
            )
            profile = f"family_lab_signal_shell:{entry['family']}"
        else:
            hybrid = _blend_spec_components(
                family_spec,
                fair_from=family_spec,
                signal_from=champion_spec,
                execution_from=family_spec,
                risk_from=champion_spec,
                parameter_sources=[family_spec, champion_spec],
            )
            profile = f"family_lab_execution_probe:{entry['family']}"

        _apply_seeded_variation(hybrid, iteration, f"family_lab:{entry['family']}:{profile_index}")
        hybrid.metadata.parent_ids = list(
            dict.fromkeys(champion_spec.metadata.parent_ids + [champion_spec.metadata.id, family_spec.metadata.id])
        )
        hybrid.metadata.id = _make_candidate_id(f"{family_spec.metadata.name}-lab", iteration, index + 160)
        hybrid.metadata.name = f"{family_spec.metadata.name} family lab cycle {iteration}"
        hybrid.metadata.created_by_role = "family_lab"
        hybrid.metadata.family = f"{family_spec.metadata.family}__lab"
        hybrid.metadata.confidence_notes = (
            f"family lab candidate | source={family_spec.metadata.family} | "
            f"champion_shell={champion_spec.metadata.family}"
        )
        candidates.append(
            {
                "spec": hybrid,
                "bucket": "family_lab",
                "origin_family": family_spec.metadata.family,
                "origin_strategy_id": family_spec.metadata.id,
                "profile": profile,
            }
        )
    return candidates[:count]


def _screen_candidate_entries(
    resolved_paths: RepoPaths,
    resolved_settings: AppSettings,
    candidate_entries: list[dict[str, Any]],
    family_scores: dict[str, float],
    bucket_scores: dict[str, float],
    iteration: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not candidate_entries:
        return [], []
    runner = BacktesterRunner(resolved_paths, resolved_settings)
    screen_days = resolved_settings.conversation.screening_tutorial_days or [-1]
    screened: list[dict[str, Any]] = []
    for index, candidate_entry in enumerate(candidate_entries):
        candidate = candidate_entry["spec"]
        compiled = compile_spec_to_artifact(resolved_paths, candidate)
        day = screen_days[(iteration + index) % len(screen_days)]
        family_prior = family_scores.get(candidate.metadata.family, 0.0)
        bucket_prior = bucket_scores.get(candidate_entry["bucket"], 0.0)
        try:
            screening = quick_screen_candidate(
                runner,
                str(compiled),
                tutorial_day=day,
                family_prior=family_prior,
                bucket_prior=bucket_prior,
            )
        except Exception as exc:
            screening = {
                "status": "failed",
                "score": float("-inf"),
                "screen_day": day,
                "error": str(exc),
                "metrics": {"total_pnl": float("-inf")},
            }
        enriched = dict(candidate_entry)
        enriched["compiled_path"] = compiled
        enriched["screening"] = screening
        screened.append(enriched)

    keep_count = max(
        1,
        min(
            resolved_settings.conversation.max_full_evaluations_per_cycle,
            len(screened),
        ),
    )
    winners: list[dict[str, Any]] = []
    kept_indices: set[int] = set()
    bucket_order = [
        "family_lab",
        "expert_builder",
        "family_jump",
        "structural",
        "explore",
        "exploit",
    ]
    for bucket in bucket_order:
        bucket_candidates = [
            (idx, entry)
            for idx, entry in enumerate(screened)
            if entry["bucket"] == bucket
        ]
        if not bucket_candidates:
            continue
        idx, winner = max(
            bucket_candidates,
            key=lambda item: (
                float(item[1]["screening"].get("score", float("-inf"))),
                float(item[1]["screening"].get("metrics", {}).get("total_pnl", float("-inf"))),
            ),
        )
        if idx not in kept_indices:
            winners.append(winner)
            kept_indices.add(idx)
        if len(winners) >= keep_count:
            break

    ranked = sorted(
        [
            (idx, entry)
            for idx, entry in enumerate(screened)
            if idx not in kept_indices
        ],
        key=lambda item: (
            float(item[1]["screening"].get("score", float("-inf"))),
            float(item[1]["screening"].get("metrics", {}).get("total_pnl", float("-inf"))),
        ),
        reverse=True,
    )
    for idx, entry in ranked:
        if len(winners) >= keep_count:
            break
        winners.append(entry)
        kept_indices.add(idx)

    return winners, screened


def _evaluate_candidate_batch(
    resolved_paths: RepoPaths,
    resolved_settings: AppSettings,
    resolved_session_name: str,
    cycle_id: str,
    champion_pnl: float,
    candidate_entries: list[dict[str, Any]],
    candidate_results: list[dict[str, Any]],
    best_candidate: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    running_best = best_candidate
    for candidate_entry in candidate_entries:
        candidate = candidate_entry["spec"]
        compiled = candidate_entry.get("compiled_path") or compile_spec_to_artifact(resolved_paths, candidate)
        _with_repo(
            resolved_paths,
            lambda repo, candidate=candidate, compiled=compiled, bucket=candidate_entry["bucket"]: persist_strategy_record(
                repo,
                candidate,
                compiled,
                stage="conversation_candidate",
                notes=f"Cycle candidate bucket={bucket}",
            ),
        )
        evaluation = _with_repo(
            resolved_paths,
            lambda repo, candidate=candidate, compiled=compiled: evaluate_compiled_strategy(
                resolved_paths,
                resolved_settings,
                repo,
                candidate,
                compiled,
            ),
        )
        candidate_summary = {
            "strategy_id": candidate.metadata.id,
            "name": candidate.metadata.name,
            "metrics": evaluation["metrics"],
            "scoring": evaluation["scoring"],
            "robustness": evaluation["robustness"],
            "validation": evaluation.get("validation", {}),
            "plagiarism": evaluation["plagiarism"],
            "decision": evaluation["decision"],
            "reason": evaluation["reason"],
            "report_path": evaluation["report_path"],
            "family": candidate.metadata.family,
            "search_bucket": candidate_entry["bucket"],
            "origin_family": candidate_entry["origin_family"],
            "origin_strategy_id": candidate_entry["origin_strategy_id"],
            "profile": candidate_entry["profile"],
            "screening": candidate_entry.get("screening", {}),
        }
        postmortem = _postmortem_turn(resolved_settings, resolved_paths, candidate_summary, champion_pnl)
        candidate_summary["postmortem"] = postmortem
        candidate_results.append(candidate_summary)
        _append_messages(
            resolved_paths,
            cycle_id,
            resolved_session_name,
            [
                ("evaluator", candidate_summary),
                ("postmortem", postmortem),
            ],
        )
        _write_memory(
            resolved_paths,
            resolved_session_name,
            cycle_id,
            candidate.metadata.id,
            "candidate_postmortem",
            f"{postmortem['result']}: {postmortem['lesson']} Next: {postmortem['next_hint']}",
        )
        if running_best is None:
            running_best = candidate_summary
        else:
            current_tuple = (
                float(candidate_summary["metrics"]["total_pnl"]),
                float(candidate_summary.get("validation", {}).get("score", 0.0)),
                float(candidate_summary["scoring"]["score"]),
            )
            best_tuple = (
                float(running_best["metrics"]["total_pnl"]),
                float(running_best.get("validation", {}).get("score", 0.0)),
                float(running_best["scoring"]["score"]),
            )
            if current_tuple > best_tuple:
                running_best = candidate_summary
    return candidate_results, running_best


def _select_stage_two_survivors(
    candidate_results: list[dict[str, Any]],
    champion_family: str,
    count: int,
) -> list[dict[str, Any]]:
    if count <= 0:
        return []
    pool = [
        candidate
        for candidate in candidate_results
        if candidate["search_bucket"] in {
            "explore",
            "structural",
            "family_jump",
            "family_lab",
            "expert_builder",
        }
    ]
    pool.sort(
        key=lambda candidate: (
            float(candidate["metrics"]["total_pnl"]),
            float(candidate.get("validation", {}).get("score", 0.0)),
            float(candidate["scoring"]["score"]),
        ),
        reverse=True,
    )
    survivors: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for candidate in pool:
        family = candidate["family"]
        if family == champion_family and candidate["search_bucket"] != "family_jump":
            continue
        if family in seen_families:
            continue
        survivors.append(candidate)
        seen_families.add(family)
        if len(survivors) >= count:
            break
    return survivors


def _build_stage_two_candidates(
    resolved_paths: RepoPaths,
    survivors: list[dict[str, Any]],
    plan: dict,
    critique: dict,
    memory_notes: list[dict],
    iteration: int,
) -> list[dict[str, Any]]:
    tuned: list[dict[str, Any]] = []
    for index, survivor in enumerate(survivors):
        row = _with_repo(resolved_paths, lambda repo, strategy_id=survivor["strategy_id"]: repo.get_strategy(strategy_id))
        if row is None:
            continue
        survivor_spec = _spec_from_row(row)
        survivor_plan = _project_plan_to_spec(plan, survivor_spec, memory_notes, iteration, count=1)
        tuned_batch = _mutate_candidates(
            survivor_spec,
            survivor_plan,
            critique,
            iteration,
            count=1,
            bucket="survivor_tune",
        )
        if not tuned_batch:
            continue
        tuned_batch[0]["profile"] = f"survivor_refine_{index}"
        tuned.append(tuned_batch[0])
    return tuned


def _build_seed_spec(family_name: str, strategy_id: str, name: str) -> StrategySpec:
    if family_name == "tutorial_submission_candidate_alpha":
        spec = build_family_spec(family_name, role="conversation_seed")
        spec.metadata.id = strategy_id
        spec.metadata.name = name
        spec.metadata.parent_ids = []
        spec.metadata.created_by_role = "conversation_seed"
        spec.metadata.confidence_notes = (
            "Seed strategy for multi-family frontier search. "
            "This family acts as an exploration anchor rather than a guaranteed champion."
        )
        return spec
    if family_name not in FAMILY_BUILDERS:
        raise ValueError(f"Unsupported frontier family: {family_name}")
    spec = build_family_spec(family_name, role="conversation_seed")
    spec.metadata.id = strategy_id
    spec.metadata.name = name
    spec.metadata.parent_ids = []
    spec.metadata.created_by_role = "conversation_seed"
    spec.metadata.confidence_notes = (
        "Seed strategy for multi-family frontier search. "
        "This family acts as an exploration anchor rather than a guaranteed champion."
    )
    return spec


def _ensure_seed_strategy(paths: RepoPaths, family_name: str) -> StrategySpec:
    seed_info = FRONTIER_SEED_SPECS[family_name]
    strategy_id = str(seed_info["strategy_id"])
    existing = _with_repo(paths, lambda repo: repo.get_strategy(strategy_id))
    if existing is not None:
        return _spec_from_row(existing)
    spec = _build_seed_spec(family_name, strategy_id=strategy_id, name=str(seed_info["name"]))
    compiled = compile_spec_to_artifact(paths, spec)
    _with_repo(paths, lambda repo: persist_strategy_record(repo, spec, compiled, stage="conversation_seed", notes="Seed strategy"))
    return spec


def _ensure_frontier_seed_strategies(paths: RepoPaths) -> list[StrategySpec]:
    return [_ensure_seed_strategy(paths, family_name) for family_name in FRONTIER_SEED_SPECS]


def _resolve_compiled_path(paths: RepoPaths, strategy_id: str) -> Path:
    row = _with_repo(paths, lambda repo: repo.get_strategy(strategy_id))
    if row is None or not row["code_path"]:
        return paths.strategies / f"{strategy_id}.py"
    return Path(row["code_path"])


def _ensure_strategy_evaluation(
    paths: RepoPaths,
    settings: AppSettings,
    spec: StrategySpec,
    compiled_path: Path,
) -> dict:
    latest_eval = _with_repo(paths, lambda repo: repo.get_latest_evaluation(spec.metadata.id))
    if latest_eval is not None:
        cached = _evaluation_from_row(latest_eval)
        cached["decision"] = "cached"
        cached["reason"] = "Using cached evaluation."
        cached["report_path"] = str(paths.reports / f"{spec.metadata.id}.md")
        return cached
    return _with_repo(
        paths,
        lambda repo: evaluate_compiled_strategy(paths, settings, repo, spec, compiled_path),
    )


def _select_frontier(paths: RepoPaths, settings: AppSettings) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    seed_specs = _ensure_frontier_seed_strategies(paths)
    entries: list[dict[str, Any]] = []
    for seed_spec in seed_specs:
        compiled_path = _resolve_compiled_path(paths, seed_spec.metadata.id)
        evaluation = _ensure_strategy_evaluation(paths, settings, seed_spec, compiled_path)
        entries.append(_strategy_entry(seed_spec, compiled_path, evaluation))

    strategy_rows = _with_repo(paths, lambda repo: repo.list_strategies())
    best_by_family: dict[str, dict[str, Any]] = {}
    for row in strategy_rows:
        strategy_id = row["strategy_id"]
        if any(entry["strategy_id"] == strategy_id for entry in entries):
            continue
        evaluation_row = _with_repo(paths, lambda repo, strategy_id=strategy_id: repo.get_latest_evaluation(strategy_id))
        if evaluation_row is None:
            continue
        spec = _spec_from_row(row)
        compiled_path = _resolve_compiled_path(paths, spec.metadata.id)
        evaluation = _evaluation_from_row(evaluation_row)
        evaluation["decision"] = "cached"
        evaluation["reason"] = "Using cached evaluation."
        evaluation["report_path"] = str(paths.reports / f"{spec.metadata.id}.md")
        entry = _strategy_entry(spec, compiled_path, evaluation)
        current = best_by_family.get(spec.metadata.family)
        if current is None or (
            entry["pnl"],
            entry["validation_score"],
            entry["score"],
        ) > (
            current["pnl"],
            current["validation_score"],
            current["score"],
        ):
            best_by_family[spec.metadata.family] = entry

    merged = {entry["strategy_id"]: entry for entry in entries}
    for entry in best_by_family.values():
        merged[entry["strategy_id"]] = entry
    sorted_entries = sorted(
        merged.values(),
        key=lambda entry: (entry["pnl"], entry["validation_score"], entry["score"]),
        reverse=True,
    )
    champion_entry = sorted_entries[0]

    frontier: list[dict[str, Any]] = [champion_entry]
    seen_families: set[str] = {champion_entry["family"]}
    alternate_entries = [
        entry
        for entry in sorted_entries
        if entry["strategy_id"] != champion_entry["strategy_id"]
    ]
    alternate_entries.sort(
        key=lambda entry: (
            _regime_complementarity(entry, champion_entry),
            entry["validation_score"],
            entry["score"],
            entry["pnl"],
        ),
        reverse=True,
    )
    for entry in alternate_entries:
        if entry["family"] in seen_families:
            continue
        frontier.append(entry)
        seen_families.add(entry["family"])
        if len(frontier) >= settings.conversation.frontier_size:
            break
    return champion_entry, frontier


def _recent_memory(paths: RepoPaths, session_name: str, limit: int) -> list[dict]:
    rows = _with_repo(paths, lambda repo: repo.list_memory_notes(session_name, limit=limit))
    return [dict(row) for row in rows]


def _create_cycle(paths: RepoPaths, session_name: str, iteration: int, champion_strategy_id: str) -> str:
    cycle_id = f"{slugify(session_name)}-{iteration:04d}-{uuid4().hex[:8]}"
    record = ConversationCycleRecord(
        cycle_id=cycle_id,
        session_name=session_name,
        iteration=iteration,
        champion_strategy_id=champion_strategy_id,
        promoted_strategy_id=None,
        status="running",
        summary_json=json_dumps({"status": "running"}),
        created_at=_now(),
        finished_at=None,
    )
    _with_repo(paths, lambda repo: repo.upsert_conversation_cycle(record))
    return cycle_id


def _append_messages(paths: RepoPaths, cycle_id: str, session_name: str, messages: list[tuple[str, dict]]) -> None:
    timestamp = _now()
    records = [
        ConversationMessageRecord(
            message_id=f"{cycle_id}-{index:02d}-{slugify(role)}-{uuid4().hex[:6]}",
            cycle_id=cycle_id,
            session_name=session_name,
            role=role,
            content_json=json.dumps(payload, sort_keys=True),
            created_at=timestamp,
        )
        for index, (role, payload) in enumerate(messages)
    ]
    _with_repo(paths, lambda repo: repo.insert_conversation_messages(records))


def _write_memory(paths: RepoPaths, session_name: str, cycle_id: str, strategy_id: str | None, note_kind: str, content: str) -> None:
    record = MemoryNoteRecord(
        note_id=f"{slugify(session_name)}-{slugify(note_kind)}-{uuid4().hex[:8]}",
        session_name=session_name,
        cycle_id=cycle_id,
        strategy_id=strategy_id,
        note_kind=note_kind,
        content=content,
        created_at=_now(),
    )
    _with_repo(paths, lambda repo: repo.insert_memory_note(record))


def _finish_cycle(
    paths: RepoPaths,
    cycle_id: str,
    session_name: str,
    iteration: int,
    champion_strategy_id: str,
    promoted_strategy_id: str | None,
    status: str,
    summary: dict,
) -> None:
    record = ConversationCycleRecord(
        cycle_id=cycle_id,
        session_name=session_name,
        iteration=iteration,
        champion_strategy_id=champion_strategy_id,
        promoted_strategy_id=promoted_strategy_id,
        status=status,
        summary_json=json_dumps(summary),
        created_at=_now(),
        finished_at=_now(),
    )
    _with_repo(paths, lambda repo: repo.upsert_conversation_cycle(record))


def run_conversation_cycle(
    session_name: str | None = None,
    paths: RepoPaths | None = None,
    settings: AppSettings | None = None,
) -> dict:
    resolved_paths = paths or RepoPaths.discover()
    resolved_settings = settings or load_settings(resolved_paths)
    resolved_session_name = session_name or resolved_settings.conversation.session_name
    lock_path = resolved_paths.caches / "conversation.loop.lock"
    with file_lock(lock_path):
        ingested = _with_repo(resolved_paths, lambda repo: ingest_all(resolved_paths, resolved_settings, repo))
        champion_entry, frontier_entries = _select_frontier(resolved_paths, resolved_settings)
        champion_spec = champion_entry["spec"]
        champion_eval = champion_entry["evaluation"]
        iteration = _with_repo(resolved_paths, lambda repo: repo.next_cycle_iteration(resolved_session_name))
        cycle_id = _create_cycle(resolved_paths, resolved_session_name, iteration, champion_spec.metadata.id)
        memory_notes = _recent_memory(resolved_paths, resolved_session_name, resolved_settings.conversation.max_memory_notes)
        recent_cycles = _recent_cycle_payloads(
            resolved_paths,
            resolved_session_name,
            max(resolved_settings.conversation.plateau_lookback_cycles * 4, 24),
        )
        plateau_state = _detect_plateau(
            recent_cycles,
            champion_spec.metadata.id,
            resolved_settings.conversation.plateau_lookback_cycles,
            resolved_settings.conversation.plateau_repeat_threshold,
        )
        recent_performance = _recent_search_performance(
            recent_cycles,
            resolved_settings.conversation.adaptive_lookback_cycles,
        )
        family_jump_cycle = (
            resolved_settings.conversation.family_jump_interval > 0
            and iteration % resolved_settings.conversation.family_jump_interval == 0
        )
        candidate_budget = _budget_split(
            resolved_settings,
            requested_exploit_count=max(1, min(resolved_settings.conversation.exploit_candidates, resolved_settings.conversation.max_candidates_per_cycle)),
            family_jump_cycle=family_jump_cycle,
            plateau_mode=bool(plateau_state["active"]),
            recent_performance=recent_performance,
        )

        strategist_plan = _strategist_turn(
            resolved_settings,
            resolved_paths,
            champion_spec,
            champion_eval,
            frontier_entries,
            candidate_budget,
            memory_notes,
            iteration,
            plateau_state,
            recent_performance,
        )
        candidate_budget = _budget_split(
            resolved_settings,
            requested_exploit_count=max(1, strategist_plan["candidate_count"]),
            family_jump_cycle=family_jump_cycle,
            plateau_mode=bool(plateau_state["active"]),
            recent_performance=recent_performance,
        )
        critic_plan = _critic_turn(
            resolved_settings,
            resolved_paths,
            champion_spec,
            frontier_entries,
            strategist_plan,
            champion_eval,
            plateau_state,
            recent_performance,
        )
        _append_messages(
            resolved_paths,
            cycle_id,
            resolved_session_name,
            [
                ("strategist", strategist_plan),
                ("critic", critic_plan),
            ],
        )

        exploit_plan = _project_plan_to_spec(
            strategist_plan,
            champion_spec,
            memory_notes,
            iteration,
            candidate_budget["exploit"],
        )
        exploit_candidates = _mutate_candidates(
            champion_spec,
            exploit_plan,
            critic_plan,
            iteration,
            count=candidate_budget["exploit"],
            bucket="exploit",
        )
        explore_candidates = _explore_candidates_from_frontier(
            frontier_entries,
            champion_entry,
            strategist_plan,
            critic_plan,
            memory_notes,
            iteration,
            candidate_budget["explore"],
        )
        family_lab_candidates = _family_lab_candidates(
            champion_entry,
            frontier_entries,
            strategist_plan,
            critic_plan,
            memory_notes,
            iteration,
            candidate_budget["family_lab"],
        )
        structural_candidates = _structural_candidates(
            champion_entry,
            frontier_entries,
            iteration,
            candidate_budget["structural"],
        )
        family_jump_candidates = _family_jump_candidates(
            champion_entry,
            frontier_entries,
            iteration,
            candidate_budget["family_jump"],
        )
        expert_builder_candidates = build_expert_candidates(
            champion_entry,
            frontier_entries,
            memory_notes,
            iteration,
            candidate_budget["expert_builder"],
            plateau_mode=bool(plateau_state["active"]),
        )
        candidates = (
            exploit_candidates
            + explore_candidates
            + family_lab_candidates
            + structural_candidates
            + family_jump_candidates
            + expert_builder_candidates
        )
        candidates, duplicates_blocked = _dedupe_candidates(resolved_paths, candidates)
        screened_candidates, screening_results = _screen_candidate_entries(
            resolved_paths,
            resolved_settings,
            candidates,
            recent_performance.get("family_scores", {}),
            recent_performance.get("bucket_scores", {}),
            iteration,
        )
        candidate_results: list[dict] = []
        best_candidate: dict | None = None
        champion_pnl = float(champion_eval.get("metrics", {}).get("total_pnl", 0.0))
        if plateau_state["active"]:
            _write_memory(
                resolved_paths,
                resolved_session_name,
                cycle_id,
                champion_spec.metadata.id,
                "plateau_mode",
                f"Plateau mode active. {plateau_state['reason']}",
            )
        candidate_results, best_candidate = _evaluate_candidate_batch(
            resolved_paths,
            resolved_settings,
            resolved_session_name,
            cycle_id,
            champion_pnl,
            screened_candidates,
            candidate_results,
            best_candidate,
        )
        stage_two_survivors = _select_stage_two_survivors(
            candidate_results,
            champion_spec.metadata.family,
            candidate_budget["survivor_tune"],
        )
        stage_two_candidates = _build_stage_two_candidates(
            resolved_paths,
            stage_two_survivors,
            strategist_plan,
            critic_plan,
            memory_notes,
            iteration,
        )
        candidate_results, best_candidate = _evaluate_candidate_batch(
            resolved_paths,
            resolved_settings,
            resolved_session_name,
            cycle_id,
            champion_pnl,
            stage_two_candidates,
            candidate_results,
            best_candidate,
        )

        promoted_strategy_id: str | None = None
        shadow_strategy_id: str | None = None
        current_best_path: Path | None = None
        promotion_reason = "No candidate cleared the champion gate."
        promotion_kind = "hold"
        status = "completed"
        best_candidate = best_candidate or {
            "strategy_id": champion_spec.metadata.id,
            "metrics": champion_eval.get("metrics", {}),
            "validation": champion_eval.get("validation", {}),
            "scoring": champion_eval.get("scoring", {}),
            "decision": "none",
            "reason": "No candidates produced.",
        }
        best_pnl = float(best_candidate["metrics"].get("total_pnl", 0.0))
        best_validation_score = float(best_candidate.get("validation", {}).get("score", 0.0))
        best_score = float(best_candidate["scoring"].get("score", 0.0))
        champion_validation_score = float(champion_eval.get("validation", {}).get("score", 0.0))
        promotion_kind, promotion_reason = champion_challenger_decision(
            best_candidate,
            champion_eval,
            champion_family=champion_spec.metadata.family,
            min_improvement=resolved_settings.conversation.promote_min_improvement,
            stale_champion_cycles=resolved_settings.conversation.stale_champion_cycles,
            shadow_pnl_gap=resolved_settings.conversation.shadow_promotion_max_pnl_gap,
            shadow_robustness_delta=resolved_settings.conversation.shadow_promotion_min_robustness_delta,
            shadow_validation_delta=resolved_settings.conversation.shadow_promotion_min_validation_delta,
            plateau_state=plateau_state,
        )
        if promotion_kind == "promote":
            promoted_strategy_id = best_candidate["strategy_id"]
            compiled = _resolve_compiled_path(resolved_paths, promoted_strategy_id)
            promoted_spec = _with_repo(resolved_paths, lambda repo: _spec_from_row(repo.get_strategy(promoted_strategy_id)))
            package_dir = package_strategy(
                resolved_paths,
                promoted_spec,
                compiled,
                {
                    "decision": "promote",
                    "reason": "Conversation champion-challenger promotion",
                    "scoring": best_candidate["scoring"],
                },
            )
            _with_repo(
                resolved_paths,
                lambda repo, promoted_spec=promoted_spec, compiled=compiled, package_dir=package_dir: persist_strategy_record(
                    repo,
                    promoted_spec,
                    compiled,
                    stage="conversation_champion",
                    notes=str(package_dir),
                ),
            )
            export_source = package_dir / "submission.py"
            if not export_source.exists():
                export_source = compiled
            current_best_path = _export_current_best(resolved_paths, export_source)
            _write_memory(
                resolved_paths,
                resolved_session_name,
                cycle_id,
                promoted_strategy_id,
                "promotion",
                f"{promotion_reason} Exported as {current_best_path.name}.",
            )
        elif promotion_kind == "shadow_promote":
            shadow_strategy_id = best_candidate["strategy_id"]
            compiled = _resolve_compiled_path(resolved_paths, shadow_strategy_id)
            shadow_spec = _with_repo(resolved_paths, lambda repo: _spec_from_row(repo.get_strategy(shadow_strategy_id)))
            _with_repo(
                resolved_paths,
                lambda repo, shadow_spec=shadow_spec, compiled=compiled: persist_strategy_record(
                    repo,
                    shadow_spec,
                    compiled,
                    stage="conversation_shadow",
                    notes=promotion_reason,
                ),
            )
            _write_memory(
                resolved_paths,
                resolved_session_name,
                cycle_id,
                shadow_strategy_id,
                "shadow_promotion",
                promotion_reason,
            )
        else:
            _write_memory(
                resolved_paths,
                resolved_session_name,
                cycle_id,
                champion_spec.metadata.id,
                "champion_hold",
                (
                    f"Champion held at {champion_pnl:.1f}. Best challenger {best_candidate['strategy_id']} "
                    f"reached {best_pnl:.1f} with score {best_score:.4f}."
                ),
            )

        promoter_message = {
            "champion_before": champion_spec.metadata.id,
            "champion_after": promoted_strategy_id or champion_spec.metadata.id,
            "champion_pnl": champion_pnl,
            "champion_validation_score": champion_validation_score,
            "best_candidate_id": best_candidate["strategy_id"],
            "best_candidate_pnl": best_pnl,
            "best_candidate_validation_score": best_validation_score,
            "best_candidate_score": best_score,
            "shadow_strategy_id": shadow_strategy_id,
            "decision": promotion_kind,
            "reason": promotion_reason,
        }
        _append_messages(
            resolved_paths,
            cycle_id,
            resolved_session_name,
            [("promoter", promoter_message)],
        )
        llm_status = _llm_runtime_status(
            resolved_settings,
            resolved_paths,
            strategist_plan=strategist_plan,
            critic_plan=critic_plan,
        )
        cycle_summary = {
            "session_name": resolved_session_name,
            "cycle_id": cycle_id,
            "iteration": iteration,
            "ingested_documents": ingested,
            "frontier": _frontier_brief(frontier_entries),
            "recent_performance": recent_performance,
            "candidate_budget": candidate_budget,
            "duplicates_blocked": duplicates_blocked,
            "screened_candidate_count": len(candidates),
            "full_evaluation_count": len(screened_candidates),
            "screening_profiles": [
                {
                    "strategy_id": entry["spec"].metadata.id,
                    "bucket": entry["bucket"],
                    "profile": entry["profile"],
                    "screen_day": entry.get("screening", {}).get("screen_day"),
                    "screen_score": entry.get("screening", {}).get("score"),
                }
                for entry in screening_results[: min(8, len(screening_results))]
            ],
            "stage_two_survivors": [candidate["strategy_id"] for candidate in stage_two_survivors],
            "champion_before": champion_spec.metadata.id,
            "champion_after": promoted_strategy_id or champion_spec.metadata.id,
            "champion_pnl": champion_pnl,
            "champion_validation_score": champion_validation_score,
            "candidate_count": len(candidate_results),
            "candidate_bucket_counts": _candidate_bucket_summary(candidate_results),
            "family_lab_profiles_tried": _profiles_for_bucket(candidate_results, "family_lab"),
            "expert_builder_profiles_tried": _profiles_for_bucket(candidate_results, "expert_builder"),
            "family_jump_profiles_tried": _profiles_for_bucket(candidate_results, "family_jump"),
            "shadow_strategy_id": shadow_strategy_id,
            "best_candidate": best_candidate,
            "decision": promotion_kind,
            "reason": promotion_reason,
            "strategist": strategist_plan,
            "critic": critic_plan,
            "family_jump_cycle": family_jump_cycle,
            "plateau_state": plateau_state,
            "llm_status": llm_status,
        }
        if current_best_path is not None:
            cycle_summary["current_best_path"] = str(current_best_path)
        cycle_summary["discord_notification"] = send_cycle_summary_message(cycle_summary, resolved_settings)
        _finish_cycle(
            resolved_paths,
            cycle_id,
            resolved_session_name,
            iteration,
            champion_spec.metadata.id,
            promoted_strategy_id or shadow_strategy_id,
            status,
            cycle_summary,
        )
        return cycle_summary


def run_conversation_loop(
    cycles: int | None = None,
    sleep_seconds: int | None = None,
    session_name: str | None = None,
) -> list[dict]:
    resolved_paths = RepoPaths.discover()
    resolved_settings = load_settings(resolved_paths)
    resolved_sleep = (
        resolved_settings.conversation.default_sleep_seconds
        if sleep_seconds is None
        else sleep_seconds
    )
    results: list[dict] = []
    iteration = 0
    try:
        while cycles is None or iteration < cycles:
            result = run_conversation_cycle(
                session_name=session_name or resolved_settings.conversation.session_name,
                paths=resolved_paths,
                settings=resolved_settings,
            )
            results.append(result)
            iteration += 1
            if cycles is not None and iteration >= cycles:
                break
            if resolved_sleep > 0:
                time.sleep(resolved_sleep)
    except KeyboardInterrupt:
        return results
    return results
