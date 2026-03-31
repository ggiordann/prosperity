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
    day_pnls: dict[str, float] = {}
    try:
        aggregate = runner.run(
            BacktestRequest(
                trader_path=trader_path,
                dataset="tutorial",
                products_mode="summary",
            )
        )
        aggregate_pnl = float(aggregate.summary.total_final_pnl)
        tests.append(
            {
                "name": "tutorial_all",
                "dataset": "tutorial",
                "day": None,
                "total_pnl": aggregate_pnl,
                "status": "ok",
            }
        )
        pnls.append(aggregate_pnl)
    except Exception as exc:
        tests.append(
            {
                "name": "tutorial_all",
                "dataset": "tutorial",
                "day": None,
                "status": "failed",
                "error": str(exc),
            }
        )

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
            day_pnls[str(day)] = pnl
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
    regime_spread = 0.0
    if len(day_pnls) > 1:
        regime_spread = max(day_pnls.values()) - min(day_pnls.values())
    regime_balance = 1.0
    if mean_pnl != 0.0 and regime_spread > 0.0:
        regime_balance = max(0.0, min(1.0, 1.0 - (regime_spread / max(abs(mean_pnl), 1.0))))
    score = max(0.0, min(1.0, 0.35 * positive_rate + 0.30 * downside + 0.20 * stability + 0.15 * regime_balance))
    return {
        "status": "ok",
        "tests": tests,
        "score": score,
        "mean_pnl": mean_pnl,
        "worst_pnl": worst_pnl,
        "positive_rate": positive_rate,
        "stability": stability,
        "regime_balance": regime_balance,
        "day_pnls": day_pnls,
        "regime_profile": {
            "best_day": max(day_pnls, key=lambda day: day_pnls[day]) if day_pnls else None,
            "worst_day": min(day_pnls, key=lambda day: day_pnls[day]) if day_pnls else None,
            "day_spread": regime_spread,
        },
    }
