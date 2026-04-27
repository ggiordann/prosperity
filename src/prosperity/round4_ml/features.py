from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from prosperity.round4_ml.config import DataConfig

PRICE_TARGET_PREFIX = "target_price_change_h"
VOUCHER_TARGET = "target_voucher_fair_price"
VOLATILITY_TARGET = "target_future_realized_volatility"
GROUP_COLUMNS = ["day", "product"]
KEY_COLUMNS = ["day", "timestamp", "product"]


@dataclass
class Standardizer:
    """Numerically stable feature normalizer fitted on the training split only."""

    columns: list[str]
    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, frame: pd.DataFrame, columns: list[str]) -> Standardizer:
        values = frame[columns].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float64)
        mean = np.nanmean(values, axis=0)
        scale = np.nanstd(values, axis=0)
        mean = np.where(np.isfinite(mean), mean, 0.0)
        scale = np.where(np.isfinite(scale) & (scale > 1e-12), scale, 1.0)
        return cls(columns=list(columns), mean=mean.astype(np.float32), scale=scale.astype(np.float32))

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        values = frame[self.columns].replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float32)
        values = (values - self.mean) / self.scale
        return np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns,
            "mean": self.mean.astype(float).tolist(),
            "scale": self.scale.astype(float).tolist(),
        }

    @classmethod
    def from_json_dict(cls, payload: dict[str, Any]) -> Standardizer:
        return cls(
            columns=list(payload["columns"]),
            mean=np.asarray(payload["mean"], dtype=np.float32),
            scale=np.asarray(payload["scale"], dtype=np.float32),
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_json_dict(), indent=2), encoding="utf-8")


@dataclass
class FeatureBundle:
    frame: pd.DataFrame
    feature_columns: list[str]
    price_target_columns: list[str]
    scaler: Standardizer
    feature_matrix: np.ndarray
    trader_profiles: pd.DataFrame
    top_traders: list[str]

    def split_frame(self, days: tuple[int, ...]) -> pd.DataFrame:
        return self.frame[self.frame["day"].isin(days)].copy()


def load_round4_data(config: DataConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    price_frames = []
    trade_frames = []
    for day in config.all_days:
        price_path = config.data_dir / config.price_pattern.format(day=day)
        trade_path = config.data_dir / config.trade_pattern.format(day=day)
        if not price_path.exists():
            raise FileNotFoundError(f"Missing price file: {price_path}")
        if not trade_path.exists():
            raise FileNotFoundError(f"Missing trade file: {trade_path}")

        prices = pd.read_csv(price_path, sep=";")
        trades = pd.read_csv(trade_path, sep=";")
        prices["day"] = prices.get("day", day)
        trades["day"] = day
        trade_frames.append(trades)
        price_frames.append(prices)

    prices = pd.concat(price_frames, ignore_index=True)
    trades = pd.concat(trade_frames, ignore_index=True)
    prices = prices.rename(columns={"symbol": "product"})
    trades = trades.rename(columns={"symbol": "product"})
    prices = prices.sort_values(KEY_COLUMNS).reset_index(drop=True)
    trades = trades.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)
    return prices, trades


def parse_voucher_strike(product: str, prefix: str = "VEV") -> int | None:
    match = re.fullmatch(rf"{re.escape(prefix)}_(\d+)", str(product))
    return int(match.group(1)) if match else None


def build_feature_bundle(config: DataConfig) -> FeatureBundle:
    prices, trades = load_round4_data(config)
    features = build_market_features(prices, config)
    trades = enrich_trades_with_quotes(trades, features, config)
    trader_profiles = fit_trader_profiles(trades, config)
    features = add_trader_features(features, trades, trader_profiles, config)
    features = add_targets(features, config)
    features = finalize_feature_frame(features)

    price_target_columns = [f"{PRICE_TARGET_PREFIX}{h}" for h in config.price_horizons]
    feature_columns = select_feature_columns(features, price_target_columns)
    train_frame = features[features["day"].isin(config.train_days)]
    scaler = Standardizer.fit(train_frame, feature_columns)
    feature_matrix = scaler.transform(features)
    top_traders = trader_profiles.sort_values("activity", ascending=False).head(config.top_traders)
    return FeatureBundle(
        frame=features,
        feature_columns=feature_columns,
        price_target_columns=price_target_columns,
        scaler=scaler,
        feature_matrix=feature_matrix,
        trader_profiles=trader_profiles,
        top_traders=top_traders["trader"].tolist(),
    )


def build_market_features(prices: pd.DataFrame, config: DataConfig) -> pd.DataFrame:
    frame = prices.copy()
    for column in frame.columns:
        if column.startswith(("bid_price_", "ask_price_", "bid_volume_", "ask_volume_")):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame["best_bid"] = pd.to_numeric(frame["bid_price_1"], errors="coerce")
    frame["best_ask"] = pd.to_numeric(frame["ask_price_1"], errors="coerce")
    computed_mid = (frame["best_bid"] + frame["best_ask"]) / 2.0
    provided_mid = pd.to_numeric(frame["mid_price"], errors="coerce")
    frame["mid_price"] = computed_mid.where(computed_mid.notna(), provided_mid)
    frame["bid_ask_spread"] = frame["best_ask"] - frame["best_bid"]
    frame["timestamp_norm"] = frame.groupby("day")["timestamp"].transform(
        lambda s: s / max(float(s.max()), 1.0)
    )
    frame["day_fraction"] = (
        frame["day"] - min(config.all_days) + frame["timestamp_norm"]
    ) / max(float(max(config.all_days) - min(config.all_days) + 1), 1.0)

    frame = add_order_book_features(frame, config)
    frame = add_price_features(frame, config)
    frame = add_voucher_features(frame, config)
    return frame.sort_values(KEY_COLUMNS).reset_index(drop=True)


def add_order_book_features(frame: pd.DataFrame, config: DataConfig) -> pd.DataFrame:
    levels = range(1, config.top_book_levels + 1)
    eps = config.epsilon
    bid_volumes = []
    ask_volumes = []
    weighted_bid_notional = 0.0
    weighted_ask_notional = 0.0
    bid_depth_weighted = 0.0
    ask_depth_weighted = 0.0
    bid_depth_weight = 0.0
    ask_depth_weight = 0.0

    for level in levels:
        bid_price = frame[f"bid_price_{level}"].fillna(0.0)
        ask_price = frame[f"ask_price_{level}"].fillna(0.0)
        bid_volume = frame[f"bid_volume_{level}"].fillna(0.0)
        ask_volume = frame[f"ask_volume_{level}"].fillna(0.0)
        bid_volumes.append(bid_volume)
        ask_volumes.append(ask_volume)
        weighted_bid_notional = weighted_bid_notional + bid_price * bid_volume
        weighted_ask_notional = weighted_ask_notional + ask_price * ask_volume
        weight = 1.0 / float(level)
        bid_depth_weighted = bid_depth_weighted + weight * bid_volume
        ask_depth_weighted = ask_depth_weighted + weight * ask_volume
        bid_depth_weight = bid_depth_weight + weight * bid_volume
        ask_depth_weight = ask_depth_weight + weight * ask_volume
        frame[f"bid_volume_top_{level}"] = sum(bid_volumes)
        frame[f"ask_volume_top_{level}"] = sum(ask_volumes)
        frame[f"total_volume_top_{level}"] = frame[f"bid_volume_top_{level}"] + frame[f"ask_volume_top_{level}"]

    bid_volume_total = sum(bid_volumes)
    ask_volume_total = sum(ask_volumes)
    total_volume = bid_volume_total + ask_volume_total
    frame["bid_volume_total"] = bid_volume_total
    frame["ask_volume_total"] = ask_volume_total
    frame["order_book_imbalance"] = (bid_volume_total - ask_volume_total) / (total_volume + eps)
    frame["depth_weighted_imbalance"] = (
        bid_depth_weighted - ask_depth_weighted
    ) / (bid_depth_weight + ask_depth_weight + eps)
    frame["weighted_bid_price"] = weighted_bid_notional / (bid_volume_total + eps)
    frame["weighted_ask_price"] = weighted_ask_notional / (ask_volume_total + eps)

    top_bid_volume = frame["bid_volume_1"].fillna(0.0)
    top_ask_volume = frame["ask_volume_1"].fillna(0.0)
    top_volume = top_bid_volume + top_ask_volume
    frame["microprice"] = (
        frame["best_ask"].fillna(frame["mid_price"]) * top_bid_volume
        + frame["best_bid"].fillna(frame["mid_price"]) * top_ask_volume
    ) / (top_volume + eps)
    frame["microprice"] = frame["microprice"].where(top_volume > 0.0, frame["mid_price"])
    frame["microprice_edge"] = frame["microprice"] - frame["mid_price"]
    frame["microprice_edge_spread"] = frame["microprice_edge"] / (frame["bid_ask_spread"].abs() + eps)
    frame["depth_mid"] = (frame["weighted_bid_price"] + frame["weighted_ask_price"]) / 2.0
    frame["depth_mid_edge"] = frame["depth_mid"] - frame["mid_price"]
    frame["bid_pressure"] = (frame["mid_price"] - frame["weighted_bid_price"]) / (
        frame["bid_ask_spread"].abs() + eps
    )
    frame["ask_pressure"] = (frame["weighted_ask_price"] - frame["mid_price"]) / (
        frame["bid_ask_spread"].abs() + eps
    )
    frame["price_pressure"] = frame["order_book_imbalance"] + frame["microprice_edge_spread"]

    far_bid = frame[f"bid_price_{config.top_book_levels}"].fillna(frame["best_bid"])
    far_ask = frame[f"ask_price_{config.top_book_levels}"].fillna(frame["best_ask"])
    frame["book_slope"] = ((far_ask - frame["best_ask"]) + (frame["best_bid"] - far_bid)) / (
        frame["bid_ask_spread"].abs() + eps
    )
    return frame


def add_price_features(frame: pd.DataFrame, config: DataConfig) -> pd.DataFrame:
    frame = frame.sort_values(KEY_COLUMNS).copy()
    groups = frame.groupby(GROUP_COLUMNS, group_keys=False)
    safe_mid = frame["mid_price"].clip(lower=config.epsilon)
    frame["log_mid_price"] = np.log(safe_mid)
    frame["log_return"] = groups["log_mid_price"].diff().fillna(0.0)

    for window in config.rolling_windows:
        frame[f"rolling_mean_{window}"] = groups["mid_price"].transform(
            lambda values, w=window: values.rolling(w, min_periods=1).mean()
        )
        frame[f"rolling_volatility_{window}"] = groups["log_return"].transform(
            lambda values, w=window: values.rolling(w, min_periods=2).std(ddof=0)
        )

    for window in config.momentum_windows:
        frame[f"momentum_{window}"] = groups["mid_price"].diff(window)
        frame[f"log_momentum_{window}"] = groups["log_mid_price"].diff(window)

    frame["rolling_volatility_20"] = frame["rolling_volatility_20"].fillna(0.0)
    return frame


def add_voucher_features(frame: pd.DataFrame, config: DataConfig) -> pd.DataFrame:
    frame = frame.copy()
    frame["strike"] = frame["product"].map(lambda product: parse_voucher_strike(product, config.voucher_prefix))
    frame["is_voucher"] = frame["strike"].notna().astype(float)
    frame["is_underlying"] = (frame["product"] == config.underlying_product).astype(float)
    frame["is_hydrogel"] = frame["product"].isin(config.hydrogel_products).astype(float)

    underlying = frame[frame["product"] == config.underlying_product][
        ["day", "timestamp", "mid_price", "rolling_volatility_20"]
    ].rename(
        columns={
            "mid_price": "underlying_mid_price",
            "rolling_volatility_20": "underlying_realized_volatility_20",
        }
    )
    frame = frame.merge(underlying, on=["day", "timestamp"], how="left")
    frame["underlying_mid_price"] = frame["underlying_mid_price"].fillna(frame["mid_price"])
    frame["underlying_realized_volatility_20"] = frame["underlying_realized_volatility_20"].fillna(
        frame["rolling_volatility_20"]
    )

    day_span = frame.groupby("day")["timestamp"].transform("max").replace(0, 1)
    elapsed_days = frame["day"] - min(config.all_days) + frame["timestamp"] / day_span
    frame["time_to_expiry_days"] = np.maximum(config.expiry_days - elapsed_days, 1e-6)
    frame["time_to_expiry_years"] = frame["time_to_expiry_days"] / 365.0

    strike = frame["strike"].fillna(0.0)
    frame["moneyness"] = np.where(
        frame["is_voucher"] > 0.0,
        frame["underlying_mid_price"] / np.maximum(strike, config.epsilon),
        0.0,
    )
    intrinsic = np.maximum(frame["underlying_mid_price"] - strike, 0.0)
    frame["intrinsic_value"] = np.where(frame["is_voucher"] > 0.0, intrinsic, 0.0)
    distance = frame["mid_price"] - frame["intrinsic_value"]
    frame["distance_from_intrinsic_value"] = np.where(frame["is_voucher"] > 0.0, distance, 0.0)
    time_value = np.maximum(distance, 0.0)
    frame["implied_volatility_proxy"] = np.where(
        frame["is_voucher"] > 0.0,
        time_value
        / (
            np.maximum(frame["underlying_mid_price"], config.epsilon)
            * np.sqrt(np.maximum(frame["time_to_expiry_years"], config.epsilon))
        ),
        0.0,
    )
    frame["voucher_delta_proxy"] = np.where(
        frame["is_voucher"] > 0.0,
        1.0 / (1.0 + np.exp(-20.0 * (frame["moneyness"] - 1.0))),
        0.0,
    )
    return frame


def enrich_trades_with_quotes(
    trades: pd.DataFrame, features: pd.DataFrame, config: DataConfig
) -> pd.DataFrame:
    quote_frame = features[
        [
            "day",
            "timestamp",
            "product",
            "best_bid",
            "best_ask",
            "mid_price",
        ]
    ].copy()
    quote_frame["future_mid_change_1"] = (
        quote_frame.sort_values(KEY_COLUMNS)
        .groupby(GROUP_COLUMNS)["mid_price"]
        .shift(-config.price_horizons[0])
        - quote_frame["mid_price"]
    )
    quote_columns = [
        "day",
        "timestamp",
        "product",
        "best_bid",
        "best_ask",
        "mid_price",
        "future_mid_change_1",
    ]
    quote_frame = quote_frame[quote_columns]
    enriched = trades.merge(quote_frame, on=KEY_COLUMNS, how="left")
    enriched["quantity"] = pd.to_numeric(enriched["quantity"], errors="coerce").fillna(0.0)
    enriched["price"] = pd.to_numeric(enriched["price"], errors="coerce")
    enriched["notional"] = enriched["price"] * enriched["quantity"]
    enriched["aggression"] = np.select(
        [
            enriched["price"] >= enriched["best_ask"],
            enriched["price"] <= enriched["best_bid"],
            enriched["price"] > enriched["mid_price"],
            enriched["price"] < enriched["mid_price"],
        ],
        [1.0, -1.0, 1.0, -1.0],
        default=0.0,
    )
    return enriched


def fit_trader_profiles(trades: pd.DataFrame, config: DataConfig) -> pd.DataFrame:
    train_trades = trades[trades["day"].isin(config.train_days)].copy()
    if train_trades.empty:
        return pd.DataFrame(columns=["trader", "activity", "informed_score", "aggressive_rate"])

    buyers = train_trades[["buyer", "quantity", "future_mid_change_1", "aggression"]].rename(
        columns={"buyer": "trader"}
    )
    buyers["side"] = 1.0
    sellers = train_trades[["seller", "quantity", "future_mid_change_1", "aggression"]].rename(
        columns={"seller": "trader"}
    )
    sellers["side"] = -1.0
    events = pd.concat([buyers, sellers], ignore_index=True)
    events["future_mid_change_1"] = events["future_mid_change_1"].fillna(0.0)
    events["alpha_contribution"] = events["side"] * events["future_mid_change_1"] * events["quantity"]
    events["is_aggressive_side"] = (
        ((events["side"] > 0.0) & (events["aggression"] > 0.0))
        | ((events["side"] < 0.0) & (events["aggression"] < 0.0))
    ).astype(float)

    profiles = (
        events.groupby("trader", as_index=False)
        .agg(
            activity=("quantity", "sum"),
            trade_events=("quantity", "count"),
            alpha_sum=("alpha_contribution", "sum"),
            aggressive_rate=("is_aggressive_side", "mean"),
        )
        .sort_values("activity", ascending=False)
        .reset_index(drop=True)
    )
    profiles["informed_score_raw"] = profiles["alpha_sum"] / np.sqrt(profiles["activity"].clip(lower=1.0))
    raw = profiles["informed_score_raw"].to_numpy(dtype=float)
    raw_mean = float(np.nanmean(raw)) if raw.size else 0.0
    raw_std = float(np.nanstd(raw)) if raw.size else 1.0
    if not math.isfinite(raw_std) or raw_std < 1e-12:
        raw_std = 1.0
    profiles["informed_score"] = (profiles["informed_score_raw"] - raw_mean) / raw_std
    profiles["is_informed"] = (
        profiles["informed_score"].abs() >= profiles["informed_score"].abs().quantile(0.75)
    ).astype(float)
    profiles["is_aggressive"] = (
        profiles["aggressive_rate"] >= profiles["aggressive_rate"].quantile(0.75)
    ).astype(float)
    return profiles


def add_trader_features(
    features: pd.DataFrame,
    trades: pd.DataFrame,
    trader_profiles: pd.DataFrame,
    config: DataConfig,
) -> pd.DataFrame:
    frame = features.copy()
    if trades.empty:
        return fill_missing_trader_columns(frame, [], config)

    score_map = trader_profiles.set_index("trader")["informed_score"].to_dict()
    aggressive_map = trader_profiles.set_index("trader")["is_aggressive"].to_dict()
    trade_work = trades.copy()
    trade_work["buyer_score"] = trade_work["buyer"].map(score_map).fillna(0.0)
    trade_work["seller_score"] = trade_work["seller"].map(score_map).fillna(0.0)
    trade_work["buyer_aggressive_profile"] = trade_work["buyer"].map(aggressive_map).fillna(0.0)
    trade_work["seller_aggressive_profile"] = trade_work["seller"].map(aggressive_map).fillna(0.0)
    trade_work["aggressive_buy_qty"] = np.where(
        trade_work["aggression"] > 0.0, trade_work["quantity"], 0.0
    )
    trade_work["aggressive_sell_qty"] = np.where(
        trade_work["aggression"] < 0.0, trade_work["quantity"], 0.0
    )
    trade_work["informed_flow"] = (
        trade_work["buyer_score"] - trade_work["seller_score"]
    ) * trade_work["quantity"]
    trade_work["aggressive_profile_flow"] = (
        trade_work["buyer_aggressive_profile"] - trade_work["seller_aggressive_profile"]
    ) * trade_work["quantity"]
    trade_work["unique_pair"] = trade_work["buyer"].astype(str) + ">" + trade_work["seller"].astype(str)

    aggregate = (
        trade_work.groupby(KEY_COLUMNS, as_index=False)
        .agg(
            trade_count=("quantity", "count"),
            trade_quantity=("quantity", "sum"),
            trade_notional=("notional", "sum"),
            avg_trade_price=("price", "mean"),
            aggressive_buy_quantity=("aggressive_buy_qty", "sum"),
            aggressive_sell_quantity=("aggressive_sell_qty", "sum"),
            informed_flow=("informed_flow", "sum"),
            aggressive_profile_flow=("aggressive_profile_flow", "sum"),
            active_trader_pairs=("unique_pair", "nunique"),
        )
        .reset_index(drop=True)
    )
    aggregate["trade_imbalance"] = (
        aggregate["aggressive_buy_quantity"] - aggregate["aggressive_sell_quantity"]
    ) / aggregate["trade_quantity"].clip(lower=config.epsilon)
    aggregate["informed_trader_indicator"] = aggregate["informed_flow"] / aggregate["trade_quantity"].clip(
        lower=config.epsilon
    )

    frame = frame.merge(aggregate, on=KEY_COLUMNS, how="left")
    trade_columns = [
        "trade_count",
        "trade_quantity",
        "trade_notional",
        "avg_trade_price",
        "aggressive_buy_quantity",
        "aggressive_sell_quantity",
        "informed_flow",
        "aggressive_profile_flow",
        "active_trader_pairs",
        "trade_imbalance",
        "informed_trader_indicator",
    ]
    zero_fill_columns = [column for column in trade_columns if column != "avg_trade_price"]
    frame[zero_fill_columns] = frame[zero_fill_columns].fillna(0.0)
    frame["avg_trade_price"] = frame["avg_trade_price"].fillna(frame["mid_price"])

    groups = frame.groupby(GROUP_COLUMNS, group_keys=False)
    for column in ["trade_count", "trade_quantity", "trade_imbalance", "informed_flow"]:
        frame[f"rolling_{column}_{config.trader_activity_window}"] = groups[column].transform(
            lambda values: values.rolling(config.trader_activity_window, min_periods=1).mean()
        )

    top_traders = (
        trader_profiles.sort_values("activity", ascending=False).head(config.top_traders)["trader"].tolist()
    )
    return add_top_trader_position_features(frame, trades, top_traders, config)


def fill_missing_trader_columns(
    frame: pd.DataFrame, top_traders: list[str], config: DataConfig
) -> pd.DataFrame:
    for column in [
        "trade_count",
        "trade_quantity",
        "trade_notional",
        "avg_trade_price",
        "aggressive_buy_quantity",
        "aggressive_sell_quantity",
        "informed_flow",
        "aggressive_profile_flow",
        "active_trader_pairs",
        "trade_imbalance",
        "informed_trader_indicator",
        f"rolling_trade_count_{config.trader_activity_window}",
        f"rolling_trade_quantity_{config.trader_activity_window}",
        f"rolling_trade_imbalance_{config.trader_activity_window}",
        f"rolling_informed_flow_{config.trader_activity_window}",
    ]:
        frame[column] = 0.0
    for trader in top_traders:
        slug = slugify_trader(trader)
        frame[f"trader_{slug}_net_position"] = 0.0
        frame[f"trader_{slug}_rolling_activity"] = 0.0
        frame[f"trader_{slug}_buy_sell_imbalance"] = 0.0
    return frame


def add_top_trader_position_features(
    frame: pd.DataFrame, trades: pd.DataFrame, top_traders: list[str], config: DataConfig
) -> pd.DataFrame:
    if not top_traders:
        return frame

    buyers = trades[["day", "timestamp", "product", "buyer", "quantity"]].rename(
        columns={"buyer": "trader"}
    )
    buyers["delta"] = buyers["quantity"]
    sellers = trades[["day", "timestamp", "product", "seller", "quantity"]].rename(
        columns={"seller": "trader"}
    )
    sellers["delta"] = -sellers["quantity"]
    events = pd.concat([buyers, sellers], ignore_index=True)
    events = events[events["trader"].isin(top_traders)]
    if events.empty:
        return fill_missing_trader_columns(frame, top_traders, config)

    events["trader_slug"] = events["trader"].map(slugify_trader)
    base_index = pd.MultiIndex.from_frame(frame[KEY_COLUMNS])
    pivot = events.pivot_table(
        index=KEY_COLUMNS,
        columns="trader_slug",
        values="delta",
        aggfunc="sum",
        fill_value=0.0,
    )
    pivot = pivot.reindex(base_index, fill_value=0.0)
    group_keys = [frame["day"].to_numpy(), frame["product"].to_numpy()]
    group_index = pd.MultiIndex.from_arrays(group_keys)

    for trader in top_traders:
        slug = slugify_trader(trader)
        if slug in pivot:
            delta = pd.Series(pivot[slug].to_numpy(dtype=np.float64), index=frame.index)
        else:
            delta = pd.Series(0.0, index=frame.index)
        frame[f"trader_{slug}_net_position"] = delta.groupby(group_index).cumsum().to_numpy()
        rolling_abs = delta.abs().groupby(group_index).transform(
            lambda values: values.rolling(config.trader_activity_window, min_periods=1).sum()
        )
        rolling_signed = delta.groupby(group_index).transform(
            lambda values: values.rolling(config.trader_activity_window, min_periods=1).sum()
        )
        frame[f"trader_{slug}_rolling_activity"] = rolling_abs.to_numpy()
        frame[f"trader_{slug}_buy_sell_imbalance"] = (
            rolling_signed / rolling_abs.clip(lower=config.epsilon)
        ).fillna(0.0).to_numpy()
    return frame


def add_targets(frame: pd.DataFrame, config: DataConfig) -> pd.DataFrame:
    frame = frame.sort_values(KEY_COLUMNS).copy()
    groups = frame.groupby(GROUP_COLUMNS, group_keys=False)
    for horizon in config.price_horizons:
        frame[f"{PRICE_TARGET_PREFIX}{horizon}"] = groups["mid_price"].shift(-horizon) - frame["mid_price"]

    frame[VOUCHER_TARGET] = groups["mid_price"].shift(-config.voucher_fair_horizon)
    is_voucher = frame.get("is_voucher", frame["product"].map(lambda p: parse_voucher_strike(p, config.voucher_prefix)).notna())
    frame.loc[~is_voucher.astype(bool), VOUCHER_TARGET] = np.nan

    frame["forward_log_return_1"] = groups["log_mid_price"].shift(-1) - frame["log_mid_price"]
    future_vol = groups["forward_log_return_1"].transform(
        lambda values: values.iloc[::-1]
        .rolling(config.realized_vol_horizon, min_periods=2)
        .std(ddof=0)
        .iloc[::-1]
    )
    observations_per_day = frame.groupby("day")["timestamp"].nunique().max()
    frame[VOLATILITY_TARGET] = future_vol * math.sqrt(max(float(observations_per_day), 1.0))
    return frame


def finalize_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.replace([np.inf, -np.inf], np.nan)
    numeric_columns = frame.select_dtypes(include=[np.number]).columns
    frame[numeric_columns] = frame[numeric_columns].astype(float)
    return frame.sort_values(KEY_COLUMNS).reset_index(drop=True)


def select_feature_columns(frame: pd.DataFrame, price_target_columns: list[str]) -> list[str]:
    excluded = {
        "day",
        "profit_and_loss",
        VOUCHER_TARGET,
        VOLATILITY_TARGET,
        "forward_log_return_1",
    }
    excluded.update(price_target_columns)
    columns = []
    for column in frame.select_dtypes(include=[np.number]).columns:
        if column in excluded:
            continue
        columns.append(column)
    return columns


def slugify_trader(trader: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(trader).strip().lower()).strip("_")
    return slug or "unknown"
