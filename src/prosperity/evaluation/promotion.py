from __future__ import annotations


def promotion_decision(score: float, plagiarism_score: float, threshold: float = 0.55) -> tuple[str, str]:
    if plagiarism_score >= 0.82:
        return "blocked", "Hard blocked due to high external code similarity."
    if score >= threshold:
        return "promote", "Candidate cleared scoring and plagiarism thresholds."
    return "reject", "Candidate did not clear promotion threshold."


def champion_challenger_decision(
    best_candidate: dict,
    champion_eval: dict,
    *,
    champion_family: str,
    min_improvement: float,
    stale_champion_cycles: int,
    shadow_pnl_gap: float,
    shadow_robustness_delta: float,
    shadow_validation_delta: float,
    plateau_state: dict,
) -> tuple[str, str]:
    if best_candidate.get("decision") != "promote":
        return "hold", "Best candidate did not clear the evaluation quality gate."

    champion_metrics = champion_eval.get("metrics", {})
    champion_scoring = champion_eval.get("scoring", {})
    champion_robustness = champion_eval.get("robustness", {})
    champion_validation = champion_eval.get("validation", {})
    best_metrics = best_candidate.get("metrics", {})
    best_scoring = best_candidate.get("scoring", {})
    best_robustness = best_candidate.get("robustness", {})
    best_validation = best_candidate.get("validation", {})

    champion_pnl = float(champion_metrics.get("total_pnl", 0.0))
    best_pnl = float(best_metrics.get("total_pnl", 0.0))
    champion_score = float(champion_scoring.get("score", 0.0))
    best_score = float(best_scoring.get("score", 0.0))
    champion_robustness_score = float(champion_robustness.get("score", 0.0))
    best_robustness_score = float(best_robustness.get("score", 0.0))
    champion_validation_score = float(champion_validation.get("score", 0.0))
    best_validation_score = float(best_validation.get("score", 0.0))

    pnl_delta = best_pnl - champion_pnl
    score_delta = best_score - champion_score
    robustness_delta = best_robustness_score - champion_robustness_score
    validation_delta = best_validation_score - champion_validation_score
    hold_streak = int(plateau_state.get("hold_streak", 0))
    alternate_family = str(best_candidate.get("family", "")) != champion_family
    discovery_bucket = str(best_candidate.get("search_bucket", "")) in {
        "explore",
        "structural",
        "family_jump",
        "family_lab",
        "expert_builder",
        "survivor_tune",
    }

    if pnl_delta >= min_improvement or (
        pnl_delta > 0 and (score_delta > 0.01 or validation_delta > 0.03)
    ):
        return "promote", (
            f"Promoted on hard champion gate: pnl delta {pnl_delta:.1f}, "
            f"score delta {score_delta:.3f}, validation delta {validation_delta:.3f}."
        )

    if (
        discovery_bucket
        and alternate_family
        and hold_streak >= stale_champion_cycles
        and pnl_delta >= -shadow_pnl_gap
        and (
            robustness_delta >= shadow_robustness_delta
            or validation_delta >= shadow_validation_delta
            or (best_score >= champion_score and pnl_delta >= -(shadow_pnl_gap / 2.0))
        )
    ):
        return "shadow_promote", (
            f"Shadow-promoted alternate family after {hold_streak} stagnant cycles: "
            f"pnl delta {pnl_delta:.1f}, robustness delta {robustness_delta:.3f}, "
            f"validation delta {validation_delta:.3f}."
        )

    return "hold", "No candidate cleared the champion gate."
