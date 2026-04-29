from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


class Trader:
    LIMIT = 10
    QUOTE_SIZE = 10
    IMPROVE = 1
    PRODUCTS = {
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "SLEEP_POD_SUEDE",
        "SLEEP_POD_POLYESTER",
        "SLEEP_POD_NYLON",
        "SLEEP_POD_COTTON",
        "MICROCHIP_CIRCLE",
        "MICROCHIP_OVAL",
        "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
        "PEBBLES_S",
        "PEBBLES_L",
        "PEBBLES_XL",
        "ROBOT_DISHES",
        "ROBOT_LAUNDRY",
        "ROBOT_IRONING",
        "UV_VISOR_YELLOW",
        "UV_VISOR_AMBER",
        "UV_VISOR_ORANGE",
        "UV_VISOR_RED",
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_VOID_BLUE",
        "PANEL_2X2",
        "PANEL_1X4",
        "PANEL_2X4",
        "OXYGEN_SHAKE_MORNING_BREATH",
        "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
        "SNACKPACK_CHOCOLATE",
        "SNACKPACK_VANILLA",
        "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY",
        "SNACKPACK_RASPBERRY",
    }

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        circle_hist = data.get("c", [])

        mids = {}
        for product, depth in state.order_depths.items():
            if depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        if "MICROCHIP_CIRCLE" in mids:
            circle_hist.append(mids["MICROCHIP_CIRCLE"])
            circle_hist = circle_hist[-110:]

        for product, depth in state.order_depths.items():
            if product not in self.PRODUCTS or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue

            fair = mids[product]
            take_edge = 10**9
            mm_edge = 0.0
            if product == "MICROCHIP_OVAL" and len(circle_hist) > 50:
                fair += 1.25 * 0.067 * (circle_hist[-1] - circle_hist[-51])
                take_edge = 5.5
                mm_edge = 1.0
            elif product == "MICROCHIP_SQUARE" and len(circle_hist) > 100:
                fair += 0.75 * 0.138 * (circle_hist[-1] - circle_hist[-101])
                take_edge = 6.0
                mm_edge = 0.5

            result[product] = self.trade_product(
                product,
                depth,
                int(state.position.get(product, 0)),
                fair,
                take_edge,
                mm_edge,
            )

        return result, 0, json.dumps({"c": circle_hist}, separators=(",", ":"))

    def trade_product(
        self,
        product: str,
        depth: OrderDepth,
        position: int,
        fair: float,
        take_edge: float,
        mm_edge: float,
    ) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_cap = max(0, self.LIMIT - position)
        sell_cap = max(0, self.LIMIT + position)
        orders: List[Order] = []

        if buy_cap > 0 and best_ask <= fair - take_edge:
            qty = min(buy_cap, self.QUOTE_SIZE, -int(depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_cap -= qty
        if sell_cap > 0 and best_bid >= fair + take_edge:
            qty = min(sell_cap, self.QUOTE_SIZE, int(depth.buy_orders[best_bid]))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
                sell_cap -= qty

        if best_bid >= best_ask:
            return orders
        if best_ask - best_bid > 2 * self.IMPROVE:
            bid_price = best_bid + self.IMPROVE
            ask_price = best_ask - self.IMPROVE
        elif best_ask - best_bid > 1:
            bid_price = best_bid + 1
            ask_price = best_ask - 1
        else:
            bid_price = best_bid
            ask_price = best_ask

        if buy_cap > 0 and bid_price <= fair - mm_edge:
            orders.append(Order(product, bid_price, min(self.QUOTE_SIZE, buy_cap)))
        if sell_cap > 0 and ask_price >= fair + mm_edge:
            orders.append(Order(product, ask_price, -min(self.QUOTE_SIZE, sell_cap)))
        return orders
