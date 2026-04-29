from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


class Trader:
    LIMIT = 10
    MM_PRODUCTS = set(['GALAXY_SOUNDS_DARK_MATTER', 'GALAXY_SOUNDS_BLACK_HOLES', 'GALAXY_SOUNDS_PLANETARY_RINGS', 'GALAXY_SOUNDS_SOLAR_WINDS', 'SLEEP_POD_SUEDE', 'SLEEP_POD_POLYESTER', 'SLEEP_POD_NYLON', 'SLEEP_POD_COTTON', 'MICROCHIP_CIRCLE', 'MICROCHIP_OVAL', 'MICROCHIP_SQUARE', 'MICROCHIP_RECTANGLE', 'MICROCHIP_TRIANGLE', 'PEBBLES_S', 'PEBBLES_L', 'PEBBLES_XL', 'ROBOT_DISHES', 'ROBOT_LAUNDRY', 'ROBOT_IRONING', 'UV_VISOR_YELLOW', 'UV_VISOR_AMBER', 'UV_VISOR_ORANGE', 'UV_VISOR_RED', 'TRANSLATOR_ASTRO_BLACK', 'TRANSLATOR_ECLIPSE_CHARCOAL', 'TRANSLATOR_VOID_BLUE', 'PANEL_2X2', 'PANEL_1X4', 'PANEL_2X4', 'OXYGEN_SHAKE_MORNING_BREATH', 'OXYGEN_SHAKE_EVENING_BREATH', 'OXYGEN_SHAKE_CHOCOLATE', 'OXYGEN_SHAKE_GARLIC', 'SNACKPACK_CHOCOLATE', 'SNACKPACK_VANILLA', 'SNACKPACK_PISTACHIO', 'SNACKPACK_STRAWBERRY', 'SNACKPACK_RASPBERRY'])
    QUOTE_SIZE = 5
    IMPROVE = 1
    MIN_EDGE = 1.0
    INV_SKEW = 0.0
    USE_PEBBLES = False
    PEBBLE_CONST = 50000.0
    PEBBLE_TAKE_EDGE = 1000000000
    PEBBLE_MM_EDGE = 0.0
    USE_MICRO_LAG = True
    MICRO_TAKE_EDGE = 5.5
    MICRO_BIAS_MULT = 1.0
    MAX_HIST = 110
    PEBBLES = ['PEBBLES_XS', 'PEBBLES_S', 'PEBBLES_M', 'PEBBLES_L', 'PEBBLES_XL']

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        hist = data.get("h", {}) if self.USE_MICRO_LAG else {}
        mids = {}
        for p, d in state.order_depths.items():
            if d.buy_orders and d.sell_orders:
                mids[p] = (max(d.buy_orders) + min(d.sell_orders)) / 2.0
        if self.USE_MICRO_LAG and "MICROCHIP_CIRCLE" in mids:
            arr = hist.get("MICROCHIP_CIRCLE", [])
            arr.append(mids["MICROCHIP_CIRCLE"])
            if len(arr) > self.MAX_HIST:
                arr = arr[-self.MAX_HIST:]
            hist["MICROCHIP_CIRCLE"] = arr

        pebble_sum = None
        if self.USE_PEBBLES and all(p in mids for p in self.PEBBLES):
            pebble_sum = sum(mids[p] for p in self.PEBBLES)

        for p, d in state.order_depths.items():
            if p not in self.MM_PRODUCTS and not (self.USE_PEBBLES and p in self.PEBBLES):
                result[p] = []
                continue
            if not d.buy_orders or not d.sell_orders:
                result[p] = []
                continue
            pos = int(state.position.get(p, 0))
            fair = mids[p]
            take_edge = 10**9
            mm_edge = self.MIN_EDGE
            if self.USE_PEBBLES and p in self.PEBBLES and pebble_sum is not None:
                fair = self.PEBBLE_CONST - (pebble_sum - mids[p])
                take_edge = self.PEBBLE_TAKE_EDGE
                mm_edge = self.PEBBLE_MM_EDGE
            elif self.USE_MICRO_LAG and p in ("MICROCHIP_OVAL", "MICROCHIP_SQUARE") and "MICROCHIP_CIRCLE" in hist:
                lag = 50 if p == "MICROCHIP_OVAL" else 100
                arr = hist.get("MICROCHIP_CIRCLE", [])
                if len(arr) > lag:
                    beta = 0.067 if p == "MICROCHIP_OVAL" else 0.138
                    fair += self.MICRO_BIAS_MULT * beta * (arr[-1] - arr[-1-lag])
                    take_edge = self.MICRO_TAKE_EDGE
            result[p] = self.trade_product(p, d, pos, fair, take_edge, mm_edge)

        trader_data = json.dumps({"h": hist}, separators=(",", ":")) if self.USE_MICRO_LAG else ""
        return result, 0, trader_data

    def trade_product(self, p: str, d: OrderDepth, pos: int, fair: float, take_edge: float, mm_edge: float) -> List[Order]:
        bb = max(d.buy_orders)
        ba = min(d.sell_orders)
        orders: List[Order] = []
        buy_cap = max(0, self.LIMIT - pos)
        sell_cap = max(0, self.LIMIT + pos)
        q = self.QUOTE_SIZE

        if buy_cap > 0 and ba <= fair - take_edge:
            qty = min(buy_cap, q, -int(d.sell_orders[ba]))
            if qty > 0:
                orders.append(Order(p, ba, qty))
                buy_cap -= qty
        if sell_cap > 0 and bb >= fair + take_edge:
            qty = min(sell_cap, q, int(d.buy_orders[bb]))
            if qty > 0:
                orders.append(Order(p, bb, -qty))
                sell_cap -= qty

        if bb >= ba:
            return orders
        imp = self.IMPROVE
        if ba - bb > 2 * imp:
            bid = bb + imp
            ask = ba - imp
        elif ba - bb > 1:
            bid = bb + 1
            ask = ba - 1
        else:
            bid = bb
            ask = ba
        adj = fair - self.INV_SKEW * pos
        if buy_cap > 0 and bid <= adj - mm_edge:
            orders.append(Order(p, bid, min(q, buy_cap)))
        if sell_cap > 0 and ask >= adj + mm_edge:
            orders.append(Order(p, ask, -min(q, sell_cap)))
        return orders
