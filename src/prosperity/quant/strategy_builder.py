from __future__ import annotations

import json
import re
from pathlib import Path

from prosperity.paths import RepoPaths
from prosperity.quant.models import AlphaSignal
from prosperity.settings import AppSettings


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower() or "alpha"


def _scale_for_feature(feature: str) -> float:
    if "imbalance" in feature or "pressure" in feature:
        return 8.0
    if "micro" in feature or "ema" in feature or "return" in feature:
        return 1.0
    if "spread" in feature or "gap" in feature:
        return 0.5
    return 2.0


def _strategy_source(params: object) -> str:
    params_json = json.dumps(params, sort_keys=True)
    return f'''from __future__ import annotations

import json
from datamodel import Order, OrderDepth, TradingState


PARAMS = json.loads(r"""{params_json}""")


class Trader:
    LIMIT = 80

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData)
        result = {{}}
        for product, order_depth in state.order_depths.items():
            if product not in PARAMS or not order_depth.buy_orders or not order_depth.sell_orders:
                result[product] = []
                continue
            product_memory = memory.setdefault(product, {{}})
            result[product] = self._trade_product(
                product,
                order_depth,
                int(state.position.get(product, 0)),
                product_memory,
            )
        return result, 0, json.dumps(memory, separators=(",", ":"))

    def _load_memory(self, trader_data: str):
        if not trader_data:
            return {{}}
        try:
            payload = json.loads(trader_data)
            return payload if isinstance(payload, dict) else {{}}
        except Exception:
            return {{}}

    def _trade_product(self, product: str, order_depth: OrderDepth, position: int, memory: dict):
        params = PARAMS[product]
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        bid_volume = max(1, int(order_depth.buy_orders[best_bid]))
        ask_volume = max(1, abs(int(order_depth.sell_orders[best_ask])))
        mid = 0.5 * (best_bid + best_ask)
        spread = best_ask - best_bid
        feature = self._feature(params["feature"], order_depth, mid, memory)

        coefficient = float(params["coefficient"])
        signal_scale = float(params["signal_scale"])
        fair = mid + coefficient * signal_scale * feature
        inventory_skew = float(params["inventory_skew"]) * position / self.LIMIT
        fair -= inventory_skew

        memory["last_mid"] = mid
        memory["ema"] = (1.0 - float(params["ema_alpha"])) * float(memory.get("ema", mid)) + float(params["ema_alpha"]) * mid

        orders = []
        buy_capacity = max(0, self.LIMIT - position)
        sell_capacity = max(0, self.LIMIT + position)
        max_take = int(params["max_take"])
        min_edge = float(params["min_edge"])

        if buy_capacity > 0 and fair - best_ask >= min_edge:
            quantity = min(buy_capacity, abs(int(order_depth.sell_orders[best_ask])), max_take)
            if quantity > 0:
                orders.append(Order(product, best_ask, quantity))
                buy_capacity -= quantity
        if sell_capacity > 0 and best_bid - fair >= min_edge:
            quantity = min(sell_capacity, int(order_depth.buy_orders[best_bid]), max_take)
            if quantity > 0:
                orders.append(Order(product, best_bid, -quantity))
                sell_capacity -= quantity

        half_spread = max(float(params["half_spread"]), spread * 0.35)
        quote_size = int(params["quote_size"])
        bid_price = min(best_ask - 1, int(round(fair - half_spread)))
        ask_price = max(best_bid + 1, int(round(fair + half_spread)))
        if buy_capacity > 0 and bid_price < best_ask:
            orders.append(Order(product, bid_price, min(quote_size, buy_capacity)))
        if sell_capacity > 0 and ask_price > best_bid:
            orders.append(Order(product, ask_price, -min(quote_size, sell_capacity)))
        return orders

    def _feature(self, feature_name: str, order_depth: OrderDepth, mid: float, memory: dict) -> float:
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        bid_volume = max(1, abs(int(order_depth.buy_orders[best_bid])))
        ask_volume = max(1, abs(int(order_depth.sell_orders[best_ask])))
        top_total = max(1, bid_volume + ask_volume)
        if feature_name == "spread":
            return float(best_ask - best_bid)
        if feature_name == "top_imbalance":
            return (bid_volume - ask_volume) / top_total
        if feature_name == "micro_delta":
            micro = (best_ask * bid_volume + best_bid * ask_volume) / top_total
            return micro - mid

        bid_prices = sorted(order_depth.buy_orders, reverse=True)
        ask_prices = sorted(order_depth.sell_orders)
        bid_depth = sum(abs(int(order_depth.buy_orders[price])) for price in bid_prices[:3])
        ask_depth = sum(abs(int(order_depth.sell_orders[price])) for price in ask_prices[:3])
        depth_total = max(1, bid_depth + ask_depth)
        if feature_name == "book_imbalance":
            return (bid_depth - ask_depth) / depth_total
        if feature_name == "depth_pressure":
            return (bid_depth - ask_depth) / depth_total
        if feature_name == "gap_asymmetry":
            bid2 = bid_prices[1] if len(bid_prices) > 1 else best_bid
            ask2 = ask_prices[1] if len(ask_prices) > 1 else best_ask
            return float((ask2 - best_ask) - (best_bid - bid2))
        if feature_name == "ema_reversion":
            return float(memory.get("ema", mid)) - mid
        last_mid = float(memory.get("last_mid", mid))
        ret = mid - last_mid
        if feature_name == "return_1_momentum":
            return ret
        if feature_name in {{"return_1_fade", "return_5_fade"}}:
            return -ret
        return 0.0
'''


def build_alpha_strategy_files(
    paths: RepoPaths,
    settings: AppSettings,
    *,
    cycle_id: str,
    signals: list[AlphaSignal],
    count: int,
) -> list[Path]:
    output_dir = paths.root / settings.quant.artifacts_dir / cycle_id
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    for index, signal in enumerate(signals[:count]):
        coefficient = 1.0 if signal.correlation >= 0 else -1.0
        params = {
            signal.product: {
                "feature": signal.feature,
                "coefficient": coefficient,
                "signal_scale": _scale_for_feature(signal.feature),
                "inventory_skew": 1.0,
                "ema_alpha": 0.04,
                "max_take": 20,
                "min_edge": 1.0,
                "half_spread": 1.5,
                "quote_size": 12,
            }
        }
        filename = f"quant_{index:02d}_{_slug(signal.product)}_{_slug(signal.feature)}_h{signal.horizon}.py"
        target = output_dir / filename
        target.write_text(_strategy_source(params), encoding="utf-8")
        created.append(target)
    return created
