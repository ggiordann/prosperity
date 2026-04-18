from __future__ import annotations

from prosperity.backtester.runner import BacktesterRunner, BacktestRequest
from prosperity.evaluation.metrics import compute_metrics


def quick_screen_candidate(
    runner: BacktesterRunner,
    trader_path: str,
    *,
    dataset: str,
    day: int,
    family_prior: float = 0.0,
    bucket_prior: float = 0.0,
) -> dict:
    result = runner.run(
        BacktestRequest(
            trader_path=trader_path,
            dataset=dataset,
            day=day,
            products_mode="summary",
        )
    )
    metrics = compute_metrics(result.summary)
    pnl = float(metrics["total_pnl"])
    trade_count = float(metrics.get("own_trade_count", 0))
    simplicity = max(0.0, 1.0 - max(0.0, trade_count - 140.0) / 220.0)
    quick_score = pnl + 140.0 * family_prior + 90.0 * bucket_prior + 40.0 * simplicity
    return {
        "score": quick_score,
        "metrics": metrics,
        "screen_dataset": dataset,
        "screen_day": day,
        "family_prior": family_prior,
        "bucket_prior": bucket_prior,
        "simplicity": simplicity,
    }
