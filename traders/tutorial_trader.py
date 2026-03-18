from __future__ import annotations

import json
from typing import Dict, List, Tuple

from prosperity.datamodel import Order, OrderDepth, TradingState


class Trader:
    POSITION_LIMITS = {"EMERALDS": 80, "TOMATOES": 80}
    EMERALDS_FAIR_VALUE = 10_000

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
        orders: List[Order] = []
        fair_value = self.EMERALDS_FAIR_VALUE - (0.10 * position)
        buy_capacity, sell_capacity = self._capacities("EMERALDS", position)

        buy_threshold = fair_value - 0.5
        sell_threshold = fair_value + 0.5

        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            quantity = min(buy_capacity, -ask_volume, 12)
            if quantity <= 0 or ask_price > buy_threshold:
                continue
            orders.append(Order("EMERALDS", ask_price, quantity))
            buy_capacity -= quantity

        for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
            quantity = min(sell_capacity, bid_volume, 12)
            if quantity <= 0 or bid_price < sell_threshold:
                continue
            orders.append(Order("EMERALDS", bid_price, -quantity))
            sell_capacity -= quantity

        return orders

    def _trade_tomatoes(
        self,
        order_depth: OrderDepth,
        position: int,
        memory: dict,
    ) -> List[Order]:
        orders: List[Order] = []
        best_bid, best_ask = self._best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return orders

        mid_price = (best_bid + best_ask) / 2.0
        signals = memory.setdefault("TOMATOES", {"ema_fast": mid_price, "ema_slow": mid_price})
        signals["ema_fast"] = 0.35 * mid_price + 0.65 * signals["ema_fast"]
        signals["ema_slow"] = 0.10 * mid_price + 0.90 * signals["ema_slow"]
        trend = signals["ema_fast"] - signals["ema_slow"]
        target_position = max(-30, min(30, int(round(trend * 4))))
        buy_capacity, sell_capacity = self._capacities("TOMATOES", position)

        if position < target_position - 2:
            quantity = min(target_position - position, 10, buy_capacity)
            if quantity > 0:
                orders.append(Order("TOMATOES", best_ask, quantity))

        if position > target_position + 2:
            quantity = min(position - target_position, 10, sell_capacity)
            if quantity > 0:
                orders.append(Order("TOMATOES", best_bid, -quantity))

        return orders

    def _capacities(self, product: str, position: int) -> Tuple[int, int]:
        limit = self.POSITION_LIMITS[product]
        return limit - position, limit + position

    def _best_bid_ask(self, order_depth: OrderDepth) -> Tuple[int | None, int | None]:
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    def _load_memory(self, trader_data: str) -> dict:
        if not trader_data:
            return {}
        try:
            return json.loads(trader_data)
        except json.JSONDecodeError:
            return {}

    def _dump_memory(self, memory: dict) -> str:
        return json.dumps(memory, separators=(",", ":"))
