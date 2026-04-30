from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


ROUND5_PRODUCTS = {
    "GALAXY_SOUNDS_DARK_MATTER",
    "GALAXY_SOUNDS_BLACK_HOLES",
    "GALAXY_SOUNDS_PLANETARY_RINGS",
    "GALAXY_SOUNDS_SOLAR_WINDS",
    "GALAXY_SOUNDS_SOLAR_FLAMES",
    "SLEEP_POD_SUEDE",
    "SLEEP_POD_LAMB_WOOL",
    "SLEEP_POD_POLYESTER",
    "SLEEP_POD_NYLON",
    "SLEEP_POD_COTTON",
    "MICROCHIP_CIRCLE",
    "MICROCHIP_OVAL",
    "MICROCHIP_SQUARE",
    "MICROCHIP_RECTANGLE",
    "MICROCHIP_TRIANGLE",
    "PEBBLES_XS",
    "PEBBLES_S",
    "PEBBLES_M",
    "PEBBLES_L",
    "PEBBLES_XL",
    "ROBOT_VACUUMING",
    "ROBOT_MOPPING",
    "ROBOT_DISHES",
    "ROBOT_LAUNDRY",
    "ROBOT_IRONING",
    "UV_VISOR_YELLOW",
    "UV_VISOR_AMBER",
    "UV_VISOR_ORANGE",
    "UV_VISOR_RED",
    "UV_VISOR_MAGENTA",
    "TRANSLATOR_SPACE_GRAY",
    "TRANSLATOR_ASTRO_BLACK",
    "TRANSLATOR_ECLIPSE_CHARCOAL",
    "TRANSLATOR_GRAPHITE_MIST",
    "TRANSLATOR_VOID_BLUE",
    "PANEL_1X2",
    "PANEL_2X2",
    "PANEL_1X4",
    "PANEL_2X4",
    "PANEL_4X4",
    "OXYGEN_SHAKE_MORNING_BREATH",
    "OXYGEN_SHAKE_EVENING_BREATH",
    "OXYGEN_SHAKE_MINT",
    "OXYGEN_SHAKE_CHOCOLATE",
    "OXYGEN_SHAKE_GARLIC",
    "SNACKPACK_CHOCOLATE",
    "SNACKPACK_VANILLA",
    "SNACKPACK_PISTACHIO",
    "SNACKPACK_STRAWBERRY",
    "SNACKPACK_RASPBERRY",
}


def clip_orders(product: str, orders: List[Order], position: int) -> List[Order]:
    if product not in ROUND5_PRODUCTS:
        return []
    buy_left = max(0, 10 - position)
    sell_left = max(0, 10 + position)
    clipped: List[Order] = []
    for order in orders:
        qty = int(order.quantity)
        if qty > 0:
            qty = min(qty, buy_left)
            if qty > 0:
                clipped.append(Order(product, int(order.price), qty))
                buy_left -= qty
        elif qty < 0:
            qty = min(-qty, sell_left)
            if qty > 0:
                clipped.append(Order(product, int(order.price), -qty))
                sell_left -= qty
    return clipped


class PebblesStrategy:
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
    L = 10
    Q = 20

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        out: Dict[str, List[Order]] = {}
        hist = data.get("h", {})
        mids = {}
        for product in self.P:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
                vals = hist.get(product, [])
                vals.append(mids[product])
                hist[product] = vals[-501:]
        for product in self.P:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                out[product] = []
                continue
            if self.MODE[product] == "mid":
                fair = mids.get(product, 0) + self.SHIFT.get(product, 0)
                take = 10**9
            else:
                fair = self.M[product] + self.SHIFT.get(product, 0)
                take = self.Z[product] * self.S[product]
            for leader, lag, coeff in self.SIG.get(product, ()):
                vals = hist.get(leader, [])
                if len(vals) > lag:
                    fair += coeff * (vals[-1] - vals[-1 - lag])
            out[product] = self.trade(product, depth, int(state.position.get(product, 0)), fair, take, self.EDGE[product], self.IMP[product])
        data["h"] = hist
        return out

    def trade(self, product: str, depth: OrderDepth, pos: int, fair: float, take: float, edge: float, imp: int) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_cap = max(0, self.L - pos)
        sell_cap = max(0, self.L + pos)
        orders: List[Order] = []
        if product in self.WALK and buy_cap > 0:
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
        if product in self.WALK and sell_cap > 0:
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


class MicrochipStrategy:
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
    SHIFT = {"MICROCHIP_OVAL": -1.0, "MICROCHIP_SQUARE": 2.0, "MICROCHIP_RECTANGLE": -470.012, "MICROCHIP_TRIANGLE": -50.0}
    SCALE = {"MICROCHIP_CIRCLE": 532.512, "MICROCHIP_OVAL": 1551.912, "MICROCHIP_SQUARE": 1830.252, "MICROCHIP_RECTANGLE": 752.019, "MICROCHIP_TRIANGLE": 833.37}
    MODE = {"MICROCHIP_CIRCLE": "static", "MICROCHIP_OVAL": "mid", "MICROCHIP_SQUARE": "mid", "MICROCHIP_RECTANGLE": "static", "MICROCHIP_TRIANGLE": "mid"}
    Z = {"MICROCHIP_CIRCLE": 0.75, "MICROCHIP_OVAL": 0.0, "MICROCHIP_SQUARE": 0.0, "MICROCHIP_RECTANGLE": 1.0, "MICROCHIP_TRIANGLE": 0.0}
    EDGE = {"MICROCHIP_CIRCLE": 6.0, "MICROCHIP_OVAL": 1.5, "MICROCHIP_SQUARE": 15.0, "MICROCHIP_RECTANGLE": 0.0, "MICROCHIP_TRIANGLE": 0.0}
    IMPROVE = {"MICROCHIP_CIRCLE": 5, "MICROCHIP_OVAL": 4, "MICROCHIP_SQUARE": 1, "MICROCHIP_RECTANGLE": 0, "MICROCHIP_TRIANGLE": 1}
    WALK = {"MICROCHIP_SQUARE"}
    LEADERS = ["MICROCHIP_OVAL", "MICROCHIP_RECTANGLE", "MICROCHIP_SQUARE", "MICROCHIP_TRIANGLE"]
    SIG = {
        "MICROCHIP_CIRCLE": (("MICROCHIP_SQUARE", 100, 1.0), ("MICROCHIP_RECTANGLE", 100, 1.0)),
        "MICROCHIP_OVAL": (("MICROCHIP_RECTANGLE", 2, -0.05), ("MICROCHIP_RECTANGLE", 1, 0.1)),
        "MICROCHIP_RECTANGLE": (("MICROCHIP_SQUARE", 200, -0.1), ("MICROCHIP_SQUARE", 200, -1.0)),
        "MICROCHIP_SQUARE": (("MICROCHIP_OVAL", 10, 0.05), ("MICROCHIP_TRIANGLE", 5, 0.05)),
        "MICROCHIP_TRIANGLE": (("MICROCHIP_OVAL", 200, 1.0), ("MICROCHIP_OVAL", 100, 0.25)),
    }
    LIMIT = 10
    L = 10
    Q = 20

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        circle_hist = data.get("c", [])
        hist = data.get("h", {})
        mids = {}
        for product, depth in state.order_depths.items():
            if depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        if "MICROCHIP_CIRCLE" in mids:
            circle_hist.append(mids["MICROCHIP_CIRCLE"])
            circle_hist = circle_hist[-110:]
        for leader in self.LEADERS:
            if leader in mids:
                arr = hist.get(leader, [])
                arr.append(mids[leader])
                hist[leader] = arr[-501:]
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = mids[product] + self.SHIFT.get(product, 0.0)
            take = 10**9
            if self.MODE[product] == "static":
                fair = self.M[product] + self.SHIFT.get(product, 0.0)
                take = self.Z[product] * self.SCALE[product]
            elif product == "MICROCHIP_OVAL" and len(circle_hist) > 50:
                fair += 1.25 * 0.067 * (circle_hist[-1] - circle_hist[-51])
                take = 5.5
            elif product == "MICROCHIP_SQUARE" and len(circle_hist) > 100:
                fair += 0.75 * 0.138 * (circle_hist[-1] - circle_hist[-101])
                take = 6.0
            for leader, lag, weight in self.SIG.get(product, ()):
                arr = hist.get(leader, [])
                if len(arr) > lag:
                    fair += weight * (arr[-1] - arr[-1 - lag])
            result[product] = self.trade(product, depth, int(state.position.get(product, 0)), fair, take, self.EDGE[product], self.IMPROVE[product])
        data["c"] = circle_hist
        data["h"] = hist
        return result

    def trade(self, product: str, depth: OrderDepth, pos: int, fair: float, take: float, edge: float, improve: int) -> List[Order]:
        return PebblesStrategy.trade(self, product, depth, pos, fair, take, edge, improve)


class GalaxySoundsStrategy:
    LIMIT = 10
    SIZE = 20
    PRODUCTS = ("GALAXY_SOUNDS_DARK_MATTER", "GALAXY_SOUNDS_BLACK_HOLES", "GALAXY_SOUNDS_PLANETARY_RINGS", "GALAXY_SOUNDS_SOLAR_WINDS", "GALAXY_SOUNDS_SOLAR_FLAMES")
    M = {"GALAXY_SOUNDS_BLACK_HOLES": 11466.872, "GALAXY_SOUNDS_DARK_MATTER": 10226.662, "GALAXY_SOUNDS_PLANETARY_RINGS": 10766.673, "GALAXY_SOUNDS_SOLAR_FLAMES": 11092.572, "GALAXY_SOUNDS_SOLAR_WINDS": 10437.544}
    S = {"GALAXY_SOUNDS_BLACK_HOLES": 958.445, "GALAXY_SOUNDS_DARK_MATTER": 330.701, "GALAXY_SOUNDS_PLANETARY_RINGS": 765.837, "GALAXY_SOUNDS_SOLAR_FLAMES": 450.15, "GALAXY_SOUNDS_SOLAR_WINDS": 541.111}
    MODE = {"GALAXY_SOUNDS_BLACK_HOLES": "mid", "GALAXY_SOUNDS_DARK_MATTER": "static", "GALAXY_SOUNDS_PLANETARY_RINGS": "static", "GALAXY_SOUNDS_SOLAR_FLAMES": "static", "GALAXY_SOUNDS_SOLAR_WINDS": "static"}
    SHIFT = {"GALAXY_SOUNDS_BLACK_HOLES": 2.0, "GALAXY_SOUNDS_DARK_MATTER": 41.338, "GALAXY_SOUNDS_PLANETARY_RINGS": -172.313, "GALAXY_SOUNDS_SOLAR_FLAMES": -33.761}
    Z = {"GALAXY_SOUNDS_BLACK_HOLES": 0.0, "GALAXY_SOUNDS_DARK_MATTER": 0.35, "GALAXY_SOUNDS_PLANETARY_RINGS": 0.8, "GALAXY_SOUNDS_SOLAR_FLAMES": 0.8, "GALAXY_SOUNDS_SOLAR_WINDS": 1.0}
    EDGE = {"GALAXY_SOUNDS_BLACK_HOLES": 1.5, "GALAXY_SOUNDS_DARK_MATTER": 0.0, "GALAXY_SOUNDS_PLANETARY_RINGS": 12.0, "GALAXY_SOUNDS_SOLAR_FLAMES": 2.0, "GALAXY_SOUNDS_SOLAR_WINDS": 2.0}
    IMPROVE = {"GALAXY_SOUNDS_BLACK_HOLES": 4, "GALAXY_SOUNDS_DARK_MATTER": 1, "GALAXY_SOUNDS_PLANETARY_RINGS": 0, "GALAXY_SOUNDS_SOLAR_FLAMES": 0, "GALAXY_SOUNDS_SOLAR_WINDS": 0}
    SIG = {
        "GALAXY_SOUNDS_BLACK_HOLES": (("GALAXY_SOUNDS_PLANETARY_RINGS", 1, 0.1), ("GALAXY_SOUNDS_PLANETARY_RINGS", 10, -0.05)),
        "GALAXY_SOUNDS_DARK_MATTER": (("GALAXY_SOUNDS_BLACK_HOLES", 1, 0.05), ("GALAXY_SOUNDS_BLACK_HOLES", 50, 0.05)),
        "GALAXY_SOUNDS_PLANETARY_RINGS": (("GALAXY_SOUNDS_SOLAR_FLAMES", 500, 0.1), ("GALAXY_SOUNDS_SOLAR_WINDS", 100, -0.1)),
        "GALAXY_SOUNDS_SOLAR_FLAMES": (("GALAXY_SOUNDS_BLACK_HOLES", 500, -1.25), ("GALAXY_SOUNDS_SOLAR_WINDS", 78, 0.15)),
        "GALAXY_SOUNDS_SOLAR_WINDS": (("GALAXY_SOUNDS_BLACK_HOLES", 50, -0.2),),
    }
    LEADERS = ("GALAXY_SOUNDS_BLACK_HOLES", "GALAXY_SOUNDS_PLANETARY_RINGS", "GALAXY_SOUNDS_SOLAR_FLAMES", "GALAXY_SOUNDS_SOLAR_WINDS")

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        hist = data.get("h", {})
        mids = {}
        for p in self.PRODUCTS:
            d = state.order_depths.get(p)
            if d and d.buy_orders and d.sell_orders:
                mids[p] = (max(d.buy_orders) + min(d.sell_orders)) / 2.0
        for p in self.LEADERS:
            if p in mids:
                arr = hist.get(p, [])
                arr.append(mids[p])
                hist[p] = arr[-501:]
        for p in self.PRODUCTS:
            d = state.order_depths.get(p)
            if not d or not d.buy_orders or not d.sell_orders:
                result[p] = []
                continue
            if self.MODE[p] == "mid":
                fair = mids[p] + self.SHIFT.get(p, 0.0)
                take = 10**9
            else:
                fair = self.M[p] + self.SHIFT.get(p, 0.0)
                take = self.Z[p] * self.S[p]
            for leader, lag, k in self.SIG.get(p, ()):
                arr = hist.get(leader, [])
                if len(arr) > lag:
                    fair += k * (arr[-1] - arr[-1 - lag])
            result[p] = self.trade(p, d, int(state.position.get(p, 0)), fair, take, self.EDGE[p], self.IMPROVE[p])
        data["h"] = hist
        return result

    def trade(self, p: str, d: OrderDepth, pos: int, fair: float, take: float, edge: float, improve: int) -> List[Order]:
        bb = max(d.buy_orders)
        ba = min(d.sell_orders)
        buy_cap = max(0, self.LIMIT - pos)
        sell_cap = max(0, self.LIMIT + pos)
        out: List[Order] = []
        if buy_cap > 0 and ba <= fair - take:
            q = min(buy_cap, self.SIZE, -int(d.sell_orders[ba]))
            if q > 0:
                out.append(Order(p, ba, q))
                buy_cap -= q
        if sell_cap > 0 and bb >= fair + take:
            q = min(sell_cap, self.SIZE, int(d.buy_orders[bb]))
            if q > 0:
                out.append(Order(p, bb, -q))
                sell_cap -= q
        if ba - bb > 2 * improve:
            bid, ask = bb + improve, ba - improve
        elif ba - bb > 1:
            bid, ask = bb + 1, ba - 1
        else:
            bid, ask = bb, ba
        if buy_cap > 0 and bid <= fair - edge:
            out.append(Order(p, bid, min(self.SIZE, buy_cap)))
        if sell_cap > 0 and ask >= fair + edge:
            out.append(Order(p, ask, -min(self.SIZE, sell_cap)))
        return out


class SleepingPodsStrategy:
    PODS = ["SLEEP_POD_SUEDE", "SLEEP_POD_LAMB_WOOL", "SLEEP_POD_POLYESTER", "SLEEP_POD_NYLON", "SLEEP_POD_COTTON"]
    M = {"SLEEP_POD_SUEDE": 11397.42, "SLEEP_POD_LAMB_WOOL": 10701.442, "SLEEP_POD_POLYESTER": 11840.561, "SLEEP_POD_NYLON": 9636.473, "SLEEP_POD_COTTON": 11527.614}
    S = {"SLEEP_POD_SUEDE": 899.946, "SLEEP_POD_LAMB_WOOL": 413.169, "SLEEP_POD_POLYESTER": 977.54, "SLEEP_POD_NYLON": 508.729, "SLEEP_POD_COTTON": 887.693}
    SHIFT = {"SLEEP_POD_SUEDE": 697.458, "SLEEP_POD_LAMB_WOOL": 10.329, "SLEEP_POD_POLYESTER": 171.07, "SLEEP_POD_COTTON": 554.808}
    MODE = {"SLEEP_POD_SUEDE": "static", "SLEEP_POD_LAMB_WOOL": "static", "SLEEP_POD_POLYESTER": "static", "SLEEP_POD_NYLON": "mid", "SLEEP_POD_COTTON": "static"}
    Z = {"SLEEP_POD_SUEDE": 0.4, "SLEEP_POD_LAMB_WOOL": 1.25, "SLEEP_POD_POLYESTER": 0.25, "SLEEP_POD_NYLON": 0.0, "SLEEP_POD_COTTON": 1.5}
    EDGE = {"SLEEP_POD_SUEDE": 6.0, "SLEEP_POD_LAMB_WOOL": 2.0, "SLEEP_POD_POLYESTER": 6.0, "SLEEP_POD_NYLON": 1.5, "SLEEP_POD_COTTON": 0.0}
    IMPROVE = {"SLEEP_POD_SUEDE": 0, "SLEEP_POD_LAMB_WOOL": 0, "SLEEP_POD_POLYESTER": 0, "SLEEP_POD_NYLON": 5, "SLEEP_POD_COTTON": 0}
    WALK = {"SLEEP_POD_SUEDE", "SLEEP_POD_COTTON"}
    SIG = {
        "SLEEP_POD_SUEDE": (("SLEEP_POD_LAMB_WOOL", 200, 0.1), ("SLEEP_POD_COTTON", 200, -0.5)),
        "SLEEP_POD_LAMB_WOOL": (("SLEEP_POD_COTTON", 500, -1.0), ("SLEEP_POD_POLYESTER", 50, 1.0)),
        "SLEEP_POD_POLYESTER": (("SLEEP_POD_SUEDE", 200, -0.05), ("SLEEP_POD_NYLON", 1, 1.0)),
        "SLEEP_POD_NYLON": (("SLEEP_POD_COTTON", 100, 1.0), ("SLEEP_POD_SUEDE", 100, -0.5)),
        "SLEEP_POD_COTTON": (("SLEEP_POD_LAMB_WOOL", 500, 0.25),),
    }
    LIMIT = 10
    L = 10
    ORDER_SIZE = 20
    Q = 20

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        hist = data.get("h", {})
        mids = {}
        for product in self.PODS:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
        for product, mid in mids.items():
            series = hist.get(product, [])
            series.append(mid)
            hist[product] = series[-501:]
        for product in self.PODS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            if self.MODE[product] == "static":
                fair = self.M[product] + self.SHIFT.get(product, 0)
                take = self.Z[product] * self.S[product]
            else:
                fair = mids[product] + self.SHIFT.get(product, 0)
                take = 10**9
            for leader, lag, scale in self.SIG.get(product, ()):
                series = hist.get(leader, [])
                if len(series) > lag:
                    fair += scale * (series[-1] - series[-1 - lag])
            result[product] = self.trade(product, depth, int(state.position.get(product, 0)), fair, take, self.EDGE[product], self.IMPROVE[product])
        data["h"] = hist
        return result

    def trade(self, product, depth, pos, fair, take, edge, improve):
        return PebblesStrategy.trade(self, product, depth, pos, fair, take, edge, improve)


class TranslatorStrategy:
    PRODUCTS = ("TRANSLATOR_SPACE_GRAY", "TRANSLATOR_ASTRO_BLACK", "TRANSLATOR_ECLIPSE_CHARCOAL", "TRANSLATOR_GRAPHITE_MIST", "TRANSLATOR_VOID_BLUE")
    MEAN = {"TRANSLATOR_ASTRO_BLACK": 9385.219, "TRANSLATOR_ECLIPSE_CHARCOAL": 9813.742, "TRANSLATOR_GRAPHITE_MIST": 10084.64, "TRANSLATOR_SPACE_GRAY": 9431.902, "TRANSLATOR_VOID_BLUE": 10858.579}
    SHIFT = {"TRANSLATOR_ASTRO_BLACK": -48.975, "TRANSLATOR_ECLIPSE_CHARCOAL": -26.673, "TRANSLATOR_GRAPHITE_MIST": -199.816, "TRANSLATOR_SPACE_GRAY": 263.921, "TRANSLATOR_VOID_BLUE": 376.515}
    STD = {"TRANSLATOR_ASTRO_BLACK": 489.746, "TRANSLATOR_ECLIPSE_CHARCOAL": 355.637, "TRANSLATOR_GRAPHITE_MIST": 499.541, "TRANSLATOR_SPACE_GRAY": 502.706, "TRANSLATOR_VOID_BLUE": 579.254}
    TAKE_Z = {"TRANSLATOR_ASTRO_BLACK": 0.1, "TRANSLATOR_ECLIPSE_CHARCOAL": 0.5, "TRANSLATOR_GRAPHITE_MIST": 0.15, "TRANSLATOR_SPACE_GRAY": 1.1, "TRANSLATOR_VOID_BLUE": 0.15}
    SIGNALS = {
        "TRANSLATOR_ASTRO_BLACK": (("TRANSLATOR_VOID_BLUE", 200, 0.1), ("TRANSLATOR_GRAPHITE_MIST", 200, 0.1)),
        "TRANSLATOR_ECLIPSE_CHARCOAL": (("TRANSLATOR_GRAPHITE_MIST", 100, 0.5), ("TRANSLATOR_SPACE_GRAY", 100, -0.25), ("TRANSLATOR_SPACE_GRAY", 5, 0.2)),
        "TRANSLATOR_GRAPHITE_MIST": (("TRANSLATOR_VOID_BLUE", 500, 0.5), ("TRANSLATOR_ECLIPSE_CHARCOAL", 20, 0.1)),
        "TRANSLATOR_SPACE_GRAY": (("TRANSLATOR_ECLIPSE_CHARCOAL", 500, 0.5), ("TRANSLATOR_GRAPHITE_MIST", 200, -0.25)),
        "TRANSLATOR_VOID_BLUE": (("TRANSLATOR_ECLIPSE_CHARCOAL", 200, -0.1), ("TRANSLATOR_ASTRO_BLACK", 20, -0.1)),
    }
    LIMIT = 10
    MAX_QTY = 20

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        history = data.get("h", {})
        mids = {}
        for product, depth in state.order_depths.items():
            if depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        for product in self.PRODUCTS:
            if product in mids:
                row = history.get(product, [])
                row.append(mids[product])
                history[product] = row[-501:]
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = self.MEAN[product] + self.SHIFT[product]
            for leader, lag, weight in self.SIGNALS[product]:
                row = history.get(leader, [])
                if len(row) > lag:
                    fair += weight * (row[-1] - row[-1 - lag])
            result[product] = self.take(product, depth, int(state.position.get(product, 0)), fair, self.TAKE_Z[product] * self.STD[product])
        data["h"] = history
        return result

    def take(self, product, depth, position, fair, take_edge):
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_cap = max(0, self.LIMIT - position)
        sell_cap = max(0, self.LIMIT + position)
        orders: List[Order] = []
        if buy_cap > 0 and best_ask <= fair - take_edge:
            qty = min(buy_cap, self.MAX_QTY, -int(depth.sell_orders[best_ask]))
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
        if sell_cap > 0 and best_bid >= fair + take_edge:
            qty = min(sell_cap, self.MAX_QTY, int(depth.buy_orders[best_bid]))
            if qty > 0:
                orders.append(Order(product, best_bid, -qty))
        return orders


class UVVisorStrategy:
    PRODUCTS = {"UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"}
    LIMIT = 10
    L = 10
    QUOTE_SIZE = 20
    Q = 20
    WALK = set()
    FAIR = {"UV_VISOR_YELLOW": 10991.551, "UV_VISOR_AMBER": 6864.932, "UV_VISOR_ORANGE": 10275.09, "UV_VISOR_RED": 10784.129, "UV_VISOR_MAGENTA": 11617.975}
    TAKE = {"UV_VISOR_YELLOW": 1.75 * 681.808, "UV_VISOR_AMBER": 0.3 * 996.918, "UV_VISOR_ORANGE": 1.55 * 550.603, "UV_VISOR_RED": 0.1 * 587.715, "UV_VISOR_MAGENTA": 0.35 * 613.554}
    EDGE = {"UV_VISOR_YELLOW": 6.0, "UV_VISOR_AMBER": 15.0, "UV_VISOR_ORANGE": 0.0, "UV_VISOR_RED": 30.0, "UV_VISOR_MAGENTA": 6.0}
    IMPROVE = {"UV_VISOR_YELLOW": 0, "UV_VISOR_AMBER": 1, "UV_VISOR_ORANGE": 0, "UV_VISOR_RED": 1, "UV_VISOR_MAGENTA": 1}
    SIGNALS = {
        "UV_VISOR_YELLOW": (("UV_VISOR_AMBER", 500, 0.15), ("UV_VISOR_RED", 500, -0.05)),
        "UV_VISOR_AMBER": (("UV_VISOR_RED", 500, 0.25), ("UV_VISOR_ORANGE", 100, 0.25)),
        "UV_VISOR_ORANGE": (("UV_VISOR_YELLOW", 200, -0.25),),
        "UV_VISOR_RED": (("UV_VISOR_YELLOW", 50, 0.1), ("UV_VISOR_ORANGE", 1, -0.25)),
        "UV_VISOR_MAGENTA": (("UV_VISOR_AMBER", 500, 1.0), ("UV_VISOR_YELLOW", 20, -0.25)),
    }

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        histories = data.setdefault("h", {})
        mids = {}
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
        for product, mid in mids.items():
            hist = histories.get(product, [])
            hist.append(mid)
            histories[product] = hist[-501:]
        result: Dict[str, List[Order]] = {}
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = self.FAIR[product]
            for leader, lag, weight in self.SIGNALS.get(product, ()):
                hist = histories.get(leader, [])
                if len(hist) > lag:
                    fair += weight * (hist[-1] - hist[-1 - lag])
            result[product] = self.trade(product, depth, int(state.position.get(product, 0)), fair, self.TAKE[product], self.EDGE[product], self.IMPROVE[product])
        return result

    def trade(self, product: str, depth: OrderDepth, position: int, fair: float, take: float, edge: float, improve: int) -> List[Order]:
        return PebblesStrategy.trade(self, product, depth, position, fair, take, edge, improve)


class OxygenShakesStrategy:
    PRODUCTS = ["OXYGEN_SHAKE_MORNING_BREATH", "OXYGEN_SHAKE_EVENING_BREATH", "OXYGEN_SHAKE_MINT", "OXYGEN_SHAKE_CHOCOLATE", "OXYGEN_SHAKE_GARLIC"]
    MEAN = {"OXYGEN_SHAKE_MORNING_BREATH": 10000.453, "OXYGEN_SHAKE_EVENING_BREATH": 9271.895, "OXYGEN_SHAKE_MINT": 9838.394, "OXYGEN_SHAKE_CHOCOLATE": 9556.879, "OXYGEN_SHAKE_GARLIC": 11925.640}
    SHIFT = {"OXYGEN_SHAKE_MORNING_BREATH": -48.960, "OXYGEN_SHAKE_MINT": 38.110, "OXYGEN_SHAKE_GARLIC": -47.667}
    MODE = {"OXYGEN_SHAKE_MORNING_BREATH": "static", "OXYGEN_SHAKE_EVENING_BREATH": "static", "OXYGEN_SHAKE_MINT": "static", "OXYGEN_SHAKE_CHOCOLATE": "mid", "OXYGEN_SHAKE_GARLIC": "static"}
    TAKE = {"OXYGEN_SHAKE_MORNING_BREATH": 1305.610, "OXYGEN_SHAKE_EVENING_BREATH": 219.902, "OXYGEN_SHAKE_MINT": 254.066, "OXYGEN_SHAKE_CHOCOLATE": 10**9, "OXYGEN_SHAKE_GARLIC": 333.672}
    EDGE = {"OXYGEN_SHAKE_MORNING_BREATH": 6.0, "OXYGEN_SHAKE_EVENING_BREATH": 15.0, "OXYGEN_SHAKE_MINT": 2.0, "OXYGEN_SHAKE_CHOCOLATE": 5.0, "OXYGEN_SHAKE_GARLIC": 25.0}
    IMPROVE = {"OXYGEN_SHAKE_MORNING_BREATH": 0, "OXYGEN_SHAKE_EVENING_BREATH": 1, "OXYGEN_SHAKE_MINT": 0, "OXYGEN_SHAKE_CHOCOLATE": 6, "OXYGEN_SHAKE_GARLIC": 5}
    SIGNALS = {
        "OXYGEN_SHAKE_MORNING_BREATH": (("OXYGEN_SHAKE_MINT", 500, 1.0), ("OXYGEN_SHAKE_MINT", 10, -1.0)),
        "OXYGEN_SHAKE_EVENING_BREATH": (("OXYGEN_SHAKE_MORNING_BREATH", 200, 0.5), ("OXYGEN_SHAKE_CHOCOLATE", 5, -0.5)),
        "OXYGEN_SHAKE_MINT": (("OXYGEN_SHAKE_GARLIC", 200, -0.05),),
        "OXYGEN_SHAKE_CHOCOLATE": (("OXYGEN_SHAKE_EVENING_BREATH", 50, -0.1), ("OXYGEN_SHAKE_GARLIC", 2, -0.05)),
        "OXYGEN_SHAKE_GARLIC": (("OXYGEN_SHAKE_MINT", 500, -1.0), ("OXYGEN_SHAKE_MINT", 200, 1.0)),
    }
    WALK = {"OXYGEN_SHAKE_GARLIC"}
    LIMIT = 10
    L = 10
    CLIP = 20
    Q = 20

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        history = data.get("h", {})
        mids = {}
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2
        for product, mid in mids.items():
            series = history.get(product, [])
            series.append(mid)
            history[product] = series[-501:]
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            if self.MODE[product] == "mid":
                fair = mids[product] + self.SHIFT.get(product, 0.0)
                take = 10**9
            else:
                fair = self.MEAN[product] + self.SHIFT.get(product, 0.0)
                take = self.TAKE[product]
            for leader, lag, weight in self.SIGNALS.get(product, ()):
                series = history.get(leader, [])
                if len(series) > lag:
                    fair += weight * (series[-1] - series[-1 - lag])
            result[product] = self.trade(product, depth, int(state.position.get(product, 0)), fair, take)
        data["h"] = history
        return result

    def trade(self, product: str, depth: OrderDepth, position: int, fair: float, take: float) -> List[Order]:
        return PebblesStrategy.trade(self, product, depth, position, fair, take, self.EDGE[product], self.IMPROVE[product])


class PanelStrategy:
    P = ["PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"]
    LIM = 10
    Q = 20
    FAIR = {"PANEL_1X2": 8982.0, "PANEL_2X2": 9593.0, "PANEL_1X4": 9523.0, "PANEL_2X4": 11312.0, "PANEL_4X4": 9879.0}
    TAKE = {"PANEL_1X2": 560.0, "PANEL_2X2": 1215.0, "PANEL_1X4": 1501.0, "PANEL_2X4": 470.0, "PANEL_4X4": 571.0}
    EDGE = {"PANEL_1X2": 2.0, "PANEL_2X2": 6.0, "PANEL_1X4": 2.0, "PANEL_2X4": 6.0, "PANEL_4X4": 2.0}
    SIG = {
        "PANEL_1X2": (("PANEL_2X2", 200, -1.0),),
        "PANEL_2X2": (("PANEL_1X2", 50, 0.5),),
        "PANEL_1X4": (("PANEL_1X2", 500, 1.0), ("PANEL_4X4", 200, 0.25)),
        "PANEL_2X4": (("PANEL_1X4", 500, -0.1), ("PANEL_1X4", 100, 0.5), ("PANEL_1X2", 200, 0.2)),
        "PANEL_4X4": (("PANEL_2X2", 100, -1.0), ("PANEL_2X4", 500, 0.25)),
    }

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        hist = data.get("h", {})
        for product in self.P:
            depth = state.order_depths.get(product)
            if depth and depth.buy_orders and depth.sell_orders:
                mid = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
                series = hist.get(product, [])
                series.append(mid)
                hist[product] = series[-501:]
        for product in self.P:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = self.FAIR[product]
            for leader, lag, weight in self.SIG.get(product, ()):
                series = hist.get(leader, [])
                if len(series) > lag:
                    fair += weight * (series[-1] - series[-1 - lag])
            result[product] = self.trade(product, depth, int(state.position.get(product, 0)), fair, self.TAKE[product], self.EDGE[product])
        data["h"] = hist
        return result

    def trade(self, product: str, depth, position: int, fair: float, take: float, edge: float) -> List[Order]:
        orders: List[Order] = []
        buy_cap = max(0, self.LIM - position)
        sell_cap = max(0, self.LIM + position)
        for price in sorted(depth.sell_orders):
            if buy_cap <= 0 or price > fair - take:
                break
            qty = min(buy_cap, self.Q, -int(depth.sell_orders[price]))
            if qty > 0:
                orders.append(Order(product, price, qty))
                buy_cap -= qty
        for price in sorted(depth.buy_orders, reverse=True):
            if sell_cap <= 0 or price < fair + take:
                break
            qty = min(sell_cap, self.Q, int(depth.buy_orders[price]))
            if qty > 0:
                orders.append(Order(product, price, -qty))
                sell_cap -= qty
        bid = max(depth.buy_orders)
        ask = min(depth.sell_orders)
        if buy_cap > 0 and bid <= fair - edge:
            orders.append(Order(product, bid, min(self.Q, buy_cap)))
        if sell_cap > 0 and ask >= fair + edge:
            orders.append(Order(product, ask, -min(self.Q, sell_cap)))
        return orders


class SnackpackStrategy:
    P = ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "SNACKPACK_PISTACHIO", "SNACKPACK_STRAWBERRY", "SNACKPACK_RASPBERRY")
    M = {"SNACKPACK_CHOCOLATE": 9843.372, "SNACKPACK_VANILLA": 10097.302, "SNACKPACK_PISTACHIO": 9495.844, "SNACKPACK_STRAWBERRY": 10706.609, "SNACKPACK_RASPBERRY": 10077.812}
    SHIFT = {"SNACKPACK_CHOCOLATE": 115.421, "SNACKPACK_VANILLA": -22.314, "SNACKPACK_STRAWBERRY": 163.608}
    S = {"SNACKPACK_CHOCOLATE": 200.733, "SNACKPACK_VANILLA": 178.515, "SNACKPACK_PISTACHIO": 187.495, "SNACKPACK_STRAWBERRY": 363.573, "SNACKPACK_RASPBERRY": 169.814}
    Z = {"SNACKPACK_CHOCOLATE": 0.50, "SNACKPACK_VANILLA": 0.65, "SNACKPACK_PISTACHIO": 0.25, "SNACKPACK_STRAWBERRY": 0.20, "SNACKPACK_RASPBERRY": 1.15}
    EDGE = {"SNACKPACK_CHOCOLATE": 8.0, "SNACKPACK_VANILLA": 8.0, "SNACKPACK_PISTACHIO": 30.0, "SNACKPACK_STRAWBERRY": 36.0, "SNACKPACK_RASPBERRY": 1.0}
    IMP = {"SNACKPACK_CHOCOLATE": 0, "SNACKPACK_VANILLA": 0, "SNACKPACK_PISTACHIO": 1, "SNACKPACK_STRAWBERRY": 4, "SNACKPACK_RASPBERRY": 0}
    SIG = {
        "SNACKPACK_CHOCOLATE": (("SNACKPACK_STRAWBERRY", 50, 0.25), ("SNACKPACK_PISTACHIO", 100, -0.05)),
        "SNACKPACK_VANILLA": (("SNACKPACK_CHOCOLATE", 100, -0.05), ("SNACKPACK_CHOCOLATE", 2, -0.25)),
        "SNACKPACK_PISTACHIO": (("SNACKPACK_RASPBERRY", 20, -0.10), ("SNACKPACK_RASPBERRY", 500, 0.05)),
        "SNACKPACK_STRAWBERRY": (("SNACKPACK_CHOCOLATE", 100, 1.0), ("SNACKPACK_PISTACHIO", 10, -0.50)),
        "SNACKPACK_RASPBERRY": (("SNACKPACK_PISTACHIO", 50, -0.25), ("SNACKPACK_PISTACHIO", 200, -0.10)),
    }
    L = 10
    Q = 20

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        hist = data.get("h", {})
        mids = {}
        for product, depth in state.order_depths.items():
            if product in self.P and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        for product in self.P:
            if product in mids:
                values = hist.get(product, [])
                values.append(mids[product])
                hist[product] = values[-501:]
        for product in self.P:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = self.M[product] + self.SHIFT.get(product, 0.0)
            for leader, lag, weight in self.SIG.get(product, ()):
                values = hist.get(leader, [])
                if len(values) > lag:
                    fair += weight * (values[-1] - values[-1 - lag])
            result[product] = self.trade(product, depth, int(state.position.get(product, 0)), fair, self.Z[product] * self.S[product], self.EDGE[product], self.IMP[product])
        data["h"] = hist
        return result

    def trade(self, product: str, depth: OrderDepth, position: int, fair: float, take_edge: float, quote_edge: float, improve: int) -> List[Order]:
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


class RoboticsStrategy:
    F = {"ROBOT_DISHES": 9962.651, "ROBOT_IRONING": 8450.985, "ROBOT_LAUNDRY": 9930.268, "ROBOT_MOPPING": 11157.750, "ROBOT_VACUUMING": 9153.395}
    TAKE = {"ROBOT_DISHES": 194.824, "ROBOT_IRONING": 963.788, "ROBOT_LAUNDRY": 767.903, "ROBOT_MOPPING": 1150.742, "ROBOT_VACUUMING": 909.940}
    EDGE = {"ROBOT_DISHES": 1.0, "ROBOT_IRONING": 0.0, "ROBOT_LAUNDRY": 2.0, "ROBOT_MOPPING": 8.0, "ROBOT_VACUUMING": 6.0}
    SIG = {
        "ROBOT_DISHES": (("ROBOT_IRONING", 200, -0.5), ("ROBOT_IRONING", 200, -0.05)),
        "ROBOT_IRONING": (("ROBOT_MOPPING", 20, -0.25), ("ROBOT_VACUUMING", 2, -0.25)),
        "ROBOT_LAUNDRY": (("ROBOT_MOPPING", 500, 1.0), ("ROBOT_VACUUMING", 500, 1.0)),
        "ROBOT_MOPPING": (("ROBOT_DISHES", 500, -0.05), ("ROBOT_VACUUMING", 20, -0.1)),
        "ROBOT_VACUUMING": (("ROBOT_MOPPING", 100, 0.05), ("ROBOT_LAUNDRY", 200, -0.25)),
    }
    WALK = {"ROBOT_DISHES", "ROBOT_LAUNDRY"}
    PRODUCTS = set(F)
    L = 10
    Q = 20

    def orders(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        hist = data.get("h", {})
        mids = {}
        for product, depth in state.order_depths.items():
            if depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
        for product in self.PRODUCTS:
            if product in mids:
                values = hist.get(product, [])
                values.append(mids[product])
                hist[product] = values[-501:]
        for product in self.PRODUCTS:
            depth = state.order_depths.get(product)
            if not depth or not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue
            fair = self.F[product]
            for leader, lag, coeff in self.SIG.get(product, ()):
                values = hist.get(leader, [])
                if len(values) > lag:
                    fair += coeff * (values[-1] - values[-1 - lag])
            result[product] = self.trade(product, depth, int(state.position.get(product, 0)), fair, self.TAKE[product], self.EDGE[product])
        data["h"] = hist
        return result

    def trade(self, product: str, depth: OrderDepth, position: int, fair: float, take_edge: float, quote_edge: float) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        buy_capacity = max(0, self.L - position)
        sell_capacity = max(0, self.L + position)
        orders: List[Order] = []
        if product in self.WALK and buy_capacity > 0:
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
        if product in self.WALK and sell_capacity > 0:
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


class Trader:
    def __init__(self):
        self.strategies = (
            ("pebbles", PebblesStrategy()),
            ("microchips", MicrochipStrategy()),
            ("galaxy_sounds", GalaxySoundsStrategy()),
            ("sleeping_pods", SleepingPodsStrategy()),
            ("translators", TranslatorStrategy()),
            ("uv_visors", UVVisorStrategy()),
            ("oxygen_shakes", OxygenShakesStrategy()),
            ("panels", PanelStrategy()),
            ("snackpacks", SnackpackStrategy()),
            ("robotics", RoboticsStrategy()),
        )

    def run(self, state: TradingState):
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}

        result: Dict[str, List[Order]] = {}
        for key, strategy in self.strategies:
            subdata = data.setdefault(key, {})
            category_orders = strategy.orders(state, subdata)
            for product, orders in category_orders.items():
                position = int(state.position.get(product, 0))
                result[product] = clip_orders(product, orders, position)

        return result, 0, json.dumps(data, separators=(",", ":"))
