from __future__ import annotations


def build_diagnostics_report(strategy_name: str, metrics: dict, robustness: dict, scoring: dict, plagiarism: dict) -> str:
    return (
        f"# Diagnostics for {strategy_name}\n\n"
        f"- Total PnL: {metrics['total_pnl']}\n"
        f"- Worst day: {metrics['worst_day_pnl']}\n"
        f"- Own trades: {metrics['own_trade_count']}\n"
        f"- Robustness status: {robustness.get('status')}\n"
        f"- Robustness score: {robustness.get('score', 0.0)}\n"
        f"- Composite score: {scoring['score']}\n"
        f"- External similarity max: {plagiarism.get('max_score', 0.0)}\n"
    )
