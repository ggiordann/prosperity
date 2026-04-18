
from __future__ import annotations

import json
import math
from typing import Dict, List

from datamodel import Order, OrderDepth, TradingState

CONFIG = json.loads(r'''{"ASH_COATED_OSMIUM": {"anchor": 10000, "anchor_blend": 0.0, "edge": 0, "fair_alpha": 0.0, "fallback_half_spread": 8.0, "inventory_skew": 0.008, "join_step": 0, "mode": "simple_join_mm", "quote_size": 18, "signal_skew": 0.0, "take_signal_scale": 0.0, "take_size": 0, "take_width": 9999}, "INTARIAN_PEPPER_ROOT": {"bias": 6.0, "clear_width": 1.5, "fair_alpha_scale": 3.0, "filter_volume": 22, "gap_weight": 0.1, "history_limit": 20, "inventory_skew": 1.6, "micro_weight": 0.08, "mode": "tutorial_distilled_mm", "quote_aggression": 1.0, "quote_size": 10, "ret1_weight": -0.02, "ret3_weight": -0.04, "second_imb_weight": 0.75, "take_aggression_step": 2.0, "take_extra": 2.5, "take_size": 12, "take_width": 1.0}}''')


class Trader:
    LIMITS = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    def run(self, state: TradingState):
        payload = self._load_state(state.traderData)
        result: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            params = CONFIG.get(product)
            if params is None:
                result[product] = []
                continue
            position = int(state.position.get(product, 0))
            product_state = payload.get(product, {})
            orders, next_state = self._trade_product(product, order_depth, position, params, product_state)
            payload[product] = next_state
            result[product] = orders

        return result, 0, json.dumps(payload, separators=(",", ":"))

    def _trade_product(self, product: str, order_depth: OrderDepth, position: int, params: dict, state: dict):
        mode = params.get("mode", "latent_fair_mm")
        if mode == "simple_join_mm":
            return self._trade_simple_join(product, order_depth, position, params), state
        if mode == "signal_reversion_mm":
            return self._trade_signal_reversion(product, order_depth, position, params, state)
        if mode == "tutorial_distilled_mm":
            return self._trade_tutorial_distilled(product, order_depth, position, params, state)
        if mode == "avellaneda_stoikov_mm":
            return self._trade_avellaneda_stoikov(product, order_depth, position, params, state)

        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        prev_fair = state.get("fair")
        prev_mid = state.get("mid")
        prev_spread = state.get("spread", params["fallback_half_spread"] * 2.0)
        prev_vol = state.get("vol", 0.0)
        prev_var = state.get("var", 0.0)

        observed_mid = self._observed_mid(best_bid, best_ask, prev_fair, prev_spread, params)
        if observed_mid is None:
            return [], state

        spread = float(best_ask - best_bid) if best_bid is not None and best_ask is not None else float(prev_spread)
        if best_bid is not None and best_ask is not None:
            bid_volume = max(order_depth.buy_orders[best_bid], 1)
            ask_volume = max(abs(order_depth.sell_orders[best_ask]), 1)
            microprice = (best_ask * bid_volume + best_bid * ask_volume) / float(bid_volume + ask_volume)
            micro_delta = microprice - observed_mid
            imbalance = (bid_volume - ask_volume) / float(bid_volume + ask_volume)
        else:
            micro_delta = 0.0
            imbalance = 0.0
        gap_asym = self._gap_asymmetry(order_depth, spread)
        alpha = float(params["fair_alpha"])
        anchor = params.get("anchor")
        fair = observed_mid if prev_fair is None else (1.0 - alpha) * float(prev_fair) + alpha * observed_mid
        if anchor is not None:
            fair = (1.0 - params["anchor_blend"]) * fair + params["anchor_blend"] * float(anchor)

        last_return = 0.0 if prev_mid is None else observed_mid - float(prev_mid)
        vol_alpha = float(params.get("vol_alpha", 0.08))
        vol = abs(last_return) if prev_mid is None else (1.0 - vol_alpha) * float(prev_vol) + vol_alpha * abs(last_return)
        vol_ratio = vol / max(spread, 1.0)
        log_return = 0.0 if prev_mid in (None, 0) or observed_mid <= 0 else math.log(observed_mid / float(prev_mid))
        variance = log_return * log_return if prev_mid is None else (1.0 - vol_alpha) * float(prev_var) + vol_alpha * (log_return * log_return)
        bs_sigma_price, bs_direction = self._black_scholes_signal(
            fair=fair,
            observed_mid=observed_mid,
            variance=variance,
            horizon=float(params.get("bs_horizon", 12.0)),
        )
        regime_active = vol_ratio >= float(params.get("regime_vol_threshold", 1.0e9))
        regime_edge_bonus = float(params.get("regime_edge_bonus", 0.0)) if regime_active else 0.0
        regime_signal_mult = float(params.get("regime_signal_mult", 1.0)) if regime_active else 1.0
        regime_quote_mult = float(params.get("regime_quote_mult", 1.0)) if regime_active else 1.0
        regime_take_mult = float(params.get("regime_take_mult", 1.0)) if regime_active else 1.0
        regime_take_width_bonus = float(params.get("regime_take_width_bonus", 0.0)) if regime_active else 0.0
        bs_signal = float(params.get("bs_signal_weight", 0.0)) * bs_direction * bs_sigma_price
        bs_edge_bonus = float(params.get("bs_edge_mult", 0.0)) * bs_sigma_price
        bs_take_width_bonus = float(params.get("bs_take_width_mult", 0.0)) * bs_sigma_price
        signal = (
            fair
            - observed_mid
            + float(params.get("micro_weight", 0.0)) * micro_delta
            + float(params.get("imbalance_weight", 0.0)) * imbalance * max(spread, 1.0)
            + float(params.get("gap_weight", 0.0)) * gap_asym
            - float(params.get("ret_weight", 0.0)) * last_return
            + float(params.get("bias", 0.0))
            + bs_signal
        )
        inv_shift = params["inventory_skew"] * position
        signal_shift = params["signal_skew"] * signal * regime_signal_mult
        take_signal_scale = params["take_signal_scale"] * regime_signal_mult
        take_width = params["take_width"] + regime_take_width_bonus + bs_take_width_bonus
        take_size = int(round(params["take_size"] * regime_take_mult))
        quote_size = int(round(params["quote_size"] * regime_quote_mult))
        edge = params["edge"] + regime_edge_bonus + bs_edge_bonus

        orders: List[Order] = []
        buy_used = 0
        sell_used = 0
        limit = self.LIMITS[product]

        if best_ask is not None:
            ask_volume = abs(order_depth.sell_orders[best_ask])
            threshold = fair - take_width + take_signal_scale * signal
            if best_ask <= threshold:
                quantity = min(ask_volume, take_size, limit - position - buy_used)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_used += quantity

        if best_bid is not None:
            bid_volume = order_depth.buy_orders[best_bid]
            threshold = fair + take_width + take_signal_scale * signal
            if best_bid >= threshold:
                quantity = min(bid_volume, take_size, limit + position - sell_used)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_used += quantity

        quote_bid = round(fair - edge - inv_shift + signal_shift)
        quote_ask = round(fair + edge - inv_shift + signal_shift)

        if best_bid is not None:
            quote_bid = max(quote_bid, best_bid + params["join_step"])
        if best_ask is not None:
            quote_ask = min(quote_ask, best_ask - params["join_step"])

        if best_ask is not None:
            quote_bid = min(quote_bid, best_ask - 1)
        if best_bid is not None:
            quote_ask = max(quote_ask, best_bid + 1)

        if quote_bid >= quote_ask:
            center = round(fair)
            if best_bid is not None and best_ask is not None:
                quote_bid = min(best_ask - 1, max(best_bid + params["join_step"], center - 1))
                quote_ask = max(best_bid + 1, min(best_ask - params["join_step"], center + 1))
            else:
                quote_bid = center - 1
                quote_ask = center + 1

        buy_size = min(quote_size, limit - position - buy_used)
        sell_size = min(quote_size, limit + position - sell_used)

        if buy_size > 0:
            orders.append(Order(product, int(quote_bid), int(buy_size)))
        if sell_size > 0:
            orders.append(Order(product, int(quote_ask), -int(sell_size)))

        return orders, {"fair": fair, "mid": observed_mid, "spread": spread, "vol": vol, "var": variance}

    def _trade_signal_reversion(self, product: str, order_depth: OrderDepth, position: int, params: dict, state: dict):
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        prev_ema = state.get("ema")
        prev_mid = state.get("mid")
        prev_spread = state.get("spread", params["fallback_half_spread"] * 2.0)
        prev_vol = state.get("vol", 0.0)
        prev_var = state.get("var", 0.0)

        observed_mid = self._observed_mid(best_bid, best_ask, prev_ema, prev_spread, params)
        if observed_mid is None:
            return [], state

        if best_bid is not None and best_ask is not None:
            bid_volume = max(order_depth.buy_orders[best_bid], 1)
            ask_volume = max(abs(order_depth.sell_orders[best_ask]), 1)
            microprice = (best_ask * bid_volume + best_bid * ask_volume) / float(bid_volume + ask_volume)
            micro_delta = microprice - observed_mid
            spread = float(best_ask - best_bid)
        else:
            micro_delta = 0.0
            spread = float(prev_spread)

        alpha = float(params["fair_alpha"])
        ema = observed_mid if prev_ema is None else (1.0 - alpha) * float(prev_ema) + alpha * observed_mid
        last_return = 0.0 if prev_mid is None else observed_mid - float(prev_mid)
        vol_alpha = float(params.get("vol_alpha", 0.08))
        vol = abs(last_return) if prev_mid is None else (1.0 - vol_alpha) * float(prev_vol) + vol_alpha * abs(last_return)
        vol_ratio = vol / max(spread, 1.0)
        log_return = 0.0 if prev_mid in (None, 0) or observed_mid <= 0 else math.log(observed_mid / float(prev_mid))
        variance = log_return * log_return if prev_mid is None else (1.0 - vol_alpha) * float(prev_var) + vol_alpha * (log_return * log_return)
        bs_sigma_price, bs_direction = self._black_scholes_signal(
            fair=ema,
            observed_mid=observed_mid,
            variance=variance,
            horizon=float(params.get("bs_horizon", 12.0)),
        )
        regime_active = vol_ratio >= float(params.get("regime_vol_threshold", 1.0e9))
        regime_edge_bonus = float(params.get("regime_edge_bonus", 0.0)) if regime_active else 0.0
        regime_signal_mult = float(params.get("regime_signal_mult", 1.0)) if regime_active else 1.0
        regime_quote_mult = float(params.get("regime_quote_mult", 1.0)) if regime_active else 1.0
        regime_take_mult = float(params.get("regime_take_mult", 1.0)) if regime_active else 1.0
        regime_take_width_bonus = float(params.get("regime_take_width_bonus", 0.0)) if regime_active else 0.0
        bs_signal = float(params.get("bs_signal_weight", 0.0)) * bs_direction * bs_sigma_price
        bs_edge_bonus = float(params.get("bs_edge_mult", 0.0)) * bs_sigma_price
        bs_take_width_bonus = float(params.get("bs_take_width_mult", 0.0)) * bs_sigma_price
        mean_reversion_signal = float(params.get("dev_weight", 1.0)) * (ema - observed_mid)
        micro_signal = float(params.get("micro_weight", 0.0)) * micro_delta
        return_signal = -float(params.get("ret_weight", 0.0)) * last_return
        bias_signal = float(params.get("bias", 0.0))
        signal = mean_reversion_signal + micro_signal + return_signal + bias_signal + bs_signal
        fair = observed_mid + signal

        inv_shift = params["inventory_skew"] * position
        signal_shift = params["signal_skew"] * signal * regime_signal_mult
        take_signal_scale = params["take_signal_scale"] * regime_signal_mult
        take_width = params["take_width"] + regime_take_width_bonus + bs_take_width_bonus
        take_size = int(round(params["take_size"] * regime_take_mult))
        quote_size = int(round(params["quote_size"] * regime_quote_mult))
        edge = params["edge"] + regime_edge_bonus + bs_edge_bonus

        orders: List[Order] = []
        buy_used = 0
        sell_used = 0
        limit = self.LIMITS[product]

        if best_ask is not None:
            ask_volume = abs(order_depth.sell_orders[best_ask])
            threshold = fair - take_width + take_signal_scale * signal
            if best_ask <= threshold:
                quantity = min(ask_volume, take_size, limit - position - buy_used)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_used += quantity

        if best_bid is not None:
            bid_volume = order_depth.buy_orders[best_bid]
            threshold = fair + take_width + take_signal_scale * signal
            if best_bid >= threshold:
                quantity = min(bid_volume, take_size, limit + position - sell_used)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_used += quantity

        quote_bid = round(fair - edge - inv_shift + signal_shift)
        quote_ask = round(fair + edge - inv_shift + signal_shift)

        if best_bid is not None:
            quote_bid = max(quote_bid, best_bid + params["join_step"])
        if best_ask is not None:
            quote_ask = min(quote_ask, best_ask - params["join_step"])

        if best_ask is not None:
            quote_bid = min(quote_bid, best_ask - 1)
        if best_bid is not None:
            quote_ask = max(quote_ask, best_bid + 1)

        if quote_bid >= quote_ask:
            center = round(fair)
            if best_bid is not None and best_ask is not None:
                quote_bid = min(best_ask - 1, max(best_bid + params["join_step"], center - 1))
                quote_ask = max(best_bid + 1, min(best_ask - params["join_step"], center + 1))
            else:
                quote_bid = center - 1
                quote_ask = center + 1

        buy_size = min(quote_size, limit - position - buy_used)
        sell_size = min(quote_size, limit + position - sell_used)

        if buy_size > 0:
            orders.append(Order(product, int(quote_bid), int(buy_size)))
        if sell_size > 0:
            orders.append(Order(product, int(quote_ask), -int(sell_size)))

        return orders, {"ema": ema, "mid": observed_mid, "spread": spread, "vol": vol, "var": variance}

    def _trade_avellaneda_stoikov(self, product: str, order_depth: OrderDepth, position: int, params: dict, state: dict):
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        prev_fair = state.get("fair")
        prev_mid = state.get("mid")
        prev_spread = state.get("spread", params["fallback_half_spread"] * 2.0)
        prev_vol = state.get("vol", 0.0)
        prev_var = state.get("var", 0.0)

        observed_mid = self._observed_mid(best_bid, best_ask, prev_fair, prev_spread, params)
        if observed_mid is None:
            return [], state

        spread = float(best_ask - best_bid) if best_bid is not None and best_ask is not None else float(prev_spread)
        if best_bid is not None and best_ask is not None:
            bid_volume = max(order_depth.buy_orders[best_bid], 1)
            ask_volume = max(abs(order_depth.sell_orders[best_ask]), 1)
            microprice = (best_ask * bid_volume + best_bid * ask_volume) / float(bid_volume + ask_volume)
            micro_delta = microprice - observed_mid
            imbalance = (bid_volume - ask_volume) / float(bid_volume + ask_volume)
        else:
            micro_delta = 0.0
            imbalance = 0.0

        alpha = float(params["fair_alpha"])
        fair = observed_mid if prev_fair is None else (1.0 - alpha) * float(prev_fair) + alpha * observed_mid
        gap_asym = self._gap_asymmetry(order_depth, spread)
        last_return = 0.0 if prev_mid is None else observed_mid - float(prev_mid)
        vol_alpha = float(params.get("vol_alpha", 0.08))
        vol = abs(last_return) if prev_mid is None else (1.0 - vol_alpha) * float(prev_vol) + vol_alpha * abs(last_return)
        log_return = 0.0 if prev_mid in (None, 0) or observed_mid <= 0 else math.log(observed_mid / float(prev_mid))
        variance = log_return * log_return if prev_mid is None else (1.0 - vol_alpha) * float(prev_var) + vol_alpha * (log_return * log_return)
        bs_sigma_price, bs_direction = self._black_scholes_signal(
            fair=fair,
            observed_mid=observed_mid,
            variance=variance,
            horizon=float(params.get("bs_horizon", 8.0)),
        )

        signal = (
            float(params.get("bias", 0.0))
            + float(params.get("micro_weight", 0.0)) * micro_delta
            + float(params.get("imbalance_weight", 0.0)) * imbalance * max(spread, 1.0)
            + float(params.get("gap_weight", 0.0)) * gap_asym
            - float(params.get("ret_weight", 0.0)) * last_return
            + float(params.get("bs_signal_weight", 0.0)) * bs_direction * bs_sigma_price
        )

        limit = self.LIMITS[product]
        position_ratio = position / float(limit)
        reservation = (
            fair
            + float(params.get("signal_skew", 0.0)) * signal
            - float(params.get("inventory_skew", 0.0)) * position
            - float(params.get("inventory_gamma", 0.0)) * position_ratio * bs_sigma_price
        )

        half_spread = (
            float(params.get("base_edge", params.get("edge", 1.0)))
            + float(params.get("spread_weight", 0.0)) * spread
            + float(params.get("sigma_edge_mult", 0.0)) * bs_sigma_price
        )
        take_width = float(params.get("take_width", 2.0)) + float(params.get("take_sigma_mult", 0.0)) * bs_sigma_price

        quote_scale = max(0.25, 1.0 / (1.0 + float(params.get("quote_sigma_mult", 0.0)) * max(bs_sigma_price, 0.0)))
        take_scale = max(0.2, 1.0 / (1.0 + float(params.get("take_risk_mult", 0.0)) * max(bs_sigma_price, 0.0)))
        quote_size = max(1, int(round(float(params["quote_size"]) * quote_scale)))
        take_size = max(1, int(round(float(params["take_size"]) * take_scale)))

        orders: List[Order] = []
        buy_used = 0
        sell_used = 0

        if best_ask is not None:
            ask_volume = abs(order_depth.sell_orders[best_ask])
            threshold = reservation - take_width
            if best_ask <= threshold:
                quantity = min(ask_volume, take_size, limit - position - buy_used)
                if quantity > 0:
                    orders.append(Order(product, best_ask, quantity))
                    buy_used += quantity

        if best_bid is not None:
            bid_volume = order_depth.buy_orders[best_bid]
            threshold = reservation + take_width
            if best_bid >= threshold:
                quantity = min(bid_volume, take_size, limit + position - sell_used)
                if quantity > 0:
                    orders.append(Order(product, best_bid, -quantity))
                    sell_used += quantity

        quote_bid = round(reservation - half_spread)
        quote_ask = round(reservation + half_spread)

        if best_bid is not None:
            quote_bid = max(quote_bid, best_bid + int(params.get("join_step", 0)))
        if best_ask is not None:
            quote_ask = min(quote_ask, best_ask - int(params.get("join_step", 0)))

        if best_ask is not None:
            quote_bid = min(quote_bid, best_ask - 1)
        if best_bid is not None:
            quote_ask = max(quote_ask, best_bid + 1)

        if quote_bid >= quote_ask:
            center = round(reservation)
            if best_bid is not None and best_ask is not None:
                quote_bid = min(best_ask - 1, max(best_bid + int(params.get("join_step", 0)), center - 1))
                quote_ask = max(best_bid + 1, min(best_ask - int(params.get("join_step", 0)), center + 1))
            else:
                quote_bid = center - 1
                quote_ask = center + 1

        buy_size = min(quote_size, limit - position - buy_used)
        sell_size = min(quote_size, limit + position - sell_used)

        if buy_size > 0:
            orders.append(Order(product, int(quote_bid), int(buy_size)))
        if sell_size > 0:
            orders.append(Order(product, int(quote_ask), -int(sell_size)))

        return orders, {"fair": fair, "mid": observed_mid, "spread": spread, "vol": vol, "var": variance}

    def _trade_simple_join(self, product: str, order_depth: OrderDepth, position: int, params: dict):
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return []
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        if best_bid >= best_ask:
            return []
        join_step = int(params["join_step"])
        if best_ask - best_bid > 1 + 2 * join_step:
            bid_price = best_bid + 1 + join_step
            ask_price = best_ask - 1 - join_step
        else:
            bid_price = best_bid
            ask_price = best_ask
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)
        skew = params["inventory_skew"] * position
        bid_price = int(round(bid_price - skew))
        ask_price = int(round(ask_price - skew))
        if bid_price >= ask_price:
            bid_price = best_bid
            ask_price = best_ask
        limit = self.LIMITS[product]
        buy_size = min(int(params["quote_size"]), max(0, limit - position))
        sell_size = min(int(params["quote_size"]), max(0, limit + position))
        orders: List[Order] = []
        if buy_size > 0:
            orders.append(Order(product, bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order(product, ask_price, -sell_size))
        return orders

    def _trade_tutorial_distilled(self, product: str, order_depth: OrderDepth, position: int, params: dict, state: dict):
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return [], state

        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        limit = self.LIMITS[product]

        filter_volume = int(params.get("filter_volume", 14))
        filtered_asks = [price for price, volume in order_depth.sell_orders.items() if abs(volume) >= filter_volume]
        filtered_bids = [price for price, volume in order_depth.buy_orders.items() if abs(volume) >= filter_volume]
        mm_ask = min(filtered_asks) if filtered_asks else best_ask
        mm_bid = max(filtered_bids) if filtered_bids else best_bid
        fair_value = 0.5 * (mm_ask + mm_bid)

        bid_volume_1 = max(order_depth.buy_orders[best_bid], 1)
        ask_volume_1 = max(abs(order_depth.sell_orders[best_ask]), 1)
        total_volume = bid_volume_1 + ask_volume_1
        microprice = (best_ask * bid_volume_1 + best_bid * ask_volume_1) / float(total_volume) if total_volume else fair_value

        history = list(state.get("fair_history", []))
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
        bid2_vol = max(order_depth.buy_orders.get(bid2, bid_volume_1), 1)
        ask2_vol = max(abs(order_depth.sell_orders.get(ask2, ask_volume_1)), 1)
        second_total = bid2_vol + ask2_vol
        second_imb = (bid2_vol - ask2_vol) / float(second_total) if second_total else 0.0
        gap_signal = (ask2 - best_ask) - (best_bid - bid2)
        ret1 = fair_value - prev1
        ret3 = fair_value - prev3
        micro_delta = microprice - fair_value

        alpha = float(params.get("fair_alpha_scale", 1.0)) * (
            float(params.get("gap_weight", 0.0)) * gap_signal
            + float(params.get("second_imb_weight", 0.0)) * second_imb
            + float(params.get("ret1_weight", 0.0)) * ret1
            + float(params.get("ret3_weight", 0.0)) * ret3
            + float(params.get("micro_weight", 0.0)) * micro_delta
        )
        fair_value = fair_value + alpha + float(params.get("bias", 0.0)) - float(params.get("inventory_skew", 0.0)) * (position / float(limit))

        orders: List[Order] = []
        buy_used = 0
        sell_used = 0
        take_width = float(params.get("take_width", 2.0))
        take_extra = float(params.get("take_extra", 1.5))
        take_step = float(params.get("take_aggression_step", 1.0))
        take_size = int(params.get("take_size", params.get("quote_size", 10)))
        buy_take_width = max(0.0, take_width - (take_step if alpha >= take_extra else 0.0))
        sell_take_width = max(0.0, take_width - (take_step if alpha <= -take_extra else 0.0))

        best_ask_size = abs(order_depth.sell_orders[best_ask])
        if best_ask <= fair_value - buy_take_width:
            quantity = min(best_ask_size, take_size, limit - position - buy_used)
            if quantity > 0:
                orders.append(Order(product, best_ask, quantity))
                buy_used += quantity

        best_bid_size = order_depth.buy_orders[best_bid]
        if best_bid >= fair_value + sell_take_width:
            quantity = min(best_bid_size, take_size, limit + position - sell_used)
            if quantity > 0:
                orders.append(Order(product, best_bid, -quantity))
                sell_used += quantity

        position_after_take = position + buy_used - sell_used
        clear_width = float(params.get("clear_width", 1.0))
        fair_bid = round(fair_value - clear_width)
        fair_ask = round(fair_value + clear_width)
        if position_after_take > 0 and fair_ask in order_depth.buy_orders:
            quantity = min(order_depth.buy_orders[fair_ask], position_after_take, limit + position - sell_used)
            if quantity > 0:
                orders.append(Order(product, fair_ask, -quantity))
                sell_used += quantity
        if position_after_take < 0 and fair_bid in order_depth.sell_orders:
            quantity = min(abs(order_depth.sell_orders[fair_bid]), -position_after_take, limit - position - buy_used)
            if quantity > 0:
                orders.append(Order(product, fair_bid, quantity))
                buy_used += quantity

        quote_aggression = int(round(float(params.get("quote_aggression", 1.0))))
        shift = quote_aggression if alpha > take_extra else (-quote_aggression if alpha < -take_extra else 0)
        ask_candidates = [price for price in order_depth.sell_orders if price > fair_value + 1]
        bid_candidates = [price for price in order_depth.buy_orders if price < fair_value - 1]
        ask_price = min(ask_candidates) - 1 - max(0, -shift) if ask_candidates else int(round(fair_value + 2 - max(0, -shift)))
        bid_price = max(bid_candidates) + 1 + max(0, shift) if bid_candidates else int(round(fair_value - 2 + max(0, shift)))
        bid_price = min(bid_price, best_ask - 1)
        ask_price = max(ask_price, best_bid + 1)

        quote_size = int(params.get("quote_size", 10))
        buy_size = min(quote_size, limit - (position + buy_used))
        sell_size = min(quote_size, limit + (position - sell_used))
        if buy_size > 0:
            orders.append(Order(product, int(bid_price), int(buy_size)))
        if sell_size > 0:
            orders.append(Order(product, int(ask_price), -int(sell_size)))

        history_limit = int(params.get("history_limit", 20))
        return orders, {"fair_history": history[-history_limit:]}

    @staticmethod
    def _gap_asymmetry(order_depth: OrderDepth, fallback_spread: float) -> float:
        bids = sorted(order_depth.buy_orders, reverse=True)
        asks = sorted(order_depth.sell_orders)
        bid_gap = fallback_spread
        ask_gap = fallback_spread
        if len(bids) >= 2:
            bid_gap = max(0.0, float(bids[0] - bids[1]))
        if len(asks) >= 2:
            ask_gap = max(0.0, float(asks[1] - asks[0]))
        return ask_gap - bid_gap

    @staticmethod
    def _observed_mid(best_bid, best_ask, prev_fair, prev_spread, params):
        if best_bid is not None and best_ask is not None:
            return 0.5 * (best_bid + best_ask)
        half_spread = 0.5 * prev_spread if prev_spread else params["fallback_half_spread"]
        if best_bid is not None:
            return float(best_bid) + half_spread
        if best_ask is not None:
            return float(best_ask) - half_spread
        return prev_fair

    @staticmethod
    def _black_scholes_signal(fair: float, observed_mid: float, variance: float, horizon: float):
        sigma = math.sqrt(max(variance, 0.0))
        tau = math.sqrt(max(horizon, 1.0))
        sigma_t = max(sigma * tau, 1.0e-6)
        sigma_price = max(observed_mid * sigma_t, 1.0)
        mispricing = fair - observed_mid
        d1 = mispricing / sigma_price + 0.5 * sigma_t
        d2 = d1 - sigma_t
        direction = (2.0 * Trader._norm_cdf(d1) - 1.0 + 2.0 * Trader._norm_cdf(d2) - 1.0) * 0.5
        return sigma_price, direction

    @staticmethod
    def _norm_cdf(value: float) -> float:
        return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))

    @staticmethod
    def _load_state(raw: str):
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
