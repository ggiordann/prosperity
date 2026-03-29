from __future__ import annotations

from prosperity.backtester.parser import BacktestSummary
from prosperity.dsl.normalization import normalized_spec_json
from prosperity.dsl.schema import StrategySpec


def spec_fingerprint(spec: StrategySpec) -> dict:
    payload = spec.model_dump(mode="json")
    return {
        "family": payload["metadata"]["family"],
        "fair_value_kinds": sorted(component["kind"] for component in payload["fair_value_models"]),
        "signal_kinds": sorted(component["kind"] for component in payload["signal_models"]),
        "layer_count": len(payload["execution_policy"]["market_making"]["layers"]),
        "normalized": normalized_spec_json(spec),
    }


def behavior_fingerprint(summary: BacktestSummary) -> dict:
    return {
        "total_pnl": summary.total_final_pnl,
        "day_pnls": [row.final_pnl for row in summary.day_results],
        "trade_counts": [row.own_trades for row in summary.day_results],
        "products": {
            row.product: [value for _, value in sorted(row.values.items())]
            for row in summary.product_contributions
        },
    }
