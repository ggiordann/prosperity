from __future__ import annotations

import itertools
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
PRODUCTS = [
    "ROBOT_VACUUMING",
    "ROBOT_MOPPING",
    "ROBOT_DISHES",
    "ROBOT_LAUNDRY",
    "ROBOT_IRONING",
]


def load_prices() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frame = pd.read_csv(path, sep=";")
        frame = frame[frame["product"].isin(PRODUCTS)].copy()
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["best_bid_vol"] = df["bid_volume_1"].abs()
    df["best_ask_vol"] = df["ask_volume_1"].abs()
    df["top_depth"] = df["best_bid_vol"] + df["best_ask_vol"]
    df["imbalance"] = (df["best_bid_vol"] - df["best_ask_vol"]) / df["top_depth"].replace(0, np.nan)
    return df


def load_trades() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("trades_round_5_day_*.csv")):
        frame = pd.read_csv(path, sep=";")
        frame = frame[frame["symbol"].isin(PRODUCTS)].copy()
        frame["day"] = int(path.stem.rsplit("_", 1)[1])
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def pivot(df: pd.DataFrame, column: str) -> dict[int, pd.DataFrame]:
    return {
        int(day): group.pivot(index="timestamp", columns="product", values=column).sort_index()
        for day, group in df.groupby("day")
    }


def corr(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3 or np.nanstd(x) == 0 or np.nanstd(y) == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def half_life(series: np.ndarray) -> float:
    y = np.diff(series)
    x = series[:-1] - np.mean(series[:-1])
    if len(x) < 20 or np.std(x) == 0:
        return float("nan")
    beta = float(np.linalg.lstsq(x[:, None], y, rcond=None)[0][0])
    if beta >= 0:
        return float("inf")
    return float(-math.log(2) / beta)


def adf_t(values: np.ndarray) -> float:
    series = np.asarray(values, dtype=float)
    diff = np.diff(series)
    lagged = series[:-1]
    if len(diff) < 50 or np.std(lagged) == 0:
        return float("nan")
    x = np.column_stack([np.ones(len(diff)), lagged])
    coef, *_ = np.linalg.lstsq(x, diff, rcond=None)
    resid = diff - x @ coef
    dof = len(diff) - x.shape[1]
    if dof <= 0:
        return float("nan")
    sigma2 = float(resid @ resid) / dof
    cov = sigma2 * np.linalg.pinv(x.T @ x)
    se = float(np.sqrt(max(cov[1, 1], 0.0)))
    return float(coef[1] / se) if se else float("nan")


def product_metrics(prices: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    volume = trades.groupby(["day", "symbol"])["quantity"].sum()
    count = trades.groupby(["day", "symbol"])["quantity"].size()
    rows = []
    for (day, product), group in prices.groupby(["day", "product"]):
        mid = group["mid_price"].to_numpy(float)
        ret = np.diff(mid)
        ac1 = corr(ret[:-1], ret[1:])
        fwd10 = mid[10:] - mid[:-10]
        trend10 = corr(ret[: len(fwd10)], fwd10) if len(ret) > 20 else float("nan")
        rows.append(
            {
                "day": int(day),
                "product": product,
                "mid_start": mid[0],
                "mid_end": mid[-1],
                "net_move": mid[-1] - mid[0],
                "vol": np.std(ret),
                "abs_ret": np.mean(np.abs(ret)),
                "autocorr1": ac1,
                "mean_reversion_score": -ac1,
                "momentum10_score": trend10,
                "spread": group["spread"].mean(),
                "top_depth": group["top_depth"].mean(),
                "trade_volume": int(volume.get((day, product), 0)),
                "trade_count": int(count.get((day, product), 0)),
                "jump95": np.quantile(np.abs(ret), 0.95),
                "jump99": np.quantile(np.abs(ret), 0.99),
                "adf_t": adf_t(mid),
                "mm_feasible": group["spread"].mean() >= 2.0 and group["top_depth"].mean() >= 14.0,
                "cross_feasible": np.quantile(np.abs(ret), 0.95) > group["spread"].mean(),
            }
        )
    return pd.DataFrame(rows)


def lead_lag(mids: dict[int, pd.DataFrame], max_lag: int = 100) -> pd.DataFrame:
    rows = []
    for day, frame in mids.items():
        ret = frame[PRODUCTS].diff().fillna(0.0)
        for leader, follower in itertools.permutations(PRODUCTS, 2):
            for lag in range(1, max_lag + 1):
                value = corr(ret[leader].to_numpy()[:-lag], ret[follower].to_numpy()[lag:])
                if np.isfinite(value):
                    rows.append((day, leader, follower, lag, value))
    raw = pd.DataFrame(rows, columns=["day", "leader", "follower", "lag", "corr"])
    grouped = (
        raw.groupby(["leader", "follower", "lag"])
        .agg(mean=("corr", "mean"), min=("corr", "min"), max=("corr", "max"), std=("corr", "std"), days=("corr", "size"))
        .reset_index()
    )
    grouped["stable_sign"] = grouped["min"] * grouped["max"] > 0
    grouped["score"] = grouped["mean"].abs() * grouped["days"] / (1.0 + grouped["std"].fillna(0) * 10.0)
    return grouped.sort_values(["stable_sign", "score"], ascending=[False, False])


def pair_stats(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    panel = pd.concat([mids[day] for day in sorted(mids)], ignore_index=True)
    rows = []
    for a, b in itertools.combinations(PRODUCTS, 2):
        x = panel[a].to_numpy(float)
        y = panel[b].to_numpy(float)
        beta = float(np.cov(x, y, ddof=0)[0, 1] / np.var(y)) if np.var(y) else 0.0
        intercept = float(np.mean(x) - beta * np.mean(y))
        resid = x - (intercept + beta * y)
        spread = x - y
        rows.append(
            {
                "a": a,
                "b": b,
                "price_corr": corr(x, y),
                "return_corr": corr(np.diff(x), np.diff(y)),
                "spread_std": np.std(spread),
                "spread_adf": adf_t(spread),
                "spread_half_life": half_life(spread),
                "hedge_beta": beta,
                "resid_std": np.std(resid),
                "resid_adf": adf_t(resid),
                "resid_half_life": half_life(resid),
            }
        )
    return pd.DataFrame(rows).sort_values(["resid_adf", "spread_adf"])


def basket_cv(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for target in PRODUCTS:
        features = [p for p in PRODUCTS if p != target]
        for test_day in sorted(mids):
            train_days = [d for d in sorted(mids) if d != test_day]
            x_train = pd.concat([mids[d][features] for d in train_days]).to_numpy(float)
            y_train = pd.concat([mids[d][target] for d in train_days]).to_numpy(float)
            x_test = mids[test_day][features].to_numpy(float)
            y_test = mids[test_day][target].to_numpy(float)
            mu_x = x_train.mean(axis=0)
            sd_x = x_train.std(axis=0)
            sd_x[sd_x == 0] = 1.0
            mu_y = y_train.mean()
            xs = (x_train - mu_x) / sd_x
            lam = 2.0
            beta_s = np.linalg.solve(xs.T @ xs + lam * np.eye(xs.shape[1]), xs.T @ (y_train - mu_y))
            beta = beta_s / sd_x
            intercept = mu_y - mu_x @ beta
            resid = y_test - (intercept + x_test @ beta)
            rows.append(
                {
                    "target": target,
                    "test_day": test_day,
                    "mae": np.mean(np.abs(resid)),
                    "std": np.std(resid),
                    "resid_ac1": corr(resid[:-1], resid[1:]),
                    "resid_adf": adf_t(resid),
                }
            )
    return pd.DataFrame(rows)


def imbalance_alpha(mids: dict[int, pd.DataFrame], imbs: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for day in mids:
        future = {h: mids[day][PRODUCTS].shift(-h) - mids[day][PRODUCTS] for h in [1, 5, 20, 100]}
        for signal_product, target in itertools.product(PRODUCTS, PRODUCTS):
            x = imbs[day][signal_product].fillna(0.0).to_numpy(float)
            for horizon, fr in future.items():
                y = fr[target].fillna(0.0).to_numpy(float)
                rows.append((day, signal_product, target, horizon, corr(x[:-horizon], y[:-horizon])))
    raw = pd.DataFrame(rows, columns=["day", "signal", "target", "horizon", "corr"])
    return (
        raw.groupby(["signal", "target", "horizon"])
        .agg(mean=("corr", "mean"), min=("corr", "min"), max=("corr", "max"), days=("corr", "size"))
        .reset_index()
        .sort_values("mean", key=lambda col: col.abs(), ascending=False)
    )


def main() -> None:
    prices = load_prices()
    trades = load_trades()
    mids = pivot(prices, "mid_price")
    imbs = pivot(prices, "imbalance")
    metrics = product_metrics(prices, trades)
    print("PRODUCT METRICS BY DAY")
    print(metrics.round(4).to_string(index=False))
    print("\nPRODUCT METRICS AGG")
    print(metrics.groupby("product").mean(numeric_only=True).round(4).to_string())
    print("\nPRICE CORR")
    print((sum(frame[PRODUCTS].corr() for frame in mids.values()) / len(mids)).round(4).to_string())
    print("\nRETURN CORR")
    print((sum(frame[PRODUCTS].diff().dropna().corr() for frame in mids.values()) / len(mids)).round(4).to_string())
    print("\nLEAD LAG TOP STABLE 1..100")
    print(lead_lag(mids).head(30).round(5).to_string(index=False))
    print("\nPAIR STATS")
    print(pair_stats(mids).round(4).to_string(index=False))
    print("\nBASKET CV")
    print(basket_cv(mids).groupby("target").mean(numeric_only=True).round(4).to_string())
    print("\nIMBALANCE ALPHA TOP")
    print(imbalance_alpha(mids, imbs).head(30).round(5).to_string(index=False))


if __name__ == "__main__":
    main()
