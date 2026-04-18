from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from datamodel import Order, OrderDepth, Trade, TradingState
except ImportError:
    @dataclass
    class Order:
        symbol: str
        price: int
        quantity: int

    @dataclass
    class Trade:
        symbol: str
        price: int
        quantity: int
        buyer: str = ""
        seller: str = ""
        timestamp: int = 0

    @dataclass
    class OrderDepth:
        buy_orders: Dict[int, int]
        sell_orders: Dict[int, int]

    @dataclass
    class TradingState:
        traderData: str
        timestamp: int
        listings: Dict[str, object]
        order_depths: Dict[str, OrderDepth]
        own_trades: Dict[str, List[Trade]]
        market_trades: Dict[str, List[Trade]]
        position: Dict[str, int]
        observations: object


@dataclass(frozen=True)
class StrategyConfig:
    limit: int = 20
    tick: int = 1
    enable_taking: bool = True
    allow_zero_edge_take: bool = False
    fast_alpha: float = 0.22
    slow_alpha: float = 0.04
    variance_alpha: float = 0.08
    imbalance_alpha: float = 0.18
    trade_alpha: float = 0.20
    micro_gain: float = 1.2
    reversion_gain: float = 0.5
    trend_gain: float = 0.1
    imbalance_gain: float = 0.4
    trade_gain: float = 0.2
    inventory_aversion: float = 0.10
    inventory_spread_gain: float = 0.85
    take_threshold: float = 1.5
    take_vol_gain: float = 0.35
    max_take_clip: int = 10
    make_edge_buffer: float = 0.8
    min_half_spread: float = 2.0
    vol_spread_gain: float = 0.35
    base_make_size: int = 6
    second_level_fraction: float = 0.5
    base_quote_half_spread: float = 4.0
    secondary_quote_gap: int = 2
    clear_width: float = 1.0
    wall_volume_threshold: int = 15
    soft_inventory_fraction: float = 0.65
    hard_inventory_fraction: float = 0.90
    compressed_spread_width: int = 0
    compressed_reversion_boost: float = 0.0
    anchor_rounding: int = 1
    directional_size_skew: float = 0.0


@dataclass
class ProductState:
    initialized: bool = False
    latent_price: float = 0.0
    latent_var: float = 4.0
    fast_price: float = 0.0
    vol2: float = 4.0
    imbalance_ema: float = 0.0
    trade_pressure_ema: float = 0.0
    last_mid: float = 0.0
    last_signal: float = 0.0
    last_bid: int = 0
    last_ask: int = 0
    limit_streak: int = 0

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, float]]) -> "ProductState":
        if not payload:
            return cls()
        return cls(
            initialized=bool(payload.get("initialized", False)),
            latent_price=float(payload.get("latent_price", 0.0)),
            latent_var=float(payload.get("latent_var", 4.0)),
            fast_price=float(payload.get("fast_price", 0.0)),
            vol2=float(payload.get("vol2", 4.0)),
            imbalance_ema=float(payload.get("imbalance_ema", 0.0)),
            trade_pressure_ema=float(payload.get("trade_pressure_ema", 0.0)),
            last_mid=float(payload.get("last_mid", 0.0)),
            last_signal=float(payload.get("last_signal", 0.0)),
            last_bid=int(payload.get("last_bid", 0)),
            last_ask=int(payload.get("last_ask", 0)),
            limit_streak=int(payload.get("limit_streak", 0)),
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "initialized": self.initialized,
            "latent_price": self.latent_price,
            "latent_var": self.latent_var,
            "fast_price": self.fast_price,
            "vol2": self.vol2,
            "imbalance_ema": self.imbalance_ema,
            "trade_pressure_ema": self.trade_pressure_ema,
            "last_mid": self.last_mid,
            "last_signal": self.last_signal,
            "last_bid": self.last_bid,
            "last_ask": self.last_ask,
            "limit_streak": self.limit_streak,
        }


class OrderBuilder:
    def __init__(self, product: str, position: int, limit: int):
        self.product = product
        self.buy_remaining = max(0, limit - position)
        self.sell_remaining = max(0, limit + position)
        self.orders: List[Order] = []

    def add_buy(self, price: int, quantity: int) -> None:
        quantity = min(quantity, self.buy_remaining)
        if quantity <= 0:
            return
        self.orders.append(Order(self.product, int(price), int(quantity)))
        self.buy_remaining -= quantity

    def add_sell(self, price: int, quantity: int) -> None:
        quantity = min(quantity, self.sell_remaining)
        if quantity <= 0:
            return
        self.orders.append(Order(self.product, int(price), -int(quantity)))
        self.sell_remaining -= quantity


class Trader:
    DEFAULT_CONFIG = StrategyConfig()
    PRODUCT_CONFIGS: Dict[str, StrategyConfig] = {
        "EMERALDS": StrategyConfig(
            limit=20,
            enable_taking=True,
            allow_zero_edge_take=True,
            fast_alpha=0.35,
            slow_alpha=0.10,
            micro_gain=0.12,
            reversion_gain=0.95,
            trend_gain=0.00,
            imbalance_gain=0.00,
            trade_gain=0.00,
            inventory_aversion=0.14,
            inventory_spread_gain=1.25,
            take_threshold=0.00,
            take_vol_gain=0.20,
            max_take_clip=12,
            make_edge_buffer=0.55,
            min_half_spread=2.40,
            vol_spread_gain=0.18,
            base_make_size=8,
            second_level_fraction=0.75,
            clear_width=0.0,
            base_quote_half_spread=4.0,
            secondary_quote_gap=2,
            wall_volume_threshold=15,
            soft_inventory_fraction=0.60,
            hard_inventory_fraction=0.90,
            compressed_spread_width=8,
            compressed_reversion_boost=1.5,
            anchor_rounding=4,
            directional_size_skew=0.45,
        ),
        "TOMATOES": StrategyConfig(
            limit=20,
            fast_alpha=0.34,
            slow_alpha=0.10,
            micro_gain=0.00,
            reversion_gain=0.88,
            trend_gain=0.18,
            imbalance_gain=0.10,
            trade_gain=0.08,
            inventory_aversion=0.06,
            inventory_spread_gain=0.75,
            take_threshold=3.20,
            take_vol_gain=0.18,
            max_take_clip=12,
            make_edge_buffer=0.75,
            min_half_spread=2.20,
            vol_spread_gain=0.18,
            base_make_size=9,
            second_level_fraction=0.75,
            clear_width=0.25,
            base_quote_half_spread=4.0,
            secondary_quote_gap=2,
            wall_volume_threshold=15,
            soft_inventory_fraction=0.70,
            hard_inventory_fraction=0.85,
            compressed_spread_width=0,
            compressed_reversion_boost=0.0,
            anchor_rounding=1,
            directional_size_skew=0.10,
        ),
    }

    def bid(self):
        return 15

    def run(self, state: TradingState):
        saved_state = self._load_state(state.traderData)
        next_state: Dict[str, Dict[str, float]] = {}
        result: Dict[str, List[Order]] = {}

        for product, depth in state.order_depths.items():
            cfg = self.PRODUCT_CONFIGS.get(product, self.DEFAULT_CONFIG)
            pstate = ProductState.from_dict(saved_state.get(product))
            position = state.position.get(product, 0)
            market_trades = state.market_trades.get(product, [])

            result[product] = self._trade_product(
                product=product,
                depth=depth,
                position=position,
                market_trades=market_trades,
                pstate=pstate,
                cfg=cfg,
            )
            next_state[product] = pstate.to_dict()

        trader_data = json.dumps(next_state, separators=(",", ":"))
        return result, 0, trader_data

    def _trade_product(
        self,
        product: str,
        depth: OrderDepth,
        position: int,
        market_trades: List[Trade],
        pstate: ProductState,
        cfg: StrategyConfig,
    ) -> List[Order]:
        buy_levels = sorted(depth.buy_orders.items(), key=lambda item: item[0], reverse=True)
        sell_levels = sorted(depth.sell_orders.items(), key=lambda item: item[0])
        if not buy_levels or not sell_levels:
            self._decay_trade_pressure(market_trades, pstate, cfg)
            return []
        if product == "EMERALDS":
            return self._trade_emeralds(buy_levels, sell_levels, position, pstate, cfg)

        best_bid, best_bid_volume = buy_levels[0]
        best_ask, best_ask_volume = sell_levels[0]
        best_ask_volume = abs(best_ask_volume)
        spread = max(cfg.tick, best_ask - best_bid)
        mid = 0.5 * (best_bid + best_ask)
        microprice = self._microprice(best_bid, best_bid_volume, best_ask, best_ask_volume, mid)
        imbalance = self._depth_imbalance(buy_levels, sell_levels)
        wall_bid, wall_ask, wall_mid = self._wall_prices(buy_levels, sell_levels, cfg.wall_volume_threshold)

        self._update_trade_pressure(market_trades, pstate, cfg)
        self._update_filters(wall_mid, mid, spread, imbalance, pstate, cfg)

        sigma = math.sqrt(max(1e-6, pstate.vol2 + 0.25 * pstate.latent_var))
        structural_fair = pstate.latent_price + cfg.trend_gain * (pstate.fast_price - pstate.latent_price)
        fair_value = (
            structural_fair
            + cfg.micro_gain * (microprice - mid)
            + cfg.reversion_gain * (wall_mid - mid)
            + cfg.imbalance_gain * pstate.imbalance_ema * max(1.0, spread / 2.0)
            + cfg.trade_gain * pstate.trade_pressure_ema * max(1.0, spread / 2.0)
        )
        reservation_price = fair_value - (
            cfg.inventory_aversion * sigma * position
            + cfg.inventory_spread_gain * (position / max(1, cfg.limit)) * spread
        )
        if abs(position) >= int(round(cfg.soft_inventory_fraction * cfg.limit)):
            pstate.limit_streak += 1
        else:
            pstate.limit_streak = max(0, pstate.limit_streak - 1)

        builder = OrderBuilder(product, position, cfg.limit)
        anchor_price = self._anchor_price(wall_mid, cfg)
        self._take_liquidity(
            builder,
            fair_value,
            anchor_price,
            sigma,
            spread,
            buy_levels,
            sell_levels,
            cfg,
        )
        self._clear_inventory(builder, fair_value, position, buy_levels, sell_levels, pstate, cfg)
        self._make_markets(
            builder,
            reservation_price,
            sigma,
            spread,
            best_bid,
            best_ask,
            position,
            pstate,
            cfg,
        )

        pstate.last_mid = mid
        pstate.last_bid = best_bid
        pstate.last_ask = best_ask
        return builder.orders

    def _trade_emeralds(
        self,
        buy_levels: List[Tuple[int, int]],
        sell_levels: List[Tuple[int, int]],
        position: int,
        pstate: ProductState,
        cfg: StrategyConfig,
    ) -> List[Order]:
        fair_value = 10000
        builder = OrderBuilder("EMERALDS", position, cfg.limit)
        best_bid, _ = buy_levels[0]
        best_ask, _ = sell_levels[0]
        imbalance = self._depth_imbalance(buy_levels, sell_levels)
        pstate.imbalance_ema = 0.30 * imbalance + 0.70 * pstate.imbalance_ema
        pstate.last_bid = best_bid
        pstate.last_ask = best_ask
        pstate.last_mid = 0.5 * (best_bid + best_ask)

        # Strictly favorable taking only: do not churn at 10000 unless inventory is stressed.
        for ask_price, ask_volume in sell_levels:
            if builder.buy_remaining <= 0 or ask_price >= fair_value:
                break
            builder.add_buy(ask_price, min(abs(ask_volume), builder.buy_remaining))

        for bid_price, bid_volume in buy_levels:
            if builder.sell_remaining <= 0 or bid_price <= fair_value:
                break
            builder.add_sell(bid_price, min(bid_volume, builder.sell_remaining))

        projected_position = position + sum(order.quantity for order in builder.orders)

        # Zero-edge clears only when inventory is genuinely large.
        if projected_position >= 12 and best_bid >= fair_value:
            clear_qty = min(projected_position - 6, builder.sell_remaining, buy_levels[0][1])
            builder.add_sell(fair_value, clear_qty)
            projected_position -= clear_qty
        elif projected_position <= -12 and best_ask <= fair_value:
            clear_qty = min((-projected_position) - 6, builder.buy_remaining, abs(sell_levels[0][1]))
            builder.add_buy(fair_value, clear_qty)
            projected_position += clear_qty

        inner_bid = 9996
        outer_bid = 9993
        inner_ask = 10004
        outer_ask = 10007
        inner_bid_size = 6
        outer_bid_size = 5
        inner_ask_size = 6
        outer_ask_size = 5

        if pstate.imbalance_ema >= 0.12:
            inner_bid += 1
            outer_bid += 1
            inner_ask_size = max(2, inner_ask_size - 1)
            outer_ask_size = max(1, outer_ask_size - 1)
        elif pstate.imbalance_ema <= -0.12:
            inner_ask -= 1
            outer_ask -= 1
            inner_bid_size = max(2, inner_bid_size - 1)
            outer_bid_size = max(1, outer_bid_size - 1)

        if projected_position > 0:
            bid_penalty = max(0, projected_position // 4)
            ask_bonus = max(0, projected_position // 4)
            inner_bid_size = max(1, inner_bid_size - bid_penalty)
            outer_bid_size = max(0, outer_bid_size - bid_penalty)
            inner_ask_size = min(12, inner_ask_size + ask_bonus)
            outer_ask_size = min(10, outer_ask_size + ask_bonus)
            if projected_position >= 8:
                inner_ask -= 1
                outer_ask -= 1
            if projected_position >= 14:
                inner_ask -= 1
                inner_bid = 9994
                outer_bid = 9991
        elif projected_position < 0:
            bid_bonus = max(0, (-projected_position) // 4)
            ask_penalty = max(0, (-projected_position) // 4)
            inner_bid_size = min(12, inner_bid_size + bid_bonus)
            outer_bid_size = min(10, outer_bid_size + bid_bonus)
            inner_ask_size = max(1, inner_ask_size - ask_penalty)
            outer_ask_size = max(0, outer_ask_size - ask_penalty)
            if projected_position <= -8:
                inner_bid += 1
                outer_bid += 1
            if projected_position <= -14:
                inner_bid += 1
                inner_ask = 10006
                outer_ask = 10009

        quote_levels = [
            ("buy", inner_bid, inner_bid_size),
            ("buy", outer_bid, outer_bid_size),
            ("sell", inner_ask, inner_ask_size),
            ("sell", outer_ask, outer_ask_size),
        ]

        for side, price, size in quote_levels:
            if size <= 0:
                continue
            if side == "buy":
                price = min(price, best_ask - 1)
                if price > best_bid:
                    builder.add_buy(price, min(builder.buy_remaining, size))
            else:
                price = max(price, best_bid + 1)
                if price < best_ask:
                    builder.add_sell(price, min(builder.sell_remaining, size))

        return builder.orders

    def _take_liquidity(
        self,
        builder: OrderBuilder,
        fair_value: float,
        anchor_price: int,
        sigma: float,
        spread: int,
        buy_levels: List[Tuple[int, int]],
        sell_levels: List[Tuple[int, int]],
        cfg: StrategyConfig,
    ) -> None:
        if not cfg.enable_taking:
            return
        edge_buffer = cfg.take_threshold + cfg.take_vol_gain * sigma

        for ask_price, ask_volume in sell_levels:
            available = abs(ask_volume)
            edge = fair_value - ask_price
            zero_edge_buy = (
                cfg.allow_zero_edge_take
                and spread <= cfg.compressed_spread_width
                and ask_price <= anchor_price
            )
            if builder.buy_remaining <= 0:
                break
            if not zero_edge_buy and edge < max(edge_buffer, 0.55 * (sell_levels[0][0] - buy_levels[0][0])):
                break
            clip_cap = cfg.max_take_clip if zero_edge_buy else cfg.max_take_clip + max(0, int(edge))
            clip = min(available, builder.buy_remaining, clip_cap)
            builder.add_buy(ask_price, clip)

        for bid_price, bid_volume in buy_levels:
            edge = bid_price - fair_value
            zero_edge_sell = (
                cfg.allow_zero_edge_take
                and spread <= cfg.compressed_spread_width
                and bid_price >= anchor_price
            )
            if builder.sell_remaining <= 0:
                break
            if not zero_edge_sell and edge < max(edge_buffer, 0.55 * (sell_levels[0][0] - buy_levels[0][0])):
                break
            clip_cap = cfg.max_take_clip if zero_edge_sell else cfg.max_take_clip + max(0, int(edge))
            clip = min(bid_volume, builder.sell_remaining, clip_cap)
            builder.add_sell(bid_price, clip)

    def _clear_inventory(
        self,
        builder: OrderBuilder,
        fair_value: float,
        position: int,
        buy_levels: List[Tuple[int, int]],
        sell_levels: List[Tuple[int, int]],
        pstate: ProductState,
        cfg: StrategyConfig,
    ) -> None:
        position_after_take = position + sum(order.quantity for order in builder.orders)
        if position_after_take == 0:
            return
        soft_threshold = max(4, int(round(cfg.soft_inventory_fraction * cfg.limit)))
        trend = pstate.fast_price - pstate.latent_price
        adverse_inventory = position_after_take * trend < 0
        if adverse_inventory and abs(trend) >= 0.75:
            soft_threshold = max(2, soft_threshold - 4)
        if abs(position_after_take) < soft_threshold and pstate.limit_streak < 3:
            return

        clear_width = cfg.clear_width
        if adverse_inventory and abs(trend) >= 0.75:
            clear_width = max(0.0, clear_width - 0.5)
        if abs(position_after_take) >= int(round(cfg.hard_inventory_fraction * cfg.limit)) or pstate.limit_streak >= 8:
            clear_width = max(0.0, clear_width - 1.0)
        elif abs(position_after_take) >= int(round(cfg.soft_inventory_fraction * cfg.limit)) or pstate.limit_streak >= 3:
            clear_width = max(0.0, clear_width - 0.5)

        fair_bid = int(math.floor(fair_value - clear_width))
        fair_ask = int(math.ceil(fair_value + clear_width))

        if position_after_take > 0:
            clear_quantity = sum(volume for price, volume in buy_levels if price >= fair_ask)
            builder.add_sell(fair_ask, min(clear_quantity, position_after_take))
        else:
            clear_quantity = sum(abs(volume) for price, volume in sell_levels if price <= fair_bid)
            builder.add_buy(fair_bid, min(clear_quantity, -position_after_take))

    def _make_markets(
        self,
        builder: OrderBuilder,
        reservation_price: float,
        sigma: float,
        spread: int,
        best_bid: int,
        best_ask: int,
        position: int,
        pstate: ProductState,
        cfg: StrategyConfig,
    ) -> None:
        limit = max(1, cfg.limit)
        inventory_ratio = position / limit
        directional_bias = self._compressed_state_bias(best_bid, best_ask, pstate, cfg)
        trend = pstate.fast_price - pstate.latent_price
        trend_bias = math.tanh(trend / max(1.0, sigma))
        adjusted_reservation = reservation_price + directional_bias * cfg.compressed_reversion_boost
        core_size = max(1, int(round(cfg.base_make_size * (1.0 - 0.45 * abs(inventory_ratio)))))
        raw_bid_size = core_size * max(0.25, 1.0 - inventory_ratio)
        raw_ask_size = core_size * max(0.25, 1.0 + inventory_ratio)
        if directional_bias > 0:
            raw_bid_size *= 1.0 + cfg.directional_size_skew
            raw_ask_size *= max(0.25, 1.0 - 0.55 * cfg.directional_size_skew)
        elif directional_bias < 0:
            raw_bid_size *= max(0.25, 1.0 - 0.55 * cfg.directional_size_skew)
            raw_ask_size *= 1.0 + cfg.directional_size_skew
        raw_bid_size *= max(0.20, 1.0 + 0.55 * trend_bias)
        raw_ask_size *= max(0.20, 1.0 - 0.55 * trend_bias)

        bid_size = max(1, int(round(raw_bid_size)))
        ask_size = max(1, int(round(raw_ask_size)))
        make_guard = cfg.make_edge_buffer + cfg.vol_spread_gain * sigma
        passive_half_spread = max(cfg.min_half_spread, 0.35 * spread + cfg.vol_spread_gain * sigma)

        inside_bid = min(best_ask - cfg.tick, best_bid + cfg.tick)
        inside_ask = max(best_bid + cfg.tick, best_ask - cfg.tick)
        if directional_bias > 0:
            inside_bid = min(best_ask - cfg.tick, inside_bid + 1)
        elif directional_bias < 0:
            inside_ask = max(best_bid + cfg.tick, inside_ask - 1)
        if trend_bias > 0.35:
            inside_bid = min(best_ask - cfg.tick, inside_bid + 1)
        elif trend_bias < -0.35:
            inside_ask = max(best_bid + cfg.tick, inside_ask - 1)
        if position > 0 and trend_bias < -0.30:
            bid_size = max(1, bid_size // 2)
            ask_size += 2
            inside_ask = max(best_bid + cfg.tick, inside_ask - 1)
        elif position < 0 and trend_bias > 0.30:
            ask_size = max(1, ask_size // 2)
            bid_size += 2
            inside_bid = min(best_ask - cfg.tick, inside_bid + 1)

        if inside_bid < best_ask and inside_bid <= adjusted_reservation - make_guard:
            builder.add_buy(inside_bid, min(builder.buy_remaining, bid_size))
        if inside_ask > best_bid and inside_ask >= adjusted_reservation + make_guard:
            builder.add_sell(inside_ask, min(builder.sell_remaining, ask_size))

        secondary_bid = min(
            best_ask - cfg.tick,
            max(best_bid, int(math.floor(adjusted_reservation - passive_half_spread))),
        )
        secondary_ask = max(
            best_bid + cfg.tick,
            min(best_ask, int(math.ceil(adjusted_reservation + passive_half_spread))),
        )
        secondary_bid_size = max(1, int(round(bid_size * cfg.second_level_fraction)))
        secondary_ask_size = max(1, int(round(ask_size * cfg.second_level_fraction)))
        if position > 0 and trend_bias < -0.30:
            secondary_bid_size = max(1, secondary_bid_size // 2)
        elif position < 0 and trend_bias > 0.30:
            secondary_ask_size = max(1, secondary_ask_size // 2)

        if secondary_bid < best_ask and secondary_bid <= adjusted_reservation - 0.5 * make_guard:
            if secondary_bid != self._last_buy_price(builder.orders):
                builder.add_buy(secondary_bid, min(builder.buy_remaining, secondary_bid_size))
        if secondary_ask > best_bid and secondary_ask >= adjusted_reservation + 0.5 * make_guard:
            if secondary_ask != self._last_sell_price(builder.orders):
                builder.add_sell(secondary_ask, min(builder.sell_remaining, secondary_ask_size))

    def _update_filters(
        self,
        signal_price: float,
        mid: float,
        spread: int,
        imbalance: float,
        pstate: ProductState,
        cfg: StrategyConfig,
    ) -> None:
        if not pstate.initialized:
            pstate.initialized = True
            pstate.latent_price = signal_price
            pstate.fast_price = signal_price
            pstate.latent_var = max(1.0, 0.25 * spread * spread)
            pstate.vol2 = max(1.0, 0.25 * spread * spread)
            pstate.imbalance_ema = imbalance
            pstate.last_mid = mid
            pstate.last_signal = signal_price
            return

        ret = signal_price - pstate.last_signal
        pstate.fast_price = cfg.fast_alpha * signal_price + (1.0 - cfg.fast_alpha) * pstate.fast_price
        pstate.latent_price = cfg.slow_alpha * signal_price + (1.0 - cfg.slow_alpha) * pstate.latent_price
        pstate.vol2 = cfg.variance_alpha * (ret * ret) + (1.0 - cfg.variance_alpha) * pstate.vol2
        pstate.imbalance_ema = cfg.imbalance_alpha * imbalance + (1.0 - cfg.imbalance_alpha) * pstate.imbalance_ema
        pstate.latent_var = max(0.25, 0.90 * pstate.latent_var + 0.10 * spread * spread)
        pstate.last_signal = signal_price

    def _update_trade_pressure(self, market_trades: List[Trade], pstate: ProductState, cfg: StrategyConfig) -> None:
        if not pstate.initialized:
            return

        signed_flow = 0.0
        for trade in market_trades:
            qty = abs(trade.quantity)
            if pstate.last_ask and trade.price >= pstate.last_ask:
                signed_flow += qty
            elif pstate.last_bid and trade.price <= pstate.last_bid:
                signed_flow -= qty
            elif pstate.last_mid:
                if trade.price > pstate.last_mid:
                    signed_flow += 0.5 * qty
                elif trade.price < pstate.last_mid:
                    signed_flow -= 0.5 * qty

        normalized = math.tanh(signed_flow / 10.0)
        pstate.trade_pressure_ema = cfg.trade_alpha * normalized + (1.0 - cfg.trade_alpha) * pstate.trade_pressure_ema

    def _decay_trade_pressure(self, market_trades: List[Trade], pstate: ProductState, cfg: StrategyConfig) -> None:
        self._update_trade_pressure(market_trades, pstate, cfg)

    @staticmethod
    def _microprice(best_bid: int, bid_volume: int, best_ask: int, ask_volume: int, fallback_mid: float) -> float:
        total = bid_volume + ask_volume
        if total <= 0:
            return fallback_mid
        return (best_ask * bid_volume + best_bid * ask_volume) / total

    @staticmethod
    def _depth_imbalance(
        buy_levels: List[Tuple[int, int]],
        sell_levels: List[Tuple[int, int]],
    ) -> float:
        weights = (1.0, 0.65, 0.45)
        weighted_bids = 0.0
        weighted_asks = 0.0
        for i, (_, volume) in enumerate(buy_levels[: len(weights)]):
            weighted_bids += weights[i] * max(0, volume)
        for i, (_, volume) in enumerate(sell_levels[: len(weights)]):
            weighted_asks += weights[i] * abs(volume)
        total = weighted_bids + weighted_asks
        if total <= 0:
            return 0.0
        return (weighted_bids - weighted_asks) / total

    @staticmethod
    def _compressed_state_bias(best_bid: int, best_ask: int, pstate: ProductState, cfg: StrategyConfig) -> int:
        if cfg.compressed_spread_width <= 0:
            return 0
        spread = best_ask - best_bid
        if spread > cfg.compressed_spread_width:
            return 0
        anchor = Trader._anchor_price(pstate.latent_price, cfg)
        if best_ask <= anchor + cfg.tick:
            return 1
        if best_bid >= anchor - cfg.tick:
            return -1
        return 0

    @staticmethod
    def _wall_prices(
        buy_levels: List[Tuple[int, int]],
        sell_levels: List[Tuple[int, int]],
        min_volume: int,
    ) -> Tuple[int, int, float]:
        wall_bid = max((price for price, volume in buy_levels if volume >= min_volume), default=buy_levels[0][0])
        wall_ask = min((price for price, volume in sell_levels if abs(volume) >= min_volume), default=sell_levels[0][0])
        return wall_bid, wall_ask, 0.5 * (wall_bid + wall_ask)

    @staticmethod
    def _anchor_price(reference: float, cfg: StrategyConfig) -> int:
        if cfg.anchor_rounding > 1:
            return int(round(reference / cfg.anchor_rounding) * cfg.anchor_rounding)
        return int(round(reference))

    @staticmethod
    def _last_buy_price(orders: List[Order]) -> Optional[int]:
        for order in reversed(orders):
            if order.quantity > 0:
                return order.price
        return None

    @staticmethod
    def _last_sell_price(orders: List[Order]) -> Optional[int]:
        for order in reversed(orders):
            if order.quantity < 0:
                return order.price
        return None

    @staticmethod
    def _load_state(trader_data: str) -> Dict[str, Dict[str, float]]:
        if not trader_data:
            return {}
        try:
            payload = json.loads(trader_data)
        except json.JSONDecodeError:
            return {}
        if isinstance(payload, dict):
            return payload
        return {}
