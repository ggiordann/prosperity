from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


F = {
    "ROBOT_DISHES": 9962.651,
    "ROBOT_IRONING": 8450.985,
    "ROBOT_LAUNDRY": 9930.268,
    "ROBOT_MOPPING": 11157.750,
    "ROBOT_VACUUMING": 9153.395,
}
TAKE = {
    "ROBOT_DISHES": 194.824,
    "ROBOT_IRONING": 963.788,
    "ROBOT_LAUNDRY": 767.903,
    "ROBOT_MOPPING": 1150.742,
    "ROBOT_VACUUMING": 909.940,
}
EDGE = {
    "ROBOT_DISHES": 1.0,
    "ROBOT_IRONING": 0.0,
    "ROBOT_LAUNDRY": 2.0,
    "ROBOT_MOPPING": 8.0,
    "ROBOT_VACUUMING": 6.0,
}
SIG = {
    "ROBOT_DISHES": (("ROBOT_IRONING", 200, -0.5), ("ROBOT_IRONING", 200, -0.05)),
    "ROBOT_IRONING": (("ROBOT_MOPPING", 20, -0.25), ("ROBOT_VACUUMING", 2, -0.25)),
    "ROBOT_LAUNDRY": (("ROBOT_MOPPING", 500, 1.0), ("ROBOT_VACUUMING", 500, 1.0)),
    "ROBOT_MOPPING": (("ROBOT_DISHES", 500, -0.05), ("ROBOT_VACUUMING", 20, -0.1)),
    "ROBOT_VACUUMING": (("ROBOT_MOPPING", 100, 0.05), ("ROBOT_LAUNDRY", 200, -0.25)),
}
WALK = {"ROBOT_DISHES", "ROBOT_LAUNDRY"}
PRODUCTS = set(F)


class Trader:
    L = 10
    Q = 20

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        hist = data.get("h", {})
        mids = {}
        for product, depth in state.order_depths.items():
            if depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        for product in PRODUCTS:
            if product in mids:
                values = hist.get(product, [])
                values.append(mids[product])
                hist[product] = values[-501:]
        for product, depth in state.order_depths.items():
            if product not in PRODUCTS or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = F[product]
            for leader, lag, coeff in SIG.get(product, ()):
                values = hist.get(leader, [])
                if len(values) > lag:
                    fair += coeff * (values[-1] - values[-1 - lag])
            position = int(state.position.get(product, 0))
            result[product] = self.trade(product, depth, position, fair, TAKE[product], EDGE[product])
        return result, 0, json.dumps({"h": hist}, separators=(",", ":"))

    def trade(
        self,
        product: str,
        depth: OrderDepth,
        position: int,
        fair: float,
        take_edge: float,
        quote_edge: float,
    ) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_capacity = max(0, self.L - position)
        sell_capacity = max(0, self.L + position)
        orders: List[Order] = []
        if product in WALK and buy_capacity > 0:
            for price in sorted(depth.sell_orders):
                if price > fair - take_edge or buy_capacity <= 0:
                    break
                qty = min(buy_capacity, self.Q, -int(depth.sell_orders[price]))
                if qty > 0:
                    orders.append(Order(product, price, qty))
                    buy_capacity -= qty
        elif buy_capacity > 0 and best_ask <= fair - take_edge:
            qty = min(buy_capacity, self.Q, -int(depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_capacity -= qty
        if product in WALK and sell_capacity > 0:
            for price in sorted(depth.buy_orders, reverse=True):
                if price < fair + take_edge or sell_capacity <= 0:
                    break
                qty = min(sell_capacity, self.Q, int(depth.buy_orders[price]))
                if qty > 0:
                    orders.append(Order(product, price, -qty))
                    sell_capacity -= qty
        elif sell_capacity > 0 and best_bid >= fair + take_edge:
            qty = min(sell_capacity, self.Q, int(depth.buy_orders[best_bid]))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_capacity -= qty
        if buy_capacity > 0 and best_bid <= fair - quote_edge:
            orders.append(Order(product, best_bid, min(self.Q, buy_capacity)))
        if sell_capacity > 0 and best_ask >= fair + quote_edge:
            orders.append(Order(product, best_ask, -min(self.Q, sell_capacity)))
        return orders
