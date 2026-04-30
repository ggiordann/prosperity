from datamodel import Order, TradingState
from typing import Dict, List
import json


PRODUCTS = (
    "TRANSLATOR_SPACE_GRAY",
    "TRANSLATOR_ASTRO_BLACK",
    "TRANSLATOR_ECLIPSE_CHARCOAL",
    "TRANSLATOR_GRAPHITE_MIST",
    "TRANSLATOR_VOID_BLUE",
)

MEAN = {
    "TRANSLATOR_ASTRO_BLACK": 9385.219,
    "TRANSLATOR_ECLIPSE_CHARCOAL": 9813.742,
    "TRANSLATOR_GRAPHITE_MIST": 10084.64,
    "TRANSLATOR_SPACE_GRAY": 9431.902,
    "TRANSLATOR_VOID_BLUE": 10858.579,
}

SHIFT = {
    "TRANSLATOR_ASTRO_BLACK": -48.975,
    "TRANSLATOR_ECLIPSE_CHARCOAL": -26.673,
    "TRANSLATOR_GRAPHITE_MIST": -199.816,
    "TRANSLATOR_SPACE_GRAY": 263.921,
    "TRANSLATOR_VOID_BLUE": 376.515,
}

STD = {
    "TRANSLATOR_ASTRO_BLACK": 489.746,
    "TRANSLATOR_ECLIPSE_CHARCOAL": 355.637,
    "TRANSLATOR_GRAPHITE_MIST": 499.541,
    "TRANSLATOR_SPACE_GRAY": 502.706,
    "TRANSLATOR_VOID_BLUE": 579.254,
}

TAKE_Z = {
    "TRANSLATOR_ASTRO_BLACK": 0.1,
    "TRANSLATOR_ECLIPSE_CHARCOAL": 0.5,
    "TRANSLATOR_GRAPHITE_MIST": 0.15,
    "TRANSLATOR_SPACE_GRAY": 1.1,
    "TRANSLATOR_VOID_BLUE": 0.15,
}

SIGNALS = {
    "TRANSLATOR_ASTRO_BLACK": (
        ("TRANSLATOR_VOID_BLUE", 200, 0.1),
        ("TRANSLATOR_GRAPHITE_MIST", 200, 0.1),
    ),
    "TRANSLATOR_ECLIPSE_CHARCOAL": (
        ("TRANSLATOR_GRAPHITE_MIST", 100, 0.5),
        ("TRANSLATOR_SPACE_GRAY", 100, -0.25),
        ("TRANSLATOR_SPACE_GRAY", 5, 0.2),
    ),
    "TRANSLATOR_GRAPHITE_MIST": (
        ("TRANSLATOR_VOID_BLUE", 500, 0.5),
        ("TRANSLATOR_ECLIPSE_CHARCOAL", 20, 0.1),
    ),
    "TRANSLATOR_SPACE_GRAY": (
        ("TRANSLATOR_ECLIPSE_CHARCOAL", 500, 0.5),
        ("TRANSLATOR_GRAPHITE_MIST", 200, -0.25),
    ),
    "TRANSLATOR_VOID_BLUE": (
        ("TRANSLATOR_ECLIPSE_CHARCOAL", 200, -0.1),
        ("TRANSLATOR_ASTRO_BLACK", 20, -0.1),
    ),
}


class Trader:
    LIMIT = 10
    MAX_QTY = 20

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        history = data.get("h", {})
        mids = {}
        for product, depth in state.order_depths.items():
            if depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0

        for product in PRODUCTS:
            if product in mids:
                row = history.get(product, [])
                row.append(mids[product])
                history[product] = row[-501:]

        for product, depth in state.order_depths.items():
            if product not in PRODUCTS or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue

            fair = MEAN[product] + SHIFT[product]
            for leader, lag, weight in SIGNALS[product]:
                row = history.get(leader, [])
                if len(row) > lag:
                    fair += weight * (row[-1] - row[-1 - lag])

            result[product] = self.take(
                product,
                depth,
                int(state.position.get(product, 0)),
                fair,
                TAKE_Z[product] * STD[product],
            )

        return result, 0, json.dumps({"h": history}, separators=(",", ":"))

    def take(self, product, depth, position, fair, take_edge):
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_cap = max(0, self.LIMIT - position)
        sell_cap = max(0, self.LIMIT + position)
        orders: List[Order] = []

        if buy_cap > 0 and best_ask <= fair - take_edge:
            qty = min(buy_cap, self.MAX_QTY, -int(depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))

        if sell_cap > 0 and best_bid >= fair + take_edge:
            qty = min(sell_cap, self.MAX_QTY, int(depth.buy_orders[best_bid]))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))

        return orders
