from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    POSITION_LIMITS = {"EMERALDS": 80, "TOMATOES": 80}
    EMERALDS_FAIR_VALUE = 10_000.0

    EMERALDS_PARAMS = {
        "micro_weight": 1.5137604255534056,
        "inventory_weight": 0.08421501537516951,
        "take_margin": 3.8974216963902246,
        "take_size": 7,
        "quote_improvement": 4,
        "make_width": 1.447594294489909,
        "make_size": 29,
    }

    TOMATO_PARAMS = {
        "fast_alpha": 0.3616096540074918,
        "slow_alpha": 0.061892039615313164,
        "vol_alpha": 0.05588642355005834,
        "trend_weight": 2.154719681455397,
        "micro_weight": -1.9240947370502437,
        "inventory_weight": 0.0909748650196874,
        "take_base": 4.156461670876781,
        "take_vol": 0.11423937327778488,
        "take_size": 16,
        "quote_improvement": 3,
        "make_base": 1.0849048633712006,
        "make_vol": 0.6943339107798843,
        "make_size": 30,
    }

    def bid(self):
        return 15

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData)
        result: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            position = state.position.get(product, 0)
            if product == "EMERALDS":
                orders = self._trade_emeralds(order_depth, position)
            elif product == "TOMATOES":
                orders = self._trade_tomatoes(order_depth, position, memory)
            else:
                orders = []
            result[product] = orders

        return result, 0, self._dump_memory(memory)

    def _trade_emeralds(self, order_depth: OrderDepth, position: int) -> List[Order]:
        best_bid, best_ask = self._best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return []

        params = self.EMERALDS_PARAMS
        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = -order_depth.sell_orders[best_ask]
        micro_price = self._micro_price(best_bid, best_ask, bid_volume, ask_volume)
        fair_value = (
            self.EMERALDS_FAIR_VALUE
            + params["micro_weight"] * (micro_price - self.EMERALDS_FAIR_VALUE)
            - params["inventory_weight"] * position
        )

        return self._build_market_making_orders(
            product="EMERALDS",
            order_depth=order_depth,
            position=position,
            fair_value=fair_value,
            take_margin=params["take_margin"],
            take_size=params["take_size"],
            quote_improvement=params["quote_improvement"],
            make_width=params["make_width"],
            make_size=params["make_size"],
        )

    def _trade_tomatoes(
        self,
        order_depth: OrderDepth,
        position: int,
        memory: dict,
    ) -> List[Order]:
        best_bid, best_ask = self._best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return []

        params = self.TOMATO_PARAMS
        signal_state = memory.setdefault("TOMATOES", {})
        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = -order_depth.sell_orders[best_ask]
        mid_price = (best_bid + best_ask) / 2.0
        micro_price = self._micro_price(best_bid, best_ask, bid_volume, ask_volume)

        fast = signal_state.get("fast_ema", mid_price)
        slow = signal_state.get("slow_ema", mid_price)
        variance = signal_state.get("variance", 1.0)
        last_mid = signal_state.get("last_mid")

        fast = (1.0 - params["fast_alpha"]) * fast + params["fast_alpha"] * mid_price
        slow = (1.0 - params["slow_alpha"]) * slow + params["slow_alpha"] * mid_price

        if last_mid is not None:
            price_change = mid_price - last_mid
            variance = (
                (1.0 - params["vol_alpha"]) * variance
                + params["vol_alpha"] * (price_change * price_change)
            )
        volatility = max(1.0, math.sqrt(max(variance, 0.0)))

        signal_state["fast_ema"] = fast
        signal_state["slow_ema"] = slow
        signal_state["variance"] = variance
        signal_state["last_mid"] = mid_price

        fair_value = (
            slow
            + params["trend_weight"] * (fast - slow)
            + params["micro_weight"] * (micro_price - mid_price)
            - params["inventory_weight"] * position
        )
        make_width = params["make_base"] + params["make_vol"] * volatility
        take_margin = params["take_base"] + params["take_vol"] * volatility

        return self._build_market_making_orders(
            product="TOMATOES",
            order_depth=order_depth,
            position=position,
            fair_value=fair_value,
            take_margin=take_margin,
            take_size=params["take_size"],
            quote_improvement=params["quote_improvement"],
            make_width=make_width,
            make_size=params["make_size"],
        )

    def _build_market_making_orders(
        self,
        *,
        product: str,
        order_depth: OrderDepth,
        position: int,
        fair_value: float,
        take_margin: float,
        take_size: int,
        quote_improvement: int,
        make_width: float,
        make_size: int,
    ) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self._best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return orders

        buy_capacity, sell_capacity = self._capacities(product, position)

        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            if buy_capacity <= 0:
                break
            if ask_price > fair_value - take_margin:
                break
            quantity = min(-ask_volume, buy_capacity, take_size)
            if quantity <= 0:
                continue
            orders.append(Order(product, ask_price, quantity))
            buy_capacity -= quantity

        for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
            if sell_capacity <= 0:
                break
            if bid_price < fair_value + take_margin:
                break
            quantity = min(bid_volume, sell_capacity, take_size)
            if quantity <= 0:
                continue
            orders.append(Order(product, bid_price, -quantity))
            sell_capacity -= quantity

        bid_quote = min(
            int(math.floor(fair_value - make_width)),
            best_bid + quote_improvement,
            best_ask - 1,
        )
        ask_quote = max(
            int(math.ceil(fair_value + make_width)),
            best_ask - quote_improvement,
            best_bid + 1,
        )

        if buy_capacity > 0 and best_bid < bid_quote < best_ask:
            orders.append(Order(product, bid_quote, min(buy_capacity, make_size)))

        if sell_capacity > 0 and best_bid < ask_quote < best_ask:
            orders.append(Order(product, ask_quote, -min(sell_capacity, make_size)))

        return orders

    def _capacities(self, product: str, position: int) -> Tuple[int, int]:
        limit = self.POSITION_LIMITS[product]
        return limit - position, limit + position

    def _best_bid_ask(self, order_depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    def _micro_price(
        self,
        best_bid: int,
        best_ask: int,
        bid_volume: int,
        ask_volume: int,
    ) -> float:
        total_volume = bid_volume + ask_volume
        if total_volume <= 0:
            return (best_bid + best_ask) / 2.0
        return (best_bid * ask_volume + best_ask * bid_volume) / total_volume

    def _load_memory(self, trader_data: str) -> dict:
        if not trader_data:
            return {}
        try:
            return json.loads(trader_data)
        except json.JSONDecodeError:
            return {}

    def _dump_memory(self, memory: dict) -> str:
        return json.dumps(memory, separators=(",", ":"))
