from __future__ import annotations

import itertools
import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5" / "global_alpha_map"

LAGS = [1, 2, 3, 5, 10, 20, 50, 100]
REV_HORIZON = 20
ROLLING_CORR_WINDOW = 200
PUBLIC_DAY_LABEL = {2: "day1_public_day_2", 3: "day2_public_day_3", 4: "day3_public_day_4"}

CATEGORIES = {
    "galaxy_sounds": [
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    ],
    "sleep_pods": [
        "SLEEP_POD_SUEDE",
        "SLEEP_POD_LAMB_WOOL",
        "SLEEP_POD_POLYESTER",
        "SLEEP_POD_NYLON",
        "SLEEP_POD_COTTON",
    ],
    "microchips": [
        "MICROCHIP_CIRCLE",
        "MICROCHIP_OVAL",
        "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
    ],
    "pebbles": ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"],
    "robotics": [
        "ROBOT_VACUUMING",
        "ROBOT_MOPPING",
        "ROBOT_DISHES",
        "ROBOT_LAUNDRY",
        "ROBOT_IRONING",
    ],
    "uv_visors": ["UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"],
    "translators": [
        "TRANSLATOR_SPACE_GRAY",
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_VOID_BLUE",
    ],
    "panels": ["PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"],
    "oxygen_shakes": [
        "OXYGEN_SHAKE_MORNING_BREATH",
        "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_MINT",
        "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
    ],
    "snackpacks": [
        "SNACKPACK_CHOCOLATE",
        "SNACKPACK_VANILLA",
        "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY",
        "SNACKPACK_RASPBERRY",
    ],
}
PRODUCT_TO_CATEGORY = {product: category for category, products in CATEGORIES.items() for product in products}
PRODUCT_ORDER = [product for products in CATEGORIES.values() for product in products]


def safe_corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return 0.0
    x = x[mask]
    y = y[mask]
    sx = float(np.std(x))
    sy = float(np.std(y))
    if sx <= 1e-12 or sy <= 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def corr_matrix(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x0 = x - np.nanmean(x, axis=0)
    y0 = y - np.nanmean(y, axis=0)
    x0 = np.nan_to_num(x0, nan=0.0)
    y0 = np.nan_to_num(y0, nan=0.0)
    denom = np.sqrt((x0 * x0).sum(axis=0))[:, None] * np.sqrt((y0 * y0).sum(axis=0))[None, :]
    out = x0.T @ y0
    with np.errstate(divide="ignore", invalid="ignore"):
        out = out / denom
    out[~np.isfinite(out)] = 0.0
    return out


def rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    series = pd.Series(values)
    return series.rolling(window, min_periods=max(5, window // 5)).mean().bfill().to_numpy(float)


def rolling_corr_stats(x: np.ndarray, y: np.ndarray, window: int = ROLLING_CORR_WINDOW) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = min(len(x), len(y))
    if n < window + 2:
        return 0.0, 0.0
    x = x[:n]
    y = y[:n]
    csum = lambda a: np.concatenate([[0.0], np.cumsum(a)])
    sx = csum(x)
    sy = csum(y)
    sx2 = csum(x * x)
    sy2 = csum(y * y)
    sxy = csum(x * y)
    sum_x = sx[window:] - sx[:-window]
    sum_y = sy[window:] - sy[:-window]
    mean_x = sum_x / window
    mean_y = sum_y / window
    var_x = (sx2[window:] - sx2[:-window]) / window - mean_x * mean_x
    var_y = (sy2[window:] - sy2[:-window]) / window - mean_y * mean_y
    cov = (sxy[window:] - sxy[:-window]) / window - mean_x * mean_y
    denom = np.sqrt(np.maximum(var_x, 0.0) * np.maximum(var_y, 0.0))
    corr = np.divide(cov, denom, out=np.full_like(cov, np.nan), where=denom > 1e-12)
    corr = corr[np.isfinite(corr)]
    if len(corr) == 0:
        return 0.0, 0.0
    return float(np.mean(corr)), float(np.std(corr))


def load_prices() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frame = pd.read_csv(path, sep=";")
        frames.append(frame)
    prices = pd.concat(frames, ignore_index=True)
    prices["category"] = prices["product"].map(PRODUCT_TO_CATEGORY)
    prices["spread"] = prices["ask_price_1"] - prices["bid_price_1"]
    depth_cols = [
        "bid_volume_1",
        "bid_volume_2",
        "bid_volume_3",
        "ask_volume_1",
        "ask_volume_2",
        "ask_volume_3",
    ]
    prices["top_depth"] = prices["bid_volume_1"].abs() + prices["ask_volume_1"].abs()
    prices["depth3"] = prices[depth_cols].abs().fillna(0.0).sum(axis=1)
    return prices


def load_trades() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("trades_round_5_day_*.csv")):
        day = int(path.stem.rsplit("_", 1)[1])
        frame = pd.read_csv(path, sep=";")
        frame["day"] = day
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def pivot_by_day(prices: pd.DataFrame, value: str) -> dict[int, pd.DataFrame]:
    out = {}
    for day, group in prices.groupby("day", sort=True):
        out[int(day)] = group.pivot(index="timestamp", columns="product", values=value).sort_index()
    return out


def ordered_products(mids: dict[int, pd.DataFrame]) -> list[str]:
    products = list(next(iter(mids.values())).columns)
    ordered = [product for product in PRODUCT_ORDER if product in products]
    ordered.extend(sorted(set(products) - set(ordered)))
    return ordered


def product_diagnostics(prices: pd.DataFrame, trades: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    trade_volume = trades.groupby(["day", "symbol"])["quantity"].sum()
    trade_count = trades.groupby(["day", "symbol"])["quantity"].size()
    rows = []
    for (day, product), group in prices.groupby(["day", "product"], sort=True):
        group = group.sort_values("timestamp")
        mid = group["mid_price"].to_numpy(float)
        ret = np.diff(mid)
        ret_ac1 = safe_corr(ret[:-1], ret[1:])
        ret_vol = float(np.std(ret))
        mid_mean = float(np.mean(mid))
        spread_mean = float(group["spread"].mean())
        top_depth = float(group["top_depth"].mean())
        depth3 = float(group["depth3"].mean())
        liq = float(top_depth / max(spread_mean, 1e-9))
        drift = float(mid[-1] - mid[0])
        drift_z = float(drift / max(ret_vol * math.sqrt(max(len(ret), 1)), 1e-9))

        z = mid - rolling_mean(mid, 200)
        future = mid[REV_HORIZON:] - mid[:-REV_HORIZON]
        mr_ic = safe_corr(z[:-REV_HORIZON], -future)

        lookback = 50
        if len(mid) > lookback + REV_HORIZON + 5:
            past_move = mid[lookback : len(mid) - REV_HORIZON] - mid[: len(mid) - REV_HORIZON - lookback]
            future_move = mid[lookback + REV_HORIZON :] - mid[lookback : len(mid) - REV_HORIZON]
            trend_ic = safe_corr(past_move, future_move)
        else:
            trend_ic = 0.0

        mean_reversion_score = float(max(0.0, -ret_ac1) + max(0.0, mr_ic))
        trend_score = float(abs(drift_z) + max(0.0, trend_ic))
        rows.append(
            {
                "public_day": PUBLIC_DAY_LABEL[int(day)],
                "day": int(day),
                "category": PRODUCT_TO_CATEGORY[product],
                "product": product,
                "mid_mean": mid_mean,
                "mid_start": float(mid[0]),
                "mid_end": float(mid[-1]),
                "net_drift_ticks": drift,
                "drift_z": drift_z,
                "avg_spread": spread_mean,
                "avg_top_depth": top_depth,
                "avg_depth3": depth3,
                "liquidity_score": liq,
                "trade_volume": int(trade_volume.get((day, product), 0)),
                "trade_count": int(trade_count.get((day, product), 0)),
                "ret_vol": ret_vol,
                "abs_ret_mean": float(np.mean(np.abs(ret))),
                "ret_ac1": ret_ac1,
                "mean_reversion_ic_h20": mr_ic,
                "mean_reversion_score": mean_reversion_score,
                "trend_ic_50_20": trend_ic,
                "trend_score": trend_score,
                "jump_95": float(np.quantile(np.abs(ret), 0.95)),
                "jump_99": float(np.quantile(np.abs(ret), 0.99)),
            }
        )

    by_day = pd.DataFrame(rows)
    agg = (
        by_day.groupby(["category", "product"])
        .agg(
            mid_mean=("mid_mean", "mean"),
            avg_spread=("avg_spread", "mean"),
            avg_top_depth=("avg_top_depth", "mean"),
            avg_depth3=("avg_depth3", "mean"),
            liquidity_score=("liquidity_score", "mean"),
            trade_volume=("trade_volume", "sum"),
            trade_count=("trade_count", "sum"),
            ret_vol=("ret_vol", "mean"),
            abs_ret_mean=("abs_ret_mean", "mean"),
            ret_ac1=("ret_ac1", "mean"),
            drift_mean_ticks=("net_drift_ticks", "mean"),
            drift_abs_mean_ticks=("net_drift_ticks", lambda s: float(np.mean(np.abs(s)))),
            drift_z_abs_mean=("drift_z", lambda s: float(np.mean(np.abs(s)))),
            mean_reversion_ic_h20=("mean_reversion_ic_h20", "mean"),
            mean_reversion_score=("mean_reversion_score", "mean"),
            mean_reversion_positive_days=("mean_reversion_ic_h20", lambda s: int(np.sum(np.asarray(s) > 0))),
            trend_ic_50_20=("trend_ic_50_20", "mean"),
            trend_score=("trend_score", "mean"),
            trend_positive_days=("trend_ic_50_20", lambda s: int(np.sum(np.asarray(s) > 0))),
            jump_95=("jump_95", "mean"),
            jump_99=("jump_99", "mean"),
        )
        .reset_index()
    )
    by_day.to_csv(OUT / "product_diagnostics_by_day.csv", index=False)
    agg.to_csv(OUT / "product_diagnostics.csv", index=False)
    return agg, by_day


def build_return_frames(mids: dict[int, pd.DataFrame], products: list[str]) -> dict[int, pd.DataFrame]:
    return {day: frame[products].diff().dropna() for day, frame in mids.items()}


def cross_product_correlations(
    mids: dict[int, pd.DataFrame],
    spreads: dict[int, pd.DataFrame],
    returns: dict[int, pd.DataFrame],
    products: list[str],
) -> pd.DataFrame:
    rows = []
    for a, b in itertools.combinations(products, 2):
        ret_corrs = []
        price_corrs = []
        spread_corrs = []
        rolling_means = []
        rolling_stds = []
        for day in sorted(mids):
            ret_a = returns[day][a].to_numpy(float)
            ret_b = returns[day][b].to_numpy(float)
            ret_corrs.append(safe_corr(ret_a, ret_b))
            price_corrs.append(safe_corr(mids[day][a].to_numpy(float), mids[day][b].to_numpy(float)))
            spread_corrs.append(safe_corr(spreads[day][a].to_numpy(float), spreads[day][b].to_numpy(float)))
            roll_mean, roll_std = rolling_corr_stats(ret_a, ret_b)
            rolling_means.append(roll_mean)
            rolling_stds.append(roll_std)
        ret_mean = float(np.mean(ret_corrs))
        ret_std = float(np.std(ret_corrs))
        sign = 1 if ret_mean >= 0 else -1
        stable_days = int(sum(1 for value in ret_corrs if value * sign > 0))
        score = (
            abs(ret_mean) * (0.5 + stable_days / 3.0)
            + 0.35 * abs(float(np.mean(rolling_means)))
            + 0.15 * abs(float(np.mean(price_corrs)))
        ) / (1.0 + 5.0 * ret_std)
        rows.append(
            {
                "product_a": a,
                "product_b": b,
                "category_a": PRODUCT_TO_CATEGORY[a],
                "category_b": PRODUCT_TO_CATEGORY[b],
                "same_category": PRODUCT_TO_CATEGORY[a] == PRODUCT_TO_CATEGORY[b],
                "return_corr_mean": ret_mean,
                "return_corr_day1": float(ret_corrs[0]),
                "return_corr_day2": float(ret_corrs[1]),
                "return_corr_day3": float(ret_corrs[2]),
                "return_corr_min": float(np.min(ret_corrs)),
                "return_corr_max": float(np.max(ret_corrs)),
                "return_corr_std": ret_std,
                "return_corr_stable_days": stable_days,
                "rolling_return_corr_mean": float(np.mean(rolling_means)),
                "rolling_return_corr_std": float(np.mean(rolling_stds)),
                "price_level_corr_mean": float(np.mean(price_corrs)),
                "spread_corr_mean": float(np.mean(spread_corrs)),
                "relationship_score": float(score),
            }
        )
    out = pd.DataFrame(rows).sort_values("relationship_score", ascending=False)
    out.to_csv(OUT / "cross_product_correlations.csv", index=False)
    return out


def fit_univariate(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    xm = float(np.mean(x))
    ym = float(np.mean(y))
    var = float(np.mean((x - xm) ** 2))
    beta = 0.0 if var <= 1e-12 else float(np.mean((x - xm) * (y - ym)) / var)
    intercept = float(ym - beta * xm)
    return intercept, beta


def residual_reversion_metrics(
    residual: np.ndarray,
    train_mean: float | None = None,
    train_std: float | None = None,
    horizon: int = REV_HORIZON,
    entry_z: float = 1.0,
) -> dict[str, float]:
    residual = np.asarray(residual, dtype=float)
    if len(residual) <= horizon + 5:
        return {"edge": 0.0, "mr_ic": 0.0, "activation": 0.0, "events": 0.0}
    mu = float(np.mean(residual)) if train_mean is None else float(train_mean)
    sd = float(np.std(residual)) if train_std is None else float(train_std)
    if sd <= 1e-9:
        return {"edge": 0.0, "mr_ic": 0.0, "activation": 0.0, "events": 0.0}
    z = (residual[:-horizon] - mu) / sd
    delta = residual[horizon:] - residual[:-horizon]
    active = np.abs(z) >= entry_z
    edge_all = -np.sign(z) * delta
    edge = float(np.mean(edge_all[active])) if np.any(active) else 0.0
    return {
        "edge": edge,
        "mr_ic": safe_corr(z, -delta),
        "activation": float(np.mean(active)),
        "events": float(np.sum(active)),
    }


def pair_spread_models(mids: dict[int, pd.DataFrame], correlations: pd.DataFrame, products: list[str]) -> pd.DataFrame:
    panels = {day: mids[day][products] for day in sorted(mids)}
    all_panel = pd.concat([panels[day] for day in sorted(panels)], ignore_index=True)
    rows = []

    def evaluate_orientation(target: str, hedge: str) -> dict[str, object]:
        edges = []
        mrics = []
        activations = []
        resid_stds = []
        for test_day in sorted(panels):
            train_days = [day for day in sorted(panels) if day != test_day]
            x_train = pd.concat([panels[day][hedge] for day in train_days]).to_numpy(float)
            y_train = pd.concat([panels[day][target] for day in train_days]).to_numpy(float)
            intercept, beta = fit_univariate(x_train, y_train)
            train_resid = y_train - (intercept + beta * x_train)
            train_mu = float(np.mean(train_resid))
            train_sd = float(np.std(train_resid))
            x_test = panels[test_day][hedge].to_numpy(float)
            y_test = panels[test_day][target].to_numpy(float)
            resid = y_test - (intercept + beta * x_test)
            metrics = residual_reversion_metrics(resid, train_mu, train_sd)
            edges.append(metrics["edge"])
            mrics.append(metrics["mr_ic"])
            activations.append(metrics["activation"])
            resid_stds.append(float(np.std(resid)))
        x_all = all_panel[hedge].to_numpy(float)
        y_all = all_panel[target].to_numpy(float)
        intercept, beta = fit_univariate(x_all, y_all)
        all_resid = y_all - (intercept + beta * x_all)
        edge_mean = float(np.mean(edges))
        mr_mean = float(np.mean(mrics))
        pos_days = int(sum(edge > 0 for edge in edges))
        resid_std_mean = float(np.mean(resid_stds))
        edge_efficiency = max(0.0, edge_mean) / max(resid_std_mean, 1.0)
        return {
            "target": target,
            "hedge": hedge,
            "intercept": float(intercept),
            "beta": float(beta),
            "residual_mean": float(np.mean(all_resid)),
            "residual_std": float(np.std(all_resid)),
            "loo_edge_mean": edge_mean,
            "loo_edge_min": float(np.min(edges)),
            "loo_positive_days": pos_days,
            "loo_mr_ic_mean": mr_mean,
            "activation_mean": float(np.mean(activations)),
            "residual_std_mean": resid_std_mean,
            "edge_efficiency": float(edge_efficiency),
            "spread_score": float(edge_efficiency * 10.0 * (pos_days / 3.0) * (1.0 + max(0.0, mr_mean))),
            "day_edges": [float(edge) for edge in edges],
        }

    for a, b in itertools.combinations(products, 2):
        left = evaluate_orientation(a, b)
        right = evaluate_orientation(b, a)
        chosen = left if left["spread_score"] >= right["spread_score"] else right
        corr_row = correlations[
            ((correlations["product_a"] == a) & (correlations["product_b"] == b))
            | ((correlations["product_a"] == b) & (correlations["product_b"] == a))
        ].iloc[0]
        rows.append(
            {
                "product_a": a,
                "product_b": b,
                "category_a": PRODUCT_TO_CATEGORY[a],
                "category_b": PRODUCT_TO_CATEGORY[b],
                "same_category": PRODUCT_TO_CATEGORY[a] == PRODUCT_TO_CATEGORY[b],
                "target": chosen["target"],
                "hedge": chosen["hedge"],
                "intercept": chosen["intercept"],
                "beta": chosen["beta"],
                "residual_mean": chosen["residual_mean"],
                "residual_std": chosen["residual_std"],
                "loo_edge_mean": chosen["loo_edge_mean"],
                "loo_edge_min": chosen["loo_edge_min"],
                "loo_positive_days": chosen["loo_positive_days"],
                "loo_mr_ic_mean": chosen["loo_mr_ic_mean"],
                "activation_mean": chosen["activation_mean"],
                "residual_std_mean": chosen["residual_std_mean"],
                "edge_efficiency": chosen["edge_efficiency"],
                "spread_score": chosen["spread_score"],
                "day_edges": json.dumps(chosen["day_edges"], separators=(",", ":")),
                "return_corr_mean": float(corr_row["return_corr_mean"]),
                "rolling_return_corr_mean": float(corr_row["rolling_return_corr_mean"]),
                "price_level_corr_mean": float(corr_row["price_level_corr_mean"]),
                "spread_corr_mean": float(corr_row["spread_corr_mean"]),
                "relationship_score": float(corr_row["relationship_score"] + chosen["spread_score"]),
            }
        )
    out = pd.DataFrame(rows).sort_values("relationship_score", ascending=False)
    out.to_csv(OUT / "pair_spread_models.csv", index=False)
    return out


def fit_lead_lag_beta(returns: dict[int, pd.DataFrame], train_days: list[int], lag: int, products: list[str]) -> tuple[np.ndarray, np.ndarray]:
    xs = []
    ys = []
    for day in train_days:
        matrix = returns[day][products].to_numpy(float)
        xs.append(matrix[:-lag])
        ys.append(matrix[lag:])
    x = np.vstack(xs)
    y = np.vstack(ys)
    x_mu = np.mean(x, axis=0)
    y_mu = np.mean(y, axis=0)
    xc = x - x_mu
    yc = y - y_mu
    denom = np.sum(xc * xc, axis=0)
    denom[denom <= 1e-12] = np.nan
    beta = (xc.T @ yc) / denom[:, None]
    beta[~np.isfinite(beta)] = 0.0
    np.fill_diagonal(beta, 0.0)
    return beta, x_mu


def test_lead_lag_matrix(
    returns: dict[int, pd.DataFrame],
    test_days: list[int],
    lag: int,
    products: list[str],
    beta: np.ndarray,
    x_mu: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    xs = []
    ys = []
    for day in test_days:
        matrix = returns[day][products].to_numpy(float)
        xs.append(matrix[:-lag])
        ys.append(matrix[lag:])
    x = np.vstack(xs)
    y = np.vstack(ys)
    xc = x - x_mu
    base_edge = np.sign(xc).T @ y / max(len(xc), 1)
    edge = np.sign(beta) * base_edge
    test_corr = np.sign(beta) * corr_matrix(xc, y)
    np.fill_diagonal(edge, 0.0)
    np.fill_diagonal(test_corr, 0.0)
    return edge, test_corr


def lead_lag_relationships(returns: dict[int, pd.DataFrame], products: list[str]) -> pd.DataFrame:
    days = sorted(returns)
    rows = []
    for lag in LAGS:
        day_corrs = {}
        for day in days:
            matrix = returns[day][products].to_numpy(float)
            day_corrs[day] = corr_matrix(matrix[:-lag], matrix[lag:])

        beta_1, xmu_1 = fit_lead_lag_beta(returns, [days[0]], lag, products)
        edge_1_test_23, corr_1_test_23 = test_lead_lag_matrix(returns, days[1:], lag, products, beta_1, xmu_1)

        beta_12, xmu_12 = fit_lead_lag_beta(returns, days[:2], lag, products)
        edge_12_test_3, corr_12_test_3 = test_lead_lag_matrix(returns, [days[2]], lag, products, beta_12, xmu_12)

        loo_edges = []
        loo_corrs = []
        for held_day in days:
            train_days = [day for day in days if day != held_day]
            beta, xmu = fit_lead_lag_beta(returns, train_days, lag, products)
            edge, corr = test_lead_lag_matrix(returns, [held_day], lag, products, beta, xmu)
            loo_edges.append(edge)
            loo_corrs.append(corr)
        loo_edge_stack = np.stack(loo_edges)
        loo_corr_stack = np.stack(loo_corrs)

        beta_all, _ = fit_lead_lag_beta(returns, days, lag, products)
        for i, leader in enumerate(products):
            for j, follower in enumerate(products):
                if i == j:
                    continue
                per_day_corr = [float(day_corrs[day][i, j]) for day in days]
                in_sample_mean = float(np.mean(per_day_corr))
                sign = 1 if in_sample_mean >= 0 else -1
                stable_days = int(sum(value * sign > 0 for value in per_day_corr))
                edge_values = [float(loo_edge_stack[k, i, j]) for k in range(len(days))]
                corr_values = [float(loo_corr_stack[k, i, j]) for k in range(len(days))]
                edge_mean = float(np.mean(edge_values))
                edge_min = float(np.min(edge_values))
                pos_days = int(sum(value > 0 for value in edge_values))
                corr_mean = float(np.mean(corr_values))
                corr_min = float(np.min(corr_values))
                score = float(max(0.0, edge_mean) * (0.25 + pos_days / 3.0) * (1.0 + max(0.0, corr_mean * 10.0)))
                rows.append(
                    {
                        "leader": leader,
                        "follower": follower,
                        "leader_category": PRODUCT_TO_CATEGORY[leader],
                        "follower_category": PRODUCT_TO_CATEGORY[follower],
                        "same_category": PRODUCT_TO_CATEGORY[leader] == PRODUCT_TO_CATEGORY[follower],
                        "lag": lag,
                        "day1_corr": per_day_corr[0],
                        "day2_corr": per_day_corr[1],
                        "day3_corr": per_day_corr[2],
                        "in_sample_corr_mean": in_sample_mean,
                        "in_sample_corr_abs_mean": abs(in_sample_mean),
                        "corr_stable_days": stable_days,
                        "train_day1_test_day2_3_edge": float(edge_1_test_23[i, j]),
                        "train_day1_test_day2_3_corr": float(corr_1_test_23[i, j]),
                        "train_day1_2_test_day3_edge": float(edge_12_test_3[i, j]),
                        "train_day1_2_test_day3_corr": float(corr_12_test_3[i, j]),
                        "loo_edge_mean": edge_mean,
                        "loo_edge_min": edge_min,
                        "loo_positive_days": pos_days,
                        "loo_corr_mean": corr_mean,
                        "loo_corr_min": corr_min,
                        "beta_all_days": float(beta_all[i, j]),
                        "lead_lag_score": score,
                    }
                )
    out = pd.DataFrame(rows).sort_values("lead_lag_score", ascending=False)
    out.to_csv(OUT / "lead_lag_relationships.csv", index=False)
    return out


def select_features(
    target: str,
    model_type: str,
    train_days: list[int],
    mids: dict[int, pd.DataFrame],
    returns: dict[int, pd.DataFrame],
    products: list[str],
) -> list[str]:
    if model_type == "same_category":
        return [p for p in CATEGORIES[PRODUCT_TO_CATEGORY[target]] if p != target and p in products]
    candidates = [p for p in products if p != target]
    if model_type == "cross_category_top8":
        candidates = [p for p in candidates if PRODUCT_TO_CATEGORY[p] != PRODUCT_TO_CATEGORY[target]]
    if model_type == "global_all_ridge":
        return candidates

    target_ret = pd.concat([returns[day][target] for day in train_days]).to_numpy(float)
    scores = []
    for feature in candidates:
        feature_ret = pd.concat([returns[day][feature] for day in train_days]).to_numpy(float)
        score = abs(safe_corr(target_ret, feature_ret))
        target_px = pd.concat([mids[day][target] for day in train_days]).to_numpy(float)
        feature_px = pd.concat([mids[day][feature] for day in train_days]).to_numpy(float)
        score += 0.2 * abs(safe_corr(target_px, feature_px))
        scores.append((score, feature))
    scores.sort(reverse=True)
    return [feature for _, feature in scores[:8]]


def fit_ridge(x_train: np.ndarray, y_train: np.ndarray, lam: float) -> tuple[float, np.ndarray, float, float]:
    x_mu = np.mean(x_train, axis=0)
    x_sd = np.std(x_train, axis=0)
    x_sd[x_sd <= 1e-9] = 1.0
    y_mu = float(np.mean(y_train))
    xs = (x_train - x_mu) / x_sd
    lhs = xs.T @ xs + lam * np.eye(xs.shape[1])
    rhs = xs.T @ (y_train - y_mu)
    try:
        beta_scaled = np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError:
        beta_scaled = np.linalg.pinv(lhs) @ rhs
    beta = beta_scaled / x_sd
    intercept = float(y_mu - x_mu @ beta)
    train_resid = y_train - (intercept + x_train @ beta)
    return intercept, beta, float(np.mean(train_resid)), float(np.std(train_resid))


def evaluate_basket_split(
    target: str,
    features: list[str],
    train_days: list[int],
    test_days: list[int],
    mids: dict[int, pd.DataFrame],
    lam: float,
) -> dict[str, float]:
    if not features:
        return {"edge": 0.0, "mr_ic": 0.0, "activation": 0.0, "resid_std": 0.0}
    x_train = pd.concat([mids[day][features] for day in train_days]).to_numpy(float)
    y_train = pd.concat([mids[day][target] for day in train_days]).to_numpy(float)
    intercept, beta, resid_mu, resid_sd = fit_ridge(x_train, y_train, lam)
    x_test = pd.concat([mids[day][features] for day in test_days]).to_numpy(float)
    y_test = pd.concat([mids[day][target] for day in test_days]).to_numpy(float)
    pred = intercept + x_test @ beta
    resid = y_test - pred
    metrics = residual_reversion_metrics(resid, resid_mu, resid_sd)
    return {
        "edge": metrics["edge"],
        "mr_ic": metrics["mr_ic"],
        "activation": metrics["activation"],
        "resid_std": float(np.std(resid)),
    }


def basket_models(
    mids: dict[int, pd.DataFrame],
    returns: dict[int, pd.DataFrame],
    diagnostics: pd.DataFrame,
    products: list[str],
) -> pd.DataFrame:
    days = sorted(mids)
    spread_by_product = diagnostics.set_index("product")["avg_spread"].to_dict()
    model_lams = {
        "same_category": 2.0,
        "cross_category_top8": 8.0,
        "global_top8": 8.0,
        "global_all_ridge": 80.0,
    }
    rows = []
    for target in products:
        for model_type, lam in model_lams.items():
            loo_edges = []
            loo_mrics = []
            loo_activations = []
            loo_resid_stds = []
            loo_features: list[list[str]] = []
            for held_day in days:
                train_days = [day for day in days if day != held_day]
                features = select_features(target, model_type, train_days, mids, returns, products)
                metrics = evaluate_basket_split(target, features, train_days, [held_day], mids, lam)
                loo_edges.append(metrics["edge"])
                loo_mrics.append(metrics["mr_ic"])
                loo_activations.append(metrics["activation"])
                loo_resid_stds.append(metrics["resid_std"])
                loo_features.append(features)

            features_1 = select_features(target, model_type, [days[0]], mids, returns, products)
            train1_test23 = evaluate_basket_split(target, features_1, [days[0]], days[1:], mids, lam)
            features_12 = select_features(target, model_type, days[:2], mids, returns, products)
            train12_test3 = evaluate_basket_split(target, features_12, days[:2], [days[2]], mids, lam)
            all_features = select_features(target, model_type, days, mids, returns, products)
            if all_features:
                x_all = pd.concat([mids[day][all_features] for day in days]).to_numpy(float)
                y_all = pd.concat([mids[day][target] for day in days]).to_numpy(float)
                intercept, beta, resid_mu, resid_sd = fit_ridge(x_all, y_all, lam)
                coef = {feature: float(value) for feature, value in zip(all_features, beta)}
            else:
                intercept, resid_mu, resid_sd, coef = 0.0, 0.0, 0.0, {}

            edge_mean = float(np.mean(loo_edges))
            mr_mean = float(np.mean(loo_mrics))
            pos_days = int(sum(edge > 0 for edge in loo_edges))
            avg_spread = float(spread_by_product.get(target, 1.0))
            resid_std_mean = float(np.mean(loo_resid_stds))
            residual_penalty = min(1.0, 5.0 * avg_spread / max(resid_std_mean, avg_spread, 1.0))
            score = float(
                (max(0.0, edge_mean) / max(avg_spread, 1.0))
                * (0.25 + pos_days / 3.0)
                * (1.0 + max(0.0, mr_mean))
                * residual_penalty
            )
            rows.append(
                {
                    "target": target,
                    "category": PRODUCT_TO_CATEGORY[target],
                    "model_type": model_type,
                    "n_features": len(all_features),
                    "features": ",".join(all_features),
                    "intercept": float(intercept),
                    "coefficients": json.dumps(coef, separators=(",", ":"), sort_keys=True),
                    "residual_mean": float(resid_mu),
                    "residual_std": float(resid_sd),
                    "loo_edge_mean": edge_mean,
                    "loo_edge_min": float(np.min(loo_edges)),
                    "loo_positive_days": pos_days,
                    "loo_mr_ic_mean": mr_mean,
                    "activation_mean": float(np.mean(loo_activations)),
                    "resid_std_mean": resid_std_mean,
                    "residual_penalty": residual_penalty,
                    "train_day1_test_day2_3_edge": float(train1_test23["edge"]),
                    "train_day1_test_day2_3_mr_ic": float(train1_test23["mr_ic"]),
                    "train_day1_2_test_day3_edge": float(train12_test3["edge"]),
                    "train_day1_2_test_day3_mr_ic": float(train12_test3["mr_ic"]),
                    "avg_spread": avg_spread,
                    "basket_score": score,
                    "loo_edges": json.dumps([float(edge) for edge in loo_edges], separators=(",", ":")),
                    "feature_sets_by_loo": json.dumps(loo_features, separators=(",", ":")),
                }
            )
    out = pd.DataFrame(rows).sort_values("basket_score", ascending=False)
    out.to_csv(OUT / "basket_models.csv", index=False)
    return out


def format_float(value: object, digits: int = 4) -> str:
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return "nan"
        if abs(float(value)) >= 1000:
            return f"{float(value):,.1f}"
        return f"{float(value):.{digits}f}"
    return str(value)


def md_table(frame: pd.DataFrame, columns: list[str], max_rows: int | None = None, digits: int = 4) -> str:
    if max_rows is not None:
        frame = frame.head(max_rows)
    if frame.empty:
        return "_No rows._"
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(format_float(row[col], digits) for col in columns) + " |")
    return "\n".join(lines)


def short_features(features: str, limit: int = 5) -> str:
    parts = [part for part in features.split(",") if part]
    if len(parts) <= limit:
        return ", ".join(parts)
    return ", ".join(parts[:limit]) + f", +{len(parts) - limit}"


def validated_lead_lag(lead_lag: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (lead_lag["loo_edge_mean"] > 0)
        & (lead_lag["loo_positive_days"] >= 2)
        & (lead_lag["train_day1_test_day2_3_edge"] > 0)
        & (lead_lag["train_day1_2_test_day3_edge"] > 0)
    )
    return lead_lag[mask].sort_values("lead_lag_score", ascending=False)


def validated_baskets(baskets: pd.DataFrame) -> pd.DataFrame:
    mask = (
        (baskets["loo_edge_mean"] > 0)
        & (baskets["loo_positive_days"] >= 2)
        & (baskets["train_day1_test_day2_3_edge"] > 0)
        & (baskets["train_day1_2_test_day3_edge"] > 0)
        & (baskets["loo_mr_ic_mean"] > 0)
    )
    return baskets[mask].sort_values("basket_score", ascending=False)


def validated_pairs(pairs: pd.DataFrame) -> pd.DataFrame:
    mask = (pairs["loo_edge_mean"] > 0) & (pairs["loo_positive_days"] >= 2) & (pairs["loo_mr_ic_mean"] > 0)
    return pairs[mask].sort_values("relationship_score", ascending=False)


def failed_validation(
    lead_lag: pd.DataFrame,
    baskets: pd.DataFrame,
    pairs: pd.DataFrame,
    correlations: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    ll_bad = lead_lag[
        (lead_lag["in_sample_corr_abs_mean"] >= lead_lag["in_sample_corr_abs_mean"].quantile(0.98))
        & ((lead_lag["loo_edge_mean"] <= 0) | (lead_lag["loo_positive_days"] <= 1))
    ].head(40)
    for _, row in ll_bad.iterrows():
        rows.append(
            {
                "type": "lead_lag",
                "relationship": f"{row['leader']} -> {row['follower']} lag {int(row['lag'])}",
                "reason": "large in-sample lag correlation did not survive leave-one-day-out edge",
                "in_sample_metric": float(row["in_sample_corr_abs_mean"]),
                "oos_metric": float(row["loo_edge_mean"]),
                "positive_days": int(row["loo_positive_days"]),
            }
        )
    basket_bad = baskets[
        (baskets["loo_mr_ic_mean"] > baskets["loo_mr_ic_mean"].quantile(0.80))
        & ((baskets["loo_edge_mean"] <= 0) | (baskets["train_day1_2_test_day3_edge"] <= 0))
    ].head(30)
    for _, row in basket_bad.iterrows():
        rows.append(
            {
                "type": "basket",
                "relationship": f"{row['target']} {row['model_type']}",
                "reason": "residual looked mean-reverting but failed edge or final-day validation",
                "in_sample_metric": float(row["loo_mr_ic_mean"]),
                "oos_metric": float(row["loo_edge_mean"]),
                "positive_days": int(row["loo_positive_days"]),
            }
        )
    pair_bad = pairs[
        (pairs["return_corr_mean"].abs() >= pairs["return_corr_mean"].abs().quantile(0.95))
        & ((pairs["loo_edge_mean"] <= 0) | (pairs["loo_positive_days"] <= 1))
    ].head(30)
    for _, row in pair_bad.iterrows():
        rows.append(
            {
                "type": "pair_spread",
                "relationship": f"{row['target']} ~ {row['hedge']}",
                "reason": "strong pair correlation did not become robust residual reversion",
                "in_sample_metric": float(abs(row["return_corr_mean"])),
                "oos_metric": float(row["loo_edge_mean"]),
                "positive_days": int(row["loo_positive_days"]),
            }
        )
    corr_bad = correlations[
        (correlations["relationship_score"] >= correlations["relationship_score"].quantile(0.98))
        & (correlations["return_corr_stable_days"] <= 1)
    ].head(20)
    for _, row in corr_bad.iterrows():
        rows.append(
            {
                "type": "correlation",
                "relationship": f"{row['product_a']} / {row['product_b']}",
                "reason": "high blended score but daily return-correlation sign was unstable",
                "in_sample_metric": float(row["relationship_score"]),
                "oos_metric": float(row["return_corr_mean"]),
                "positive_days": int(row["return_corr_stable_days"]),
            }
        )
    out = pd.DataFrame(rows).sort_values(["type", "in_sample_metric"], ascending=[True, False])
    out.to_csv(OUT / "failed_validation.csv", index=False)
    return out


def leader_laggard_tables(valid_ll: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    leaders = (
        valid_ll.groupby(["leader_category", "leader"])
        .agg(
            edge_count=("follower", "size"),
            score_sum=("lead_lag_score", "sum"),
            avg_oos_edge=("loo_edge_mean", "mean"),
            unique_followers=("follower", "nunique"),
        )
        .reset_index()
        .sort_values(["score_sum", "edge_count"], ascending=False)
    )
    laggards = (
        valid_ll.groupby(["follower_category", "follower"])
        .agg(
            edge_count=("leader", "size"),
            score_sum=("lead_lag_score", "sum"),
            avg_oos_edge=("loo_edge_mean", "mean"),
            unique_leaders=("leader", "nunique"),
        )
        .reset_index()
        .sort_values(["score_sum", "edge_count"], ascending=False)
    )
    leaders.to_csv(OUT / "leaders.csv", index=False)
    laggards.to_csv(OUT / "laggards.csv", index=False)
    return leaders, laggards


def avoid_tables(
    diagnostics: pd.DataFrame,
    valid_pairs_df: pd.DataFrame,
    valid_ll: pd.DataFrame,
    valid_basket_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    product_scores = {product: 0.0 for product in diagnostics["product"]}
    for _, row in valid_pairs_df.iterrows():
        product_scores[row["product_a"]] += float(row["relationship_score"])
        product_scores[row["product_b"]] += float(row["relationship_score"])
    for _, row in valid_ll.iterrows():
        product_scores[row["leader"]] += float(row["lead_lag_score"]) * 0.5
        product_scores[row["follower"]] += float(row["lead_lag_score"])
    for _, row in valid_basket_df.iterrows():
        product_scores[row["target"]] += float(row["basket_score"]) * 10.0

    max_alpha = max(product_scores.values()) if product_scores else 0.0
    rows = []
    for _, row in diagnostics.iterrows():
        score = float(product_scores.get(row["product"], 0.0))
        alpha_weakness = 1.0 / (1.0 + score / max(max_alpha * 0.05, 1.0))
        avoid_score = (
            alpha_weakness
            + 0.25 / max(float(row["liquidity_score"]), 1e-9)
            + max(0.0, 0.05 - float(row["mean_reversion_score"]))
            + max(0.0, float(row["avg_spread"]) / max(float(row["ret_vol"]), 1e-9) - 1.5) * 0.05
        )
        rows.append(
            {
                "category": row["category"],
                "product": row["product"],
                "avoid_score": float(avoid_score),
                "validated_alpha_score": score,
                "liquidity_score": float(row["liquidity_score"]),
                "avg_spread": float(row["avg_spread"]),
                "ret_vol": float(row["ret_vol"]),
                "mean_reversion_score": float(row["mean_reversion_score"]),
                "reason": "few validated global edges and/or unattractive spread/liquidity",
            }
        )
    products = pd.DataFrame(rows).sort_values(["validated_alpha_score", "avoid_score"], ascending=[True, False])
    categories = (
        products.groupby("category")
        .agg(
            avoid_score=("avoid_score", "mean"),
            validated_alpha_score=("validated_alpha_score", "sum"),
            liquidity_score=("liquidity_score", "mean"),
            avg_spread=("avg_spread", "mean"),
        )
        .reset_index()
        .sort_values(["validated_alpha_score", "avoid_score"], ascending=[True, False])
    )
    products.to_csv(OUT / "products_to_avoid.csv", index=False)
    categories.to_csv(OUT / "categories_to_avoid.csv", index=False)
    return products, categories


def make_json_candidates(
    pair_candidates: pd.DataFrame,
    basket_candidates: pd.DataFrame,
    lead_candidates: pd.DataFrame,
    diagnostics: pd.DataFrame,
    avoid_products: pd.DataFrame,
    avoid_categories: pd.DataFrame,
) -> None:
    def clean_record(row: pd.Series) -> dict[str, object]:
        out: dict[str, object] = {}
        for key, value in row.items():
            if isinstance(value, np.integer):
                out[key] = int(value)
            elif isinstance(value, np.floating):
                out[key] = None if not np.isfinite(float(value)) else float(value)
            elif isinstance(value, float):
                out[key] = None if not np.isfinite(value) else value
            elif isinstance(value, str):
                try:
                    if key in {"coefficients", "loo_edges", "feature_sets_by_loo", "day_edges"}:
                        out[key] = json.loads(value)
                    else:
                        out[key] = value
                except json.JSONDecodeError:
                    out[key] = value
            else:
                out[key] = value
        return out

    pair_records = []
    for _, row in pair_candidates.head(30).iterrows():
        rec = clean_record(row)
        rec["recommended_parameters"] = {
            "entry_z": 1.25,
            "exit_z": 0.25,
            "lookback_ticks_for_z": 200,
            "position_limit": 10,
            "formula": f"{row['target']} fair = {row['intercept']:.6f} + {row['beta']:.8f} * {row['hedge']}",
        }
        pair_records.append(rec)

    basket_records = []
    fair_value_formulas = {}
    for _, row in basket_candidates.head(20).iterrows():
        rec = clean_record(row)
        coeffs = rec.get("coefficients", {})
        formula_terms = [f"{coef:.8f}*{name}" for name, coef in coeffs.items()]
        formula = f"{row['target']} fair = {row['intercept']:.6f}"
        if formula_terms:
            formula += " + " + " + ".join(formula_terms)
        rec["recommended_parameters"] = {
            "entry_z": 1.25,
            "exit_z": 0.25,
            "residual_mean": float(row["residual_mean"]),
            "residual_std": float(row["residual_std"]),
            "horizon_ticks": REV_HORIZON,
            "model_lambda": {"same_category": 2.0, "cross_category_top8": 8.0, "global_top8": 8.0, "global_all_ridge": 80.0}[row["model_type"]],
            "position_limit": 10,
            "formula": formula,
        }
        basket_records.append(rec)
        fair_value_formulas[f"{row['target']}::{row['model_type']}"] = {
            "target": row["target"],
            "model_type": row["model_type"],
            "intercept": float(row["intercept"]),
            "coefficients": coeffs,
            "residual_mean": float(row["residual_mean"]),
            "residual_std": float(row["residual_std"]),
            "entry_z": 1.25,
            "exit_z": 0.25,
        }

    lead_records = []
    for _, row in lead_candidates.head(30).iterrows():
        rec = clean_record(row)
        rec["recommended_parameters"] = {
            "feature": f"{row['leader']} one-tick return lagged by {int(row['lag'])} ticks",
            "fair_shift": f"{row['follower']} fair += {row['beta_all_days']:.8f} * ({row['leader']}_mid[t-{int(row['lag'])}] - {row['leader']}_mid[t-{int(row['lag'])}-1])",
            "min_history_ticks": int(row["lag"]) + 2,
            "entry_edge_ticks": max(1.0, abs(float(row["loo_edge_mean"])) * 2.0),
            "position_limit": 10,
        }
        lead_records.append(rec)

    payload = {
        "meta": {
            "round": 5,
            "data_days": [2, 3, 4],
            "public_day_mapping": PUBLIC_DAY_LABEL,
            "position_limit": 10,
            "backtester_location": "prosperity_rust_backtester/",
            "backtest_command": "cd prosperity_rust_backtester && ./scripts/cargo_local.sh run --release -- --trader traders/latest_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id <run_id>",
            "data_location": "prosperity_rust_backtester/datasets/round5/",
            "notes": [
                "Research artifact only; not a final trader.",
                "Lead-lag OOS edge is a sign-prediction proxy on lagged one-tick returns.",
                "Basket and pair edges are residual-reversion proxies with leave-one-day-out validation.",
            ],
        },
        "pair_spreads": pair_records,
        "baskets": basket_records,
        "lead_lag_pairs": lead_records,
        "product_fair_value_formulas": fair_value_formulas,
        "top_mean_reversion_products": [clean_record(row) for _, row in diagnostics.sort_values("mean_reversion_score", ascending=False).head(20).iterrows()],
        "top_trend_products": [clean_record(row) for _, row in diagnostics.sort_values("trend_score", ascending=False).head(20).iterrows()],
        "avoid_products": [clean_record(row) for _, row in avoid_products.head(20).iterrows()],
        "avoid_categories": [clean_record(row) for _, row in avoid_categories.iterrows()],
    }
    (OUT / "alpha_candidates.json").write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def make_markdown(
    diagnostics: pd.DataFrame,
    correlations: pd.DataFrame,
    pair_candidates: pd.DataFrame,
    lead_candidates: pd.DataFrame,
    basket_candidates: pd.DataFrame,
    failed: pd.DataFrame,
    leaders: pd.DataFrame,
    laggards: pd.DataFrame,
    avoid_products: pd.DataFrame,
    avoid_categories: pd.DataFrame,
) -> None:
    pair_md = pair_candidates.head(30).copy()
    pair_md["pair"] = pair_md["product_a"] + " / " + pair_md["product_b"]
    pair_md["cats"] = pair_md["category_a"] + " / " + pair_md["category_b"]
    pair_cols = [
        "pair",
        "cats",
        "target",
        "hedge",
        "return_corr_mean",
        "rolling_return_corr_mean",
        "price_level_corr_mean",
        "spread_corr_mean",
        "loo_edge_mean",
        "loo_positive_days",
        "relationship_score",
    ]

    lead_md = lead_candidates.head(30).copy()
    lead_md["edge"] = lead_md["leader"] + " -> " + lead_md["follower"]
    lead_md["cats"] = lead_md["leader_category"] + " -> " + lead_md["follower_category"]
    lead_cols = [
        "edge",
        "cats",
        "lag",
        "day1_corr",
        "day2_corr",
        "day3_corr",
        "loo_edge_mean",
        "loo_positive_days",
        "train_day1_test_day2_3_edge",
        "train_day1_2_test_day3_edge",
        "beta_all_days",
    ]

    basket_md = basket_candidates.head(20).copy()
    basket_md["feature_preview"] = basket_md["features"].map(short_features)
    basket_cols = [
        "target",
        "category",
        "model_type",
        "feature_preview",
        "loo_edge_mean",
        "loo_positive_days",
        "loo_mr_ic_mean",
        "train_day1_2_test_day3_edge",
        "residual_std",
        "basket_score",
    ]

    mr_cols = [
        "product",
        "category",
        "mean_reversion_score",
        "mean_reversion_ic_h20",
        "ret_ac1",
        "ret_vol",
        "avg_spread",
        "trade_volume",
    ]
    trend_cols = [
        "product",
        "category",
        "trend_score",
        "drift_abs_mean_ticks",
        "drift_z_abs_mean",
        "trend_ic_50_20",
        "ret_vol",
        "avg_spread",
    ]

    leader_cols = ["leader", "leader_category", "edge_count", "unique_followers", "score_sum", "avg_oos_edge"]
    laggard_cols = ["follower", "follower_category", "edge_count", "unique_leaders", "score_sum", "avg_oos_edge"]

    cross_share_pairs = float(np.mean(pair_candidates.head(30)["same_category"] == False)) if not pair_candidates.empty else 0.0
    cross_share_leads = float(np.mean(lead_candidates.head(30)["same_category"] == False)) if not lead_candidates.empty else 0.0
    cross_share_baskets = float(
        np.mean(basket_candidates.head(20)["model_type"].isin(["cross_category_top8", "global_top8", "global_all_ridge"]))
    ) if not basket_candidates.empty else 0.0

    hypotheses = [
        "Use validated lead-lag as small fair-value nudges, not standalone max-size trades; require at least the reported lag history and suppress if the follower spread is too wide.",
        "Prioritize residual models with positive leave-one-day-out edge on at least two days and positive train-day1/day2-to-day3 validation; this is the strongest guard against day 1 red herrings.",
        "For pair and basket spreads, trade residual z-scores with entry around 1.25 and exit near 0.25; do not use raw level correlation as a trading rule.",
        "Cross-category candidates exist, but the report keeps same-category candidates when they validate better; strategy agents should compare both because all products share the same tight position limit.",
    ]

    lines = [
        "# Round 5 Global Alpha Map",
        "",
        "Generated from the bundled Round 5 public files. In this report, validation day 1/2/3 means public data day 2/3/4 respectively.",
        "",
        "## Repository Map",
        "",
        "- Rust backtester: `prosperity_rust_backtester/`.",
        "- Backtest command: `cd prosperity_rust_backtester && ./scripts/cargo_local.sh run --release -- --trader traders/latest_trader.py --dataset round5 --products full --artifact-mode full --flat --run-id <run_id>`.",
        "- Round 5 data: `prosperity_rust_backtester/datasets/round5/prices_round_5_day_{2,3,4}.csv` and `trades_round_5_day_{2,3,4}.csv`.",
        "- Current trader files: `prosperity_rust_backtester/traders/latest_trader.py`, `all_products_trader.py`, `limit_breach_trader.py`, plus untracked `final_round5_trader.py` and `final_round5_trader_expanded.py` in this workspace.",
        "- `datamodel.py`: the Rust backtester embeds it in `prosperity_rust_backtester/src/pytrader.rs`; the official reference copy is in `wiki/writing-an-algorithm-in-python.md` Appendix B. There is no standalone checked-in backtester `datamodel.py` file.",
        "- Supported final imports from the official wiki: standard Python 3.12 libraries plus `pandas`; current local traders use `from datamodel import Order, OrderDepth, TradingState`, `typing`, and `json`.",
        "- Final submission constraints to preserve: single Python file, under 100KB, correct Prosperity `datamodel` imports, 900ms `run` budget, `traderData` practical cap around 50,000 chars, and Round 5 position limit 10 for every product.",
        "",
        "## Scope Checks",
        "",
        f"- Products analyzed: `{len(diagnostics)}` across `{len(CATEGORIES)}` categories.",
        f"- Cross-category share among top pairs: `{cross_share_pairs:.0%}`.",
        f"- Cross-category share among top lead-lag edges: `{cross_share_leads:.0%}`.",
        f"- Global/cross-category share among top basket models: `{cross_share_baskets:.0%}`.",
        "- Trade CSV buyer/seller fields are blank, so counterparty-ID flow alpha is unavailable from public Round 5 files.",
        "",
        "## Top 30 Pair Relationships",
        "",
        md_table(pair_md, pair_cols, digits=4),
        "",
        "## Top 30 Lead-Lag Relationships",
        "",
        md_table(lead_md, lead_cols, digits=5),
        "",
        "## Top 20 Basket Residual Opportunities",
        "",
        md_table(basket_md, basket_cols, digits=4),
        "",
        "## Top 20 Mean-Reverting Products",
        "",
        md_table(diagnostics.sort_values("mean_reversion_score", ascending=False), mr_cols, max_rows=20, digits=4),
        "",
        "## Top 20 Drift/Trend Products",
        "",
        md_table(diagnostics.sort_values("trend_score", ascending=False), trend_cols, max_rows=20, digits=4),
        "",
        "## Relationships That Failed Validation",
        "",
        md_table(failed, ["type", "relationship", "reason", "in_sample_metric", "oos_metric", "positive_days"], max_rows=30, digits=5),
        "",
        "## Leaders",
        "",
        md_table(leaders, leader_cols, max_rows=15, digits=5),
        "",
        "## Laggards",
        "",
        md_table(laggards, laggard_cols, max_rows=15, digits=5),
        "",
        "## Products And Categories To Avoid",
        "",
        "Categories with little validated alpha mass or worse liquidity:",
        "",
        md_table(avoid_categories, ["category", "validated_alpha_score", "avoid_score", "liquidity_score", "avg_spread"], max_rows=10, digits=4),
        "",
        "Product-level avoid list:",
        "",
        md_table(avoid_products, ["product", "category", "avoid_score", "validated_alpha_score", "liquidity_score", "avg_spread", "reason"], max_rows=20, digits=4),
        "",
        "## Best Alpha Hypotheses",
        "",
    ]
    lines.extend(f"- {hypothesis}" for hypothesis in hypotheses)
    lines.extend(
        [
            "",
            "## Supporting Tables",
            "",
            "- `product_diagnostics.csv` and `product_diagnostics_by_day.csv`",
            "- `cross_product_correlations.csv`",
            "- `lead_lag_relationships.csv`",
            "- `pair_spread_models.csv`",
            "- `basket_models.csv`",
            "- `failed_validation.csv`, `leaders.csv`, `laggards.csv`",
            "- `alpha_candidates.json` for machine-readable strategy-agent handoff",
        ]
    )
    (OUT / "ALPHA_MAP.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices = load_prices()
    trades = load_trades()
    mids = pivot_by_day(prices, "mid_price")
    spreads = pivot_by_day(prices, "spread")
    products = ordered_products(mids)
    mids = {day: frame[products] for day, frame in mids.items()}
    spreads = {day: frame[products] for day, frame in spreads.items()}
    returns = build_return_frames(mids, products)

    diagnostics, _ = product_diagnostics(prices, trades)
    correlations = cross_product_correlations(mids, spreads, returns, products)
    pairs = pair_spread_models(mids, correlations, products)
    lead_lag = lead_lag_relationships(returns, products)
    baskets = basket_models(mids, returns, diagnostics, products)

    pair_candidates = validated_pairs(pairs)
    lead_candidates = validated_lead_lag(lead_lag)
    basket_candidates = validated_baskets(baskets)
    failed = failed_validation(lead_lag, baskets, pairs, correlations)
    leaders, laggards = leader_laggard_tables(lead_candidates)
    avoid_products, avoid_categories = avoid_tables(diagnostics, pair_candidates, lead_candidates, basket_candidates)

    make_json_candidates(pair_candidates, basket_candidates, lead_candidates, diagnostics, avoid_products, avoid_categories)
    make_markdown(
        diagnostics,
        correlations,
        pair_candidates,
        lead_candidates,
        basket_candidates,
        failed,
        leaders,
        laggards,
        avoid_products,
        avoid_categories,
    )
    print(f"wrote {OUT / 'ALPHA_MAP.md'}")
    print(f"wrote {OUT / 'alpha_candidates.json'}")


if __name__ == "__main__":
    main()
