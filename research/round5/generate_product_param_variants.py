from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "round5" / "generated_traders_product_params"

PRODUCTS = [
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

TEMPLATE = r'''from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json

class Trader:
    LIMIT = 10
    Q = 20
    P = "__PRODUCT__"
    IMP = __IMP__
    EDGE = __EDGE__
    MICRO = __MICRO__

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        hist = data.get("c", [])
        mids = {}
        for p, d in state.order_depths.items():
            if d.buy_orders and d.sell_orders:
                mids[p] = (max(d.buy_orders) + min(d.sell_orders)) / 2.0
        if "MICROCHIP_CIRCLE" in mids:
            hist.append(mids["MICROCHIP_CIRCLE"])
            hist = hist[-110:]
        for p, d in state.order_depths.items():
            if p != self.P or not d.buy_orders or not d.sell_orders:
                result[p] = []
                continue
            fair = mids[p]
            take = 10**9
            edge = self.EDGE
            if self.MICRO and p == "MICROCHIP_OVAL" and len(hist) > 50:
                fair += __OVAL_M__ * 0.067 * (hist[-1] - hist[-51])
                take = __OVAL_T__
                edge = __OVAL_E__
            elif self.MICRO and p == "MICROCHIP_SQUARE" and len(hist) > 100:
                fair += __SQUARE_M__ * 0.138 * (hist[-1] - hist[-101])
                take = __SQUARE_T__
                edge = __SQUARE_E__
            result[p] = self.trade(p, d, int(state.position.get(p, 0)), fair, take, edge)
        return result, 0, json.dumps({"c": hist}, separators=(",", ":"))

    def trade(self, p: str, d: OrderDepth, pos: int, fair: float, take: float, edge: float) -> List[Order]:
        bb = max(d.buy_orders)
        ba = min(d.sell_orders)
        bc = max(0, self.LIMIT - pos)
        sc = max(0, self.LIMIT + pos)
        out: List[Order] = []
        if bc > 0 and ba <= fair - take:
            q = min(bc, self.Q, -int(d.sell_orders[ba]))
            if q > 0:
                out.append(Order(p, ba, q))
                bc -= q
        if sc > 0 and bb >= fair + take:
            q = min(sc, self.Q, int(d.buy_orders[bb]))
            if q > 0:
                out.append(Order(p, bb, -q))
                sc -= q
        if bb >= ba:
            return out
        if self.IMP <= 0:
            bid, ask = bb, ba
        elif ba - bb > 2 * self.IMP:
            bid, ask = bb + self.IMP, ba - self.IMP
        elif ba - bb > 1:
            bid, ask = bb + 1, ba - 1
        else:
            bid, ask = bb, ba
        if bc > 0 and bid <= fair - edge:
            out.append(Order(p, bid, min(self.Q, bc)))
        if sc > 0 and ask >= fair + edge:
            out.append(Order(p, ask, -min(self.Q, sc)))
        return out
'''


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    specs = []
    for product in PRODUCTS:
        if product in ("MICROCHIP_OVAL", "MICROCHIP_SQUARE"):
            settings = []
            for imp in [0, 1, 2]:
                for edge in [0.0, 0.5, 1.0, 2.0]:
                    settings.append((imp, edge, True))
        else:
            settings = []
            for imp in [0, 1, 2, 3]:
                for edge in [0.0, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0]:
                    settings.append((imp, edge, False))
        for imp, edge, micro in settings:
            safe = product.replace("_", "")
            name = f"pp_{safe}_i{imp}_e{str(edge).replace('.','p')}{'_micro' if micro else ''}"
            text = TEMPLATE
            reps = {
                "__PRODUCT__": product,
                "__IMP__": repr(imp),
                "__EDGE__": repr(edge),
                "__MICRO__": repr(micro),
                "__OVAL_M__": "1.25",
                "__OVAL_T__": "5.5",
                "__OVAL_E__": "1.0",
                "__SQUARE_M__": "0.75",
                "__SQUARE_T__": "6.0",
                "__SQUARE_E__": "0.5",
            }
            for k, v in reps.items():
                text = text.replace(k, v)
            path = OUT / f"{name}.py"
            path.write_text(text)
            specs.append({"name": name, "path": str(path.relative_to(ROOT)), "product": product, "improve": imp, "edge": edge, "micro": micro})
    manifest = OUT / "manifest.json"
    manifest.write_text(json.dumps(specs, indent=2))
    print(f"wrote {len(specs)} variants")


if __name__ == "__main__":
    main()
