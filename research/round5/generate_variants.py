from __future__ import annotations

import itertools
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_RUN = ROOT / "prosperity_rust_backtester" / "runs" / "r5_baseline_full"
OUT = ROOT / "research" / "round5" / "generated_traders"


ALL_PRODUCTS = [
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
]

PEBBLES = ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"]


TEMPLATE = r'''from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


class Trader:
    LIMIT = 10
    MM_PRODUCTS = set(__MM_PRODUCTS__)
    QUOTE_SIZE = __QUOTE_SIZE__
    IMPROVE = __IMPROVE__
    MIN_EDGE = __MIN_EDGE__
    INV_SKEW = __INV_SKEW__
    USE_PEBBLES = __USE_PEBBLES__
    PEBBLE_CONST = __PEBBLE_CONST__
    PEBBLE_TAKE_EDGE = __PEBBLE_TAKE_EDGE__
    PEBBLE_MM_EDGE = __PEBBLE_MM_EDGE__
    USE_MICRO_LAG = __USE_MICRO_LAG__
    MICRO_TAKE_EDGE = __MICRO_TAKE_EDGE__
    MICRO_BIAS_MULT = __MICRO_BIAS_MULT__
    MAX_HIST = 110
    PEBBLES = __PEBBLES__

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
'''


def baseline_table() -> dict[str, list[float]]:
    out = {p: [] for p in ALL_PRODUCTS}
    for path in sorted(BASE_RUN.glob("round5-day+*-metrics.json")):
        data = json.loads(path.read_text())
        for p in ALL_PRODUCTS:
            out[p].append(float(data["final_pnl_by_product"].get(p, 0.0)))
    return out


def render(path: Path, *, products: list[str], quote_size: int = 5, improve: int = 1, min_edge: float = 0.0,
           inv_skew: float = 0.0, use_pebbles: bool = False, pebble_take_edge: float = 10**9,
           pebble_mm_edge: float = 0.0, use_micro_lag: bool = False, micro_take_edge: float = 10**9,
           micro_bias_mult: float = 1.0, pebble_const: float = 50000.0) -> None:
    text = TEMPLATE
    replacements = {
        "__MM_PRODUCTS__": repr(products),
        "__QUOTE_SIZE__": repr(quote_size),
        "__IMPROVE__": repr(improve),
        "__MIN_EDGE__": repr(min_edge),
        "__INV_SKEW__": repr(inv_skew),
        "__USE_PEBBLES__": repr(use_pebbles),
        "__PEBBLE_CONST__": repr(pebble_const),
        "__PEBBLE_TAKE_EDGE__": repr(pebble_take_edge),
        "__PEBBLE_MM_EDGE__": repr(pebble_mm_edge),
        "__USE_MICRO_LAG__": repr(use_micro_lag),
        "__MICRO_TAKE_EDGE__": repr(micro_take_edge),
        "__MICRO_BIAS_MULT__": repr(micro_bias_mult),
        "__PEBBLES__": repr(PEBBLES),
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pnl = baseline_table()
    total_pos = [p for p, xs in pnl.items() if sum(xs) > 0]
    pos_2day = [p for p, xs in pnl.items() if sum(x > 0 for x in xs) >= 2 and sum(xs) > 0]
    pos_all = [p for p, xs in pnl.items() if all(x > 0 for x in xs)]
    drop_obvious = [
        p for p, xs in pnl.items()
        if all(x < 0 for x in xs) or (sum(x > 0 for x in xs) <= 1 and sum(xs) < -3000)
    ]
    robust = [p for p in ALL_PRODUCTS if p not in drop_obvious]
    specs = []
    subsets = {
        "all": ALL_PRODUCTS,
        "totalpos": total_pos,
        "pos2day": pos_2day,
        "posall": pos_all,
        "robust": robust,
    }
    for subset_name, products in subsets.items():
        for q, imp, skew, edge in itertools.product([3, 5, 8, 10], [1, 2], [0.0, 0.4], [0.0, 1.0]):
            specs.append((f"mm_{subset_name}_q{q}_i{imp}_s{str(skew).replace('.','p')}_e{str(edge).replace('.','p')}", dict(products=products, quote_size=q, improve=imp, inv_skew=skew, min_edge=edge)))
    for products_name, products in [("all", ALL_PRODUCTS), ("robust", robust), ("totalpos", total_pos)]:
        for edge, mm_edge in itertools.product([2.0, 4.0, 6.0, 8.0, 12.0], [0.0, 1.0, 2.0]):
            specs.append((f"peb_{products_name}_te{str(edge).replace('.','p')}_me{str(mm_edge).replace('.','p')}", dict(products=products, quote_size=5, improve=1, use_pebbles=True, pebble_take_edge=edge, pebble_mm_edge=mm_edge)))
        for mult, take in itertools.product([1.0, 2.0, 3.0, 5.0], [2.0, 4.0, 6.0]):
            specs.append((f"micro_{products_name}_m{str(mult).replace('.','p')}_t{str(take).replace('.','p')}", dict(products=products, quote_size=5, improve=1, use_micro_lag=True, micro_bias_mult=mult, micro_take_edge=take)))
        specs.append((f"combo_{products_name}", dict(products=products, quote_size=5, improve=1, use_pebbles=True, pebble_take_edge=6.0, pebble_mm_edge=1.0, use_micro_lag=True, micro_bias_mult=3.0, micro_take_edge=4.0)))

    manifest = []
    for name, kwargs in specs:
        path = OUT / f"{name}.py"
        render(path, **kwargs)
        manifest.append({"name": name, "path": str(path.relative_to(ROOT)), **{k: v for k, v in kwargs.items() if k != "products"}, "n_products": len(kwargs["products"])})
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {len(manifest)} variants to {OUT}")


if __name__ == "__main__":
    main()
