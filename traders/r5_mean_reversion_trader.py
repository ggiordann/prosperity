from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


LIMIT = 10
SIZE = 8
MIN_OBS = 80
ROUND5_PREFIXES = (
    "GALAXY_SOUNDS_",
    "MICROCHIP_",
    "OXYGEN_SHAKE_",
    "PANEL_",
    "PEBBLES_",
    "ROBOT_",
    "SLEEP_POD_",
    "SNACKPACK_",
    "TRANSLATOR_",
    "UV_VISOR_",
)
GROUPS = {
    "pebbles": ("PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"),
    "microchips": ("MICROCHIP_CIRCLE", "MICROCHIP_OVAL", "MICROCHIP_SQUARE", "MICROCHIP_RECTANGLE", "MICROCHIP_TRIANGLE"),
    "galaxy": ("GALAXY_SOUNDS_DARK_MATTER", "GALAXY_SOUNDS_BLACK_HOLES", "GALAXY_SOUNDS_PLANETARY_RINGS", "GALAXY_SOUNDS_SOLAR_WINDS", "GALAXY_SOUNDS_SOLAR_FLAMES"),
    "sleeping": ("SLEEP_POD_SUEDE", "SLEEP_POD_LAMB_WOOL", "SLEEP_POD_POLYESTER", "SLEEP_POD_NYLON", "SLEEP_POD_COTTON"),
    "translators": ("TRANSLATOR_SPACE_GRAY", "TRANSLATOR_ASTRO_BLACK", "TRANSLATOR_ECLIPSE_CHARCOAL", "TRANSLATOR_GRAPHITE_MIST", "TRANSLATOR_VOID_BLUE"),
    "uv": ("UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"),
    "oxygen": ("OXYGEN_SHAKE_MORNING_BREATH", "OXYGEN_SHAKE_EVENING_BREATH", "OXYGEN_SHAKE_MINT", "OXYGEN_SHAKE_CHOCOLATE", "OXYGEN_SHAKE_GARLIC"),
    "panels": ("PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"),
    "snackpacks": ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "SNACKPACK_PISTACHIO", "SNACKPACK_STRAWBERRY", "SNACKPACK_RASPBERRY"),
    "robotics": ("ROBOT_VACUUMING", "ROBOT_MOPPING", "ROBOT_DISHES", "ROBOT_LAUNDRY", "ROBOT_IRONING"),
}
PRODUCT_GROUP = {p: g for g, ps in GROUPS.items() for p in ps}
ALL_R5 = tuple(PRODUCT_GROUP)

# Config supports self, category-residual, and cross-residual fair values. The
# accepted live config is intentionally self-only after residual candidates failed
# product-level backtests or relied on unstable basket betas.
CONFIG = {
    "PEBBLES_XL": ("self", "sma", 288, 0.0, 1.75, 0.45, 1000.0),
}


def median(xs: List[float]) -> float:
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    if n % 2:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def stdev(xs: List[float]) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    avg = sum(xs) / n
    return (sum((x - avg) * (x - avg) for x in xs) / (n - 1)) ** 0.5


def clip(product: str, orders: List[Order], pos: int) -> List[Order]:
    buy_left = max(0, LIMIT - pos)
    sell_left = max(0, LIMIT + pos)
    out: List[Order] = []
    for order in orders:
        qty = int(order.quantity)
        if qty > 0 and buy_left > 0:
            qty = min(qty, buy_left)
            out.append(Order(product, int(order.price), qty))
            buy_left -= qty
        elif qty < 0 and sell_left > 0:
            qty = min(-qty, sell_left)
            out.append(Order(product, int(order.price), -qty))
            sell_left -= qty
    return out


class Trader:
    def run(self, state: TradingState):
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        anchors = data.get("a", {})
        residuals = data.get("r", {})

        mids: Dict[str, float] = {}
        result: Dict[str, List[Order]] = {}
        for product, depth in state.order_depths.items():
            if product.startswith(ROUND5_PREFIXES) and depth.buy_orders and depth.sell_orders:
                mids[product] = (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0
                anchors.setdefault(product, mids[product])
            result[product] = []

        bps = {
            p: 10000.0 * (mids[p] / float(anchors[p]) - 1.0)
            for p in mids
            if p in anchors and anchors[p]
        }

        for product, cfg in CONFIG.items():
            depth = state.order_depths.get(product)
            if product not in mids or not depth or not depth.buy_orders or not depth.sell_orders:
                continue
            kind, method, window, beta, enter_z, margin, max_vol = cfg
            basket = self.index_bps(product, kind, bps)
            if basket is None:
                continue

            anchor = float(anchors[product])
            synthetic = anchor * (1.0 + beta * basket / 10000.0)
            residual = mids[product] - synthetic
            hist = list(residuals.get(product, []))
            orders: List[Order] = []
            if len(hist) >= MIN_OBS:
                lookback = hist[-window:]
                fair_residual = self.fair_residual(lookback, method)
                vol = stdev(lookback)
                if 1.0 <= vol <= max_vol:
                    fair = synthetic + fair_residual
                    orders = self.trade(product, depth, int(state.position.get(product, 0)), fair, vol, enter_z, margin)
            hist.append(residual)
            residuals[product] = hist[-(window + 5):]
            result[product] = clip(product, orders, int(state.position.get(product, 0)))

        return result, 0, json.dumps({"a": anchors, "r": residuals}, separators=(",", ":"))

    def index_bps(self, product: str, kind: str, bps: Dict[str, float]):
        if kind == "self":
            return 0.0
        group = PRODUCT_GROUP.get(product)
        values: List[float] = []
        for other in ALL_R5:
            if other == product or other not in bps:
                continue
            same_group = PRODUCT_GROUP.get(other) == group
            if (kind == "category" and same_group) or (kind == "cross" and not same_group):
                values.append(float(bps[other]))
        if not values:
            return None
        return sum(values) / len(values)

    def fair_residual(self, xs: List[float], method: str) -> float:
        if method == "sma":
            return sum(xs) / len(xs)
        if method == "ema":
            alpha = 2.0 / (len(xs) + 1.0)
            value = xs[0]
            for x in xs[1:]:
                value = alpha * x + (1.0 - alpha) * value
            return value
        return median(xs)

    def trade(self, product: str, depth: OrderDepth, pos: int, fair: float, vol: float, enter_z: float, margin: float) -> List[Order]:
        best_bid = max(depth.buy_orders)
        best_ask = min(depth.sell_orders)
        spread = best_ask - best_bid
        mid = 0.5 * (best_bid + best_ask)
        fair -= pos * min(6.0, 0.08 * vol)
        z = (mid - fair) / vol
        edge = abs(mid - fair) - 0.5 * spread
        buy_left = max(0, LIMIT - pos)
        sell_left = max(0, LIMIT + pos)
        orders: List[Order] = []

        if abs(z) < 0.35:
            if pos > 0 and sell_left > 0:
                orders.append(Order(product, best_bid, -min(SIZE, pos, int(depth.buy_orders[best_bid]))))
            elif pos < 0 and buy_left > 0:
                orders.append(Order(product, best_ask, min(SIZE, -pos, -int(depth.sell_orders[best_ask]))))
            return orders
        if abs(z) < enter_z or edge <= margin:
            return orders

        if z < -enter_z and buy_left > 0:
            if best_ask <= fair - margin:
                qty = min(SIZE, buy_left, -int(depth.sell_orders[best_ask]))
                if qty > 0:
                    orders.append(Order(product, best_ask, qty))
                    buy_left -= qty
            quote = min(best_bid + 1, int(fair - margin))
            if buy_left > 0 and quote < best_ask:
                orders.append(Order(product, quote, min(SIZE, buy_left)))
        elif z > enter_z and sell_left > 0:
            if best_bid >= fair + margin:
                qty = min(SIZE, sell_left, int(depth.buy_orders[best_bid]))
                if qty > 0:
                    orders.append(Order(product, best_bid, -qty))
                    sell_left -= qty
            quote = max(best_ask - 1, int(fair + margin))
            if sell_left > 0 and quote > best_bid:
                orders.append(Order(product, quote, -min(SIZE, sell_left)))
        return orders
