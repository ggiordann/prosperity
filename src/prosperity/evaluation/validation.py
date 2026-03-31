from __future__ import annotations

from statistics import pstdev

from prosperity.backtester.runner import BacktesterRunner, BacktestRequest


def run_validation_suite(
    runner: BacktesterRunner,
    trader_path: str,
    tutorial_days: list[int],
) -> dict:
    tests: list[dict] = []
    pnls: list[float] = []
    for day in tutorial_days:
        try:
            result = runner.run(
                BacktestRequest(
                    trader_path=trader_path,
                    dataset="tutorial",
                    day=day,
                    products_mode="summary",
                )
            )
            pnl = float(result.summary.total_final_pnl)
            tests.append(
                {
                    "name": f"tutorial_day_{day}",
                    "dataset": "tutorial",
                    "day": day,
                    "total_pnl": pnl,
                    "status": "ok",
                }
            )
            pnls.append(pnl)
        except Exception as exc:
            tests.append(
                {
                    "name": f"tutorial_day_{day}",
                    "dataset": "tutorial",
                    "day": day,
                    "status": "failed",
                    "error": str(exc),
                }
            )

    if not pnls:
        return {"status": "insufficient-data", "tests": tests, "score": 0.0}

    mean_pnl = sum(pnls) / len(pnls)
    worst_pnl = min(pnls)
    positive_rate = sum(1 for pnl in pnls if pnl > 0) / len(pnls)
    stability = 1.0
    if len(pnls) > 1:
        baseline = max(abs(mean_pnl), 1.0)
        stability = max(0.0, min(1.0, 1.0 - (pstdev(pnls) / baseline)))
    downside = 0.0 if mean_pnl <= 0 else max(0.0, min(1.0, worst_pnl / max(mean_pnl, 1.0)))
    score = max(0.0, min(1.0, 0.45 * positive_rate + 0.35 * downside + 0.20 * stability))
    return {
        "status": "ok",
        "tests": tests,
        "score": score,
        "mean_pnl": mean_pnl,
        "worst_pnl": worst_pnl,
        "positive_rate": positive_rate,
        "stability": stability,
    }
