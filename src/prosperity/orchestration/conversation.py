from __future__ import annotations

import copy
import json
import random
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from prosperity.db import DatabaseSession, ExperimentRepository
from prosperity.db.models import (
    ConversationCycleRecord,
    ConversationMessageRecord,
    MemoryNoteRecord,
)
from prosperity.dsl.crossover import crossover_specs
from prosperity.dsl.mutators import apply_structural_profile
from prosperity.dsl.schema import ParameterDef, StrategySpec
from prosperity.external.discord_notifier import send_cycle_summary_message
from prosperity.generation.family_registry import (
    tutorial_market_maker,
    tutorial_microprice_reversion,
    tutorial_submission_candidate_alpha,
)
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
        "builder": tutorial_submission_candidate_alpha,
    },
    "tutorial_microprice_reversion": {
        "strategy_id": "conversation-microprice-seed",
        "name": "Conversation Microprice Seed",
        "builder": tutorial_microprice_reversion,
    },
    "tutorial_wall_mid_mm": {
        "strategy_id": "conversation-wall-mid-seed",
        "name": "Conversation Wall Mid Seed",
        "builder": tutorial_market_maker,
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


def _spec_from_row(row) -> StrategySpec:
    return StrategySpec.model_validate_json(row["spec_json"])


def _evaluation_from_row(row) -> dict:
    payload = json.loads(row["metrics_json"])
    return {
        "metrics": payload.get("metrics", {}),
        "robustness": payload.get("robustness", {}),
        "scoring": payload.get("scoring", {}),
        "plagiarism": payload.get("plagiarism", {}),
        "behavior_fingerprint": payload.get("behavior_fingerprint", {}),
        "critique": payload.get("critique", {}),
    }


def _strategy_entry(spec: StrategySpec, compiled_path: Path, evaluation: dict) -> dict[str, Any]:
    metrics = evaluation.get("metrics", {})
    scoring = evaluation.get("scoring", {})
    return {
        "strategy_id": spec.metadata.id,
        "family": spec.metadata.family,
        "name": spec.metadata.name,
        "spec": spec,
        "compiled_path": compiled_path,
        "evaluation": evaluation,
        "pnl": float(metrics.get("total_pnl", 0.0)),
        "score": float(scoring.get("score", 0.0)),
    }


def _frontier_brief(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "strategy_id": entry["strategy_id"],
            "family": entry["family"],
            "pnl": entry["pnl"],
            "score": entry["score"],
        }
        for entry in entries
    ]


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


def _heuristic_plan(spec: StrategySpec, memory_notes: list[dict], iteration: int, max_candidates: int) -> dict:
    focus = [
        "fair_alpha_scale",
        "second_imb_weight",
        "gap_weight",
        "ret1_weight",
        "micro_weight",
        "tomato_take_width",
    ]
    if iteration % 3 == 0:
        focus = ["quote_aggression", "take_extra", "tomato_take_width", "clear_width"]
    note_text = " ".join(note["content"] for note in memory_notes[:4]).lower()
    defensive = any(token in note_text for token in ("aggressive", "inventory", "drawdown", "worse"))
    directions = {name: "neutral" for name in focus}
    directions["fair_alpha_scale"] = "down" if defensive else "up"
    directions["second_imb_weight"] = "down" if defensive else "up"
    directions["tomato_take_width"] = "up" if defensive else "down"
    directions["take_extra"] = "up" if defensive else "down"
    directions["quote_aggression"] = "down" if defensive else "up"
    return {
        "thesis": "Search locally around the TOMATOES alpha overlay while keeping EMERALDS stable.",
        "focus_parameters": focus,
        "directions": directions,
        "candidate_count": max(3, min(max_candidates, 6)),
        "guardrails": [
            "Do not disturb EMERALDS unless the change is tiny.",
            "Keep turnover bounded and avoid purely aggressive variants.",
        ],
        "reasoning": "Use recent postmortems to alternate between more aggressive and more defensive local search.",
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


def _strategist_turn(
    settings: AppSettings,
    paths: RepoPaths,
    champion_spec: StrategySpec,
    champion_eval: dict,
    frontier_entries: list[dict[str, Any]],
    candidate_budget: dict[str, int],
    memory_notes: list[dict],
    iteration: int,
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
        return _heuristic_plan(champion_spec, memory_notes, iteration, settings.conversation.max_candidates_per_cycle)
    return _normalize_plan(payload, allowed, settings.conversation.max_candidates_per_cycle)


def _critic_turn(
    settings: AppSettings,
    paths: RepoPaths,
    champion_spec: StrategySpec,
    frontier_entries: list[dict[str, Any]],
    plan: dict,
    champion_eval: dict,
) -> dict:
    allowed = _allowed_parameters(champion_spec)
    context = json_dumps(
        {
            "allowed_parameters": allowed,
            "plan": plan,
            "frontier": _frontier_brief(frontier_entries),
            "champion_metrics": champion_eval.get("metrics", {}),
            "champion_scoring": champion_eval.get("scoring", {}),
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
        return _heuristic_critic(plan)
    return _normalize_critic(payload, allowed)


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
        return _heuristic_postmortem(
            candidate_result["strategy_id"],
            float(candidate_result["metrics"]["total_pnl"]),
            champion_pnl,
        )
    return _normalize_postmortem(payload)


def _make_candidate_id(base_name: str, iteration: int, variant_index: int) -> str:
    return f"{slugify(base_name)}-c{iteration:03d}-v{variant_index:02d}-{uuid4().hex[:6]}"


def _budget_split(settings: AppSettings, requested_exploit_count: int) -> dict[str, int]:
    total = max(1, settings.conversation.max_candidates_per_cycle)
    exploit = min(total, max(1, min(settings.conversation.exploit_candidates, requested_exploit_count)))
    remaining = total - exploit
    structural = min(settings.conversation.structural_candidates, remaining)
    remaining -= structural
    explore = min(settings.conversation.explore_candidates, remaining)
    remaining -= explore
    exploit += remaining
    return {
        "total": exploit + explore + structural,
        "exploit": exploit,
        "explore": explore,
        "structural": structural,
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
        }.items():
            if name not in parameter_map:
                continue
            parameter = parameter_map[name]
            span = parameter.upper - parameter.lower
            step = span * parameter.mutation_scale * 0.5
            sign = 1.0 if direction == "up" else -1.0
            parameter.default = _clamp(parameter.default + sign * step, parameter.lower, parameter.upper)


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


def _build_seed_spec(family_name: str, strategy_id: str, name: str) -> StrategySpec:
    if family_name == "tutorial_submission_candidate_alpha":
        return tutorial_submission_candidate_alpha(
            role="conversation_seed",
            strategy_id=strategy_id,
            name=name,
        )
    if family_name == "tutorial_microprice_reversion":
        spec = tutorial_microprice_reversion(role="conversation_seed")
    elif family_name == "tutorial_wall_mid_mm":
        spec = tutorial_market_maker(role="conversation_seed")
    else:
        raise ValueError(f"Unsupported frontier family: {family_name}")
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
        if current is None or (entry["pnl"], entry["score"]) > (current["pnl"], current["score"]):
            best_by_family[spec.metadata.family] = entry

    merged = {entry["strategy_id"]: entry for entry in entries}
    for entry in best_by_family.values():
        merged[entry["strategy_id"]] = entry
    sorted_entries = sorted(merged.values(), key=lambda entry: (entry["pnl"], entry["score"]), reverse=True)
    champion_entry = sorted_entries[0]

    frontier: list[dict[str, Any]] = []
    seen_families: set[str] = set()
    for entry in sorted_entries:
        if entry["family"] in seen_families:
            continue
        frontier.append(entry)
        seen_families.add(entry["family"])
        if len(frontier) >= settings.conversation.frontier_size:
            break
    if champion_entry["strategy_id"] not in {entry["strategy_id"] for entry in frontier}:
        frontier.insert(0, champion_entry)
        frontier = frontier[: settings.conversation.frontier_size]
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
        candidate_budget = _budget_split(
            resolved_settings,
            requested_exploit_count=max(1, min(resolved_settings.conversation.exploit_candidates, resolved_settings.conversation.max_candidates_per_cycle)),
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
        )
        candidate_budget = _budget_split(
            resolved_settings,
            requested_exploit_count=max(1, strategist_plan["candidate_count"]),
        )
        critic_plan = _critic_turn(
            resolved_settings,
            resolved_paths,
            champion_spec,
            frontier_entries,
            strategist_plan,
            champion_eval,
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
        structural_candidates = _structural_candidates(
            champion_entry,
            frontier_entries,
            iteration,
            candidate_budget["structural"],
        )
        candidates = exploit_candidates + explore_candidates + structural_candidates
        candidate_results: list[dict] = []
        best_candidate: dict | None = None
        champion_pnl = float(champion_eval.get("metrics", {}).get("total_pnl", 0.0))
        champion_score = float(champion_eval.get("scoring", {}).get("score", 0.0))

        for candidate_entry in candidates:
            candidate = candidate_entry["spec"]
            compiled = compile_spec_to_artifact(resolved_paths, candidate)
            _with_repo(
                resolved_paths,
                lambda repo, candidate=candidate, compiled=compiled: persist_strategy_record(
                    repo,
                    candidate,
                    compiled,
                    stage="conversation_candidate",
                    notes=f"Cycle {iteration} candidate",
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
                "plagiarism": evaluation["plagiarism"],
                "decision": evaluation["decision"],
                "reason": evaluation["reason"],
                "report_path": evaluation["report_path"],
                "family": candidate.metadata.family,
                "search_bucket": candidate_entry["bucket"],
                "origin_family": candidate_entry["origin_family"],
                "origin_strategy_id": candidate_entry["origin_strategy_id"],
                "profile": candidate_entry["profile"],
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
            if best_candidate is None:
                best_candidate = candidate_summary
            else:
                current_tuple = (
                    float(candidate_summary["metrics"]["total_pnl"]),
                    float(candidate_summary["scoring"]["score"]),
                )
                best_tuple = (
                    float(best_candidate["metrics"]["total_pnl"]),
                    float(best_candidate["scoring"]["score"]),
                )
                if current_tuple > best_tuple:
                    best_candidate = candidate_summary

        promoted_strategy_id: str | None = None
        promotion_reason = "No candidate cleared the champion gate."
        status = "completed"
        best_candidate = best_candidate or {
            "strategy_id": champion_spec.metadata.id,
            "metrics": champion_eval.get("metrics", {}),
            "scoring": champion_eval.get("scoring", {}),
            "decision": "none",
            "reason": "No candidates produced.",
        }
        best_pnl = float(best_candidate["metrics"].get("total_pnl", 0.0))
        best_score = float(best_candidate["scoring"].get("score", 0.0))
        min_improvement = resolved_settings.conversation.promote_min_improvement
        should_promote = (
            best_candidate.get("decision") == "promote"
            and (
                best_pnl >= champion_pnl + min_improvement
                or (best_pnl > champion_pnl and best_score > champion_score + 0.01)
            )
        )
        if should_promote:
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
            promotion_reason = (
                f"Promoted {promoted_strategy_id} over {champion_spec.metadata.id} with "
                f"submission PnL delta {best_pnl - champion_pnl:.1f}."
            )
            _write_memory(
                resolved_paths,
                resolved_session_name,
                cycle_id,
                promoted_strategy_id,
                "promotion",
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
            "best_candidate_id": best_candidate["strategy_id"],
            "best_candidate_pnl": best_pnl,
            "best_candidate_score": best_score,
            "decision": "promote" if promoted_strategy_id else "hold",
            "reason": promotion_reason,
        }
        _append_messages(
            resolved_paths,
            cycle_id,
            resolved_session_name,
            [("promoter", promoter_message)],
        )
        cycle_summary = {
            "session_name": resolved_session_name,
            "cycle_id": cycle_id,
            "iteration": iteration,
            "ingested_documents": ingested,
            "frontier": _frontier_brief(frontier_entries),
            "candidate_budget": candidate_budget,
            "champion_before": champion_spec.metadata.id,
            "champion_after": promoted_strategy_id or champion_spec.metadata.id,
            "champion_pnl": champion_pnl,
            "candidate_count": len(candidate_results),
            "best_candidate": best_candidate,
            "decision": "promote" if promoted_strategy_id else "hold",
            "reason": promotion_reason,
            "strategist": strategist_plan,
            "critic": critic_plan,
        }
        cycle_summary["discord_notification"] = send_cycle_summary_message(cycle_summary, resolved_settings)
        _finish_cycle(
            resolved_paths,
            cycle_id,
            resolved_session_name,
            iteration,
            champion_spec.metadata.id,
            promoted_strategy_id,
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
