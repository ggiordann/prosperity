from __future__ import annotations

from prosperity.backtester.runner import BacktesterRunner, BacktestRequest


def run_robustness_suite(runner: BacktesterRunner, trader_path: str, dataset: str) -> dict:
    tests = []
    pnls: list[float] = []
    requests = [
        ("base", None, None),
        ("slippage", 5.0, None),
        ("queue_penetration", None, 0.5),
    ]
    for name, price_slippage_bps, queue_penetration in requests:
        try:
            result = runner.run(
                BacktestRequest(
                    trader_path=trader_path,
                    dataset=dataset,
                    products_mode="summary",
                    price_slippage_bps=price_slippage_bps,
                    queue_penetration=queue_penetration,
                )
            )
            tests.append(
                {
                    "name": name,
                    "total_pnl": float(result.summary.total_final_pnl),
                    "status": "ok",
                }
            )
            pnls.append(float(result.summary.total_final_pnl))
        except Exception as exc:
            tests.append({"name": name, "status": "failed", "error": str(exc)})
    if len(pnls) < 2:
        return {"status": "insufficient-data", "tests": tests, "score": 0.0}
    base = float(pnls[0]) if pnls else 0.0
    worst = min(pnls)
    score = 0.0 if base <= 0 else max(0.0, min(1.0, worst / base))
    return {"status": "ok", "tests": tests, "score": score}
