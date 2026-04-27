from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

from prosperity.round4_ml.config import BacktestConfig


@dataclass
class BacktestResult:
    signals: pd.DataFrame
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    metrics: dict[str, float]

    def save(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.signals.to_csv(output_dir / "trading_signals.csv", index=False)
        self.trades.to_csv(output_dir / "simulated_trades.csv", index=False)
        self.equity_curve.to_csv(output_dir / "equity_curve.csv", index=False)
        (output_dir / "backtest_metrics.json").write_text(
            json.dumps(self.metrics, indent=2, sort_keys=True),
            encoding="utf-8",
        )


@dataclass
class BacktestOptimizationResult:
    config: BacktestConfig
    sweep: pd.DataFrame

    @property
    def best_row(self) -> dict[str, float]:
        if self.sweep.empty:
            return {}
        return self.sweep.iloc[0].to_dict()


def optimize_backtest_config(
    validation_predictions: pd.DataFrame,
    base_config: BacktestConfig,
) -> BacktestOptimizationResult:
    """Tune signal/risk thresholds on validation PnL before evaluating Day 3."""

    rows = []
    best_score = -float("inf")
    best_config = base_config
    for asset_multiplier in [0.25, 0.6]:
        for voucher_multiplier in [0.04, 0.12]:
            for spread_multiplier in [0.5, 0.9]:
                for risk_aversion in [0.0, 0.2]:
                    for min_edge in [0.25, 0.5]:
                        candidate = replace(
                            base_config,
                            asset_vol_threshold_multiplier=asset_multiplier,
                            voucher_vol_threshold_multiplier=voucher_multiplier,
                            spread_threshold_multiplier=spread_multiplier,
                            risk_aversion=risk_aversion,
                            min_edge=min_edge,
                        )
                        signals = generate_signals(validation_predictions, candidate)
                        result = run_backtest(signals, candidate)
                        score = result.metrics["total_pnl"] - 0.05 * result.metrics["max_drawdown"]
                        row = {
                            "score": score,
                            "asset_vol_threshold_multiplier": asset_multiplier,
                            "voucher_vol_threshold_multiplier": voucher_multiplier,
                            "spread_threshold_multiplier": spread_multiplier,
                            "risk_aversion": risk_aversion,
                            "min_edge": min_edge,
                            **result.metrics,
                        }
                        rows.append(row)
                        if score > best_score:
                            best_score = score
                            best_config = candidate
    sweep = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    return BacktestOptimizationResult(config=best_config, sweep=sweep)


def generate_signals(predictions: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    frame = predictions.copy()
    price_prediction_columns = [
        column for column in frame.columns if column.startswith("predicted_price_change_")
    ]
    if not price_prediction_columns:
        raise ValueError("Predictions must include predicted_price_change_* columns.")

    frame["predicted_price_edge"] = frame[price_prediction_columns].mean(axis=1)
    spread_component = config.spread_threshold_multiplier * frame["bid_ask_spread"].abs().fillna(0.0)
    price_volatility = (
        frame["mid_price"].abs()
        * frame.get("rolling_volatility_20", 0.0).fillna(0.0)
        * np.sqrt(max(len(price_prediction_columns), 1))
    )
    asset_threshold = np.maximum(
        config.min_edge,
        spread_component + config.asset_vol_threshold_multiplier * price_volatility,
    )

    voucher_volatility = (
        frame.get("underlying_mid_price", frame["mid_price"]).abs()
        * frame["predicted_future_volatility"].clip(lower=0.0)
        * np.sqrt(frame.get("time_to_expiry_years", 1.0).clip(lower=1e-6))
    )
    voucher_threshold = np.maximum(
        config.min_edge,
        spread_component + config.voucher_vol_threshold_multiplier * voucher_volatility,
    )

    frame["voucher_mispricing_edge"] = frame["predicted_voucher_fair_price"] - frame["mid_price"]
    is_voucher = frame.get("is_voucher", 0.0).fillna(0.0) > 0.0
    frame["signal_edge"] = np.where(is_voucher, frame["voucher_mispricing_edge"], frame["predicted_price_edge"])
    frame["dynamic_threshold"] = np.where(is_voucher, voucher_threshold, asset_threshold)
    frame["raw_signal"] = np.select(
        [
            frame["signal_edge"] > frame["dynamic_threshold"],
            frame["signal_edge"] < -frame["dynamic_threshold"],
        ],
        [1, -1],
        default=0,
    )
    frame["signal_confidence"] = frame["signal_edge"].abs() / frame["dynamic_threshold"].clip(lower=1e-6)
    return frame


def run_backtest(signals: pd.DataFrame, config: BacktestConfig) -> BacktestResult:
    frame = signals.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)
    positions: dict[str, int] = {}
    cash = 0.0
    peak_equity = 0.0
    stopped = False
    trade_rows: list[dict[str, float | int | str]] = []
    equity_rows: list[dict[str, float | int]] = []

    for (day, timestamp), group in frame.groupby(["day", "timestamp"], sort=True):
        current_mid = group.set_index("product")["mid_price"].to_dict()
        equity_before = mark_to_market(cash, positions, current_mid)
        peak_equity = max(peak_equity, equity_before)
        drawdown = peak_equity - equity_before
        if drawdown >= config.stop_loss:
            stopped = True

        for row in group.itertuples(index=False):
            product = str(row.product)
            side = int(row.raw_signal)
            position = positions.get(product, 0)
            if stopped:
                if not config.flatten_on_stop or position == 0:
                    continue
                side = -1 if position > 0 else 1
            if side == 0:
                continue

            limit = config.position_limits.get(product, config.position_limits.get("DEFAULT", 100))
            order_size = config.voucher_order_size if float(getattr(row, "is_voucher", 0.0)) > 0.0 else config.asset_order_size
            risk_penalty = config.risk_aversion * abs(position) / max(float(limit), 1.0)
            if not stopped and float(row.signal_confidence) <= 1.0 + risk_penalty:
                continue

            if side > 0:
                available = int(max(float(getattr(row, "ask_volume_1", 0.0) or 0.0), 0.0))
                price = float(row.best_ask)
                max_position_qty = limit - position
            else:
                available = int(max(float(getattr(row, "bid_volume_1", 0.0) or 0.0), 0.0))
                price = float(row.best_bid)
                max_position_qty = limit + position

            if not np.isfinite(price) or available <= 0 or max_position_qty <= 0:
                continue
            quantity = int(min(order_size, available, max_position_qty))
            if quantity <= 0:
                continue

            projected_positions = positions.copy()
            projected_positions[product] = position + side * quantity
            projected_gross = gross_exposure(projected_positions, current_mid)
            current_gross = gross_exposure(positions, current_mid)
            if projected_gross > config.max_gross_exposure and projected_gross > current_gross:
                continue

            fee = config.taker_fee_per_unit * quantity
            cash -= side * quantity * price
            cash -= fee
            positions[product] = projected_positions[product]
            trade_rows.append(
                {
                    "day": int(day),
                    "timestamp": int(timestamp),
                    "product": product,
                    "side": side,
                    "quantity": quantity,
                    "price": price,
                    "cash_after": cash,
                    "position_after": positions[product],
                    "signal_edge": float(row.signal_edge),
                    "dynamic_threshold": float(row.dynamic_threshold),
                    "gross_exposure_after": projected_gross,
                    "stopped": int(stopped),
                }
            )

        equity = mark_to_market(cash, positions, current_mid)
        gross = gross_exposure(positions, current_mid)
        peak_equity = max(peak_equity, equity)
        equity_rows.append(
            {
                "day": int(day),
                "timestamp": int(timestamp),
                "cash": cash,
                "equity": equity,
                "gross_exposure": gross,
                "drawdown": max(0.0, peak_equity - equity),
                "stopped": int(stopped),
                "open_positions": sum(1 for value in positions.values() if value != 0),
                "max_abs_position": max([abs(value) for value in positions.values()] + [0]),
            }
        )

    trades = pd.DataFrame(trade_rows)
    equity_curve = pd.DataFrame(equity_rows)
    metrics = compute_metrics(equity_curve, trades)
    return BacktestResult(signals=frame, trades=trades, equity_curve=equity_curve, metrics=metrics)


def mark_to_market(cash: float, positions: dict[str, int], mid_prices: dict[str, float]) -> float:
    equity = cash
    for product, position in positions.items():
        mid = mid_prices.get(product)
        if mid is not None and np.isfinite(mid):
            equity += position * float(mid)
    return float(equity)


def gross_exposure(positions: dict[str, int], mid_prices: dict[str, float]) -> float:
    gross = 0.0
    for product, position in positions.items():
        mid = mid_prices.get(product)
        if mid is not None and np.isfinite(mid):
            gross += abs(position) * abs(float(mid))
    return float(gross)


def compute_metrics(equity_curve: pd.DataFrame, trades: pd.DataFrame) -> dict[str, float]:
    if equity_curve.empty:
        return {
            "total_pnl": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "win_rate": 0.0,
            "trade_count": 0.0,
            "turnover": 0.0,
            "mean_gross_exposure": 0.0,
            "max_gross_exposure": 0.0,
            "max_abs_position": 0.0,
        }
    pnl_changes = equity_curve["equity"].diff().fillna(equity_curve["equity"])
    volatility = float(pnl_changes.std(ddof=0))
    sharpe = 0.0 if volatility <= 1e-12 else float(pnl_changes.mean() / volatility * np.sqrt(len(pnl_changes)))
    turnover = 0.0
    if not trades.empty:
        turnover = float((trades["quantity"].abs() * trades["price"].abs()).sum())
    active_changes = pnl_changes[pnl_changes != 0.0]
    win_rate = float((active_changes > 0.0).mean()) if len(active_changes) else 0.0
    return {
        "total_pnl": float(equity_curve["equity"].iloc[-1]),
        "sharpe_ratio": sharpe,
        "max_drawdown": float(equity_curve["drawdown"].max()),
        "win_rate": win_rate,
        "trade_count": float(len(trades)),
        "turnover": turnover,
        "mean_gross_exposure": float(equity_curve["gross_exposure"].mean()),
        "max_gross_exposure": float(equity_curve["gross_exposure"].max()),
        "max_abs_position": float(equity_curve["max_abs_position"].max()),
    }
