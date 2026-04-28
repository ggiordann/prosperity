from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from prosperity.round4_engine.config import EngineConfig
from prosperity.round4_engine.risk import PortfolioState, RiskManager
from prosperity.round4_engine.strategies import (
    MarketMakingStrategy,
    PassiveQuote,
    SignalCombinationEngine,
    VoucherArbitrageStrategy,
)


@dataclass(frozen=True)
class BacktestResult:
    label: str
    signals: pd.DataFrame
    trades: pd.DataFrame
    equity_curve: pd.DataFrame
    metrics: dict[str, float]
    product_pnl: pd.DataFrame

    def save(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.signals.to_csv(output_dir / f"{self.label}_signals.csv", index=False)
        self.trades.to_csv(output_dir / f"{self.label}_trades.csv", index=False)
        self.equity_curve.to_csv(output_dir / f"{self.label}_equity_curve.csv", index=False)
        self.product_pnl.to_csv(output_dir / f"{self.label}_product_pnl.csv", index=False)
        (output_dir / f"{self.label}_metrics.json").write_text(
            json.dumps(self.metrics, indent=2, sort_keys=True),
            encoding="utf-8",
        )


class BacktestEngine:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.risk = RiskManager(config.risk)
        self.signal_engine = SignalCombinationEngine(config.strategy, config.data)
        self.arbitrage = VoucherArbitrageStrategy(config.strategy, config.data)
        self.market_maker = MarketMakingStrategy(config.strategy)

    def run(
        self,
        feature_frame: pd.DataFrame,
        *,
        days: Iterable[int],
        label: str = "backtest",
        verbose: bool = False,
    ) -> BacktestResult:
        day_tuple = tuple(days)
        frame = feature_frame[feature_frame["day"].isin(day_tuple)].copy()
        if frame.empty:
            raise ValueError(f"No feature rows available for days={day_tuple}")

        signals = self.signal_engine.compute(frame)
        signals = signals.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)
        portfolio = PortfolioState()
        pending_quotes: dict[str, PassiveQuote] = {}
        trade_rows: list[dict[str, float | int | str]] = []
        equity_rows: list[dict[str, float | int]] = []
        last_mid_prices: dict[str, float] = {}
        previous_day: int | None = None

        for (day, timestamp), group in signals.groupby(["day", "timestamp"], sort=True):
            day_int = int(day)
            if previous_day is not None and day_int != previous_day:
                pending_quotes.clear()
            previous_day = day_int

            group = group.reset_index(drop=True)
            mid_prices = {
                str(product): float(mid_price)
                for product, mid_price in zip(
                    group["product"].to_numpy(),
                    group["mid_price"].to_numpy(),
                    strict=False,
                )
                if np.isfinite(mid_price)
            }
            last_mid_prices.update(mid_prices)
            equity_before = self.risk.mark_to_market(portfolio.cash, portfolio.positions, mid_prices)
            self.risk.update_stop_state(day_int, equity_before, portfolio)

            self._fill_pending_quotes(
                day_int,
                int(timestamp),
                group,
                pending_quotes,
                portfolio,
                mid_prices,
                trade_rows,
            )

            if portfolio.stopped:
                if self.config.risk.flatten_on_stop:
                    self._flatten_positions(
                        day_int,
                        int(timestamp),
                        group,
                        portfolio,
                        mid_prices,
                        trade_rows,
                    )
            else:
                self._execute_arbitrage(
                    day_int,
                    int(timestamp),
                    group,
                    portfolio,
                    mid_prices,
                    trade_rows,
                )
                self._execute_directional_signals(
                    day_int,
                    int(timestamp),
                    group,
                    portfolio,
                    mid_prices,
                    trade_rows,
                )
                pending_quotes = self._place_market_making_quotes(group, portfolio)

            equity = self.risk.mark_to_market(portfolio.cash, portfolio.positions, mid_prices)
            gross = self.risk.gross_exposure(portfolio.positions, mid_prices)
            portfolio.peak_equity = max(portfolio.peak_equity, equity)
            equity_rows.append(
                {
                    "day": day_int,
                    "timestamp": int(timestamp),
                    "cash": portfolio.cash,
                    "equity": equity,
                    "gross_exposure": gross,
                    "drawdown": max(0.0, portfolio.peak_equity - equity),
                    "stopped": int(portfolio.stopped),
                    "open_positions": sum(1 for position in portfolio.positions.values() if position),
                    "max_abs_position": max([abs(position) for position in portfolio.positions.values()] + [0]),
                }
            )

        trades = pd.DataFrame(trade_rows)
        equity_curve = pd.DataFrame(equity_rows)
        product_pnl = self._compute_product_pnl(trades, portfolio.positions, last_mid_prices)
        metrics = self._compute_metrics(equity_curve, trades, product_pnl)
        result = BacktestResult(
            label=label,
            signals=signals,
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            product_pnl=product_pnl,
        )
        if verbose:
            print(
                f"[{label}] pnl={metrics['total_pnl']:.2f} "
                f"sharpe={metrics['sharpe_ratio']:.3f} "
                f"drawdown={metrics['max_drawdown']:.2f} "
                f"trades={int(metrics['trade_count'])}"
            )
        return result

    def _execute_arbitrage(
        self,
        day: int,
        timestamp: int,
        group: pd.DataFrame,
        portfolio: PortfolioState,
        mid_prices: dict[str, float],
        trade_rows: list[dict[str, float | int | str]],
    ) -> None:
        legs = self.arbitrage.detect(group)
        if not legs:
            return
        by_product = group.set_index("product", drop=False)
        for leg in legs:
            if leg.product not in by_product.index:
                continue
            row = by_product.loc[leg.product]
            size = self.config.risk.arbitrage_order_size
            if leg.product == self.config.data.underlying_product and leg.reason.startswith("delta_hedge"):
                size = max(1, int(round(size * self.config.strategy.voucher_delta_hedge)))
            self._execute_aggressive_order(
                day,
                timestamp,
                row,
                leg.side,
                size,
                "voucher_arbitrage",
                portfolio,
                mid_prices,
                trade_rows,
                signal_edge=leg.edge,
                paired_product=leg.paired_product or "",
                reason=leg.reason,
            )

    def _execute_directional_signals(
        self,
        day: int,
        timestamp: int,
        group: pd.DataFrame,
        portfolio: PortfolioState,
        mid_prices: dict[str, float],
        trade_rows: list[dict[str, float | int | str]],
    ) -> None:
        active = group[group["final_signal"].ne(0)]
        for _, row in active.iterrows():
            side = int(row["final_signal"])
            if side == 0:
                continue
            base_size = (
                self.config.risk.voucher_order_size
                if bool(row["is_voucher"])
                else self.config.risk.market_order_size
            )
            size = max(1, int(round(base_size * min(float(row["signal_confidence"]), 2.5))))
            self._execute_aggressive_order(
                day,
                timestamp,
                row,
                side,
                size,
                "combined_signal",
                portfolio,
                mid_prices,
                trade_rows,
                signal_edge=float(row["final_signal_score"]),
                reason="weighted_vote",
            )

    def _flatten_positions(
        self,
        day: int,
        timestamp: int,
        group: pd.DataFrame,
        portfolio: PortfolioState,
        mid_prices: dict[str, float],
        trade_rows: list[dict[str, float | int | str]],
    ) -> None:
        by_product = group.set_index("product", drop=False)
        for product, position in list(portfolio.positions.items()):
            if position == 0 or product not in by_product.index:
                continue
            side = -1 if position > 0 else 1
            self._execute_aggressive_order(
                day,
                timestamp,
                by_product.loc[product],
                side,
                abs(position),
                "risk_flatten",
                portfolio,
                mid_prices,
                trade_rows,
                signal_edge=0.0,
                reason="stop_loss",
            )

    def _execute_aggressive_order(
        self,
        day: int,
        timestamp: int,
        row: pd.Series,
        side: int,
        requested_quantity: int,
        source: str,
        portfolio: PortfolioState,
        mid_prices: dict[str, float],
        trade_rows: list[dict[str, float | int | str]],
        *,
        signal_edge: float,
        paired_product: str = "",
        reason: str = "",
    ) -> None:
        product = str(row["product"])
        if side > 0:
            price = float(row["ask_price_1"])
            visible_quantity = int(max(float(row.get("ask_volume_1", 0.0)), 0.0))
        else:
            price = float(row["bid_price_1"])
            visible_quantity = int(max(float(row.get("bid_volume_1", 0.0)), 0.0))
        if not np.isfinite(price) or visible_quantity <= 0:
            return
        requested_quantity = min(requested_quantity, visible_quantity)
        quantity = self.risk.clip_quantity(
            product,
            side,
            requested_quantity,
            portfolio,
            mid_prices,
            price,
        )
        if quantity <= 0:
            return
        self._apply_fill(
            day,
            timestamp,
            product,
            side,
            quantity,
            price,
            source,
            portfolio,
            trade_rows,
            signal_edge=signal_edge,
            paired_product=paired_product,
            reason=reason,
            liquidity="taker",
        )

    def _place_market_making_quotes(
        self,
        group: pd.DataFrame,
        portfolio: PortfolioState,
    ) -> dict[str, PassiveQuote]:
        if not self.config.strategy.market_making_enabled:
            return {}
        quotes: dict[str, PassiveQuote] = {}
        eligible = group[
            (~group["is_voucher"].astype(bool))
            & (group["final_signal_score"].abs() <= self.config.strategy.combined_signal_threshold)
        ]
        for _, row in eligible.iterrows():
            product = str(row["product"])
            limit = self.risk.limit_for(product)
            quote = self.market_maker.quote(
                row,
                portfolio.position(product),
                limit,
                self.config.risk.market_making_quote_size,
            )
            if quote is not None:
                quotes[product] = quote
        return quotes

    def _fill_pending_quotes(
        self,
        day: int,
        timestamp: int,
        group: pd.DataFrame,
        pending_quotes: dict[str, PassiveQuote],
        portfolio: PortfolioState,
        mid_prices: dict[str, float],
        trade_rows: list[dict[str, float | int | str]],
    ) -> None:
        if not pending_quotes:
            return
        by_product = group.set_index("product", drop=False)
        for product, quote in list(pending_quotes.items()):
            if product not in by_product.index:
                continue
            row = by_product.loc[product]
            if quote.bid_quantity > 0 and float(row.ask_price_1) <= quote.bid_price:
                quantity = self.risk.clip_quantity(
                    product,
                    1,
                    min(quote.bid_quantity, int(max(float(row.ask_volume_1), 0.0))),
                    portfolio,
                    mid_prices,
                    quote.bid_price,
                )
                if quantity > 0:
                    self._apply_fill(
                        day,
                        timestamp,
                        product,
                        1,
                        quantity,
                        float(quote.bid_price),
                        "market_making",
                        portfolio,
                        trade_rows,
                        signal_edge=quote.fair_value - quote.bid_price,
                        reason="passive_bid_fill",
                        liquidity="maker",
                    )
            if quote.ask_quantity > 0 and float(row.bid_price_1) >= quote.ask_price:
                quantity = self.risk.clip_quantity(
                    product,
                    -1,
                    min(quote.ask_quantity, int(max(float(row.bid_volume_1), 0.0))),
                    portfolio,
                    mid_prices,
                    quote.ask_price,
                )
                if quantity > 0:
                    self._apply_fill(
                        day,
                        timestamp,
                        product,
                        -1,
                        quantity,
                        float(quote.ask_price),
                        "market_making",
                        portfolio,
                        trade_rows,
                        signal_edge=quote.ask_price - quote.fair_value,
                        reason="passive_ask_fill",
                        liquidity="maker",
                    )

    def _apply_fill(
        self,
        day: int,
        timestamp: int,
        product: str,
        side: int,
        quantity: int,
        price: float,
        source: str,
        portfolio: PortfolioState,
        trade_rows: list[dict[str, float | int | str]],
        *,
        signal_edge: float,
        reason: str,
        liquidity: str,
        paired_product: str = "",
    ) -> None:
        fee_per_unit = (
            self.config.risk.maker_fee_per_unit
            if liquidity == "maker"
            else self.config.risk.taker_fee_per_unit
        )
        fee = fee_per_unit * quantity
        portfolio.cash -= side * quantity * price
        portfolio.cash -= fee
        new_position = portfolio.position(product) + side * quantity
        portfolio.set_position(product, new_position)
        trade_rows.append(
            {
                "day": day,
                "timestamp": timestamp,
                "product": product,
                "side": side,
                "quantity": quantity,
                "price": price,
                "fee": fee,
                "cash_after": portfolio.cash,
                "position_after": new_position,
                "source": source,
                "reason": reason,
                "liquidity": liquidity,
                "signal_edge": signal_edge,
                "paired_product": paired_product,
            }
        )

    def _compute_product_pnl(
        self,
        trades: pd.DataFrame,
        final_positions: dict[str, int],
        last_mid_prices: dict[str, float],
    ) -> pd.DataFrame:
        products = sorted(set(last_mid_prices) | set(final_positions))
        rows: list[dict[str, float | int | str]] = []
        for product in products:
            product_trades = trades[trades["product"].eq(product)] if not trades.empty else pd.DataFrame()
            cash_flow = 0.0
            fees = 0.0
            turnover = 0.0
            if not product_trades.empty:
                cash_flow = float(
                    (-product_trades["side"] * product_trades["quantity"] * product_trades["price"]).sum()
                )
                fees = float(product_trades["fee"].sum())
                turnover = float((product_trades["quantity"] * product_trades["price"].abs()).sum())
            position = int(final_positions.get(product, 0))
            final_mid = float(last_mid_prices.get(product, 0.0))
            rows.append(
                {
                    "product": product,
                    "realized_cash_flow": cash_flow - fees,
                    "final_position": position,
                    "final_mid_price": final_mid,
                    "mark_to_market": position * final_mid,
                    "total_pnl": cash_flow - fees + position * final_mid,
                    "turnover": turnover,
                    "trade_count": int(len(product_trades)),
                }
            )
        return pd.DataFrame(rows).sort_values("total_pnl", ascending=False).reset_index(drop=True)

    @staticmethod
    def _compute_metrics(
        equity_curve: pd.DataFrame,
        trades: pd.DataFrame,
        product_pnl: pd.DataFrame,
    ) -> dict[str, float]:
        if equity_curve.empty:
            return {
                "total_pnl": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "trade_win_rate": 0.0,
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
        active_changes = pnl_changes[pnl_changes.abs() > 1e-12]
        win_rate = float((active_changes > 0.0).mean()) if len(active_changes) else 0.0
        return {
            "total_pnl": float(equity_curve["equity"].iloc[-1]),
            "product_pnl_sum": float(product_pnl["total_pnl"].sum()) if not product_pnl.empty else 0.0,
            "sharpe_ratio": sharpe,
            "max_drawdown": float(equity_curve["drawdown"].max()),
            "trade_win_rate": win_rate,
            "trade_count": float(len(trades)),
            "turnover": turnover,
            "mean_gross_exposure": float(equity_curve["gross_exposure"].mean()),
            "max_gross_exposure": float(equity_curve["gross_exposure"].max()),
            "max_abs_position": float(equity_curve["max_abs_position"].max()),
        }
