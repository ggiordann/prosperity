from __future__ import annotations


def score_candidate(
    metrics: dict,
    robustness: dict,
    novelty: float,
    plagiarism_score: float,
    validation: dict | None = None,
) -> dict:
    pnl_component = 1.0 if metrics["total_pnl"] > 0 else 0.0
    worst_day_component = 1.0 if metrics["worst_day_pnl"] > 0 else 0.0
    simplicity_component = max(0.0, 1.0 - 0.01 * metrics.get("own_trade_count", 0))
    robustness_component = robustness.get("score", 0.0)
    validation_component = 0.0 if validation is None else float(validation.get("score", 0.0))
    anti_crowding_component = 1.0 - plagiarism_score
    baseline_outperformance_component = pnl_component
    score = (
        0.25 * pnl_component
        + 0.18 * robustness_component
        + 0.15 * validation_component
        + 0.08 * worst_day_component
        + 0.12 * novelty
        + 0.07 * simplicity_component
        + 0.10 * baseline_outperformance_component
        + 0.05 * anti_crowding_component
    )
    return {
        "score": score,
        "components": {
            "pnl_component": pnl_component,
            "robustness_component": robustness_component,
            "validation_component": validation_component,
            "worst_day_component": worst_day_component,
            "novelty_component": novelty,
            "simplicity_component": simplicity_component,
            "baseline_outperformance_component": baseline_outperformance_component,
            "anti_crowding_component": anti_crowding_component,
        },
    }
