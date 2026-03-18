from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from prosperity.backtest import BacktestConfig, BacktestEngine, generate_tutorial_scenario, load_frames_from_csv
from traders.tutorial_trader import Trader


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
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for summary artifacts.",
    )
    args = parser.parse_args()

    if args.order_depth_csv:
        frames = load_frames_from_csv(args.order_depth_csv, args.trade_csv)
    else:
        frames = generate_tutorial_scenario(steps=args.steps, seed=args.seed)

    config = BacktestConfig(
        position_limits={"EMERALDS": 80, "TOMATOES": 80},
        submission_id="SUBMISSION",
        fill_model="queue_reactive",
        passive_fill_fraction=0.5,
    )
    engine = BacktestEngine(frames=frames, config=config)
    result = engine.run(Trader())

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write_summary(args.output_dir / "tutorial_summary.json", result)
    _write_equity_curve(args.output_dir / "tutorial_equity_curve.csv", result)
    _write_fills(args.output_dir / "tutorial_fills.csv", result)

    print(f"Steps: {len(result.step_summaries)}")
    print(f"Final PnL: {result.total_pnl:.2f}")
    print(f"Realized PnL: {result.realized_pnl:.2f}")
    print(f"Unrealized PnL: {result.unrealized_pnl:.2f}")
    print(f"Final positions: {result.final_positions}")
    print(f"Fill ratio: {result.metrics['fill_ratio']:.3f}")
    print(f"Max drawdown: {result.metrics['max_drawdown']:.2f}")
    print(f"Sharpe-like: {result.metrics['sharpe_like']:.2f}")


def _write_summary(path: Path, result) -> None:
    summary = {
        "total_pnl": result.total_pnl,
        "realized_pnl": result.realized_pnl,
        "unrealized_pnl": result.unrealized_pnl,
        "final_positions": result.final_positions,
        "metrics": result.metrics,
        "submitted_volume": result.submitted_volume,
        "filled_volume": result.filled_volume,
    }
    path.write_text(json.dumps(summary, indent=2))


def _write_equity_curve(path: Path, result) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "timestamp",
                "cash",
                "realized_pnl",
                "unrealized_pnl",
                "total_pnl",
                "own_trade_count",
                "positions",
            ]
        )
        for step in result.step_summaries:
            writer.writerow(
                [
                    step.timestamp,
                    f"{step.cash:.2f}",
                    f"{step.realized_pnl:.2f}",
                    f"{step.unrealized_pnl:.2f}",
                    f"{step.total_pnl:.2f}",
                    step.own_trade_count,
                    json.dumps(step.positions, sort_keys=True),
                ]
            )


def _write_fills(path: Path, result) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "symbol", "price", "quantity", "buyer", "seller"])
        for fill in result.fills:
            writer.writerow(
                [fill.timestamp, fill.symbol, fill.price, fill.quantity, fill.buyer or "", fill.seller or ""]
            )


if __name__ == "__main__":
    main()
