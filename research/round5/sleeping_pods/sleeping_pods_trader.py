from datamodel import Order, TradingState
from typing import Dict, List
import json

PODS = [
    "SLEEP_POD_SUEDE",
    "SLEEP_POD_LAMB_WOOL",
    "SLEEP_POD_POLYESTER",
    "SLEEP_POD_NYLON",
    "SLEEP_POD_COTTON",
]

M = {
    "SLEEP_POD_SUEDE": 11397.42,
    "SLEEP_POD_LAMB_WOOL": 10701.442,
    "SLEEP_POD_POLYESTER": 11840.561,
    "SLEEP_POD_NYLON": 9636.473,
    "SLEEP_POD_COTTON": 11527.614,
}
S = {
    "SLEEP_POD_SUEDE": 899.946,
    "SLEEP_POD_LAMB_WOOL": 413.169,
    "SLEEP_POD_POLYESTER": 977.54,
    "SLEEP_POD_NYLON": 508.729,
    "SLEEP_POD_COTTON": 887.693,
}
SHIFT = {
    "SLEEP_POD_SUEDE": 697.458,
    "SLEEP_POD_LAMB_WOOL": 10.329,
    "SLEEP_POD_POLYESTER": 171.07,
    "SLEEP_POD_COTTON": 554.808,
}
MODE = {
    "SLEEP_POD_SUEDE": "static",
    "SLEEP_POD_LAMB_WOOL": "static",
    "SLEEP_POD_POLYESTER": "static",
    "SLEEP_POD_NYLON": "mid",
    "SLEEP_POD_COTTON": "static",
}
Z = {
    "SLEEP_POD_SUEDE": 0.4,
    "SLEEP_POD_LAMB_WOOL": 1.25,
    "SLEEP_POD_POLYESTER": 0.25,
    "SLEEP_POD_NYLON": 0.0,
    "SLEEP_POD_COTTON": 1.5,
}
EDGE = {
    "SLEEP_POD_SUEDE": 6.0,
    "SLEEP_POD_LAMB_WOOL": 2.0,
    "SLEEP_POD_POLYESTER": 6.0,
    "SLEEP_POD_NYLON": 1.5,
    "SLEEP_POD_COTTON": 0.0,
}
IMPROVE = {
    "SLEEP_POD_SUEDE": 0,
    "SLEEP_POD_LAMB_WOOL": 0,
    "SLEEP_POD_POLYESTER": 0,
    "SLEEP_POD_NYLON": 5,
    "SLEEP_POD_COTTON": 0,
}
WALK = {"SLEEP_POD_SUEDE", "SLEEP_POD_COTTON"}

SIG = {
    "SLEEP_POD_SUEDE": (
        ("SLEEP_POD_LAMB_WOOL", 200, 0.1),
        ("SLEEP_POD_COTTON", 200, -0.5),
    ),
    "SLEEP_POD_LAMB_WOOL": (
        ("SLEEP_POD_COTTON", 500, -1.0),
        ("SLEEP_POD_POLYESTER", 50, 1.0),
    ),
    "SLEEP_POD_POLYESTER": (
        ("SLEEP_POD_SUEDE", 200, -0.05),
        ("SLEEP_POD_NYLON", 1, 1.0),
    ),
    "SLEEP_POD_NYLON": (
        ("SLEEP_POD_COTTON", 100, 1.0),
        ("SLEEP_POD_SUEDE", 100, -0.5),
    ),
    "SLEEP_POD_COTTON": (("SLEEP_POD_LAMB_WOOL", 500, 0.25),),
}


class Trader:
    LIMIT = 10
    ORDER_SIZE = 20

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        hist = data.get("h", {})
        mids = {}

        for product in PODS:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2

        for product, mid in mids.items():
            series = hist.get(product, [])
            series.append(mid)
            hist[product] = series[-501:]

        for product in PODS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue

            if MODE[product] == "static":
                fair = M[product] + SHIFT.get(product, 0)
                take = Z[product] * S[product]
            else:
                fair = mids[product] + SHIFT.get(product, 0)
                take = 10**9

            for leader, lag, scale in SIG.get(product, ()):
                series = hist.get(leader, [])
                if len(series) > lag:
                    fair += scale * (series[-1] - series[-1 - lag])

            pos = int(state.position.get(product, 0))
            result[product] = self.trade(
                product,
                depth,
                pos,
                fair,
                take,
                EDGE[product],
                IMPROVE[product],
            )

        return result, 0, json.dumps({"h": hist}, separators=(",", ":"))

    def trade(self, product, depth, pos, fair, take, edge, improve):
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_cap = max(0, self.LIMIT - pos)
        sell_cap = max(0, self.LIMIT + pos)
        orders = []

        if product in WALK and buy_cap > 0:
            for price in sorted(depth.sell_orders):
                if price > fair - take or buy_cap <= 0:
                    break
                qty = min(buy_cap, self.ORDER_SIZE, -int(depth.sell_orders[price]))
                if qty > 0:
                    orders.append(Order(product, price, qty))
                    buy_cap -= qty
        elif buy_cap > 0 and best_ask <= fair - take:
            qty = min(buy_cap, self.ORDER_SIZE, -int(depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_cap -= qty

        if product in WALK and sell_cap > 0:
            for price in sorted(depth.buy_orders, reverse=True):
                if price < fair + take or sell_cap <= 0:
                    break
                qty = min(sell_cap, self.ORDER_SIZE, int(depth.buy_orders[price]))
                if qty > 0:
                    orders.append(Order(product, price, -qty))
                    sell_cap -= qty
        elif sell_cap > 0 and best_bid >= fair + take:
            qty = min(sell_cap, self.ORDER_SIZE, int(depth.buy_orders[best_bid]))
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
            orders.append(Order(product, bid, min(self.ORDER_SIZE, buy_cap)))
        if sell_cap > 0 and ask >= fair + edge:
            orders.append(Order(product, ask, -min(self.ORDER_SIZE, sell_cap)))

        return orders
