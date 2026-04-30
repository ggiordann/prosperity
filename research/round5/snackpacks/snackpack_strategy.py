from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


P = (
    "SNACKPACK_CHOCOLATE",
    "SNACKPACK_VANILLA",
    "SNACKPACK_PISTACHIO",
    "SNACKPACK_STRAWBERRY",
    "SNACKPACK_RASPBERRY",
)
M = {
    "SNACKPACK_CHOCOLATE": 9843.372,
    "SNACKPACK_VANILLA": 10097.302,
    "SNACKPACK_PISTACHIO": 9495.844,
    "SNACKPACK_STRAWBERRY": 10706.609,
    "SNACKPACK_RASPBERRY": 10077.812,
}
SHIFT = {
    "SNACKPACK_CHOCOLATE": 115.421,
    "SNACKPACK_VANILLA": -22.314,
    "SNACKPACK_STRAWBERRY": 163.608,
}
S = {
    "SNACKPACK_CHOCOLATE": 200.733,
    "SNACKPACK_VANILLA": 178.515,
    "SNACKPACK_PISTACHIO": 187.495,
    "SNACKPACK_STRAWBERRY": 363.573,
    "SNACKPACK_RASPBERRY": 169.814,
}
Z = {
    "SNACKPACK_CHOCOLATE": 0.50,
    "SNACKPACK_VANILLA": 0.65,
    "SNACKPACK_PISTACHIO": 0.25,
    "SNACKPACK_STRAWBERRY": 0.20,
    "SNACKPACK_RASPBERRY": 1.15,
}
EDGE = {
    "SNACKPACK_CHOCOLATE": 8.0,
    "SNACKPACK_VANILLA": 8.0,
    "SNACKPACK_PISTACHIO": 30.0,
    "SNACKPACK_STRAWBERRY": 36.0,
    "SNACKPACK_RASPBERRY": 1.0,
}
IMP = {
    "SNACKPACK_CHOCOLATE": 0,
    "SNACKPACK_VANILLA": 0,
    "SNACKPACK_PISTACHIO": 1,
    "SNACKPACK_STRAWBERRY": 4,
    "SNACKPACK_RASPBERRY": 0,
}
SIG = {
    "SNACKPACK_CHOCOLATE": (("SNACKPACK_STRAWBERRY", 50, 0.25), ("SNACKPACK_PISTACHIO", 100, -0.05)),
    "SNACKPACK_VANILLA": (("SNACKPACK_CHOCOLATE", 100, -0.05), ("SNACKPACK_CHOCOLATE", 2, -0.25)),
    "SNACKPACK_PISTACHIO": (("SNACKPACK_RASPBERRY", 20, -0.10), ("SNACKPACK_RASPBERRY", 500, 0.05)),
    "SNACKPACK_STRAWBERRY": (("SNACKPACK_CHOCOLATE", 100, 1.0), ("SNACKPACK_PISTACHIO", 10, -0.50)),
    "SNACKPACK_RASPBERRY": (("SNACKPACK_PISTACHIO", 50, -0.25), ("SNACKPACK_PISTACHIO", 200, -0.10)),
}


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
            if product in P and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        for product in P:
            if product in mids:
                values = hist.get(product, [])
                values.append(mids[product])
                hist[product] = values[-501:]
        for product, depth in state.order_depths.items():
            if product not in P or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = M[product] + SHIFT.get(product, 0.0)
            for leader, lag, weight in SIG.get(product, ()):
                values = hist.get(leader, [])
                if len(values) > lag:
                    fair += weight * (values[-1] - values[-1 - lag])
            result[product] = self.trade(
                product,
                depth,
                int(state.position.get(product, 0)),
                fair,
                Z[product] * S[product],
                EDGE[product],
                IMP[product],
            )
        return result, 0, json.dumps({"h": hist}, separators=(",", ":"))

    def trade(
        self,
        product: str,
        depth: OrderDepth,
        position: int,
        fair: float,
        take_edge: float,
        quote_edge: float,
        improve: int,
    ) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_cap = max(0, self.L - position)
        sell_cap = max(0, self.L + position)
        orders: List[Order] = []

        if buy_cap > 0 and best_ask <= fair - take_edge:
            qty = min(buy_cap, self.Q, -int(depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_cap -= qty
        if sell_cap > 0 and best_bid >= fair + take_edge:
            qty = min(sell_cap, self.Q, int(depth.buy_orders[best_bid]))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_cap -= qty

        if best_bid >= best_ask:
            return orders
        if best_ask - best_bid > 2 * improve:
            bid = best_bid + improve
            ask = best_ask - improve
        elif best_ask - best_bid > 1:
            bid = best_bid + 1
            ask = best_ask - 1
        else:
            bid = best_bid
            ask = best_ask
        if buy_cap > 0 and bid <= fair - quote_edge:
            orders.append(Order(product, bid, min(self.Q, buy_cap)))
        if sell_cap > 0 and ask >= fair + quote_edge:
            orders.append(Order(product, ask, -min(self.Q, sell_cap)))
        return orders
