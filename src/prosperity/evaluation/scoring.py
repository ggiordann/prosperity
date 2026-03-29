from __future__ import annotations


def score_candidate(metrics: dict, robustness: dict, novelty: float, plagiarism_score: float) -> dict:
    pnl_component = 1.0 if metrics["total_pnl"] > 0 else 0.0
    worst_day_component = 1.0 if metrics["worst_day_pnl"] > 0 else 0.0
    simplicity_component = max(0.0, 1.0 - 0.01 * metrics.get("own_trade_count", 0))
    robustness_component = robustness.get("score", 0.0)
    anti_crowding_component = 1.0 - plagiarism_score
    score = (
        0.35 * pnl_component
        + 0.20 * robustness_component
        + 0.10 * worst_day_component
        + 0.10 * novelty
        + 0.10 * simplicity_component
        + 0.10 * pnl_component
        + 0.05 * anti_crowding_component
    )
    return {
        "score": score,
        "components": {
            "pnl_component": pnl_component,
            "robustness_component": robustness_component,
            "worst_day_component": worst_day_component,
            "novelty_component": novelty,
            "simplicity_component": simplicity_component,
            "baseline_outperformance_component": pnl_component,
            "anti_crowding_component": anti_crowding_component,
        },
    }
