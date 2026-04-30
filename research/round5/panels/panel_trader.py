from datamodel import Order, TradingState
from typing import Dict, List
import json


P = ["PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"]
LIM = 10
Q = 20

FAIR = {
    "PANEL_1X2": 8982.0,
    "PANEL_2X2": 9593.0,
    "PANEL_1X4": 9523.0,
    "PANEL_2X4": 11312.0,
    "PANEL_4X4": 9879.0,
}
TAKE = {
    "PANEL_1X2": 560.0,
    "PANEL_2X2": 1215.0,
    "PANEL_1X4": 1501.0,
    "PANEL_2X4": 470.0,
    "PANEL_4X4": 571.0,
}
EDGE = {
    "PANEL_1X2": 2.0,
    "PANEL_2X2": 6.0,
    "PANEL_1X4": 2.0,
    "PANEL_2X4": 6.0,
    "PANEL_4X4": 2.0,
}
SIG = {
    "PANEL_1X2": (("PANEL_2X2", 200, -1.0),),
    "PANEL_2X2": (("PANEL_1X2", 50, 0.5),),
    "PANEL_1X4": (("PANEL_1X2", 500, 1.0), ("PANEL_4X4", 200, 0.25)),
    "PANEL_2X4": (("PANEL_1X4", 500, -0.1), ("PANEL_1X4", 100, 0.5), ("PANEL_1X2", 200, 0.2)),
    "PANEL_4X4": (("PANEL_2X2", 100, -1.0), ("PANEL_2X4", 500, 0.25)),
}


class Trader:
    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            memory = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            memory = {}
        hist = memory.get("h", {})
        mids = {}

        for product in P:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                bid = max(depth.buy_orders)
                ask = min(depth.sell_orders)
                mids[product] = (bid + ask) / 2.0
                series = hist.get(product, [])
                series.append(mids[product])
                hist[product] = series[-501:]

        for product in P:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = FAIR[product]
            for leader, lag, weight in SIG.get(product, ()):
                series = hist.get(leader, [])
                if len(series) > lag:
                    fair += weight * (series[-1] - series[-1 - lag])
            position = int(state.position.get(product, 0))
            result[product] = self.trade(product, depth, position, fair, TAKE[product], EDGE[product])

        return result, 0, json.dumps({"h": hist}, separators=(",", ":"))

    def trade(self, product: str, depth, position: int, fair: float, take: float, edge: float) -> List[Order]:
        orders: List[Order] = []
        buy_cap = max(0, LIM - position)
        sell_cap = max(0, LIM + position)

        for price in sorted(depth.sell_orders):
            if buy_cap <= 0 or price > fair - take:
                break
            qty = min(buy_cap, Q, -int(depth.sell_orders[price]))
            if qty > 0:
                orders.append(Order(product, price, qty))
                buy_cap -= qty

        for price in sorted(depth.buy_orders, reverse=True):
            if sell_cap <= 0 or price < fair + take:
                break
            qty = min(sell_cap, Q, int(depth.buy_orders[price]))
            if qty > 0:
                orders.append(Order(product, price, -qty))
                sell_cap -= qty

        bid = max(depth.buy_orders)
        ask = min(depth.sell_orders)
        if buy_cap > 0 and bid <= fair - edge:
            orders.append(Order(product, bid, min(Q, buy_cap)))
        if sell_cap > 0 and ask >= fair + edge:
            orders.append(Order(product, ask, -min(Q, sell_cap)))
        return orders
