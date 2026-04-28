from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from prosperity.round4_engine.config import Round4DataConfig

KEY_COLUMNS = ["day", "timestamp", "product"]
TRADE_KEY_COLUMNS = ["day", "timestamp", "product"]
VOUCHER_RE = re.compile(r"VEV_(\d+)$")


@dataclass(frozen=True)
class Round4MarketData:
    prices: pd.DataFrame
    trades: pd.DataFrame

    @property
    def products(self) -> tuple[str, ...]:
        return tuple(sorted(self.prices["product"].dropna().astype(str).unique()))


def parse_voucher_strike(product: str) -> int | None:
    match = VOUCHER_RE.fullmatch(str(product))
    return int(match.group(1)) if match else None


def normalize_product_name(product: str, config: Round4DataConfig) -> str:
    if product == "HYDROGEL":
        return config.hydrogel_product
    return str(product)


def read_semicolon_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing Round 4 data file: {path}")
    return pd.read_csv(path, sep=";")


def load_round4_data(config: Round4DataConfig) -> Round4MarketData:
    price_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []

    for day in config.all_days:
        price_path = config.data_dir / config.price_pattern.format(day=day)
        trade_path = config.data_dir / config.trade_pattern.format(day=day)
        prices = read_semicolon_csv(price_path)
        trades = read_semicolon_csv(trade_path)

        prices["day"] = pd.to_numeric(prices.get("day", day), errors="coerce").fillna(day).astype(int)
        trades["day"] = day
        prices = prices.rename(columns={"symbol": "product"})
        trades = trades.rename(columns={"symbol": "product"})
        prices["product"] = prices["product"].map(lambda product: normalize_product_name(product, config))
        trades["product"] = trades["product"].map(lambda product: normalize_product_name(product, config))

        price_frames.append(prices)
        trade_frames.append(trades)

    prices = pd.concat(price_frames, ignore_index=True)
    trades = pd.concat(trade_frames, ignore_index=True)

    for column in [
        "timestamp",
        "bid_price_1",
        "bid_volume_1",
        "bid_price_2",
        "bid_volume_2",
        "bid_price_3",
        "bid_volume_3",
        "ask_price_1",
        "ask_volume_1",
        "ask_price_2",
        "ask_volume_2",
        "ask_price_3",
        "ask_volume_3",
        "mid_price",
    ]:
        if column in prices:
            prices[column] = pd.to_numeric(prices[column], errors="coerce")

    for column in ["timestamp", "price", "quantity"]:
        if column in trades:
            trades[column] = pd.to_numeric(trades[column], errors="coerce")

    prices["best_bid"] = prices["bid_price_1"]
    prices["best_ask"] = prices["ask_price_1"]
    computed_mid = (prices["best_bid"] + prices["best_ask"]) / 2.0
    prices["mid_price"] = computed_mid.where(computed_mid.notna(), prices["mid_price"])
    prices["strike"] = prices["product"].map(parse_voucher_strike)
    prices["is_voucher"] = prices["strike"].notna()
    prices["is_underlying"] = prices["product"].eq(config.underlying_product)
    prices["is_hydrogel"] = prices["product"].eq(config.hydrogel_product)

    trades["quantity"] = trades["quantity"].fillna(0).astype(int)
    trades["price"] = trades["price"].astype(float)
    trades["buyer"] = trades["buyer"].fillna("UNKNOWN").astype(str)
    trades["seller"] = trades["seller"].fillna("UNKNOWN").astype(str)

    prices = prices.sort_values(KEY_COLUMNS).reset_index(drop=True)
    trades = trades.sort_values(["day", "timestamp", "product", "buyer", "seller"]).reset_index(drop=True)
    return Round4MarketData(prices=prices, trades=trades)


def split_prices(prices: pd.DataFrame, days: tuple[int, ...]) -> pd.DataFrame:
    return prices[prices["day"].isin(days)].copy()


def split_trades(trades: pd.DataFrame, days: tuple[int, ...]) -> pd.DataFrame:
    return trades[trades["day"].isin(days)].copy()


def product_snapshot(group: pd.DataFrame) -> dict[str, pd.Series]:
    return {str(row.product): row for row in group.itertuples(index=False)}


def safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default
