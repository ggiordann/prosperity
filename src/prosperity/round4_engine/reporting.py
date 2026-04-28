from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from prosperity.round4_engine.backtest import BacktestResult
from prosperity.round4_engine.config import EngineConfig


def save_performance_report(
    result: BacktestResult,
    config: EngineConfig,
    output_dir: Path,
    *,
    sweep: pd.DataFrame | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result.save(output_dir)
    (output_dir / "engine_config.json").write_text(
        json.dumps(config.to_json_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if sweep is not None and not sweep.empty:
        sweep.to_csv(output_dir / "validation_sweep.csv", index=False)
    _plot_equity(result, output_dir / f"{result.label}_equity_curve.png")
    _plot_inventory(result, output_dir / f"{result.label}_inventory.png")
    _write_markdown_summary(result, config, output_dir / f"{result.label}_report.md", sweep=sweep)


def _plot_equity(result: BacktestResult, path: Path) -> None:
    if result.equity_curve.empty:
        return
    plt.figure(figsize=(11, 5))
    x = result.equity_curve["day"].astype(str) + ":" + result.equity_curve["timestamp"].astype(str)
    plt.plot(range(len(result.equity_curve)), result.equity_curve["equity"], linewidth=1.4)
    plt.title("Round 4 Multi-Strategy Equity Curve")
    plt.xlabel("Tick")
    plt.ylabel("PnL")
    if len(x) > 0:
        ticks = list(range(0, len(x), max(len(x) // 8, 1)))
        plt.xticks(ticks, [x.iloc[tick] for tick in ticks], rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _plot_inventory(result: BacktestResult, path: Path) -> None:
    if result.trades.empty:
        return
    position_frame = result.trades.pivot_table(
        index=["day", "timestamp"],
        columns="product",
        values="position_after",
        aggfunc="last",
    ).ffill()
    if position_frame.empty:
        return
    plt.figure(figsize=(11, 6))
    for product in position_frame.columns:
        plt.plot(range(len(position_frame)), position_frame[product], linewidth=1.0, label=product)
    plt.title("Inventory Over Time")
    plt.xlabel("Trade Event")
    plt.ylabel("Position")
    plt.legend(loc="best", fontsize=7, ncol=2)
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def _write_markdown_summary(
    result: BacktestResult,
    config: EngineConfig,
    path: Path,
    *,
    sweep: pd.DataFrame | None,
) -> None:
    metrics = result.metrics
    lines = [
        "# Round 4 Multi-Strategy Trading Report",
        "",
        "## Metrics",
        "",
        f"- Total PnL: {metrics['total_pnl']:.2f}",
        f"- Sharpe ratio: {metrics['sharpe_ratio']:.4f}",
        f"- Max drawdown: {metrics['max_drawdown']:.2f}",
        f"- Trade win rate: {metrics['trade_win_rate']:.4f}",
        f"- Trade count: {int(metrics['trade_count'])}",
        f"- Turnover: {metrics['turnover']:.2f}",
        f"- Mean gross exposure: {metrics['mean_gross_exposure']:.2f}",
        f"- Max gross exposure: {metrics['max_gross_exposure']:.2f}",
        "",
        "## Strategies",
        "",
        "- Mean reversion: rolling-20 fair value with volatility-scaled thresholds.",
        "- Order-book imbalance: top-three-level depth imbalance with momentum confirmation.",
        "- Market making: dynamic fair-value quoting widened by volatility and inventory.",
        "- Voucher arbitrage: intrinsic-value, monotonicity, and call-spread-bound checks.",
        "- Trader behavior: walk-forward trader alpha scores from post-trade price movement.",
        "",
        "## Product PnL",
        "",
        _markdown_table(result.product_pnl) if not result.product_pnl.empty else "_No trades._",
        "",
    ]
    if sweep is not None and not sweep.empty:
        lines.extend(
            [
                "## Validation Sweep Top 10",
                "",
                _markdown_table(sweep.head(10)),
                "",
            ]
        )
    lines.extend(
        [
            "## Risk Settings",
            "",
            f"- Max gross exposure: {config.risk.max_gross_exposure:.2f}",
            f"- Stop loss: {config.risk.stop_loss:.2f}",
            f"- Max daily loss: {config.risk.max_daily_loss:.2f}",
            f"- Position limits: {config.risk.position_limits}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return ""
    columns = [str(column) for column in frame.columns]
    rows = ["| " + " | ".join(columns) + " |"]
    rows.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in frame.iterrows():
        values = []
        for value in row.tolist():
            if isinstance(value, float):
                values.append(f"{value:.4f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)
