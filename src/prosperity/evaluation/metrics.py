from __future__ import annotations

from prosperity.backtester.parser import BacktestSummary


def compute_metrics(summary: BacktestSummary) -> dict:
    per_day = {row.set_name: row.final_pnl for row in summary.day_results}
    product_pnl = {row.product: row.values for row in summary.product_contributions}
    own_trade_count = sum(row.own_trades for row in summary.day_results)
    worst_day = min((row.final_pnl for row in summary.day_results), default=0.0)
    return {
        "total_pnl": summary.total_final_pnl,
        "per_day_pnl": per_day,
        "per_product_pnl": product_pnl,
        "own_trade_count": own_trade_count,
        "worst_day_pnl": worst_day,
        "day_count": len(summary.day_results),
    }
