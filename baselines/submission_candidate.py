from __future__ import annotations

import json
from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    LIMITS = {"EMERALDS": 80, "TOMATOES": 80}
    EMERALDS_QUOTE_SIZE = 5
    TOMATO_FILTER_VOLUME = 16
    TOMATO_TAKE_WIDTH = 2
    TOMATO_HISTORY_LIMIT = 20
    FAIR_ALPHA_SCALE = 1.3
    GAP_WEIGHT = 0.1
    SECOND_IMB_WEIGHT = 1.0
    RET1_WEIGHT = -0.045
    RET3_WEIGHT = 0.0
    MICRO_WEIGHT = -0.025
    INVENTORY_SKEW = 0.0
    CLEAR_WIDTH = 1
    QUOTE_AGGRESSION = 1
    TAKE_EXTRA = 1.5

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

    def _trade_tomatoes(self, order_depth: OrderDepth, position: int, history: List[float]) -> Tuple[List[Order], List[float]]:
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        filtered_asks = [price for price, volume in order_depth.sell_orders.items() if abs(volume) >= self.TOMATO_FILTER_VOLUME]
        filtered_bids = [price for price, volume in order_depth.buy_orders.items() if abs(volume) >= self.TOMATO_FILTER_VOLUME]
        mm_ask = min(filtered_asks) if filtered_asks else best_ask
        mm_bid = max(filtered_bids) if filtered_bids else best_bid
        fair_value = 0.5 * (mm_ask + mm_bid)

        bid_volume_1 = order_depth.buy_orders[best_bid]
        ask_volume_1 = abs(order_depth.sell_orders[best_ask])
        total_volume = bid_volume_1 + ask_volume_1
        microprice = (best_ask * bid_volume_1 + best_bid * ask_volume_1) / total_volume if total_volume else fair_value

        history.append(fair_value)
        prev1 = history[-2] if len(history) >= 2 else fair_value
        prev3 = history[-4] if len(history) >= 4 else prev1
        if len(history) >= 4:
            fair_value = 0.6 * fair_value + 0.25 * history[-2] + 0.15 * history[-4]
        elif len(history) >= 2:
            fair_value = 0.75 * fair_value + 0.25 * history[-2]

        second_bids = sorted(order_depth.buy_orders, reverse=True)
        second_asks = sorted(order_depth.sell_orders)
        bid2 = second_bids[1] if len(second_bids) > 1 else best_bid
        ask2 = second_asks[1] if len(second_asks) > 1 else best_ask
        bid2_vol = order_depth.buy_orders.get(bid2, bid_volume_1)
        ask2_vol = abs(order_depth.sell_orders.get(ask2, ask_volume_1))
        second_total = bid2_vol + ask2_vol
        second_imb = (bid2_vol - ask2_vol) / second_total if second_total else 0.0
        gap_signal = (ask2 - best_ask) - (best_bid - bid2)
        ret1 = fair_value - prev1
        ret3 = fair_value - prev3
        micro_delta = microprice - fair_value

        alpha = self.FAIR_ALPHA_SCALE * (
            self.GAP_WEIGHT * gap_signal
            + self.SECOND_IMB_WEIGHT * second_imb
            + self.RET1_WEIGHT * ret1
            + self.RET3_WEIGHT * ret3
            + self.MICRO_WEIGHT * micro_delta
        )
        fair_value = fair_value + alpha - self.INVENTORY_SKEW * (position / self.LIMITS["TOMATOES"])

        orders: List[Order] = []
        buy_volume = 0
        sell_volume = 0
        buy_take_width = max(0, self.TOMATO_TAKE_WIDTH - int(abs(alpha) >= self.TAKE_EXTRA and alpha > 0))
        sell_take_width = max(0, self.TOMATO_TAKE_WIDTH - int(abs(alpha) >= self.TAKE_EXTRA and alpha < 0))

        best_ask_size = -order_depth.sell_orders[best_ask]
        if best_ask <= fair_value - buy_take_width:
            quantity = min(best_ask_size, self.LIMITS["TOMATOES"] - position - buy_volume)
            if quantity > 0:
                orders.append(Order("TOMATOES", best_ask, quantity))
                buy_volume += quantity

        best_bid_size = order_depth.buy_orders[best_bid]
        if best_bid >= fair_value + sell_take_width:
            quantity = min(best_bid_size, self.LIMITS["TOMATOES"] + position - sell_volume)
            if quantity > 0:
                orders.append(Order("TOMATOES", best_bid, -quantity))
                sell_volume += quantity

        position_after_take = position + buy_volume - sell_volume
        fair_bid = round(fair_value - self.CLEAR_WIDTH)
        fair_ask = round(fair_value + self.CLEAR_WIDTH)
        if position_after_take > 0 and fair_ask in order_depth.buy_orders:
            quantity = min(order_depth.buy_orders[fair_ask], position_after_take, self.LIMITS["TOMATOES"] + position - sell_volume)
            if quantity > 0:
                orders.append(Order("TOMATOES", fair_ask, -quantity))
                sell_volume += quantity
        if position_after_take < 0 and fair_bid in order_depth.sell_orders:
            quantity = min(abs(order_depth.sell_orders[fair_bid]), -position_after_take, self.LIMITS["TOMATOES"] - position - buy_volume)
            if quantity > 0:
                orders.append(Order("TOMATOES", fair_bid, quantity))
                buy_volume += quantity

        shift = self.QUOTE_AGGRESSION if alpha > self.TAKE_EXTRA else (-self.QUOTE_AGGRESSION if alpha < -self.TAKE_EXTRA else 0)
        ask_candidates = [price for price in order_depth.sell_orders if price > fair_value + 1]
        bid_candidates = [price for price in order_depth.buy_orders if price < fair_value - 1]
        ask_price = min(ask_candidates) - 1 - max(0, -shift) if ask_candidates else int(round(fair_value + 2 - max(0, -shift)))
        bid_price = max(bid_candidates) + 1 + max(0, shift) if bid_candidates else int(round(fair_value - 2 + max(0, shift)))
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        buy_size = self.LIMITS["TOMATOES"] - (position + buy_volume)
        sell_size = self.LIMITS["TOMATOES"] + (position - sell_volume)
        if buy_size > 0:
            orders.append(Order("TOMATOES", bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order("TOMATOES", ask_price, -sell_size))
        return orders, history

    @staticmethod
    def _load_state(trader_data: str) -> Dict[str, List[float]]:
        if not trader_data:
            return {}
        try:
            payload = json.loads(trader_data)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
