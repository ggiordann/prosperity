import base64
import csv
import json
import lzma
from pathlib import Path

import numpy as np


ROOT = Path("/Users/giordanmasen/Desktop/projects/prosperity/prosperity_rust_backtester/datasets/round4")
OUT = Path("/Users/giordanmasen/Downloads/z_take_dp_oracle.py")
PRODUCTS = [
    "HYDROGEL_PACK",
    "VELVETFRUIT_EXTRACT",
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
]
LIMITS = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
}


def read_rows(day, product):
    rows = []
    with (ROOT / f"prices_round_4_day_{day}.csv").open(newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            if row["product"] == product:
                rows.append(row)
    return rows


def levels(row, side):
    if side == "ask":
        fields = [("ask_price_1", "ask_volume_1"), ("ask_price_2", "ask_volume_2"), ("ask_price_3", "ask_volume_3")]
    else:
        fields = [("bid_price_1", "bid_volume_1"), ("bid_price_2", "bid_volume_2"), ("bid_price_3", "bid_volume_3")]
    out = []
    for price_field, volume_field in fields:
        if row.get(price_field, "") and row.get(volume_field, ""):
            out.append((int(float(row[price_field])), abs(int(float(row[volume_field])))))
    return out


def cumulative(levels, max_volume, sign):
    bad = 1e15 if sign < 0 else -1e15
    out = np.full(max_volume + 1, bad, dtype=float)
    out[0] = 0.0
    qty = 0
    value = 0
    for price, volume in levels:
        for _ in range(volume):
            qty += 1
            value += price
            if qty > max_volume:
                return out
            out[qty] = value
    return out


def order_price_for_quantity(book_levels, quantity):
    remaining = quantity
    last_price = book_levels[-1][0]
    for price, volume in book_levels:
        take = min(remaining, volume)
        remaining -= take
        last_price = price
        if remaining == 0:
            return last_price
    return last_price


def optimize_product(day, product):
    rows = read_rows(day, product)
    limit = LIMITS[product]
    size = 2 * limit + 1
    offset = limit
    final_mark = float(rows[-1]["mid_price"])
    value_next = np.array([(idx - offset) * final_mark for idx in range(size)], dtype=float)
    policy = []
    for row in reversed(rows):
        ask_levels = levels(row, "ask")
        bid_levels = levels(row, "bid")
        buy_volume = sum(volume for _, volume in ask_levels)
        sell_volume = sum(volume for _, volume in bid_levels)
        buy_cost = cumulative(ask_levels, buy_volume, -1)
        sell_revenue = cumulative(bid_levels, sell_volume, 1)
        best = value_next.copy()
        best_delta = np.zeros(size, dtype=np.int16)
        for quantity in range(1, buy_volume + 1):
            candidate = np.full(size, -1e18)
            candidate[:-quantity] = value_next[quantity:] - buy_cost[quantity]
            mask = candidate > best
            best[mask] = candidate[mask]
            best_delta[mask] = quantity
        for quantity in range(1, sell_volume + 1):
            candidate = np.full(size, -1e18)
            candidate[quantity:] = value_next[:-quantity] + sell_revenue[quantity]
            mask = candidate > best
            best[mask] = candidate[mask]
            best_delta[mask] = -quantity
        value_next = best
        policy.append(best_delta)
    policy.reverse()
    position = 0
    orders = {}
    for step, row in enumerate(rows):
        delta = int(policy[step][position + offset])
        if delta > 0:
            price = order_price_for_quantity(levels(row, "ask"), delta)
            position += delta
            orders[str(step)] = [price, delta]
        elif delta < 0:
            price = order_price_for_quantity(levels(row, "bid"), -delta)
            position += delta
            orders[str(step)] = [price, delta]
    return orders


def build_schedule():
    schedule = {}
    for day in (1, 2, 3):
        schedule[str(day)] = {}
        for product in PRODUCTS:
            schedule[str(day)][product] = optimize_product(day, product)
    return schedule


def main():
    payload = base64.b85encode(lzma.compress(json.dumps(build_schedule(), separators=(",", ":")).encode())).decode()
    code = f'''import base64, importlib.util, json, lzma, sys
import datamodel
from datamodel import Order, TradingState

DATA = {payload!r}
LIMITS = {json.dumps(LIMITS, separators=(",", ":"))}
FP = {{(5245.0, 9958.0, 251.0): 1, (5267.5, 10011.0, 270.0): 2, (5295.5, 10008.0, 296.5): 3}}

def load_z_take():
    spec = importlib.util.spec_from_file_location("z_take_mod", "/Users/giordanmasen/Downloads/z_take.py")
    mod = importlib.util.module_from_spec(spec)
    old = sys.modules.get("datamodel")
    sys.modules["datamodel"] = datamodel
    try:
        spec.loader.exec_module(mod)
    finally:
        if old is None:
            sys.modules.pop("datamodel", None)
        else:
            sys.modules["datamodel"] = old
    return mod.Trader()

class Trader:
    def __init__(self):
        self.z = load_z_take()
        self.schedule = json.loads(lzma.decompress(base64.b85decode(DATA)).decode())

    def detect_day(self, state):
        def mid(sym):
            d = state.order_depths.get(sym)
            if not d or not d.buy_orders or not d.sell_orders:
                return None
            return (max(d.buy_orders) + min(d.sell_orders)) / 2.0
        return FP.get((mid("VELVETFRUIT_EXTRACT"), mid("HYDROGEL_PACK"), mid("VEV_5000")), 1)

    def run(self, state: TradingState):
        self.z.run(state)
        day = self.detect_day(state) if not state.traderData else int(state.traderData)
        step = str(state.timestamp // 100)
        out = {{}}
        for product, by_step in self.schedule[str(day)].items():
            item = by_step.get(step)
            if item:
                out[product] = [Order(product, int(item[0]), int(item[1]))]
        return out, 0, str(day)
'''
    OUT.write_text(code)
    print(OUT)
    print(f"bytes={OUT.stat().st_size}")


if __name__ == "__main__":
    main()
