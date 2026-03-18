from __future__ import annotations

import csv
import math
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from prosperity.backtest.types import MarketFrame
from prosperity.datamodel import Listing, Observation, OrderDepth, Trade


def generate_tutorial_scenario(steps: int = 1000, seed: int = 7) -> List[MarketFrame]:
    rng = random.Random(seed)
    listings = {
        "EMERALDS": Listing(symbol="EMERALDS", product="EMERALDS", denomination="XIRECS"),
        "TOMATOES": Listing(symbol="TOMATOES", product="TOMATOES", denomination="XIRECS"),
    }

    emerald_mid = 10_000.0
    tomato_mid = 5_000.0
    frames: List[MarketFrame] = []

    for step in range(steps):
        timestamp = step * 100
        emerald_mid += 0.18 * (10_000 - emerald_mid) + rng.gauss(0.0, 0.8)
        tomato_mid += (
            0.06 * (5_020 - tomato_mid)
            + 8.0 * math.sin(step / 35.0)
            + rng.gauss(0.0, 5.0)
        )

        emerald_mid_price = int(round(emerald_mid))
        tomato_mid_price = int(round(tomato_mid))

        order_depths = {
            "EMERALDS": _build_depth(emerald_mid_price, spread=1, rng=rng, min_size=8, max_size=20),
            "TOMATOES": _build_depth(tomato_mid_price, spread=2, rng=rng, min_size=6, max_size=18),
        }
        market_trades = {
            "EMERALDS": _build_market_trades("EMERALDS", emerald_mid_price, rng, timestamp),
            "TOMATOES": _build_market_trades("TOMATOES", tomato_mid_price, rng, timestamp),
        }

        frames.append(
            MarketFrame(
                timestamp=timestamp,
                listings=listings,
                order_depths=order_depths,
                market_trades=market_trades,
                observations=Observation(),
            )
        )

    return frames


def load_frames_from_csv(order_depth_path: str | Path, trade_path: str | Path | None = None) -> List[MarketFrame]:
    order_depth_rows = _read_rows(order_depth_path)
    trade_rows = _read_rows(trade_path) if trade_path else []

    trade_lookup: Dict[tuple[int, str], List[Trade]] = defaultdict(list)
    for row in trade_rows:
        symbol = _product_from_row(row)
        timestamp = int(float(row["timestamp"]))
        trade_lookup[(timestamp, symbol)].append(
            Trade(
                symbol=symbol,
                price=int(float(row["price"])),
                quantity=int(float(row["quantity"])),
                buyer=row.get("buyer") or "",
                seller=row.get("seller") or "",
                timestamp=timestamp,
            )
        )

    grouped_rows: Dict[int, List[dict]] = defaultdict(list)
    for row in order_depth_rows:
        grouped_rows[int(float(row["timestamp"]))].append(row)

    listings: Dict[str, Listing] = {}
    frames: List[MarketFrame] = []
    for timestamp in sorted(grouped_rows):
        order_depths: Dict[str, OrderDepth] = {}
        market_trades: Dict[str, List[Trade]] = defaultdict(list)
        for row in grouped_rows[timestamp]:
            symbol = _product_from_row(row)
            listings.setdefault(symbol, Listing(symbol=symbol, product=symbol, denomination="XIRECS"))
            order_depths[symbol] = _depth_from_row(row)
            market_trades[symbol].extend(trade_lookup.get((timestamp, symbol), []))

        frames.append(
            MarketFrame(
                timestamp=timestamp,
                listings=listings,
                order_depths=order_depths,
                market_trades=dict(market_trades),
                observations=Observation(),
            )
        )

    return frames


def discover_replay_files(data_dir: str | Path) -> List[Tuple[str, Path, Path | None]]:
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(data_dir)

    price_files = sorted(
        data_dir.glob("prices_*.csv"),
        key=_replay_sort_key,
    )
    if not price_files:
        raise FileNotFoundError(f"No prices_*.csv files found in {data_dir}")

    pairs: List[Tuple[str, Path, Path | None]] = []
    for price_file in price_files:
        suffix = price_file.name.removeprefix("prices_")
        trade_file = data_dir / f"trades_{suffix}"
        label = price_file.stem.removeprefix("prices_")
        pairs.append((label, price_file, trade_file if trade_file.exists() else None))

    return pairs


def _build_depth(mid_price: int, spread: int, rng: random.Random, min_size: int, max_size: int) -> OrderDepth:
    buy_orders: Dict[int, int] = {}
    sell_orders: Dict[int, int] = {}
    level_gap = 1
    top_bid = mid_price - spread
    top_ask = mid_price + spread

    for level in range(3):
        bid_price = top_bid - (level * level_gap)
        ask_price = top_ask + (level * level_gap)
        buy_orders[bid_price] = rng.randint(min_size, max_size)
        sell_orders[ask_price] = -rng.randint(min_size, max_size)

    return OrderDepth(buy_orders=buy_orders, sell_orders=sell_orders)


def _build_market_trades(symbol: str, mid_price: int, rng: random.Random, timestamp: int) -> List[Trade]:
    trades: List[Trade] = []
    trade_count = rng.randint(0, 2)
    for _ in range(trade_count):
        price = mid_price + rng.choice([-1, 0, 1])
        quantity = rng.randint(1, 8)
        trades.append(
            Trade(
                symbol=symbol,
                price=price,
                quantity=quantity,
                buyer="",
                seller="",
                timestamp=timestamp,
            )
        )
    return trades


def _read_rows(path: str | Path | None) -> List[dict]:
    if path is None:
        return []
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    with path.open("r", newline="") as handle:
        sample = handle.read(2048)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        return [row for row in reader]


def _product_from_row(row: dict) -> str:
    for key in ("product", "symbol"):
        if row.get(key):
            return row[key]
    raise KeyError("CSV row must contain either 'product' or 'symbol'.")


def _depth_from_row(row: dict) -> OrderDepth:
    buy_orders: Dict[int, int] = {}
    sell_orders: Dict[int, int] = {}

    level = 1
    while f"bid_price_{level}" in row or f"ask_price_{level}" in row:
        bid_price = row.get(f"bid_price_{level}")
        bid_volume = row.get(f"bid_volume_{level}")
        ask_price = row.get(f"ask_price_{level}")
        ask_volume = row.get(f"ask_volume_{level}")

        if bid_price not in (None, "") and bid_volume not in (None, ""):
            buy_orders[int(float(bid_price))] = int(float(bid_volume))
        if ask_price not in (None, "") and ask_volume not in (None, ""):
            sell_orders[int(float(ask_price))] = -abs(int(float(ask_volume)))
        level += 1

    if not buy_orders and row.get("bid_price") and row.get("bid_volume"):
        buy_orders[int(float(row["bid_price"]))] = int(float(row["bid_volume"]))
    if not sell_orders and row.get("ask_price") and row.get("ask_volume"):
        sell_orders[int(float(row["ask_price"]))] = -abs(int(float(row["ask_volume"])))

    return OrderDepth(buy_orders=buy_orders, sell_orders=sell_orders)


def _replay_sort_key(path: Path) -> Tuple[int, int, str]:
    match = re.match(r"prices_round_(-?\d+)_day_(-?\d+)\.csv", path.name)
    if match:
        return (int(match.group(1)), int(match.group(2)), path.name)
    return (10**9, 10**9, path.name)
