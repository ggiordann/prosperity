from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from prosperity.round4_engine.config import Round4DataConfig, StrategyConfig


@dataclass(frozen=True)
class PassiveQuote:
    product: str
    bid_price: int
    ask_price: int
    bid_quantity: int
    ask_quantity: int
    fair_value: float
    half_spread: float


@dataclass(frozen=True)
class ArbitrageLeg:
    product: str
    side: int
    edge: float
    reason: str
    paired_product: str | None = None


class MeanReversionStrategy:
    def __init__(self, config: StrategyConfig):
        self.config = config

    def compute(self, frame: pd.DataFrame) -> pd.DataFrame:
        window = self.config.mean_reversion_window
        fair_value = frame[f"rolling_mean_{window}"]
        volatility_edge = frame["mid_price"].abs() * frame[f"rolling_volatility_{window}"].fillna(0.0)
        threshold = np.maximum(
            self.config.mean_reversion_min_edge,
            self.config.mean_reversion_vol_multiplier * volatility_edge
            + 0.20 * frame["bid_ask_spread"].abs().fillna(0.0),
        )
        deviation = frame["mid_price"] - fair_value
        signal = np.select(
            [deviation > threshold, deviation < -threshold],
            [-1.0, 1.0],
            default=0.0,
        )
        result = pd.DataFrame(index=frame.index)
        result["mean_reversion_fair_value"] = fair_value
        result["mean_reversion_edge"] = -deviation
        result["mean_reversion_threshold"] = threshold
        result["mean_reversion_signal"] = signal
        result["mean_reversion_confidence"] = (deviation.abs() / np.maximum(threshold, 1e-9)).clip(0.0, 4.0)
        return result


class OrderBookImbalanceStrategy:
    def __init__(self, config: StrategyConfig):
        self.config = config

    def compute(self, frame: pd.DataFrame) -> pd.DataFrame:
        imbalance = 0.65 * frame["order_book_imbalance"] + 0.35 * frame["depth_imbalance"]
        momentum = frame[f"momentum_{self.config.imbalance_momentum_window}"]
        threshold = self.config.imbalance_threshold
        buy = (imbalance > threshold) & (momentum >= 0.0)
        sell = (imbalance < -threshold) & (momentum <= 0.0)
        signal = np.select([buy, sell], [1.0, -1.0], default=0.0)
        result = pd.DataFrame(index=frame.index)
        result["imbalance_score"] = imbalance
        result["imbalance_signal"] = signal
        result["imbalance_confidence"] = (imbalance.abs() / max(threshold, 1e-9)).clip(0.0, 4.0)
        return result


class TraderBehaviorStrategy:
    def __init__(self, config: StrategyConfig, data_config: Round4DataConfig):
        self.config = config
        self.data_config = data_config

    def compute(self, frame: pd.DataFrame) -> pd.DataFrame:
        window = self.data_config.trader_activity_window
        alpha = frame[f"rolling_trader_alpha_signal_{window}"].fillna(0.0)
        threshold = self.config.trader_alpha_threshold
        signal = np.select(
            [alpha > threshold, alpha < -threshold],
            [1.0, -1.0],
            default=0.0,
        )
        result = pd.DataFrame(index=frame.index)
        result["trader_signal_strength"] = alpha
        result["trader_signal"] = signal
        result["trader_confidence"] = (alpha.abs() / max(threshold, 1e-9)).clip(0.0, 4.0)
        return result


class SignalCombinationEngine:
    def __init__(self, strategy_config: StrategyConfig, data_config: Round4DataConfig):
        self.strategy_config = strategy_config
        self.data_config = data_config
        self.mean_reversion = MeanReversionStrategy(strategy_config)
        self.imbalance = OrderBookImbalanceStrategy(strategy_config)
        self.trader = TraderBehaviorStrategy(strategy_config, data_config)

    def compute(self, frame: pd.DataFrame) -> pd.DataFrame:
        signals = frame.copy()
        parts = [
            self.mean_reversion.compute(frame),
            self.imbalance.compute(frame),
            self.trader.compute(frame),
        ]
        for part in parts:
            signals = signals.join(part)

        weights = self.strategy_config.weights
        weighted_score = (
            weights.mean_reversion
            * signals["mean_reversion_signal"]
            * signals["mean_reversion_confidence"]
            + weights.imbalance * signals["imbalance_signal"] * signals["imbalance_confidence"]
            + weights.trader * signals["trader_signal"] * signals["trader_confidence"]
        )
        dollar_edge = (
            weights.mean_reversion * signals["mean_reversion_edge"].fillna(0.0)
            + weights.imbalance
            * signals["imbalance_score"].fillna(0.0)
            * signals["bid_ask_spread"].abs().fillna(0.0)
            * 0.5
            + weights.trader
            * signals["trader_signal_strength"].fillna(0.0)
            * signals["mid_price"].abs().fillna(0.0)
            * signals["rolling_volatility_20"].fillna(0.0)
            * 4.0
        )
        signals["final_signal_score"] = weighted_score
        signals["execution_edge"] = dollar_edge
        visible_cost = (
            self.strategy_config.execution_cost_multiplier
            * signals["bid_ask_spread"].abs().fillna(0.0)
            + 0.10
        )
        threshold = self.strategy_config.combined_signal_threshold
        signals["final_signal"] = np.select(
            [
                (weighted_score > threshold) & (dollar_edge > visible_cost),
                (weighted_score < -threshold) & (dollar_edge < -visible_cost),
            ],
            [1, -1],
            default=0,
        )
        if not self.strategy_config.directional_voucher_trading_enabled:
            signals.loc[signals["is_voucher"].astype(bool), "final_signal"] = 0
        signals["signal_confidence"] = (weighted_score.abs() / max(threshold, 1e-9)).clip(0.0, 8.0)
        return signals


class MarketMakingStrategy:
    def __init__(self, config: StrategyConfig):
        self.config = config

    def quote(self, row: pd.Series, position: int, limit: int, quantity: int) -> PassiveQuote | None:
        if not self.config.market_making_enabled:
            return None
        if not np.isfinite(row.best_bid) or not np.isfinite(row.best_ask):
            return None

        fair_value = float(row.mean_reversion_fair_value)
        if not np.isfinite(fair_value) or fair_value <= 0.0:
            fair_value = float(row.mid_price)

        volatility_edge = abs(float(row.mid_price)) * max(float(row.rolling_volatility_20), 0.0)
        inventory_ratio = abs(position) / max(float(limit), 1.0)
        half_spread = (
            self.config.market_making_base_spread
            + self.config.market_making_vol_multiplier * volatility_edge
            + self.config.market_making_inventory_multiplier * inventory_ratio * max(float(row.bid_ask_spread), 1.0)
        )
        half_spread = float(
            np.clip(
                half_spread,
                self.config.market_making_min_spread,
                self.config.market_making_max_spread,
            )
        )
        skew = -math.copysign(inventory_ratio * half_spread, position) if position else 0.0
        fair_value += skew
        bid_price = min(int(math.floor(fair_value - half_spread)), int(row.best_ask) - 1)
        ask_price = max(int(math.ceil(fair_value + half_spread)), int(row.best_bid) + 1)
        if bid_price >= ask_price:
            return None

        buy_capacity = max(0, limit - position)
        sell_capacity = max(0, limit + position)
        bid_quantity = min(quantity, buy_capacity)
        ask_quantity = min(quantity, sell_capacity)
        if bid_quantity <= 0 and ask_quantity <= 0:
            return None
        return PassiveQuote(
            product=str(row.product),
            bid_price=bid_price,
            ask_price=ask_price,
            bid_quantity=bid_quantity,
            ask_quantity=ask_quantity,
            fair_value=fair_value,
            half_spread=half_spread,
        )


class VoucherArbitrageStrategy:
    def __init__(self, config: StrategyConfig, data_config: Round4DataConfig):
        self.config = config
        self.data_config = data_config

    def detect(self, timestamp_group: pd.DataFrame) -> list[ArbitrageLeg]:
        legs: list[ArbitrageLeg] = []
        if not timestamp_group["product"].eq(self.data_config.underlying_product).any():
            return legs

        vouchers = timestamp_group.loc[
            timestamp_group["is_voucher"].astype(bool),
            ["product", "strike", "ask_price_1", "bid_price_1", "intrinsic_value"],
        ].sort_values("strike")
        if vouchers.empty:
            return legs

        rows = list(vouchers.itertuples(index=False, name=None))
        for product, _strike, ask_price, _bid_price, intrinsic_value in rows:
            if not np.isfinite(ask_price) or not np.isfinite(intrinsic_value):
                continue
            edge = float(intrinsic_value) - float(ask_price)
            if edge > self.config.voucher_intrinsic_edge:
                legs.append(
                    ArbitrageLeg(
                        product=str(product),
                        side=1,
                        edge=edge,
                        reason="voucher_below_intrinsic",
                        paired_product=self.data_config.underlying_product,
                    )
                )
                hedge_edge = max(edge * self.config.voucher_delta_hedge, 0.0)
                legs.append(
                    ArbitrageLeg(
                        product=self.data_config.underlying_product,
                        side=-1,
                        edge=hedge_edge,
                        reason=f"delta_hedge_{product}",
                        paired_product=str(product),
                    )
                )

        for lower, higher in zip(rows, rows[1:], strict=False):
            lower_product, lower_strike, lower_ask, lower_bid, _lower_intrinsic = lower
            higher_product, higher_strike, higher_ask, higher_bid, _higher_intrinsic = higher
            lower_ask = float(lower_ask)
            lower_bid = float(lower_bid)
            higher_ask = float(higher_ask)
            higher_bid = float(higher_bid)
            strike_gap = float(higher_strike - lower_strike)

            monotonic_edge = higher_bid - lower_ask
            if monotonic_edge > self.config.voucher_cross_edge:
                reason = f"monotonicity_{lower_product}_{higher_product}"
                legs.append(
                    ArbitrageLeg(str(lower_product), 1, monotonic_edge, reason, str(higher_product))
                )
                legs.append(
                    ArbitrageLeg(str(higher_product), -1, monotonic_edge, reason, str(lower_product))
                )

            spread_edge = lower_bid - higher_ask - strike_gap
            if spread_edge > self.config.voucher_cross_edge:
                reason = f"call_spread_bound_{lower_product}_{higher_product}"
                legs.append(
                    ArbitrageLeg(str(lower_product), -1, spread_edge, reason, str(higher_product))
                )
                legs.append(
                    ArbitrageLeg(str(higher_product), 1, spread_edge, reason, str(lower_product))
                )

        return legs
