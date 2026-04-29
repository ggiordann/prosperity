from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


class Trader:
    LIMIT = 10
    QUOTE_SIZE = 5
    IMPROVE = 1
    PRODUCTS = set([
        "GALAXY_SOUNDS_DARK_MATTER", "GALAXY_SOUNDS_BLACK_HOLES", "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS", "SLEEP_POD_SUEDE", "SLEEP_POD_POLYESTER", "SLEEP_POD_NYLON",
        "SLEEP_POD_COTTON", "MICROCHIP_CIRCLE", "MICROCHIP_OVAL", "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE", "MICROCHIP_TRIANGLE", "PEBBLES_S", "PEBBLES_L", "PEBBLES_XL",
        "ROBOT_DISHES", "ROBOT_LAUNDRY", "ROBOT_IRONING", "UV_VISOR_YELLOW", "UV_VISOR_AMBER",
        "UV_VISOR_ORANGE", "UV_VISOR_RED", "TRANSLATOR_ASTRO_BLACK", "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_VOID_BLUE", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4",
        "OXYGEN_SHAKE_MORNING_BREATH", "OXYGEN_SHAKE_EVENING_BREATH", "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC", "SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY", "SNACKPACK_RASPBERRY",
    ])

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        hist = data.get("h", [])
        mids = {}
        for p, d in state.order_depths.items():
            if d.buy_orders and d.sell_orders:
                mids[p] = (max(d.buy_orders) + min(d.sell_orders)) / 2.0
        if "MICROCHIP_CIRCLE" in mids:
            hist.append(mids["MICROCHIP_CIRCLE"])
            hist = hist[-110:]

        for p, d in state.order_depths.items():
            if p not in self.PRODUCTS or not d.buy_orders or not d.sell_orders:
                result[p] = []
                continue
            fair = mids[p]
            take_edge = 10**9
            mm_edge = 0.0
            if p == "MICROCHIP_OVAL" and len(hist) > 50:
                fair += 1.25 * 0.067 * (hist[-1] - hist[-51])
                take_edge = 6.0
                mm_edge = 0.5
            elif p == "MICROCHIP_SQUARE" and len(hist) > 100:
                fair += 0.5 * 0.138 * (hist[-1] - hist[-101])
                take_edge = 6.5
                mm_edge = 0.0
            result[p] = self.trade_product(p, d, int(state.position.get(p, 0)), fair, take_edge, mm_edge)

        return result, 0, json.dumps({"h": hist}, separators=(",", ":"))

    def trade_product(self, p: str, d: OrderDepth, pos: int, fair: float, take_edge: float, mm_edge: float) -> List[Order]:
        bb = max(d.buy_orders)
        ba = min(d.sell_orders)
        orders: List[Order] = []
        buy_cap = max(0, self.LIMIT - pos)
        sell_cap = max(0, self.LIMIT + pos)
        if buy_cap > 0 and ba <= fair - take_edge:
            qty = min(buy_cap, self.QUOTE_SIZE, -int(d.sell_orders[ba]))
            if qty > 0:
                orders.append(Order(p, ba, qty))
                buy_cap -= qty
        if sell_cap > 0 and bb >= fair + take_edge:
            qty = min(sell_cap, self.QUOTE_SIZE, int(d.buy_orders[bb]))
            if qty > 0:
                orders.append(Order(p, bb, -qty))
                sell_cap -= qty
        if bb >= ba:
            return orders
        if ba - bb > 2:
            bid = bb + self.IMPROVE
            ask = ba - self.IMPROVE
        else:
            bid = bb
            ask = ba
        if buy_cap > 0 and bid <= fair - mm_edge:
            orders.append(Order(p, bid, min(self.QUOTE_SIZE, buy_cap)))
        if sell_cap > 0 and ask >= fair + mm_edge:
            orders.append(Order(p, ask, -min(self.QUOTE_SIZE, sell_cap)))
        return orders
