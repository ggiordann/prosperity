from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


PRODUCTS = [
    "OXYGEN_SHAKE_MORNING_BREATH",
    "OXYGEN_SHAKE_EVENING_BREATH",
    "OXYGEN_SHAKE_MINT",
    "OXYGEN_SHAKE_CHOCOLATE",
    "OXYGEN_SHAKE_GARLIC",
]

MEAN = {
    "OXYGEN_SHAKE_MORNING_BREATH": 10000.453,
    "OXYGEN_SHAKE_EVENING_BREATH": 9271.895,
    "OXYGEN_SHAKE_MINT": 9838.394,
    "OXYGEN_SHAKE_CHOCOLATE": 9556.879,
    "OXYGEN_SHAKE_GARLIC": 11925.640,
}

SHIFT = {
    "OXYGEN_SHAKE_MORNING_BREATH": -48.960,
    "OXYGEN_SHAKE_MINT": 38.110,
    "OXYGEN_SHAKE_GARLIC": -47.667,
}

MODE = {
    "OXYGEN_SHAKE_MORNING_BREATH": "static",
    "OXYGEN_SHAKE_EVENING_BREATH": "static",
    "OXYGEN_SHAKE_MINT": "static",
    "OXYGEN_SHAKE_CHOCOLATE": "mid",
    "OXYGEN_SHAKE_GARLIC": "static",
}

TAKE = {
    "OXYGEN_SHAKE_MORNING_BREATH": 1305.610,
    "OXYGEN_SHAKE_EVENING_BREATH": 219.902,
    "OXYGEN_SHAKE_MINT": 254.066,
    "OXYGEN_SHAKE_CHOCOLATE": 10**9,
    "OXYGEN_SHAKE_GARLIC": 333.672,
}

EDGE = {
    "OXYGEN_SHAKE_MORNING_BREATH": 6.0,
    "OXYGEN_SHAKE_EVENING_BREATH": 15.0,
    "OXYGEN_SHAKE_MINT": 2.0,
    "OXYGEN_SHAKE_CHOCOLATE": 5.0,
    "OXYGEN_SHAKE_GARLIC": 25.0,
}

IMPROVE = {
    "OXYGEN_SHAKE_MORNING_BREATH": 0,
    "OXYGEN_SHAKE_EVENING_BREATH": 1,
    "OXYGEN_SHAKE_MINT": 0,
    "OXYGEN_SHAKE_CHOCOLATE": 6,
    "OXYGEN_SHAKE_GARLIC": 5,
}

SIGNALS = {
    "OXYGEN_SHAKE_MORNING_BREATH": (
        ("OXYGEN_SHAKE_MINT", 500, 1.0),
        ("OXYGEN_SHAKE_MINT", 10, -1.0),
    ),
    "OXYGEN_SHAKE_EVENING_BREATH": (
        ("OXYGEN_SHAKE_MORNING_BREATH", 200, 0.5),
        ("OXYGEN_SHAKE_CHOCOLATE", 5, -0.5),
    ),
    "OXYGEN_SHAKE_MINT": (
        ("OXYGEN_SHAKE_GARLIC", 200, -0.05),
    ),
    "OXYGEN_SHAKE_CHOCOLATE": (
        ("OXYGEN_SHAKE_EVENING_BREATH", 50, -0.1),
        ("OXYGEN_SHAKE_GARLIC", 2, -0.05),
    ),
    "OXYGEN_SHAKE_GARLIC": (
        ("OXYGEN_SHAKE_MINT", 500, -1.0),
        ("OXYGEN_SHAKE_MINT", 200, 1.0),
    ),
}

WALK = {"OXYGEN_SHAKE_GARLIC"}


class Trader:
    LIMIT = 10
    CLIP = 20

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        history = data.get("h", {})
        mids = {}

        for product in PRODUCTS:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2

        for product, mid in mids.items():
            series = history.get(product, [])
            series.append(mid)
            history[product] = series[-501:]

        for product in PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                continue

            if MODE[product] == "mid":
                fair = mids[product] + SHIFT.get(product, 0.0)
                take = 10**9
            else:
                fair = MEAN[product] + SHIFT.get(product, 0.0)
                take = TAKE[product]

            for leader, lag, weight in SIGNALS.get(product, ()):
                series = history.get(leader, [])
                if len(series) > lag:
                    fair += weight * (series[-1] - series[-1 - lag])

            position = int(state.position.get(product, 0))
            result[product] = self.trade(product, depth, position, fair, take)

        return result, 0, json.dumps({"h": history}, separators=(",", ":"))

    def trade(
        self,
        product: str,
        depth: OrderDepth,
        position: int,
        fair: float,
        take: float,
    ) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_capacity = max(0, self.LIMIT - position)
        sell_capacity = max(0, self.LIMIT + position)
        orders: List[Order] = []

        if product in WALK:
            for price in sorted(depth.sell_orders):
                if price > fair - take or buy_capacity <= 0:
                    break
                qty = min(buy_capacity, self.CLIP, -int(depth.sell_orders[price]))
                if qty > 0:
                    orders.append(Order(product, price, qty))
                    buy_capacity -= qty
            for price in sorted(depth.buy_orders, reverse=True):
                if price < fair + take or sell_capacity <= 0:
                    break
                qty = min(sell_capacity, self.CLIP, int(depth.buy_orders[price]))
                if qty > 0:
                    orders.append(Order(product, price, -qty))
                    sell_capacity -= qty
        else:
            if buy_capacity > 0 and best_ask <= fair - take:
                qty = min(buy_capacity, self.CLIP, -int(depth.sell_orders[best_ask]))
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_capacity -= qty
            if sell_capacity > 0 and best_bid >= fair + take:
                qty = min(sell_capacity, self.CLIP, int(depth.buy_orders[best_bid]))
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_capacity -= qty

        improve = IMPROVE[product]
        if best_ask - best_bid > 2 * improve:
            bid = best_bid + improve
            ask = best_ask - improve
        elif best_ask - best_bid > 1:
            bid = best_bid + 1
            ask = best_ask - 1
        else:
            bid = best_bid
            ask = best_ask

        if buy_capacity > 0 and bid <= fair - EDGE[product]:
            orders.append(Order(product, bid, min(self.CLIP, buy_capacity)))
        if sell_capacity > 0 and ask >= fair + EDGE[product]:
            orders.append(Order(product, ask, -min(self.CLIP, sell_capacity)))
        return orders
