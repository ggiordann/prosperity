from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from prosperity.round4_engine.config import Round4DataConfig
from prosperity.round4_engine.data import KEY_COLUMNS, Round4MarketData


@dataclass(frozen=True)
class TraderProfiles:
    frame: pd.DataFrame

    @property
    def alpha(self) -> dict[str, float]:
        if self.frame.empty:
            return {}
        return {
            f"{row.product}:{row.trader}": float(row.trader_alpha_score)
            for row in self.frame.itertuples(index=False)
        }


@dataclass(frozen=True)
class FeatureSet:
    frame: pd.DataFrame
    trader_profiles: TraderProfiles


class FeatureEngineer:
    """Vectorized Round 4 feature builder with trader scores fitted on past days."""

    def __init__(self, config: Round4DataConfig):
        self.config = config
        self._cache: dict[tuple[int, ...], FeatureSet] = {}

    def build(self, market_data: Round4MarketData, fit_days: tuple[int, ...]) -> FeatureSet:
        cache_key = tuple(fit_days)
        if cache_key in self._cache:
            return self._cache[cache_key]

        base = self._build_market_features(market_data.prices)
        enriched_trades = self._enrich_trades_with_quotes(market_data.trades, base)
        trader_profiles = TraderProfiles(self._fit_trader_profiles(enriched_trades, fit_days))
        frame = self._add_trader_features(base, enriched_trades, trader_profiles)
        frame = self._finalize(frame)

        feature_set = FeatureSet(frame=frame, trader_profiles=trader_profiles)
        self._cache[cache_key] = feature_set
        return feature_set

    def _build_market_features(self, prices: pd.DataFrame) -> pd.DataFrame:
        frame = prices.copy()
        frame["bid_ask_spread"] = frame["best_ask"] - frame["best_bid"]
        frame = self._add_order_book_features(frame)
        frame = self._add_price_features(frame)
        frame = self._add_voucher_features(frame)
        return frame.sort_values(KEY_COLUMNS).reset_index(drop=True)

    def _add_order_book_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        levels = range(1, self.config.top_book_levels + 1)
        bid_total = pd.Series(0.0, index=frame.index)
        ask_total = pd.Series(0.0, index=frame.index)
        bid_weighted = pd.Series(0.0, index=frame.index)
        ask_weighted = pd.Series(0.0, index=frame.index)
        bid_notional = pd.Series(0.0, index=frame.index)
        ask_notional = pd.Series(0.0, index=frame.index)

        for level in levels:
            bid_price = frame[f"bid_price_{level}"].fillna(0.0)
            ask_price = frame[f"ask_price_{level}"].fillna(0.0)
            bid_volume = frame[f"bid_volume_{level}"].fillna(0.0)
            ask_volume = frame[f"ask_volume_{level}"].fillna(0.0)
            weight = 1.0 / float(level)
            bid_total = bid_total + bid_volume
            ask_total = ask_total + ask_volume
            bid_weighted = bid_weighted + weight * bid_volume
            ask_weighted = ask_weighted + weight * ask_volume
            bid_notional = bid_notional + bid_price * bid_volume
            ask_notional = ask_notional + ask_price * ask_volume
            frame[f"bid_volume_top_{level}"] = bid_total
            frame[f"ask_volume_top_{level}"] = ask_total

        total = bid_total + ask_total
        eps = self.config.epsilon
        frame["total_bid_volume"] = bid_total
        frame["total_ask_volume"] = ask_total
        frame["order_book_imbalance"] = (bid_total - ask_total) / (total + eps)
        frame["depth_imbalance"] = (bid_weighted - ask_weighted) / (bid_weighted + ask_weighted + eps)
        frame["weighted_bid_price"] = bid_notional / (bid_total + eps)
        frame["weighted_ask_price"] = ask_notional / (ask_total + eps)
        frame["depth_mid"] = (frame["weighted_bid_price"] + frame["weighted_ask_price"]) / 2.0

        top_bid_volume = frame["bid_volume_1"].fillna(0.0)
        top_ask_volume = frame["ask_volume_1"].fillna(0.0)
        top_total = top_bid_volume + top_ask_volume
        frame["microprice"] = (
            frame["best_ask"].fillna(frame["mid_price"]) * top_bid_volume
            + frame["best_bid"].fillna(frame["mid_price"]) * top_ask_volume
        ) / (top_total + eps)
        frame["microprice"] = frame["microprice"].where(top_total > 0.0, frame["mid_price"])
        frame["microprice_edge"] = frame["microprice"] - frame["mid_price"]
        frame["depth_mid_edge"] = frame["depth_mid"] - frame["mid_price"]
        return frame

    def _add_price_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.sort_values(KEY_COLUMNS).copy()
        groups = frame.groupby(["day", "product"], group_keys=False)
        safe_mid = frame["mid_price"].clip(lower=self.config.epsilon)
        frame["log_mid_price"] = np.log(safe_mid)
        frame["log_return"] = groups["log_mid_price"].diff().fillna(0.0)

        for window in self.config.rolling_windows:
            frame[f"rolling_mean_{window}"] = groups["mid_price"].transform(
                lambda values, w=window: values.rolling(w, min_periods=1).mean()
            )
            frame[f"rolling_volatility_{window}"] = groups["log_return"].transform(
                lambda values, w=window: values.rolling(w, min_periods=2).std(ddof=0)
            )

        for window in self.config.momentum_windows:
            frame[f"momentum_{window}"] = groups["mid_price"].diff(window).fillna(0.0)
            frame[f"log_momentum_{window}"] = groups["log_mid_price"].diff(window).fillna(0.0)

        horizon = self.config.trader_alpha_horizon
        frame[f"future_mid_change_{horizon}"] = (
            groups["mid_price"].shift(-horizon) - frame["mid_price"]
        ).fillna(0.0)
        return frame

    def _add_voucher_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        underlying = frame[frame["product"].eq(self.config.underlying_product)][
            [
                "day",
                "timestamp",
                "mid_price",
                "rolling_volatility_20",
                f"future_mid_change_{self.config.trader_alpha_horizon}",
            ]
        ].rename(
            columns={
                "mid_price": "underlying_mid_price",
                "rolling_volatility_20": "underlying_volatility_20",
                f"future_mid_change_{self.config.trader_alpha_horizon}": (
                    f"future_underlying_mid_change_{self.config.trader_alpha_horizon}"
                ),
            }
        )
        frame = frame.merge(underlying, on=["day", "timestamp"], how="left")
        frame["underlying_mid_price"] = frame["underlying_mid_price"].fillna(frame["mid_price"])
        frame["underlying_volatility_20"] = frame["underlying_volatility_20"].fillna(
            frame["rolling_volatility_20"]
        )
        underlying_change = f"future_underlying_mid_change_{self.config.trader_alpha_horizon}"
        frame[underlying_change] = frame[underlying_change].fillna(
            frame[f"future_mid_change_{self.config.trader_alpha_horizon}"]
        )
        strike = frame["strike"].fillna(0.0)
        frame["intrinsic_value"] = np.where(
            frame["is_voucher"], np.maximum(frame["underlying_mid_price"] - strike, 0.0), 0.0
        )
        frame["voucher_time_value"] = np.where(
            frame["is_voucher"], frame["mid_price"] - frame["intrinsic_value"], 0.0
        )
        frame["moneyness"] = np.where(
            frame["is_voucher"],
            frame["underlying_mid_price"] / np.maximum(strike, self.config.epsilon),
            0.0,
        )
        elapsed_day_fraction = frame["timestamp"] / max(float(frame["timestamp"].max()), 1.0)
        elapsed_days = frame["day"] - min(self.config.all_days) + elapsed_day_fraction
        frame["time_to_expiry_days"] = np.maximum(
            self.config.expiry_days_at_round4 - elapsed_days,
            1.0 / self.config.ticks_per_day,
        )
        frame["delta_proxy"] = np.where(
            frame["is_voucher"],
            1.0 / (1.0 + np.exp(-18.0 * (frame["moneyness"] - 1.0))),
            1.0,
        )
        return frame

    def _enrich_trades_with_quotes(self, trades: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        quote_columns = [
            "day",
            "timestamp",
            "product",
            "best_bid",
            "best_ask",
            "mid_price",
            "is_voucher",
            f"future_mid_change_{self.config.trader_alpha_horizon}",
            f"future_underlying_mid_change_{self.config.trader_alpha_horizon}",
        ]
        enriched = trades.merge(features[quote_columns], on=["day", "timestamp", "product"], how="left")
        enriched["quantity"] = enriched["quantity"].fillna(0.0).astype(float)
        enriched["notional"] = enriched["price"] * enriched["quantity"]
        enriched["buyer_aggressive"] = (enriched["price"] >= enriched["best_ask"]).astype(float)
        enriched["seller_aggressive"] = (enriched["price"] <= enriched["best_bid"]).astype(float)
        enriched["signed_quote_aggression"] = np.select(
            [
                enriched["price"] >= enriched["best_ask"],
                enriched["price"] <= enriched["best_bid"],
                enriched["price"] > enriched["mid_price"],
                enriched["price"] < enriched["mid_price"],
            ],
            [1.0, -1.0, 0.5, -0.5],
            default=0.0,
        )
        return enriched

    def _fit_trader_profiles(self, enriched_trades: pd.DataFrame, fit_days: tuple[int, ...]) -> pd.DataFrame:
        trades = enriched_trades[enriched_trades["day"].isin(fit_days)].copy()
        if trades.empty:
            return pd.DataFrame(
                columns=[
                    "product",
                    "trader",
                    "buy_volume",
                    "sell_volume",
                    "net_buy_volume",
                    "net_sell_volume",
                    "trade_events",
                    "rolling_trader_activity",
                    "trader_aggressiveness_score",
                    "trader_alpha_score",
                    "trader_reliability",
                ]
            )

        horizon_col = f"future_mid_change_{self.config.trader_alpha_horizon}"
        buyers = trades[["product", "buyer", "quantity", horizon_col, "buyer_aggressive"]].rename(
            columns={"buyer": "trader", "buyer_aggressive": "aggressive"}
        )
        buyers["side"] = 1.0
        sellers = trades[["product", "seller", "quantity", horizon_col, "seller_aggressive"]].rename(
            columns={"seller": "trader", "seller_aggressive": "aggressive"}
        )
        sellers["side"] = -1.0
        events = pd.concat([buyers, sellers], ignore_index=True)

        cross_col = f"future_underlying_mid_change_{self.config.trader_alpha_horizon}"
        voucher_trades = trades[trades["is_voucher"].astype(bool)].copy()
        if not voucher_trades.empty and cross_col in voucher_trades:
            cross_buyers = voucher_trades[["buyer", "quantity", cross_col, "buyer_aggressive"]].rename(
                columns={
                    "buyer": "trader",
                    cross_col: horizon_col,
                    "buyer_aggressive": "aggressive",
                }
            )
            cross_buyers["product"] = self.config.underlying_product
            cross_buyers["side"] = 1.0
            cross_sellers = voucher_trades[["seller", "quantity", cross_col, "seller_aggressive"]].rename(
                columns={
                    "seller": "trader",
                    cross_col: horizon_col,
                    "seller_aggressive": "aggressive",
                }
            )
            cross_sellers["product"] = self.config.underlying_product
            cross_sellers["side"] = -1.0
            events = pd.concat([events, cross_buyers, cross_sellers], ignore_index=True)
        events[horizon_col] = events[horizon_col].fillna(0.0)
        events["signed_alpha"] = events["side"] * events[horizon_col]
        events["alpha_notional"] = events["signed_alpha"] * events["quantity"]
        events["buy_volume"] = np.where(events["side"] > 0, events["quantity"], 0.0)
        events["sell_volume"] = np.where(events["side"] < 0, events["quantity"], 0.0)

        profiles = (
            events.groupby(["product", "trader"], as_index=False)
            .agg(
                buy_volume=("buy_volume", "sum"),
                sell_volume=("sell_volume", "sum"),
                trade_events=("quantity", "count"),
                activity=("quantity", "sum"),
                alpha_notional=("alpha_notional", "sum"),
                trader_aggressiveness_score=("aggressive", "mean"),
            )
            .reset_index(drop=True)
        )
        profiles["net_buy_volume"] = profiles["buy_volume"] - profiles["sell_volume"]
        profiles["net_sell_volume"] = profiles["sell_volume"] - profiles["buy_volume"]
        profiles["rolling_trader_activity"] = profiles["activity"]
        profiles["trader_alpha_raw"] = profiles["alpha_notional"] / profiles["activity"].clip(lower=1.0)

        product_groups = profiles.groupby("product")["trader_alpha_raw"]
        raw_mean = product_groups.transform("mean")
        raw_std = product_groups.transform("std").replace(0.0, np.nan).fillna(1.0)
        profiles["trader_alpha_score"] = (profiles["trader_alpha_raw"] - raw_mean) / raw_std
        events_component = np.sqrt(profiles["trade_events"].clip(lower=0.0))
        volume_component = np.sqrt(profiles["activity"].clip(lower=0.0))
        profiles["trader_reliability"] = (
            events_component / (events_component + 3.0)
        ) * (volume_component / (volume_component + 12.0))
        return profiles.sort_values("activity", ascending=False).reset_index(drop=True)

    def _add_trader_features(
        self,
        frame: pd.DataFrame,
        enriched_trades: pd.DataFrame,
        trader_profiles: TraderProfiles,
    ) -> pd.DataFrame:
        profile_frame = trader_profiles.frame
        if enriched_trades.empty or profile_frame.empty:
            return self._fill_missing_trader_features(frame)

        alpha_map = profile_frame.set_index(["product", "trader"])["trader_alpha_score"].to_dict()
        reliability_map = profile_frame.set_index(["product", "trader"])["trader_reliability"].to_dict()
        trades = enriched_trades.copy()
        buyer_keys = list(zip(trades["product"], trades["buyer"], strict=False))
        seller_keys = list(zip(trades["product"], trades["seller"], strict=False))
        trades["buyer_alpha"] = [alpha_map.get(key, 0.0) for key in buyer_keys]
        trades["seller_alpha"] = [alpha_map.get(key, 0.0) for key in seller_keys]
        trades["buyer_reliability"] = [reliability_map.get(key, 0.0) for key in buyer_keys]
        trades["seller_reliability"] = [reliability_map.get(key, 0.0) for key in seller_keys]
        trades["alpha_buy_volume"] = trades["quantity"] * trades["buyer_alpha"] * trades["buyer_reliability"]
        trades["alpha_sell_volume"] = trades["quantity"] * trades["seller_alpha"] * trades["seller_reliability"]
        trades["trader_alpha_flow"] = trades["alpha_buy_volume"] - trades["alpha_sell_volume"]
        trades["aggressive_buy_volume"] = np.where(trades["signed_quote_aggression"] > 0, trades["quantity"], 0.0)
        trades["aggressive_sell_volume"] = np.where(trades["signed_quote_aggression"] < 0, trades["quantity"], 0.0)
        trades["trader_pair"] = trades["buyer"].astype(str) + ">" + trades["seller"].astype(str)

        aggregate = (
            trades.groupby(["day", "timestamp", "product"], as_index=False)
            .agg(
                trade_count=("quantity", "count"),
                trade_quantity=("quantity", "sum"),
                trade_notional=("notional", "sum"),
                avg_trade_price=("price", "mean"),
                aggressive_buy_volume=("aggressive_buy_volume", "sum"),
                aggressive_sell_volume=("aggressive_sell_volume", "sum"),
                trader_alpha_flow=("trader_alpha_flow", "sum"),
                active_trader_pairs=("trader_pair", "nunique"),
            )
            .reset_index(drop=True)
        )
        aggregate["trade_imbalance"] = (
            aggregate["aggressive_buy_volume"] - aggregate["aggressive_sell_volume"]
        ) / aggregate["trade_quantity"].clip(lower=self.config.epsilon)
        aggregate["trader_alpha_signal"] = aggregate["trader_alpha_flow"] / aggregate[
            "trade_quantity"
        ].clip(lower=self.config.epsilon)

        cross_trades = trades[trades["is_voucher"].astype(bool)].copy()
        if not cross_trades.empty:
            cross_trades["target_product"] = self.config.underlying_product
            buyer_keys = list(zip(cross_trades["target_product"], cross_trades["buyer"], strict=False))
            seller_keys = list(zip(cross_trades["target_product"], cross_trades["seller"], strict=False))
            cross_trades["buyer_alpha"] = [alpha_map.get(key, 0.0) for key in buyer_keys]
            cross_trades["seller_alpha"] = [alpha_map.get(key, 0.0) for key in seller_keys]
            cross_trades["buyer_reliability"] = [reliability_map.get(key, 0.0) for key in buyer_keys]
            cross_trades["seller_reliability"] = [reliability_map.get(key, 0.0) for key in seller_keys]
            cross_trades["trader_alpha_flow"] = (
                cross_trades["quantity"]
                * (
                    cross_trades["buyer_alpha"] * cross_trades["buyer_reliability"]
                    - cross_trades["seller_alpha"] * cross_trades["seller_reliability"]
                )
            )
            cross_aggregate = (
                cross_trades.groupby(["day", "timestamp", "target_product"], as_index=False)
                .agg(
                    trade_count=("quantity", "count"),
                    trade_quantity=("quantity", "sum"),
                    trade_notional=("notional", "sum"),
                    avg_trade_price=("mid_price", "mean"),
                    aggressive_buy_volume=("aggressive_buy_volume", "sum"),
                    aggressive_sell_volume=("aggressive_sell_volume", "sum"),
                    trader_alpha_flow=("trader_alpha_flow", "sum"),
                    active_trader_pairs=("trader_pair", "nunique"),
                )
                .rename(columns={"target_product": "product"})
            )
            cross_aggregate["trade_imbalance"] = 0.0
            cross_aggregate["trader_alpha_signal"] = cross_aggregate["trader_alpha_flow"] / cross_aggregate[
                "trade_quantity"
            ].clip(lower=self.config.epsilon)
            aggregate = (
                pd.concat([aggregate, cross_aggregate], ignore_index=True)
                .groupby(["day", "timestamp", "product"], as_index=False)
                .agg(
                    trade_count=("trade_count", "sum"),
                    trade_quantity=("trade_quantity", "sum"),
                    trade_notional=("trade_notional", "sum"),
                    avg_trade_price=("avg_trade_price", "mean"),
                    aggressive_buy_volume=("aggressive_buy_volume", "sum"),
                    aggressive_sell_volume=("aggressive_sell_volume", "sum"),
                    trader_alpha_flow=("trader_alpha_flow", "sum"),
                    active_trader_pairs=("active_trader_pairs", "sum"),
                    trade_imbalance=("trade_imbalance", "mean"),
                )
            )
            aggregate["trader_alpha_signal"] = aggregate["trader_alpha_flow"] / aggregate[
                "trade_quantity"
            ].clip(lower=self.config.epsilon)

        frame = frame.merge(aggregate, on=["day", "timestamp", "product"], how="left")
        frame = self._fill_missing_trader_features(frame)
        groups = frame.groupby(["day", "product"], group_keys=False)
        window = self.config.trader_activity_window
        for column in ["trade_count", "trade_quantity", "trade_imbalance", "trader_alpha_signal"]:
            frame[f"rolling_{column}_{window}"] = groups[column].transform(
                lambda values, w=window: values.rolling(w, min_periods=1).mean()
            )
        return frame

    def _fill_missing_trader_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        defaults = {
            "trade_count": 0.0,
            "trade_quantity": 0.0,
            "trade_notional": 0.0,
            "avg_trade_price": np.nan,
            "aggressive_buy_volume": 0.0,
            "aggressive_sell_volume": 0.0,
            "trader_alpha_flow": 0.0,
            "active_trader_pairs": 0.0,
            "trade_imbalance": 0.0,
            "trader_alpha_signal": 0.0,
        }
        for column, default in defaults.items():
            if column not in frame:
                frame[column] = default
        numeric_columns = [column for column in defaults if column != "avg_trade_price"]
        frame[numeric_columns] = frame[numeric_columns].fillna(0.0)
        frame["avg_trade_price"] = frame["avg_trade_price"].fillna(frame["mid_price"])
        window = self.config.trader_activity_window
        for column in ["trade_count", "trade_quantity", "trade_imbalance", "trader_alpha_signal"]:
            rolling_column = f"rolling_{column}_{window}"
            if rolling_column not in frame:
                frame[rolling_column] = 0.0
        return frame

    def _finalize(self, frame: pd.DataFrame) -> pd.DataFrame:
        frame = frame.replace([np.inf, -np.inf], np.nan)
        numeric_columns = frame.select_dtypes(include=[np.number, "bool"]).columns
        frame[numeric_columns] = frame[numeric_columns].fillna(0.0)
        return frame.sort_values(KEY_COLUMNS).reset_index(drop=True)
