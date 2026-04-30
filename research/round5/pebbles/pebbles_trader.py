from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json

P = ("PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL")
M = {
    "PEBBLES_XS": 7404.64,
    "PEBBLES_S": 8932.357,
    "PEBBLES_M": 10263.243,
    "PEBBLES_L": 10174.111,
    "PEBBLES_XL": 13225.589,
}
SHIFT = {"PEBBLES_XS": -1014.683, "PEBBLES_S": 1.0, "PEBBLES_M": -17.195, "PEBBLES_L": -31.117}
MODE = {"PEBBLES_XS": "static", "PEBBLES_S": "mid", "PEBBLES_M": "static", "PEBBLES_L": "static", "PEBBLES_XL": "static"}
Z = {"PEBBLES_XS": 0.35, "PEBBLES_S": 0.0, "PEBBLES_M": 0.15, "PEBBLES_L": 0.35, "PEBBLES_XL": 0.35}
S = {"PEBBLES_XS": 1449.547, "PEBBLES_S": 833.282, "PEBBLES_M": 687.817, "PEBBLES_L": 622.332, "PEBBLES_XL": 1776.546}
EDGE = {"PEBBLES_XS": 2.0, "PEBBLES_S": 3.0, "PEBBLES_M": 20.0, "PEBBLES_L": 0.0, "PEBBLES_XL": 0.0}
IMP = {"PEBBLES_XS": 0, "PEBBLES_S": 1, "PEBBLES_M": 4, "PEBBLES_L": 1, "PEBBLES_XL": 0}
WALK = {"PEBBLES_M"}
SIG = {
    "PEBBLES_XS": (("PEBBLES_XL", 200, 0.1), ("PEBBLES_XL", 500, 0.25)),
    "PEBBLES_S": (("PEBBLES_XS", 500, 0.1), ("PEBBLES_L", 10, -0.1)),
    "PEBBLES_M": (("PEBBLES_XS", 200, -0.0625), ("PEBBLES_XL", 200, 0.625)),
    "PEBBLES_L": (("PEBBLES_S", 500, 0.5), ("PEBBLES_XL", 5, 0.5)),
    "PEBBLES_XL": (("PEBBLES_M", 20, -1.0), ("PEBBLES_M", 500, -0.1)),
}


class Trader:
    L = 10
    Q = 20

    def run(self, state: TradingState):
        out: Dict[str, List[Order]] = {}
        try:
            hist = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            hist = {}

        mids = {}
        for product in P:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
                vals = hist.get(product, [])
                vals.append(mids[product])
                hist[product] = vals[-501:]

        for product in P:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                out[product] = []
                continue

            if MODE[product] == "mid":
                fair = mids.get(product, 0) + SHIFT.get(product, 0)
                take = 10**9
            else:
                fair = M[product] + SHIFT.get(product, 0)
                take = Z[product] * S[product]

            for leader, lag, coeff in SIG.get(product, ()):
                vals = hist.get(leader, [])
                if len(vals) > lag:
                    fair += coeff * (vals[-1] - vals[-1 - lag])

            pos = int(state.position.get(product, 0))
            out[product] = self.trade(product, depth, pos, fair, take, EDGE[product], IMP[product])

        return out, 0, json.dumps(hist, separators=(",", ":"))

    def trade(self, product: str, depth: OrderDepth, pos: int, fair: float, take: float, edge: float, imp: int) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_cap = max(0, self.L - pos)
        sell_cap = max(0, self.L + pos)
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

        if best_ask - best_bid > 2 * imp:
            bid, ask = best_bid + imp, best_ask - imp
        elif best_ask - best_bid > 1:
            bid, ask = best_bid + 1, best_ask - 1
        else:
            bid, ask = best_bid, best_ask

        if buy_cap > 0 and bid <= fair - edge:
            orders.append(Order(product, bid, min(self.Q, buy_cap)))
        if sell_cap > 0 and ask >= fair + edge:
            orders.append(Order(product, ask, -min(self.Q, sell_cap)))
        return orders
