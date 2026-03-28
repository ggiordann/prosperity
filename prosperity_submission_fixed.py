from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Tuple

try:
    from datamodel import Order, OrderDepth, TradingState
except ImportError:
    from prosperity.datamodel import Order, OrderDepth, TradingState


class Trader:
    POSITION_LIMITS = {"EMERALDS": 80, "TOMATOES": 80}
    STABLE_VALUE = 10_000.0

    EMERALDS = {
        "take_width": 1.0,
        "strong_take_width": 4.0,
        "take_size": 8,
        "soft_limit": 52,
        "inventory_penalty": 0.06,
        "age_penalty": 0.05,
        "make_width": 3.2,
        "make_fraction": 0.25,
        "max_quote_distance": 4,
        "make_size": 28,
    }

    TOMATOES = {
        "process_var": 1.8,
        "obs_base_var": 4.0,
        "spread_var_weight": 0.11,
        "fast_alpha": 0.28,
        "slow_alpha": 0.06,
        "vol_alpha": 0.08,
        "trend_weight": 0.55,
        "reversion_weight": 0.35,
        "micro_weight": 0.35,
        "wall_weight": 0.55,
        "mid_weight": 0.10,
        "inventory_penalty": 0.12,
        "age_penalty": 0.08,
        "take_width": 1.5,
        "take_vol_weight": 0.80,
        "strong_take_width": 3.75,
        "adverse_volume": 18,
        "take_size": 8,
        "soft_limit": 56,
        "make_base_width": 2.15,
        "make_vol_weight": 0.40,
        "make_fraction": 0.24,
        "max_quote_distance": 4,
        "make_size": 26,
    }

    def bid(self):
        return 15

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData)
        result: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            position = state.position.get(product, 0)
            self._update_inventory_state(memory, product, position)

            if product == "EMERALDS":
                orders = self._trade_emeralds(order_depth, position, memory)
            elif product == "TOMATOES":
                orders = self._trade_tomatoes(order_depth, position, memory)
            else:
                orders = []

            result[product] = orders

        return result, 0, self._dump_memory(memory)

    def _trade_emeralds(
        self,
        order_depth: OrderDepth,
        position: int,
        memory: dict,
    ) -> List[Order]:
        view = self._book_view(order_depth)
        if view is None:
            return []

        params = self.EMERALDS
        inventory_age = memory["EMERALDS"]["inventory_age"]
        fair_value = (
            self.STABLE_VALUE
            - params["inventory_penalty"] * position
            - params["age_penalty"] * inventory_age * self._position_sign(position)
        )

        return self._generate_orders(
            product="EMERALDS",
            order_depth=order_depth,
            position=position,
            fair_value=fair_value,
            volatility=0.0,
            inventory_age=inventory_age,
            params=params,
            adverse_volume=0,
            prevent_adverse=False,
        )

    def _trade_tomatoes(
        self,
        order_depth: OrderDepth,
        position: int,
        memory: dict,
    ) -> List[Order]:
        view = self._book_view(order_depth)
        if view is None:
            return []

        params = self.TOMATOES
        signal_state = memory.setdefault("TOMATOES", {})

        wall_mid = view["wall_mid"]
        micro_price = view["micro_price"]
        mid_price = view["mid_price"]
        observation = (
            params["wall_weight"] * wall_mid
            + params["mid_weight"] * mid_price
            + params["micro_weight"] * micro_price
        )

        latent_mean = signal_state.get("latent_mean", observation)
        latent_var = signal_state.get("latent_var", params["obs_base_var"])
        prior_var = latent_var + params["process_var"]
        observation_var = (
            params["obs_base_var"]
            + params["spread_var_weight"] * (view["spread"] * view["spread"])
        )
        gain = prior_var / (prior_var + observation_var)
        latent_mean = latent_mean + gain * (observation - latent_mean)
        latent_var = max(0.5, (1.0 - gain) * prior_var)

        fast_ema = signal_state.get("fast_ema", observation)
        slow_ema = signal_state.get("slow_ema", observation)
        fast_ema = (1.0 - params["fast_alpha"]) * fast_ema + params["fast_alpha"] * observation
        slow_ema = (1.0 - params["slow_alpha"]) * slow_ema + params["slow_alpha"] * observation

        last_observation = signal_state.get("last_observation")
        variance = signal_state.get("variance", 1.0)
        if last_observation is not None:
            move = observation - last_observation
            variance = (
                (1.0 - params["vol_alpha"]) * variance
                + params["vol_alpha"] * (move * move)
            )
        volatility = max(1.0, math.sqrt(max(variance, 0.0)))

        inventory_age = signal_state.get("inventory_age", 0)
        fair_value = (
            latent_mean
            + params["trend_weight"] * (fast_ema - slow_ema)
            + params["reversion_weight"] * (latent_mean - observation)
            - params["inventory_penalty"] * position
            - params["age_penalty"] * inventory_age * self._position_sign(position)
        )

        signal_state["latent_mean"] = latent_mean
        signal_state["latent_var"] = latent_var
        signal_state["fast_ema"] = fast_ema
        signal_state["slow_ema"] = slow_ema
        signal_state["variance"] = variance
        signal_state["last_observation"] = observation

        return self._generate_orders(
            product="TOMATOES",
            order_depth=order_depth,
            position=position,
            fair_value=fair_value,
            volatility=volatility,
            inventory_age=inventory_age,
            params=params,
            adverse_volume=params["adverse_volume"],
            prevent_adverse=True,
        )

    def _generate_orders(
        self,
        *,
        product: str,
        order_depth: OrderDepth,
        position: int,
        fair_value: float,
        volatility: float,
        inventory_age: int,
        params: dict,
        adverse_volume: int,
        prevent_adverse: bool,
    ) -> List[Order]:
        view = self._book_view(order_depth)
        if view is None:
            return []

        orders: List[Order] = []
        buy_taken = 0
        sell_taken = 0
        best_bid = view["best_bid"]
        best_ask = view["best_ask"]

        take_width = params["take_width"] + params.get("take_vol_weight", 0.0) * volatility
        strong_take_width = params["strong_take_width"] + 0.25 * volatility
        target_distance = self._quote_distance(
            spread=view["spread"],
            fraction=params["make_fraction"],
            max_distance=params["max_quote_distance"],
        )

        buy_taken, sell_taken = self._take_orders(
            product=product,
            order_depth=order_depth,
            view=view,
            fair_value=fair_value,
            take_width=take_width,
            strong_take_width=strong_take_width,
            take_size=params["take_size"],
            current_position=position,
            buy_taken=buy_taken,
            sell_taken=sell_taken,
            orders=orders,
            prevent_adverse=prevent_adverse,
            adverse_volume=adverse_volume,
            max_cross_distance=target_distance + 1,
        )
        make_width = params["make_width"] if product == "EMERALDS" else (
            params["make_base_width"] + params["make_vol_weight"] * volatility
        )

        skew = 0
        projected_position = position + buy_taken - sell_taken
        if projected_position > params["soft_limit"]:
            skew = -1
        elif projected_position < -params["soft_limit"]:
            skew = 1
        if inventory_age > 20:
            skew -= self._position_sign(projected_position)

        bid_quote = min(
            int(math.floor(fair_value - make_width)),
            best_bid + target_distance + max(skew, 0),
            best_ask - 1,
        )
        ask_quote = max(
            int(math.ceil(fair_value + make_width)),
            best_ask - target_distance + min(skew, 0),
            best_bid + 1,
        )

        buy_capacity, sell_capacity = self._remaining_capacities(
            product=product,
            position=position,
            buy_taken=buy_taken,
            sell_taken=sell_taken,
        )
        make_size = params["make_size"]
        if abs(projected_position) > params["soft_limit"]:
            make_size = max(8, make_size // 2)

        if buy_capacity > 0 and best_bid < bid_quote < best_ask:
            orders.append(Order(product, bid_quote, min(buy_capacity, make_size)))

        if sell_capacity > 0 and best_bid < ask_quote < best_ask:
            orders.append(Order(product, ask_quote, -min(sell_capacity, make_size)))

        return orders

    def _take_orders(
        self,
        *,
        product: str,
        order_depth: OrderDepth,
        view: dict,
        fair_value: float,
        take_width: float,
        strong_take_width: float,
        take_size: int,
        current_position: int,
        buy_taken: int,
        sell_taken: int,
        orders: List[Order],
        prevent_adverse: bool,
        adverse_volume: int,
        max_cross_distance: int,
    ) -> Tuple[int, int]:
        buy_capacity, sell_capacity = self._remaining_capacities(
            product=product,
            position=current_position,
            buy_taken=buy_taken,
            sell_taken=sell_taken,
        )
        best_bid = view["best_bid"]
        best_ask = view["best_ask"]

        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            if buy_capacity <= 0:
                break
            visible_volume = -ask_volume
            if ask_price - best_bid > max_cross_distance:
                continue
            if ask_price > fair_value - take_width:
                break
            if prevent_adverse and visible_volume > adverse_volume and ask_price > fair_value - strong_take_width:
                continue
            quantity = min(visible_volume, buy_capacity, take_size)
            if quantity <= 0:
                continue
            orders.append(Order(product, ask_price, quantity))
            buy_taken += quantity
            buy_capacity -= quantity

        for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
            if sell_capacity <= 0:
                break
            if best_ask - bid_price > max_cross_distance:
                continue
            if bid_price < fair_value + take_width:
                break
            if prevent_adverse and bid_volume > adverse_volume and bid_price < fair_value + strong_take_width:
                continue
            quantity = min(bid_volume, sell_capacity, take_size)
            if quantity <= 0:
                continue
            orders.append(Order(product, bid_price, -quantity))
            sell_taken += quantity
            sell_capacity -= quantity

        return buy_taken, sell_taken
    def _remaining_capacities(
        self,
        *,
        product: str,
        position: int,
        buy_taken: int,
        sell_taken: int,
    ) -> Tuple[int, int]:
        limit = self.POSITION_LIMITS[product]
        buy_capacity = max(0, limit - (position + buy_taken - sell_taken))
        sell_capacity = max(0, limit + (position + buy_taken - sell_taken))
        return buy_capacity, sell_capacity

    def _quote_distance(self, *, spread: int, fraction: float, max_distance: int) -> int:
        if spread <= 1:
            return 1
        return max(1, min(max_distance, int(round(spread * fraction))))

    def _book_view(self, order_depth: OrderDepth) -> Optional[dict]:
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None

        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        bid_volume = order_depth.buy_orders[best_bid]
        ask_volume = -order_depth.sell_orders[best_ask]
        spread = best_ask - best_bid

        wall_bid = max(order_depth.buy_orders.items(), key=lambda item: (item[1], item[0]))[0]
        wall_ask = min(order_depth.sell_orders.items(), key=lambda item: (item[1], item[0]))[0]
        mid_price = (best_bid + best_ask) / 2.0
        wall_mid = (wall_bid + wall_ask) / 2.0
        micro_price = self._micro_price(best_bid, best_ask, bid_volume, ask_volume)

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "mid_price": mid_price,
            "wall_mid": wall_mid,
            "micro_price": micro_price,
        }

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

    def _update_inventory_state(self, memory: dict, product: str, position: int) -> None:
        state = memory.setdefault(product, {})
        last_position = state.get("last_position", 0)
        if position == 0:
            inventory_age = 0
        elif position * last_position > 0:
            inventory_age = state.get("inventory_age", 0) + 1
        else:
            inventory_age = 1
        state["inventory_age"] = inventory_age
        state["last_position"] = position

    def _position_sign(self, position: int) -> int:
        if position > 0:
            return 1
        if position < 0:
            return -1
        return 0

    def _load_memory(self, trader_data: str) -> dict:
        if not trader_data:
            return {}
        try:
            return json.loads(trader_data)
        except json.JSONDecodeError:
            return {}

    def _dump_memory(self, memory: dict) -> str:
        payload = json.dumps(memory, separators=(",", ":"))
        if len(payload) > 49000:
            # Drop high-cardinality state before exceeding Prosperity's cap.
            compact = {
                product: {
                    key: value
                    for key, value in state.items()
                    if key in {
                        "latent_mean",
                        "latent_var",
                        "fast_ema",
                        "slow_ema",
                        "variance",
                        "last_observation",
                        "inventory_age",
                        "last_position",
                    }
                }
                for product, state in memory.items()
            }
            payload = json.dumps(compact, separators=(",", ":"))
        return payload
