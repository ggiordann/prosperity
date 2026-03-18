from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Callable, Dict, List

from prosperity.backtest.engine import BacktestEngine
from prosperity.backtest.scenario import (
    discover_replay_files,
    generate_tutorial_scenario,
    load_frames_from_csv,
)
from prosperity.backtest.types import BacktestConfig, BacktestResult
from traders.tutorial_trader import Trader

DEFAULT_POSITION_LIMITS = {"EMERALDS": 80, "TOMATOES": 80}


def default_backtest_config() -> BacktestConfig:
    return BacktestConfig(
        position_limits=dict(DEFAULT_POSITION_LIMITS),
        submission_id="SUBMISSION",
        fill_model="queue_reactive",
        passive_fill_fraction=0.5,
    )


def run_frames_backtest(frames, trader_factory: Callable[[], Any] = Trader) -> BacktestResult:
    engine = BacktestEngine(frames=frames, config=default_backtest_config())
    trader = _build_trader(trader_factory)
    return engine.run(trader)


def run_synthetic_backtest(
    *,
    steps: int,
    seed: int,
    output_dir: str | Path,
    label: str = "tutorial",
    trader_factory: Callable[[], Any] = Trader,
) -> Dict[str, Any]:
    frames = generate_tutorial_scenario(steps=steps, seed=seed)
    result = run_frames_backtest(frames, trader_factory=trader_factory)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    run_payload = write_result_bundle(output_dir, label, result)
    return {
        "mode": "synthetic",
        "label": label,
        "output_dir": str(output_dir),
        "run": run_payload,
    }


def run_single_replay(
    *,
    order_depth_csv: str | Path,
    trade_csv: str | Path | None,
    output_dir: str | Path,
    label: str | None = None,
    trader_factory: Callable[[], Any] = Trader,
) -> Dict[str, Any]:
    order_depth_csv = Path(order_depth_csv)
    frames = load_frames_from_csv(order_depth_csv, trade_csv)
    result = run_frames_backtest(frames, trader_factory=trader_factory)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    label = label or order_depth_csv.stem.removeprefix("prices_")
    run_payload = write_result_bundle(output_dir, label, result)
    return {
        "mode": "single_replay",
        "label": label,
        "output_dir": str(output_dir),
        "run": run_payload,
    }


def run_directory_backtest(
    *,
    data_dir: str | Path,
    output_dir: str | Path,
    trader_factory: Callable[[], Any] = Trader,
) -> Dict[str, Any]:
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    aggregate_total_pnl = 0.0
    aggregate_realized_pnl = 0.0
    aggregate_unrealized_pnl = 0.0
    aggregate_submitted_volume = 0
    aggregate_filled_volume = 0
    runs: List[Dict[str, Any]] = []

    for label, order_depth_csv, trade_csv in discover_replay_files(data_dir):
        frames = load_frames_from_csv(order_depth_csv, trade_csv)
        result = run_frames_backtest(frames, trader_factory=trader_factory)
        run_payload = write_result_bundle(output_dir, label, result)
        run_payload["source"] = {
            "order_depth_csv": str(order_depth_csv),
            "trade_csv": str(trade_csv) if trade_csv else None,
        }
        runs.append(run_payload)

        aggregate_total_pnl += result.total_pnl
        aggregate_realized_pnl += result.realized_pnl
        aggregate_unrealized_pnl += result.unrealized_pnl
        aggregate_submitted_volume += result.submitted_volume
        aggregate_filled_volume += result.filled_volume

    aggregate = {
        "runs": len(runs),
        "total_pnl": aggregate_total_pnl,
        "realized_pnl": aggregate_realized_pnl,
        "unrealized_pnl": aggregate_unrealized_pnl,
        "submitted_volume": aggregate_submitted_volume,
        "filled_volume": aggregate_filled_volume,
        "fill_ratio": (
            aggregate_filled_volume / aggregate_submitted_volume if aggregate_submitted_volume else 0.0
        ),
    }
    (output_dir / "aggregate_summary.json").write_text(json.dumps(aggregate, indent=2))

    return {
        "mode": "directory",
        "data_dir": str(data_dir),
        "output_dir": str(output_dir),
        "aggregate": aggregate,
        "runs": runs,
    }


def write_result_bundle(output_dir: str | Path, label: str, result: BacktestResult) -> Dict[str, Any]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / f"{label}_summary.json"
    equity_curve_path = output_dir / f"{label}_equity_curve.csv"
    fills_path = output_dir / f"{label}_fills.csv"

    summary = result_to_summary(result)
    summary_path.write_text(json.dumps(summary, indent=2))
    _write_equity_curve(equity_curve_path, result)
    _write_fills(fills_path, result)

    return {
        "label": label,
        "summary": summary,
        "files": {
            "summary": str(summary_path),
            "equity_curve": str(equity_curve_path),
            "fills": str(fills_path),
        },
    }


def result_to_summary(result: BacktestResult) -> Dict[str, Any]:
    return {
        "total_pnl": result.total_pnl,
        "realized_pnl": result.realized_pnl,
        "unrealized_pnl": result.unrealized_pnl,
        "final_positions": result.final_positions,
        "metrics": result.metrics,
        "submitted_volume": result.submitted_volume,
        "filled_volume": result.filled_volume,
    }


def load_result_index(output_dir: str | Path) -> Dict[str, Any]:
    output_dir = Path(output_dir)
    aggregate_path = output_dir / "aggregate_summary.json"
    aggregate = json.loads(aggregate_path.read_text()) if aggregate_path.exists() else None

    runs: List[Dict[str, Any]] = []
    for summary_path in sorted(output_dir.glob("*_summary.json")):
        if summary_path.name == "aggregate_summary.json":
            continue
        label = summary_path.stem.removesuffix("_summary")
        summary = json.loads(summary_path.read_text())
        runs.append(
            {
                "label": label,
                "summary": summary,
                "files": {
                    "summary": str(summary_path),
                    "equity_curve": str(output_dir / f"{label}_equity_curve.csv"),
                    "fills": str(output_dir / f"{label}_fills.csv"),
                },
            }
        )

    return {
        "output_dir": str(output_dir),
        "aggregate": aggregate,
        "runs": runs,
    }


def load_equity_curve(output_dir: str | Path, label: str) -> List[Dict[str, Any]]:
    output_dir = Path(output_dir)
    path = output_dir / f"{label}_equity_curve.csv"
    rows: List[Dict[str, Any]] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "timestamp": int(row["timestamp"]),
                    "cash": float(row["cash"]),
                    "realized_pnl": float(row["realized_pnl"]),
                    "unrealized_pnl": float(row["unrealized_pnl"]),
                    "total_pnl": float(row["total_pnl"]),
                    "own_trade_count": int(row["own_trade_count"]),
                    "positions": json.loads(row["positions"]),
                }
            )
    return rows


def load_fills(output_dir: str | Path, label: str, limit: int | None = None) -> List[Dict[str, Any]]:
    output_dir = Path(output_dir)
    path = output_dir / f"{label}_fills.csv"
    rows: List[Dict[str, Any]] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                {
                    "timestamp": int(row["timestamp"]),
                    "symbol": row["symbol"],
                    "price": int(row["price"]),
                    "quantity": int(row["quantity"]),
                    "buyer": row["buyer"],
                    "seller": row["seller"],
                }
            )
    if limit is not None:
        return rows[:limit]
    return rows


def _build_trader(trader_factory):
    if hasattr(trader_factory, "run") and not isinstance(trader_factory, type):
        return trader_factory
    return trader_factory()


def _write_equity_curve(path: Path, result: BacktestResult) -> None:
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


def _write_fills(path: Path, result: BacktestResult) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "symbol", "price", "quantity", "buyer", "seller"])
        for fill in result.fills:
            writer.writerow(
                [fill.timestamp, fill.symbol, fill.price, fill.quantity, fill.buyer or "", fill.seller or ""]
            )
