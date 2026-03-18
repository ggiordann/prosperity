from __future__ import annotations

import argparse
from pathlib import Path

from prosperity.backtest import run_directory_backtest, run_single_replay, run_synthetic_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local Prosperity tutorial backtest.")
    parser.add_argument("--steps", type=int, default=1000, help="Number of synthetic steps to generate.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed for the synthetic scenario.")
    parser.add_argument(
        "--order-depth-csv",
        type=Path,
        help="Optional path to an order depth replay CSV.",
    )
    parser.add_argument(
        "--trade-csv",
        type=Path,
        help="Optional path to a trade replay CSV matching the order depth timestamps.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Optional directory containing IMC prices_*.csv and trades_*.csv files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for summary artifacts.",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.data_dir:
        payload = run_directory_backtest(data_dir=args.data_dir, output_dir=args.output_dir)
        _print_directory_payload(payload)
        return

    if args.order_depth_csv:
        label = args.order_depth_csv.stem.removeprefix("prices_")
        payload = run_single_replay(
            order_depth_csv=args.order_depth_csv,
            trade_csv=args.trade_csv,
            output_dir=args.output_dir,
            label=label,
        )
    else:
        payload = run_synthetic_backtest(
            steps=args.steps,
            seed=args.seed,
            output_dir=args.output_dir,
            label="tutorial",
        )

    _print_run_payload(payload["run"])


def _print_directory_payload(payload) -> None:
    for run in payload["runs"]:
        _print_run_payload(run)
    print("Aggregate")
    print(f"Runs: {payload['aggregate']['runs']}")
    print(f"Total PnL: {payload['aggregate']['total_pnl']:.2f}")
    print(f"Realized PnL: {payload['aggregate']['realized_pnl']:.2f}")
    print(f"Unrealized PnL: {payload['aggregate']['unrealized_pnl']:.2f}")
    print(f"Fill ratio: {payload['aggregate']['fill_ratio']:.3f}")


def _print_run_payload(run) -> None:
    summary = run["summary"]
    print(run["label"])
    print(f"Final PnL: {summary['total_pnl']:.2f}")
    print(f"Realized PnL: {summary['realized_pnl']:.2f}")
    print(f"Unrealized PnL: {summary['unrealized_pnl']:.2f}")
    print(f"Final positions: {summary['final_positions']}")
    print(f"Fill ratio: {summary['metrics']['fill_ratio']:.3f}")
    print(f"Max drawdown: {summary['metrics']['max_drawdown']:.2f}")
    print(f"Sharpe-like: {summary['metrics']['sharpe_like']:.2f}")


if __name__ == "__main__":
    main()
