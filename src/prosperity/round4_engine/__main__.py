from __future__ import annotations

import argparse
import json
from dataclasses import replace
from itertools import product
from pathlib import Path

import pandas as pd

from prosperity.round4_engine.backtest import BacktestEngine, BacktestResult
from prosperity.round4_engine.config import (
    EngineConfig,
    Round4DataConfig,
    StrategyConfig,
    StrategyWeights,
)
from prosperity.round4_engine.data import load_round4_data
from prosperity.round4_engine.features import FeatureEngineer
from prosperity.round4_engine.reporting import save_performance_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Round 4 deterministic multi-strategy engine")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("prosperity_rust_backtester/datasets/round4"),
        help="Directory containing prices_round_4_day_*.csv and trades_round_4_day_*.csv.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("analysis/round4_engine_outputs"),
        help="Directory for reports, CSVs, metrics, and plots.",
    )
    parser.add_argument("--no-tune", action="store_true", help="Run only the baseline config.")
    parser.add_argument(
        "--enable-market-making",
        action="store_true",
        help="Enable passive market-making fills in the historical simulator.",
    )
    parser.add_argument("--max-runs", type=int, default=36, help="Maximum validation configs to backtest.")
    parser.add_argument("--target-pnl", type=float, default=1_000_000.0, help="Validation PnL target.")
    return parser.parse_args()


def candidate_strategy_configs(base: StrategyConfig) -> list[StrategyConfig]:
    weight_sets = [
        StrategyWeights(mean_reversion=0.85, imbalance=0.95, trader=0.55),
        StrategyWeights(mean_reversion=1.15, imbalance=0.70, trader=0.65),
        StrategyWeights(mean_reversion=0.60, imbalance=1.25, trader=0.45),
        StrategyWeights(mean_reversion=0.95, imbalance=0.85, trader=0.95),
    ]
    candidates: list[StrategyConfig] = []
    for (
        weights,
        mean_reversion_vol_multiplier,
        imbalance_threshold,
        combined_signal_threshold,
        voucher_cross_edge,
        execution_cost_multiplier,
    ) in product(
        weight_sets,
        [0.85, 1.15, 1.45],
        [0.12, 0.18, 0.24],
        [0.70, 0.90],
        [0.25, 0.45],
        [1.5, 2.0, 3.0, 5.0],
    ):
        candidates.append(
            replace(
                base,
                weights=weights,
                mean_reversion_vol_multiplier=mean_reversion_vol_multiplier,
                imbalance_threshold=imbalance_threshold,
                combined_signal_threshold=combined_signal_threshold,
                voucher_cross_edge=voucher_cross_edge,
                execution_cost_multiplier=execution_cost_multiplier,
            )
        )
    return candidates


def tune_on_validation(
    base_config: EngineConfig,
    validation_features: pd.DataFrame,
    *,
    max_runs: int,
    target_pnl: float,
) -> tuple[EngineConfig, pd.DataFrame, BacktestResult]:
    rows: list[dict[str, float | int]] = []
    best_result: BacktestResult | None = None
    best_config = base_config
    best_score = -float("inf")

    candidates = candidate_strategy_configs(base_config.strategy)
    for idx, strategy_config in enumerate(candidates[:max_runs], start=1):
        candidate = replace(base_config, strategy=strategy_config)
        result = BacktestEngine(candidate).run(
            validation_features,
            days=base_config.data.validation_days,
            label=f"validation_{idx:03d}",
            verbose=True,
        )
        metrics = result.metrics
        score = metrics["total_pnl"] - 0.05 * metrics["max_drawdown"]
        rows.append(
            {
                "run": idx,
                "score": score,
                "total_pnl": metrics["total_pnl"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "trade_count": metrics["trade_count"],
                "mean_reversion_weight": strategy_config.weights.mean_reversion,
                "imbalance_weight": strategy_config.weights.imbalance,
                "trader_weight": strategy_config.weights.trader,
                "mean_reversion_vol_multiplier": strategy_config.mean_reversion_vol_multiplier,
                "imbalance_threshold": strategy_config.imbalance_threshold,
                "combined_signal_threshold": strategy_config.combined_signal_threshold,
                "voucher_cross_edge": strategy_config.voucher_cross_edge,
                "execution_cost_multiplier": strategy_config.execution_cost_multiplier,
            }
        )
        if score > best_score:
            best_score = score
            best_config = candidate
            best_result = result
        if metrics["total_pnl"] >= target_pnl:
            print(f"Target reached on validation run {idx}: pnl={metrics['total_pnl']:.2f}")
            break

    if best_result is None:
        raise RuntimeError("Validation tuning did not run any backtests.")
    sweep = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return best_config, sweep, best_result


def main() -> None:
    args = parse_args()
    data_config = Round4DataConfig(data_dir=args.data_dir)
    strategy_config = StrategyConfig(market_making_enabled=args.enable_market_making)
    base_config = EngineConfig(data=data_config, strategy=strategy_config, output_dir=args.output_dir)

    market_data = load_round4_data(data_config)
    engineer = FeatureEngineer(data_config)

    validation_feature_set = engineer.build(market_data, fit_days=data_config.train_days)
    baseline = BacktestEngine(base_config).run(
        validation_feature_set.frame,
        days=data_config.validation_days,
        label="validation_baseline",
        verbose=True,
    )

    if args.no_tune:
        best_config = base_config
        sweep = pd.DataFrame()
        best_validation = baseline
    else:
        best_config, sweep, best_validation = tune_on_validation(
            base_config,
            validation_feature_set.frame,
            max_runs=args.max_runs,
            target_pnl=args.target_pnl,
        )
        save_performance_report(best_validation, best_config, args.output_dir / "validation", sweep=sweep)

    final_feature_set = engineer.build(
        market_data,
        fit_days=data_config.train_days + data_config.validation_days,
    )
    final_result = BacktestEngine(best_config).run(
        final_feature_set.frame,
        days=data_config.test_days,
        label="test_day3",
        verbose=True,
    )
    save_performance_report(final_result, best_config, args.output_dir, sweep=sweep)
    final_feature_set.trader_profiles.frame.to_csv(args.output_dir / "trader_profiles.csv", index=False)
    (args.output_dir / "best_engine_config.json").write_text(
        json.dumps(best_config.to_json_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        "Final Day 3 backtest: "
        f"pnl={final_result.metrics['total_pnl']:.2f}, "
        f"sharpe={final_result.metrics['sharpe_ratio']:.3f}, "
        f"drawdown={final_result.metrics['max_drawdown']:.2f}, "
        f"trades={int(final_result.metrics['trade_count'])}"
    )


if __name__ == "__main__":
    main()
