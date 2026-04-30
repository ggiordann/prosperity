from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List
import json


class GalaxySoundsStrategy:
    LIMIT = 10
    SIZE = 20
    PRODUCTS = (
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    )
    M = {
        "GALAXY_SOUNDS_BLACK_HOLES": 11466.872,
        "GALAXY_SOUNDS_DARK_MATTER": 10226.662,
        "GALAXY_SOUNDS_PLANETARY_RINGS": 10766.673,
        "GALAXY_SOUNDS_SOLAR_FLAMES": 11092.572,
        "GALAXY_SOUNDS_SOLAR_WINDS": 10437.544,
    }
    S = {
        "GALAXY_SOUNDS_BLACK_HOLES": 958.445,
        "GALAXY_SOUNDS_DARK_MATTER": 330.701,
        "GALAXY_SOUNDS_PLANETARY_RINGS": 765.837,
        "GALAXY_SOUNDS_SOLAR_FLAMES": 450.15,
        "GALAXY_SOUNDS_SOLAR_WINDS": 541.111,
    }
    MODE = {
        "GALAXY_SOUNDS_BLACK_HOLES": "mid",
        "GALAXY_SOUNDS_DARK_MATTER": "static",
        "GALAXY_SOUNDS_PLANETARY_RINGS": "static",
        "GALAXY_SOUNDS_SOLAR_FLAMES": "static",
        "GALAXY_SOUNDS_SOLAR_WINDS": "static",
    }
    SHIFT = {
        "GALAXY_SOUNDS_BLACK_HOLES": 2.0,
        "GALAXY_SOUNDS_DARK_MATTER": 41.338,
        "GALAXY_SOUNDS_PLANETARY_RINGS": -172.313,
        "GALAXY_SOUNDS_SOLAR_FLAMES": -33.761,
    }
    Z = {
        "GALAXY_SOUNDS_BLACK_HOLES": 0.0,
        "GALAXY_SOUNDS_DARK_MATTER": 0.35,
        "GALAXY_SOUNDS_PLANETARY_RINGS": 0.8,
        "GALAXY_SOUNDS_SOLAR_FLAMES": 0.8,
        "GALAXY_SOUNDS_SOLAR_WINDS": 1.0,
    }
    EDGE = {
        "GALAXY_SOUNDS_BLACK_HOLES": 1.5,
        "GALAXY_SOUNDS_DARK_MATTER": 0.0,
        "GALAXY_SOUNDS_PLANETARY_RINGS": 12.0,
        "GALAXY_SOUNDS_SOLAR_FLAMES": 2.0,
        "GALAXY_SOUNDS_SOLAR_WINDS": 2.0,
    }
    IMPROVE = {
        "GALAXY_SOUNDS_BLACK_HOLES": 4,
        "GALAXY_SOUNDS_DARK_MATTER": 1,
        "GALAXY_SOUNDS_PLANETARY_RINGS": 0,
        "GALAXY_SOUNDS_SOLAR_FLAMES": 0,
        "GALAXY_SOUNDS_SOLAR_WINDS": 0,
    }
    SIG = {
        "GALAXY_SOUNDS_BLACK_HOLES": (
            ("GALAXY_SOUNDS_PLANETARY_RINGS", 1, 0.1),
            ("GALAXY_SOUNDS_PLANETARY_RINGS", 10, -0.05),
        ),
        "GALAXY_SOUNDS_DARK_MATTER": (
            ("GALAXY_SOUNDS_BLACK_HOLES", 1, 0.05),
            ("GALAXY_SOUNDS_BLACK_HOLES", 50, 0.05),
        ),
        "GALAXY_SOUNDS_PLANETARY_RINGS": (
            ("GALAXY_SOUNDS_SOLAR_FLAMES", 500, 0.1),
            ("GALAXY_SOUNDS_SOLAR_WINDS", 100, -0.1),
        ),
        "GALAXY_SOUNDS_SOLAR_FLAMES": (
            ("GALAXY_SOUNDS_BLACK_HOLES", 500, -1.25),
            ("GALAXY_SOUNDS_SOLAR_WINDS", 78, 0.15),
        ),
        "GALAXY_SOUNDS_SOLAR_WINDS": (("GALAXY_SOUNDS_BLACK_HOLES", 50, -0.2),),
    }
    LEADERS = (
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
        "GALAXY_SOUNDS_SOLAR_WINDS",
    )

    def run(self, state: TradingState, data: dict) -> Dict[str, List[Order]]:
        result: Dict[str, List[Order]] = {}
        hist = data.get("galaxy_h", {})
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
            pos = int(state.position.get(p, 0))
            result[p] = self.trade(p, d, pos, fair, take, self.EDGE[p], self.IMPROVE[p])

        data["galaxy_h"] = hist
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


class Trader:
    def __init__(self):
        self.galaxy = GalaxySoundsStrategy()

    def run(self, state: TradingState):
        try:
            data = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            data = {}
        result = self.galaxy.run(state, data)
        return result, 0, json.dumps(data, separators=(",", ":"))
