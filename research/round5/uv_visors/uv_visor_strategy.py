from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


class UVVisorStrategy:
    PRODUCTS = {
        "UV_VISOR_YELLOW",
        "UV_VISOR_AMBER",
        "UV_VISOR_ORANGE",
        "UV_VISOR_RED",
        "UV_VISOR_MAGENTA",
    }
    LIMIT = 10
    QUOTE_SIZE = 20

    FAIR = {
        "UV_VISOR_YELLOW": 10991.551,
        "UV_VISOR_AMBER": 6864.932,
        "UV_VISOR_ORANGE": 10275.09,
        "UV_VISOR_RED": 10784.129,
        "UV_VISOR_MAGENTA": 11617.975,
    }
    TAKE = {
        "UV_VISOR_YELLOW": 1.75 * 681.808,
        "UV_VISOR_AMBER": 0.3 * 996.918,
        "UV_VISOR_ORANGE": 1.55 * 550.603,
        "UV_VISOR_RED": 0.1 * 587.715,
        "UV_VISOR_MAGENTA": 0.35 * 613.554,
    }
    EDGE = {
        "UV_VISOR_YELLOW": 6.0,
        "UV_VISOR_AMBER": 15.0,
        "UV_VISOR_ORANGE": 0.0,
        "UV_VISOR_RED": 30.0,
        "UV_VISOR_MAGENTA": 6.0,
    }
    IMPROVE = {
        "UV_VISOR_YELLOW": 0,
        "UV_VISOR_AMBER": 1,
        "UV_VISOR_ORANGE": 0,
        "UV_VISOR_RED": 1,
        "UV_VISOR_MAGENTA": 1,
    }
    SIGNALS = {
        "UV_VISOR_YELLOW": (("UV_VISOR_AMBER", 500, 0.15), ("UV_VISOR_RED", 500, -0.05)),
        "UV_VISOR_AMBER": (("UV_VISOR_RED", 500, 0.25), ("UV_VISOR_ORANGE", 100, 0.25)),
        "UV_VISOR_ORANGE": (("UV_VISOR_YELLOW", 200, -0.25),),
        "UV_VISOR_RED": (("UV_VISOR_YELLOW", 50, 0.1), ("UV_VISOR_ORANGE", 1, -0.25)),
        "UV_VISOR_MAGENTA": (("UV_VISOR_AMBER", 500, 1.0), ("UV_VISOR_YELLOW", 20, -0.25)),
    }

    def run(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        histories = data.setdefault("uv_h", {})
        mids = {}
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2

        for product, mid in mids.items():
            hist = histories.get(product, [])
            hist.append(mid)
            histories[product] = hist[-501:]

        result: Dict[str, List[Order]] = {}
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue
            fair = self.FAIR[product]
            for leader, lag, weight in self.SIGNALS.get(product, ()):
                hist = histories.get(leader, [])
                if len(hist) > lag:
                    fair += weight * (hist[-1] - hist[-1 - lag])
            result[product] = self.trade(
                product,
                depth,
                int(state.position.get(product, 0)),
                fair,
                self.TAKE[product],
                self.EDGE[product],
                self.IMPROVE[product],
            )
        return result

    def trade(self, product: str, depth: OrderDepth, position: int, fair: float, take: float, edge: float, improve: int) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_room = max(0, self.LIMIT - position)
        sell_room = max(0, self.LIMIT + position)
        orders: List[Order] = []

        if buy_room and best_ask <= fair - take:
            quantity = min(buy_room, self.QUOTE_SIZE, -int(depth.sell_orders[best_ask]))
            if quantity > 0:
                orders.append(Order(product, best_ask, quantity))
                buy_room -= quantity
        if sell_room and best_bid >= fair + take:
            quantity = min(sell_room, self.QUOTE_SIZE, int(depth.buy_orders[best_bid]))
            if quantity > 0:
                orders.append(Order(product, best_bid, -quantity))
                sell_room -= quantity

        if best_ask - best_bid > 2 * improve:
            bid = best_bid + improve
            ask = best_ask - improve
        elif best_ask - best_bid > 1:
            bid = best_bid + 1
            ask = best_ask - 1
        else:
            bid = best_bid
            ask = best_ask

        if buy_room and bid <= fair - edge:
            orders.append(Order(product, bid, min(self.QUOTE_SIZE, buy_room)))
        if sell_room and ask >= fair + edge:
            orders.append(Order(product, ask, -min(self.QUOTE_SIZE, sell_room)))
        return orders


class Trader:
    def __init__(self):
        self.uv = UVVisorStrategy()

    def run(self, state: TradingState):
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        result = self.uv.run(state, data)
        return result, 0, json.dumps(data, separators=(",", ":"))
