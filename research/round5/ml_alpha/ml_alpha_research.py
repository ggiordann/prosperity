#!/usr/bin/env python3
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5" / "ml_alpha"

CATEGORIES: dict[str, list[str]] = {
    "galaxy": [
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    ],
    "sleep": [
        "SLEEP_POD_SUEDE",
        "SLEEP_POD_LAMB_WOOL",
        "SLEEP_POD_POLYESTER",
        "SLEEP_POD_NYLON",
        "SLEEP_POD_COTTON",
    ],
    "microchip": [
        "MICROCHIP_CIRCLE",
        "MICROCHIP_OVAL",
        "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
    ],
    "pebbles": ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"],
    "robot": [
        "ROBOT_VACUUMING",
        "ROBOT_MOPPING",
        "ROBOT_DISHES",
        "ROBOT_LAUNDRY",
        "ROBOT_IRONING",
    ],
    "uv": ["UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"],
    "translator": [
        "TRANSLATOR_SPACE_GRAY",
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_VOID_BLUE",
    ],
    "panel": ["PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"],
    "oxygen": [
        "OXYGEN_SHAKE_MORNING_BREATH",
        "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_MINT",
        "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
    ],
    "snack": [
        "SNACKPACK_CHOCOLATE",
        "SNACKPACK_VANILLA",
        "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY",
        "SNACKPACK_RASPBERRY",
    ],
}

PRODUCT_TO_CATEGORY = {p: c for c, ps in CATEGORIES.items() for p in ps}
PRODUCTS = [p for ps in CATEGORIES.values() for p in ps]
LAGS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
MODEL_FEATURES = [
    "ret_1",
    "ret_3",
    "ret_5",
    "ret_10",
    "ret_20",
    "ret_50",
    "ret_100",
    "ret_200",
    "ret_500",
    "obi_1",
    "obi_3",
    "spread",
    "depth_1",
    "depth_3",
    "z_50",
    "z_200",
    "z_500",
    "vol_20",
    "vol_100",
    "cat_ret_1_ex",
    "cat_ret_5_ex",
    "cat_resid",
    "cat_resid_z_200",
    "trade_qty",
    "trade_count",
    "trade_signed",
]
MODEL_FEATURES += [f"xcat_{cat}_ret_1" for cat in CATEGORIES]
MODEL_FEATURES += [f"xcat_{cat}_ret_5" for cat in CATEGORIES]
STUMP_FEATURES = [
    "ret_1",
    "ret_3",
    "ret_5",
    "ret_10",
    "ret_20",
    "z_50",
    "z_200",
    "cat_ret_1_ex",
    "cat_ret_5_ex",
    "cat_resid_z_200",
    "obi_1",
    "spread",
    "vol_20",
]
SPLITS = [
    ("train_d2_test_d3d4", [2], [3, 4]),
    ("train_d2d3_test_d4", [2, 3], [4]),
    ("loo_test_d2", [3, 4], [2]),
    ("loo_test_d3", [2, 4], [3]),
    ("loo_test_d4", [2, 3], [4]),
]


def corr(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 30:
        return 0.0
    xs = x[mask].astype(float)
    ys = y[mask].astype(float)
    xs -= xs.mean()
    ys -= ys.mean()
    denom = math.sqrt(float(xs @ xs) * float(ys @ ys))
    return 0.0 if denom == 0 else float((xs @ ys) / denom)


def ridge_fit(x: np.ndarray, y: np.ndarray, lam: float = 8.0) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    mu = x.mean(axis=0)
    sig = x.std(axis=0)
    sig[sig == 0] = 1.0
    xs = (x - mu) / sig
    y_mu = float(y.mean())
    yc = y - y_mu
    eye = np.eye(xs.shape[1])
    beta_s = np.linalg.solve(xs.T @ xs + lam * eye, xs.T @ yc)
    beta = beta_s / sig
    intercept = y_mu - float(mu @ beta)
    return beta, mu, sig, intercept


def predict(x: np.ndarray, beta: np.ndarray, intercept: float) -> np.ndarray:
    return x @ beta + intercept


def load_prices() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frames.append(pd.read_csv(path, sep=";"))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["product"].isin(PRODUCTS)].copy()
    df["category"] = df["product"].map(PRODUCT_TO_CATEGORY)
    for col in [
        "bid_price_1",
        "bid_price_2",
        "bid_price_3",
        "ask_price_1",
        "ask_price_2",
        "ask_price_3",
        "bid_volume_1",
        "bid_volume_2",
        "bid_volume_3",
        "ask_volume_1",
        "ask_volume_2",
        "ask_volume_3",
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def load_trades() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("trades_round_5_day_*.csv")):
        day = int(path.stem.rsplit("_", 1)[1])
        frame = pd.read_csv(path, sep=";")
        frame["day"] = day
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=["day", "timestamp", "symbol", "price", "quantity"])
    return pd.concat(frames, ignore_index=True)


def add_trade_flow(features: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        features["trade_qty"] = 0.0
        features["trade_count"] = 0.0
        features["trade_signed"] = 0.0
        return features
    mid_lookup = features[["day", "timestamp", "product", "mid_price"]].rename(columns={"product": "symbol"})
    tr = trades.merge(mid_lookup, on=["day", "timestamp", "symbol"], how="left")
    tr["signed"] = np.sign(tr["price"] - tr["mid_price"].fillna(tr["price"])) * tr["quantity"]
    flow = (
        tr.groupby(["day", "timestamp", "symbol"])
        .agg(trade_qty=("quantity", "sum"), trade_count=("quantity", "size"), trade_signed=("signed", "sum"))
        .reset_index()
        .rename(columns={"symbol": "product"})
    )
    out = features.merge(flow, on=["day", "timestamp", "product"], how="left")
    for col in ["trade_qty", "trade_count", "trade_signed"]:
        out[col] = out[col].fillna(0.0)
    return out


def prepare_features(prices: pd.DataFrame, trades: pd.DataFrame) -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    rows = []
    mids_by_day: dict[int, pd.DataFrame] = {}
    for day, day_df in prices.groupby("day", sort=True):
        day_df = day_df.sort_values(["timestamp", "product"]).copy()
        mids = day_df.pivot(index="timestamp", columns="product", values="mid_price").sort_index()
        bids = day_df.pivot(index="timestamp", columns="product", values="bid_price_1").sort_index()
        asks = day_df.pivot(index="timestamp", columns="product", values="ask_price_1").sort_index()
        mids_by_day[int(day)] = mids[PRODUCTS]

        ret_by_lag = {lag: mids.diff(lag).fillna(0.0) for lag in LAGS}
        cat_ret = {}
        for cat, products in CATEGORIES.items():
            cat_ret[(cat, 1)] = ret_by_lag[1][products].mean(axis=1)
            cat_ret[(cat, 5)] = ret_by_lag[5][products].mean(axis=1)

        open_move = mids - mids.iloc[0]
        cat_move = {cat: open_move[products].mean(axis=1) for cat, products in CATEGORIES.items()}

        for product in PRODUCTS:
            product_rows = day_df[day_df["product"] == product].sort_values("timestamp").copy()
            product_rows["best_bid"] = bids[product].to_numpy(float)
            product_rows["best_ask"] = asks[product].to_numpy(float)
            product_rows["spread"] = product_rows["ask_price_1"] - product_rows["bid_price_1"]
            product_rows["depth_1"] = product_rows["bid_volume_1"].abs() + product_rows["ask_volume_1"].abs()
            product_rows["depth_3"] = (
                product_rows[["bid_volume_1", "bid_volume_2", "bid_volume_3"]].abs().sum(axis=1)
                + product_rows[["ask_volume_1", "ask_volume_2", "ask_volume_3"]].abs().sum(axis=1)
            )
            denom_1 = product_rows["depth_1"].replace(0, np.nan)
            denom_3 = product_rows["depth_3"].replace(0, np.nan)
            product_rows["obi_1"] = (
                product_rows["bid_volume_1"].abs() - product_rows["ask_volume_1"].abs()
            ) / denom_1
            product_rows["obi_3"] = (
                product_rows[["bid_volume_1", "bid_volume_2", "bid_volume_3"]].abs().sum(axis=1)
                - product_rows[["ask_volume_1", "ask_volume_2", "ask_volume_3"]].abs().sum(axis=1)
            ) / denom_3
            product_rows["obi_1"] = product_rows["obi_1"].fillna(0.0)
            product_rows["obi_3"] = product_rows["obi_3"].fillna(0.0)
            mid = product_rows["mid_price"]
            for lag in LAGS:
                product_rows[f"ret_{lag}"] = mid.diff(lag).fillna(0.0)
            for window in [50, 200, 500]:
                mean = mid.rolling(window, min_periods=12).mean()
                std = mid.rolling(window, min_periods=12).std().replace(0, np.nan)
                product_rows[f"z_{window}"] = ((mid - mean) / std).fillna(0.0).clip(-8.0, 8.0)
            ret_1 = mid.diff().fillna(0.0)
            product_rows["vol_20"] = ret_1.rolling(20, min_periods=8).std().fillna(0.0)
            product_rows["vol_100"] = ret_1.rolling(100, min_periods=20).std().fillna(0.0)
            for h in [1, 3, 5]:
                product_rows[f"target_{h}"] = mid.shift(-h) - mid
            product_rows["target_cross_buy_5"] = mid.shift(-5) - product_rows["best_ask"]
            product_rows["target_cross_sell_5"] = product_rows["best_bid"] - mid.shift(-5)
            product_rows["target_cross_profitable_5"] = (
                (product_rows["target_cross_buy_5"] > 0) | (product_rows["target_cross_sell_5"] > 0)
            ).astype(float)
            product_rows["target_revert_5"] = -np.sign(product_rows["z_200"]) * product_rows["target_5"]

            cat = PRODUCT_TO_CATEGORY[product]
            products = CATEGORIES[cat]
            n_other = len(products) - 1
            for lag in [1, 5]:
                product_rows[f"cat_ret_{lag}_ex"] = (
                    ret_by_lag[lag][products].sum(axis=1).to_numpy(float) - ret_by_lag[lag][product].to_numpy(float)
                ) / n_other
            product_rows["cat_resid"] = (
                open_move[product].to_numpy(float)
                - (open_move[products].sum(axis=1).to_numpy(float) - open_move[product].to_numpy(float)) / n_other
            )
            resid = pd.Series(product_rows["cat_resid"].to_numpy(float))
            resid_mean = resid.rolling(200, min_periods=30).mean()
            resid_std = resid.rolling(200, min_periods=30).std().replace(0, np.nan)
            product_rows["cat_resid_z_200"] = ((resid - resid_mean) / resid_std).fillna(0.0).clip(-8.0, 8.0).to_numpy()

            for cat_name in CATEGORIES:
                product_rows[f"xcat_{cat_name}_ret_1"] = cat_ret[(cat_name, 1)].to_numpy(float)
                product_rows[f"xcat_{cat_name}_ret_5"] = cat_ret[(cat_name, 5)].to_numpy(float)
            rows.append(product_rows)

    features = pd.concat(rows, ignore_index=True)
    features = add_trade_flow(features, trades)
    features[MODEL_FEATURES] = features[MODEL_FEATURES].replace([np.inf, -np.inf], 0.0).fillna(0.0)
    for col in ["target_1", "target_3", "target_5", "target_cross_buy_5", "target_cross_sell_5", "target_revert_5"]:
        features[col] = features[col].replace([np.inf, -np.inf], np.nan)
    return features, mids_by_day


def feature_power(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for feature in MODEL_FEATURES:
        for target in ["target_1", "target_3", "target_5", "target_cross_buy_5", "target_cross_sell_5", "target_revert_5"]:
            vals = []
            for day, day_df in features.groupby("day", sort=True):
                vals.append(corr(day_df[feature].to_numpy(float), day_df[target].to_numpy(float)))
            abs_vals = [abs(v) for v in vals]
            rows.append(
                {
                    "feature": feature,
                    "target": target,
                    "ic_mean": float(np.mean(vals)),
                    "abs_ic_mean": float(np.mean(abs_vals)),
                    "ic_min": float(np.min(vals)),
                    "ic_max": float(np.max(vals)),
                    "same_sign_days": int(np.all(np.array(vals) >= 0) or np.all(np.array(vals) <= 0)),
                    "day_2_ic": vals[0],
                    "day_3_ic": vals[1],
                    "day_4_ic": vals[2],
                }
            )
    out = pd.DataFrame(rows).sort_values(["same_sign_days", "abs_ic_mean"], ascending=False)
    out.to_csv(OUT / "feature_power.csv", index=False)
    return out


def _corr_matrix(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x0 = x - x.mean(axis=0)
    y0 = y - y.mean(axis=0)
    denom = np.sqrt((x0 * x0).sum(axis=0))[:, None] * np.sqrt((y0 * y0).sum(axis=0))[None, :]
    denom[denom == 0] = np.nan
    return (x0.T @ y0) / denom


def lead_lag_scan(mids_by_day: dict[int, pd.DataFrame], horizon: int = 5) -> pd.DataFrame:
    rows = []
    products = PRODUCTS
    for lag in LAGS:
        by_day_corr = {}
        by_day_slope = {}
        for day, mids in mids_by_day.items():
            arr = mids[products].to_numpy(float)
            x = arr[lag:-horizon] - arr[:-lag-horizon]
            y = arr[lag + horizon :] - arr[lag:-horizon]
            c = _corr_matrix(x, y)
            x0 = x - x.mean(axis=0)
            y0 = y - y.mean(axis=0)
            var = (x0 * x0).sum(axis=0)
            slope = (x0.T @ y0) / np.where(var[:, None] == 0, np.nan, var[:, None])
            by_day_corr[day] = c
            by_day_slope[day] = slope
        for i, leader in enumerate(products):
            for j, follower in enumerate(products):
                if leader == follower:
                    continue
                vals = [float(by_day_corr[day][i, j]) for day in sorted(by_day_corr)]
                slopes = [float(by_day_slope[day][i, j]) for day in sorted(by_day_slope)]
                if not np.all(np.isfinite(vals)):
                    continue
                same_sign = np.all(np.array(vals) > 0) or np.all(np.array(vals) < 0)
                rows.append(
                    {
                        "leader": leader,
                        "follower": follower,
                        "lag": lag,
                        "same_category": PRODUCT_TO_CATEGORY[leader] == PRODUCT_TO_CATEGORY[follower],
                        "leader_category": PRODUCT_TO_CATEGORY[leader],
                        "follower_category": PRODUCT_TO_CATEGORY[follower],
                        "ic_mean": float(np.mean(vals)),
                        "abs_ic_mean": float(np.mean(np.abs(vals))),
                        "ic_min": float(np.min(vals)),
                        "ic_max": float(np.max(vals)),
                        "same_sign_days": int(same_sign),
                        "slope_mean": float(np.nanmean(slopes)),
                        "day_2_ic": vals[0],
                        "day_3_ic": vals[1],
                        "day_4_ic": vals[2],
                    }
                )
    out = pd.DataFrame(rows)
    out["score"] = out["abs_ic_mean"] * (1 + out["same_sign_days"]) * np.where(out["same_category"], 1.2, 1.0)
    out = out.sort_values(["same_sign_days", "score"], ascending=False)
    out.to_csv(OUT / "leadlag_edges.csv", index=False)

    selected = []
    robust = out[(out["same_sign_days"] == 1) & (out["abs_ic_mean"] >= 0.018)].copy()
    for follower, g in robust.groupby("follower"):
        selected.append(g.sort_values("score", ascending=False).head(3))
    distilled = pd.concat(selected, ignore_index=True).sort_values("score", ascending=False)
    distilled.to_csv(OUT / "leadlag_distilled_candidates.csv", index=False)
    return out


def basket_residual_scan(mids_by_day: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for split_name, train_days, test_days in SPLITS:
        for cat, products in CATEGORIES.items():
            for target in products:
                others = [p for p in products if p != target]
                x_train_parts = []
                y_train_parts = []
                for day in train_days:
                    moves = mids_by_day[day][products] - mids_by_day[day][products].iloc[0]
                    x_train_parts.append(moves[others].to_numpy(float))
                    y_train_parts.append(moves[target].to_numpy(float))
                x_train = np.vstack(x_train_parts)
                y_train = np.concatenate(y_train_parts)
                beta, _, _, intercept = ridge_fit(x_train, y_train, lam=5.0)
                train_resid = y_train - predict(x_train, beta, intercept)
                resid_std = float(np.std(train_resid)) or 1.0
                for day in test_days:
                    moves = mids_by_day[day][products] - mids_by_day[day][products].iloc[0]
                    x = moves[others].to_numpy(float)
                    y = moves[target].to_numpy(float)
                    resid = y - predict(x, beta, intercept)
                    z = resid / resid_std
                    mid = mids_by_day[day][target].to_numpy(float)
                    future = np.roll(mid, -5) - mid
                    future[-5:] = np.nan
                    mask = np.isfinite(future) & (np.abs(z) >= 1.5)
                    edge = -np.sign(z[mask]) * future[mask]
                    rows.append(
                        {
                            "split": split_name,
                            "test_day": day,
                            "category": cat,
                            "target": target,
                            "features": ",".join(others),
                            "resid_std_train": resid_std,
                            "extreme_count": int(mask.sum()),
                            "reversion_edge_mean": float(np.mean(edge)) if len(edge) else 0.0,
                            "reversion_win_rate": float(np.mean(edge > 0)) if len(edge) else 0.0,
                            "coef_json": json.dumps({p: float(b) for p, b in zip(others, beta)}, separators=(",", ":")),
                            "intercept": float(intercept),
                        }
                    )
    out = pd.DataFrame(rows)
    summary = (
        out.groupby(["category", "target", "features"])
        .agg(
            edge_mean=("reversion_edge_mean", "mean"),
            edge_min=("reversion_edge_mean", "min"),
            win_rate=("reversion_win_rate", "mean"),
            total_extremes=("extreme_count", "sum"),
            splits=("split", "nunique"),
        )
        .reset_index()
        .sort_values(["edge_min", "edge_mean"], ascending=False)
    )
    out.to_csv(OUT / "basket_residuals_by_split.csv", index=False)
    summary.to_csv(OUT / "basket_residuals.csv", index=False)
    return summary


def model_validations(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    ablation_rows = []
    threshold_rows = []
    features = features.dropna(subset=["target_5"]).copy()
    feature_sets = {
        "all": MODEL_FEATURES,
        "no_orderbook": [f for f in MODEL_FEATURES if f not in {"obi_1", "obi_3", "spread", "depth_1", "depth_3"}],
        "no_zscore": [f for f in MODEL_FEATURES if not f.startswith("z_") and "resid_z" not in f],
        "no_category": [f for f in MODEL_FEATURES if not f.startswith("cat_") and not f.startswith("xcat_")],
        "local_only": [f for f in MODEL_FEATURES if f.startswith("ret_") or f.startswith("z_") or f.startswith("vol_")],
    }

    for split_name, train_days, test_days in SPLITS:
        train = features[features["day"].isin(train_days)]
        test = features[features["day"].isin(test_days)]
        for product in PRODUCTS:
            trp = train[train["product"] == product]
            tep = test[test["product"] == product]
            if len(trp) < 200 or len(tep) < 200:
                continue
            y_train = trp["target_5"].to_numpy(float)
            y_test = tep["target_5"].to_numpy(float)
            spread = tep["spread"].to_numpy(float)

            for set_name, cols in feature_sets.items():
                x_train = trp[cols].to_numpy(float)
                x_test = tep[cols].to_numpy(float)
                beta, _, _, intercept = ridge_fit(x_train, y_train, lam=12.0)
                pred = predict(x_test, beta, intercept)
                ic = corr(pred, y_test)
                sign_acc = float(np.mean(np.sign(pred) == np.sign(y_test)))
                for mult in [0.5, 0.75, 1.0, 1.25, 1.5]:
                    threshold = mult * np.maximum(1.0, spread / 2.0)
                    buy = pred > threshold
                    sell = pred < -threshold
                    pnl = np.where(buy, y_test - spread / 2.0, 0.0) + np.where(sell, -y_test - spread / 2.0, 0.0)
                    if set_name == "all":
                        threshold_rows.append(
                            {
                                "split": split_name,
                                "product": product,
                                "threshold_mult": mult,
                                "n_trades_proxy": int((buy | sell).sum()),
                                "proxy_edge_sum": float(np.nansum(pnl)),
                                "proxy_edge_mean": float(np.nanmean(pnl[buy | sell])) if (buy | sell).any() else 0.0,
                            }
                        )
                buy = pred > np.maximum(1.0, spread / 2.0)
                sell = pred < -np.maximum(1.0, spread / 2.0)
                pnl = np.where(buy, y_test - spread / 2.0, 0.0) + np.where(sell, -y_test - spread / 2.0, 0.0)
                row = {
                    "split": split_name,
                    "product": product,
                    "feature_set": set_name,
                    "model": "ridge_linear",
                    "ic": ic,
                    "sign_accuracy": sign_acc,
                    "n_trades_proxy": int((buy | sell).sum()),
                    "proxy_edge_sum": float(np.nansum(pnl)),
                }
                rows.append(row)
                if set_name != "all":
                    ablation_rows.append(row)

            y_class = np.where(y_train > trp["spread"].to_numpy(float) / 2.0, 1.0, -1.0)
            beta, _, _, intercept = ridge_fit(trp[MODEL_FEATURES].to_numpy(float), y_class, lam=20.0)
            score = predict(tep[MODEL_FEATURES].to_numpy(float), beta, intercept)
            rows.append(
                {
                    "split": split_name,
                    "product": product,
                    "feature_set": "all",
                    "model": "logistic_like_ridge_score",
                    "ic": corr(score, y_test),
                    "sign_accuracy": float(np.mean(np.sign(score) == np.sign(y_test))),
                    "n_trades_proxy": int((np.abs(score) > 0.25).sum()),
                    "proxy_edge_sum": float(np.nansum(np.where(score > 0.25, y_test - spread / 2.0, 0.0) + np.where(score < -0.25, -y_test - spread / 2.0, 0.0))),
                }
            )

            # Manual shallow tree: choose one pre-ranked simple feature and threshold.
            best = None
            for col in STUMP_FEATURES:
                x = trp[col].to_numpy(float)
                tx = tep[col].to_numpy(float)
                qs = np.nanquantile(x, [0.10, 0.25, 0.50, 0.75, 0.90])
                for q in np.unique(qs):
                    for side in [-1.0, 1.0]:
                        train_signal = side * np.where(x > q, 1.0, -1.0)
                        train_pnl = np.where(train_signal > 0, y_train - trp["spread"].to_numpy(float) / 2.0, -y_train - trp["spread"].to_numpy(float) / 2.0)
                        score = float(np.nanmean(train_pnl))
                        if best is None or score > best[0]:
                            best = (score, col, float(q), side)
            if best is not None:
                _, col, q, side = best
                sig = side * np.where(tep[col].to_numpy(float) > q, 1.0, -1.0)
                pnl = np.where(sig > 0, y_test - spread / 2.0, -y_test - spread / 2.0)
                rows.append(
                    {
                        "split": split_name,
                        "product": product,
                        "feature_set": "single_feature",
                        "model": f"decision_stump:{col}:{q:.4g}:{side:+.0f}",
                        "ic": corr(sig, y_test),
                        "sign_accuracy": float(np.mean(sig == np.sign(y_test))),
                        "n_trades_proxy": int(len(sig)),
                        "proxy_edge_sum": float(np.nansum(pnl)),
                    }
                )

    model_out = pd.DataFrame(rows)
    model_out.to_csv(OUT / "model_validation.csv", index=False)
    ablation_out = pd.DataFrame(ablation_rows)
    ablation_out.to_csv(OUT / "feature_ablation.csv", index=False)
    threshold_out = pd.DataFrame(threshold_rows)
    threshold_out.to_csv(OUT / "threshold_perturbation.csv", index=False)
    return model_out, ablation_out, threshold_out


def robust_summary(features: pd.DataFrame, leadlag: pd.DataFrame, baskets: pd.DataFrame, models: pd.DataFrame) -> dict[str, object]:
    feature_top = pd.read_csv(OUT / "feature_power.csv").head(20).to_dict("records")
    top_same = leadlag[(leadlag["same_category"]) & (leadlag["same_sign_days"] == 1)].head(30)
    top_cross = leadlag[(~leadlag["same_category"]) & (leadlag["same_sign_days"] == 1)].head(30)
    model_summary = (
        models.groupby(["model", "feature_set"], as_index=False)
        .agg(ic=("ic", "mean"), sign_accuracy=("sign_accuracy", "mean"), proxy_edge_sum=("proxy_edge_sum", "sum"), trades=("n_trades_proxy", "sum"))
        .sort_values("proxy_edge_sum", ascending=False)
    )
    product_stats = (
        features.groupby("product")
        .agg(
            category=("category", "first"),
            mean_mid=("mid_price", "mean"),
            std_mid=("mid_price", "std"),
            mean_spread=("spread", "mean"),
            mean_depth=("depth_1", "mean"),
            ret1_ac=("ret_1", lambda s: corr(s.shift(1).fillna(0).to_numpy(float), s.to_numpy(float))),
            z_revert_5=("target_revert_5", "mean"),
        )
        .reset_index()
        .sort_values("z_revert_5", ascending=False)
    )
    product_stats.to_csv(OUT / "product_feature_stats.csv", index=False)
    params = {
        "top_same_category_edges": top_same[["leader", "follower", "lag", "ic_mean", "slope_mean"]].head(60).to_dict("records"),
        "top_cross_category_edges": top_cross[["leader", "follower", "lag", "ic_mean", "slope_mean"]].head(30).to_dict("records"),
        "top_basket_reversions": baskets.head(30).to_dict("records"),
        "product_static_stats": product_stats.to_dict("records"),
    }
    (OUT / "distilled_params.json").write_text(json.dumps(params, indent=2), encoding="utf-8")
    summary = {
        "rows": int(len(features)),
        "days": sorted(int(d) for d in features["day"].unique()),
        "products": len(PRODUCTS),
        "feature_power_top20": feature_top,
        "model_summary": model_summary.head(20).to_dict("records"),
        "same_category_edges_top10": top_same.head(10).to_dict("records"),
        "cross_category_edges_top10": top_cross.head(10).to_dict("records"),
        "basket_top10": baskets.head(10).to_dict("records"),
        "sklearn_available": False,
        "random_forest_note": "sklearn is not installed in this workspace; random forest was skipped rather than vendored.",
        "nn_note": "A neural net was not promoted: three public days are too few for a high-variance model, and final runtime cannot depend on torch.",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    model_summary.to_csv(OUT / "model_summary.csv", index=False)
    return summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("loading prices/trades")
    prices = load_prices()
    trades = load_trades()
    feature_cache = OUT / "features.parquet"
    print("preparing features")
    if feature_cache.exists():
        features = pd.read_parquet(feature_cache)
        mids_by_day = {
            int(day): g.pivot(index="timestamp", columns="product", values="mid_price").sort_index()[PRODUCTS]
            for day, g in prices.groupby("day", sort=True)
        }
    else:
        features, mids_by_day = prepare_features(prices, trades)
        features.to_parquet(feature_cache, index=False)
    research_sample = features[features["timestamp"] % 500 == 0].copy()
    print(f"feature rows={len(features):,}; research sample={len(research_sample):,}")
    print("ranking features")
    fp = feature_power(research_sample)
    print("scanning lead-lag")
    leadlag = lead_lag_scan(mids_by_day)
    print("scanning basket residuals")
    baskets = basket_residual_scan(mids_by_day)
    print("validating models")
    models, _, _ = model_validations(research_sample)
    print("writing summary")
    summary = robust_summary(features, leadlag, baskets, models)
    print(
        json.dumps(
            {
                "rows": summary["rows"],
                "top_feature": fp.iloc[0][["feature", "target", "abs_ic_mean"]].to_dict(),
                "top_leadlag": leadlag.iloc[0][["leader", "follower", "lag", "abs_ic_mean"]].to_dict(),
                "out": str(OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
