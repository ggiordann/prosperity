from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


PRODUCTS = {
    "MICROCHIP_CIRCLE",
    "MICROCHIP_OVAL",
    "MICROCHIP_SQUARE",
    "MICROCHIP_RECTANGLE",
    "MICROCHIP_TRIANGLE",
}
M = {
    "MICROCHIP_CIRCLE": 9214.885,
    "MICROCHIP_OVAL": 8179.599,
    "MICROCHIP_SQUARE": 13594.748,
    "MICROCHIP_RECTANGLE": 8732.439,
    "MICROCHIP_TRIANGLE": 9686.391,
}
SHIFT = {
    "MICROCHIP_OVAL": -1.0,
    "MICROCHIP_SQUARE": 2.0,
    "MICROCHIP_RECTANGLE": -470.012,
    "MICROCHIP_TRIANGLE": -50.0,
}
SCALE = {
    "MICROCHIP_CIRCLE": 532.512,
    "MICROCHIP_OVAL": 1551.912,
    "MICROCHIP_SQUARE": 1830.252,
    "MICROCHIP_RECTANGLE": 752.019,
    "MICROCHIP_TRIANGLE": 833.37,
}
MODE = {
    "MICROCHIP_CIRCLE": "static",
    "MICROCHIP_OVAL": "mid",
    "MICROCHIP_SQUARE": "mid",
    "MICROCHIP_RECTANGLE": "static",
    "MICROCHIP_TRIANGLE": "mid",
}
Z = {
    "MICROCHIP_CIRCLE": 0.75,
    "MICROCHIP_OVAL": 0.0,
    "MICROCHIP_SQUARE": 0.0,
    "MICROCHIP_RECTANGLE": 1.0,
    "MICROCHIP_TRIANGLE": 0.0,
}
EDGE = {
    "MICROCHIP_CIRCLE": 6.0,
    "MICROCHIP_OVAL": 1.5,
    "MICROCHIP_SQUARE": 15.0,
    "MICROCHIP_RECTANGLE": 0.0,
    "MICROCHIP_TRIANGLE": 0.0,
}
IMPROVE = {
    "MICROCHIP_CIRCLE": 5,
    "MICROCHIP_OVAL": 4,
    "MICROCHIP_SQUARE": 1,
    "MICROCHIP_RECTANGLE": 0,
    "MICROCHIP_TRIANGLE": 1,
}
WALK = {"MICROCHIP_SQUARE"}
LEADERS = [
    "MICROCHIP_OVAL",
    "MICROCHIP_RECTANGLE",
    "MICROCHIP_SQUARE",
    "MICROCHIP_TRIANGLE",
]
SIG = {
    "MICROCHIP_CIRCLE": (
        ("MICROCHIP_SQUARE", 100, 1.0),
        ("MICROCHIP_RECTANGLE", 100, 1.0),
    ),
    "MICROCHIP_OVAL": (
        ("MICROCHIP_RECTANGLE", 2, -0.05),
        ("MICROCHIP_RECTANGLE", 1, 0.1),
    ),
    "MICROCHIP_RECTANGLE": (
        ("MICROCHIP_SQUARE", 200, -0.1),
        ("MICROCHIP_SQUARE", 200, -1.0),
    ),
    "MICROCHIP_SQUARE": (
        ("MICROCHIP_OVAL", 10, 0.05),
        ("MICROCHIP_TRIANGLE", 5, 0.05),
    ),
    "MICROCHIP_TRIANGLE": (
        ("MICROCHIP_OVAL", 200, 1.0),
        ("MICROCHIP_OVAL", 100, 0.25),
    ),
}


class Trader:
    LIMIT = 10
    Q = 20

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        circle_hist = data.get("c", [])
        hist = data.get("h", {})

        mids = {}
        for product, depth in state.order_depths.items():
            if depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0

        if "MICROCHIP_CIRCLE" in mids:
            circle_hist.append(mids["MICROCHIP_CIRCLE"])
            circle_hist = circle_hist[-110:]
        for leader in LEADERS:
            if leader in mids:
                arr = hist.get(leader, [])
                arr.append(mids[leader])
                hist[leader] = arr[-501:]

        for product, depth in state.order_depths.items():
            if product not in PRODUCTS:
                result[product] = []
                continue
            if not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue

            fair = mids[product] + SHIFT.get(product, 0.0)
            take = 10**9
            if MODE[product] == "static":
                fair = M[product] + SHIFT.get(product, 0.0)
                take = Z[product] * SCALE[product]
            elif product == "MICROCHIP_OVAL" and len(circle_hist) > 50:
                fair += 1.25 * 0.067 * (circle_hist[-1] - circle_hist[-51])
                take = 5.5
            elif product == "MICROCHIP_SQUARE" and len(circle_hist) > 100:
                fair += 0.75 * 0.138 * (circle_hist[-1] - circle_hist[-101])
                take = 6.0

            for leader, lag, weight in SIG.get(product, ()):
                arr = hist.get(leader, [])
                if len(arr) > lag:
                    fair += weight * (arr[-1] - arr[-1 - lag])

            result[product] = self.trade(
                product,
                depth,
                int(state.position.get(product, 0)),
                fair,
                take,
                EDGE[product],
                IMPROVE[product],
            )

        return result, 0, json.dumps({"c": circle_hist, "h": hist}, separators=(",", ":"))

    def trade(self, product: str, depth: OrderDepth, pos: int, fair: float, take: float, edge: float, improve: int) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_cap = max(0, self.LIMIT - pos)
        sell_cap = max(0, self.LIMIT + pos)
        orders: List[Order] = []

        if product in WALK and buy_cap > 0:
            for price in sorted(depth.sell_orders):
                if price > fair - take or buy_cap <= 0:
                    break
                qty = min(buy_cap, self.Q, -int(depth.sell_orders[price]))
                if qty > 0:
                    orders.append(Order(product, price, qty))
                    buy_cap -= qty
        elif buy_cap > 0 and best_ask <= fair - take:
            qty = min(buy_cap, self.Q, -int(depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_cap -= qty

        if product in WALK and sell_cap > 0:
            for price in sorted(depth.buy_orders, reverse=True):
                if price < fair + take or sell_cap <= 0:
                    break
                qty = min(sell_cap, self.Q, int(depth.buy_orders[price]))
                if qty > 0:
                    orders.append(Order(product, price, -qty))
                    sell_cap -= qty
        elif sell_cap > 0 and best_bid >= fair + take:
            qty = min(sell_cap, self.Q, int(depth.buy_orders[best_bid]))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_cap -= qty

        if best_ask - best_bid > 2 * improve:
            bid = best_bid + improve
            ask = best_ask - improve
        elif best_ask - best_bid > 1:
            bid = best_bid + 1
            ask = best_ask - 1
        else:
            bid = best_bid
            ask = best_ask

        if buy_cap > 0 and bid <= fair - edge:
            orders.append(Order(product, bid, min(self.Q, buy_cap)))
        if sell_cap > 0 and ask >= fair + edge:
            orders.append(Order(product, ask, -min(self.Q, sell_cap)))
        return orders
