from __future__ import annotations

import json
from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    LIMITS = {
        "EMERALDS": 80,
        "TOMATOES": 80,
    }

    EMERALDS_QUOTE_SIZE = 5
    TOMATO_FILTER_VOLUME = 12
    TOMATO_TAKE_WIDTH = 1
    TOMATO_HISTORY_LIMIT = 20

    def bid(self):
        return 15

    def run(self, state: TradingState):
        trader_state = self._load_state(state.traderData)
        result: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            if not order_depth.buy_orders or not order_depth.sell_orders:
                result[product] = []
                continue

            position = state.position.get(product, 0)

            if product == "EMERALDS":
                result[product] = self._trade_emeralds(order_depth, position)
            elif product == "TOMATOES":
                history = trader_state.get("tomato_fair_history", [])
                orders, history = self._trade_tomatoes(order_depth, position, history)
                trader_state["tomato_fair_history"] = history[-self.TOMATO_HISTORY_LIMIT :]
                result[product] = orders
            else:
                result[product] = []

        return result, 0, json.dumps(trader_state, separators=(",", ":"))

    def _trade_emeralds(self, order_depth: OrderDepth, position: int) -> List[Order]:
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        spread = best_ask - best_bid

        bid_price = best_bid + 1 if spread > 1 else best_bid
        ask_price = best_ask - 1 if spread > 1 else best_ask

        buy_size = min(self.EMERALDS_QUOTE_SIZE, max(0, self.LIMITS["EMERALDS"] - position))
        sell_size = min(self.EMERALDS_QUOTE_SIZE, max(0, self.LIMITS["EMERALDS"] + position))

        orders: List[Order] = []
        if buy_size > 0 and bid_price < best_ask:
            orders.append(Order("EMERALDS", bid_price, buy_size))
        if sell_size > 0 and ask_price > best_bid:
            orders.append(Order("EMERALDS", ask_price, -sell_size))
        return orders

    def _trade_tomatoes(
        self,
        order_depth: OrderDepth,
        position: int,
        history: List[float],
    ) -> Tuple[List[Order], List[float]]:
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)

        filtered_asks = [
            price for price, volume in order_depth.sell_orders.items()
            if abs(volume) >= self.TOMATO_FILTER_VOLUME
        ]
        filtered_bids = [
            price for price, volume in order_depth.buy_orders.items()
            if abs(volume) >= self.TOMATO_FILTER_VOLUME
        ]

        mm_ask = min(filtered_asks) if filtered_asks else best_ask
        mm_bid = max(filtered_bids) if filtered_bids else best_bid
        fair_value = 0.5 * (mm_ask + mm_bid)

        history.append(fair_value)
        if len(history) >= 4:
            fair_value = 0.6 * fair_value + 0.25 * history[-2] + 0.15 * history[-4]
        elif len(history) >= 2:
            fair_value = 0.75 * fair_value + 0.25 * history[-2]

        orders: List[Order] = []
        buy_volume = 0
        sell_volume = 0

        buy_volume, sell_volume = self._take_best_orders(
            product="TOMATOES",
            fair_value=fair_value,
            take_width=self.TOMATO_TAKE_WIDTH,
            orders=orders,
            order_depth=order_depth,
            position=position,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
        )

        buy_volume, sell_volume = self._clear_inventory(
            product="TOMATOES",
            fair_value=fair_value,
            orders=orders,
            order_depth=order_depth,
            position=position,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
        )

        self._make_tomato_quotes(
            fair_value=fair_value,
            orders=orders,
            order_depth=order_depth,
            position=position,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
        )

        return orders, history

    def _take_best_orders(
        self,
        product: str,
        fair_value: float,
        take_width: int,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_volume: int,
        sell_volume: int,
    ) -> Tuple[int, int]:
        limit = self.LIMITS[product]

        best_ask = min(order_depth.sell_orders)
        best_ask_size = -order_depth.sell_orders[best_ask]
        if best_ask <= fair_value - take_width:
            quantity = min(best_ask_size, limit - position - buy_volume)
            if quantity > 0:
                orders.append(Order(product, best_ask, quantity))
                buy_volume += quantity

        best_bid = max(order_depth.buy_orders)
        best_bid_size = order_depth.buy_orders[best_bid]
        if best_bid >= fair_value + take_width:
            quantity = min(best_bid_size, limit + position - sell_volume)
            if quantity > 0:
                orders.append(Order(product, best_bid, -quantity))
                sell_volume += quantity

        return buy_volume, sell_volume

    def _clear_inventory(
        self,
        product: str,
        fair_value: float,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_volume: int,
        sell_volume: int,
    ) -> Tuple[int, int]:
        limit = self.LIMITS[product]
        position_after_take = position + buy_volume - sell_volume
        fair_level = round(fair_value)

        if position_after_take > 0 and fair_level in order_depth.buy_orders:
            quantity = min(
                order_depth.buy_orders[fair_level],
                position_after_take,
                limit + position - sell_volume,
            )
            if quantity > 0:
                orders.append(Order(product, fair_level, -quantity))
                sell_volume += quantity

        if position_after_take < 0 and fair_level in order_depth.sell_orders:
            quantity = min(
                abs(order_depth.sell_orders[fair_level]),
                -position_after_take,
                limit - position - buy_volume,
            )
            if quantity > 0:
                orders.append(Order(product, fair_level, quantity))
                buy_volume += quantity

        return buy_volume, sell_volume

    def _make_tomato_quotes(
        self,
        fair_value: float,
        orders: List[Order],
        order_depth: OrderDepth,
        position: int,
        buy_volume: int,
        sell_volume: int,
    ) -> None:
        ask_candidates = [
            price for price in order_depth.sell_orders
            if price > fair_value + 1
        ]
        bid_candidates = [
            price for price in order_depth.buy_orders
            if price < fair_value - 1
        ]

        ask_price = min(ask_candidates) - 1 if ask_candidates else int(round(fair_value + 2))
        bid_price = max(bid_candidates) + 1 if bid_candidates else int(round(fair_value - 2))

        buy_size = self.LIMITS["TOMATOES"] - (position + buy_volume)
        sell_size = self.LIMITS["TOMATOES"] + (position - sell_volume)

        if buy_size > 0:
            orders.append(Order("TOMATOES", bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order("TOMATOES", ask_price, -sell_size))

    @staticmethod
    def _load_state(trader_data: str) -> Dict[str, List[float]]:
        if not trader_data:
            return {}
        try:
            payload = json.loads(trader_data)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
