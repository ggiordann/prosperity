from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5" / "pebbles"
P = ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"]


def load_prices() -> pd.DataFrame:
    cols = [
        "day",
        "timestamp",
        "product",
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
    ]
    frames = []
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frame = pd.read_csv(path, sep=";", usecols=cols)
        frames.append(frame[frame["product"].isin(P)].copy())
    df = pd.concat(frames, ignore_index=True)
    for i in (1, 2, 3):
        df[f"bv{i}"] = df[f"bid_volume_{i}"].fillna(0).abs()
        df[f"av{i}"] = df[f"ask_volume_{i}"].fillna(0).abs()
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["top_depth"] = df["bv1"] + df["av1"]
    df["book_depth"] = df[["bv1", "bv2", "bv3", "av1", "av2", "av3"]].sum(axis=1)
    df["top_imbalance"] = (df["bv1"] - df["av1"]) / df["top_depth"].replace(0, np.nan)
    df["book_imbalance"] = (df[["bv1", "bv2", "bv3"]].sum(axis=1) - df[["av1", "av2", "av3"]].sum(axis=1)) / df[
        "book_depth"
    ].replace(0, np.nan)
    return df


def load_trades() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("trades_round_5_day_*.csv")):
        day = int(path.stem.rsplit("_", 1)[1])
        frame = pd.read_csv(path, sep=";")
        frame = frame[frame["symbol"].isin(P)].copy()
        frame["day"] = day
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def pivots(prices: pd.DataFrame) -> dict[int, pd.DataFrame]:
    return {int(day): group.pivot(index="timestamp", columns="product", values="mid_price")[P] for day, group in prices.groupby("day")}


def corr(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 20 or np.std(x[mask]) == 0 or np.std(y[mask]) == 0:
        return float("nan")
    return float(np.corrcoef(x[mask], y[mask])[0, 1])


def adf_t(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 50 or np.std(x) == 0:
        return float("nan")
    y = np.diff(x)
    lag = x[:-1]
    X = np.column_stack([lag, np.ones(len(lag))])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(1, len(y) - X.shape[1])
    sigma2 = float((resid @ resid) / dof)
    inv = np.linalg.pinv(X.T @ X)
    se = float(np.sqrt(max(0.0, sigma2 * inv[0, 0])))
    return float(beta[0] / se) if se > 0 else float("nan")


def half_life(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 50 or np.std(x) == 0:
        return float("nan")
    y = np.diff(x)
    lag = x[:-1] - np.mean(x[:-1])
    beta = float((lag @ y) / max(lag @ lag, 1e-12))
    if beta >= 0:
        return float("inf")
    return float(-np.log(2) / beta)


def product_diagnostics(prices: pd.DataFrame, trades: pd.DataFrame) -> None:
    tv = trades.groupby(["day", "symbol"])["quantity"].sum()
    tc = trades.groupby(["day", "symbol"]).size()
    rows = []
    for (day, product), group in prices.groupby(["day", "product"]):
        mid = group["mid_price"].to_numpy(float)
        ret = np.diff(mid)
        ac1 = corr(ret[:-1], ret[1:])
        mom20 = corr(mid[20:-20] - mid[:-40], mid[40:] - mid[20:-20]) if len(mid) > 50 else float("nan")
        rows.append(
            {
                "day": int(day),
                "product": product,
                "first_mid": mid[0],
                "last_mid": mid[-1],
                "mean_mid": float(np.mean(mid)),
                "min_mid": float(np.min(mid)),
                "max_mid": float(np.max(mid)),
                "ret_vol": float(np.std(ret)),
                "abs_ret_mean": float(np.mean(np.abs(ret))),
                "return_ac1": ac1,
                "mean_reversion_score": -ac1,
                "momentum_score_20": mom20,
                "avg_spread": float(group["spread"].mean()),
                "median_spread": float(group["spread"].median()),
                "avg_top_depth": float(group["top_depth"].mean()),
                "avg_book_depth": float(group["book_depth"].mean()),
                "jump_95": float(np.quantile(np.abs(ret), 0.95)),
                "jump_99": float(np.quantile(np.abs(ret), 0.99)),
                "adf_mid_t": adf_t(mid),
                "adf_return_t": adf_t(ret),
                "trade_count": int(tc.get((day, product), 0)),
                "trade_volume": int(tv.get((day, product), 0)),
                "passive_mm_feasible": bool(group["spread"].mean() >= 8 and group["top_depth"].mean() >= 20),
                "aggressive_crossing_feasible": bool(np.quantile(np.abs(ret), 0.95) > group["spread"].mean()),
            }
        )
    by_day = pd.DataFrame(rows)
    by_day.to_csv(OUT / "product_diagnostics_by_day.csv", index=False)
    agg = (
        by_day.groupby("product")
        .agg(
            mean_mid=("mean_mid", "mean"),
            ret_vol=("ret_vol", "mean"),
            abs_ret_mean=("abs_ret_mean", "mean"),
            return_ac1=("return_ac1", "mean"),
            mean_reversion_score=("mean_reversion_score", "mean"),
            momentum_score_20=("momentum_score_20", "mean"),
            avg_spread=("avg_spread", "mean"),
            avg_top_depth=("avg_top_depth", "mean"),
            avg_book_depth=("avg_book_depth", "mean"),
            jump_95=("jump_95", "mean"),
            jump_99=("jump_99", "mean"),
            adf_mid_t=("adf_mid_t", "mean"),
            trade_count=("trade_count", "sum"),
            trade_volume=("trade_volume", "sum"),
            passive_mm_feasible=("passive_mm_feasible", "mean"),
            aggressive_crossing_feasible=("aggressive_crossing_feasible", "mean"),
        )
        .reset_index()
    )
    agg.to_csv(OUT / "product_diagnostics.csv", index=False)


def curve_diagnostics(mids: dict[int, pd.DataFrame]) -> None:
    rows = []
    for day, pivot in mids.items():
        total = pivot.sum(axis=1)
        row = {
            "day": day,
            "sum_mean": float(total.mean()),
            "sum_std": float(total.std()),
            "sum_min": float(total.min()),
            "sum_max": float(total.max()),
            "strict_size_order_pct": float(((pivot["PEBBLES_XS"] < pivot["PEBBLES_S"]) & (pivot["PEBBLES_S"] < pivot["PEBBLES_M"]) & (pivot["PEBBLES_M"] < pivot["PEBBLES_L"]) & (pivot["PEBBLES_L"] < pivot["PEBBLES_XL"])).mean()),
            "adf_sum_t": adf_t(total),
            "sum_half_life": half_life(total),
        }
        for a, b in zip(P, P[1:]):
            row[f"{a}_lt_{b}_pct"] = float((pivot[a] < pivot[b]).mean())
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "curve_diagnostics.csv", index=False)


def correlation_tables(mids: dict[int, pd.DataFrame]) -> None:
    rows = []
    for day, pivot in mids.items():
        returns = pivot.diff().dropna()
        for a, b in itertools.combinations(P, 2):
            rows.append(
                {
                    "day": day,
                    "a": a,
                    "b": b,
                    "price_corr": float(pivot[a].corr(pivot[b])),
                    "return_corr": float(returns[a].corr(returns[b])),
                }
            )
    pd.DataFrame(rows).to_csv(OUT / "correlation_by_day.csv", index=False)


def lead_lag(mids: dict[int, pd.DataFrame]) -> None:
    lags = list(range(1, 101)) + [150, 200, 300, 500]
    horizons = [1, 5, 20, 100]
    rows = []
    for horizon in horizons:
        for leader, target in itertools.permutations(P, 2):
            for lag in lags:
                vals = []
                for day, pivot in mids.items():
                    signal = (pivot[leader] - pivot[leader].shift(lag)).to_numpy()
                    future = (pivot[target].shift(-horizon) - pivot[target]).to_numpy()
                    vals.append(corr(signal[lag : len(pivot) - horizon], future[lag : len(pivot) - horizon]))
                clean = [v for v in vals if np.isfinite(v)]
                if len(clean) == 3:
                    rows.append(
                        {
                            "horizon": horizon,
                            "leader": leader,
                            "target": target,
                            "lag": lag,
                            "mean_corr": float(np.mean(clean)),
                            "min_corr": float(np.min(clean)),
                            "max_corr": float(np.max(clean)),
                            "positive_days": int(sum(v > 0 for v in clean)),
                        }
                    )
    out = pd.DataFrame(rows)
    out["abs_mean_corr"] = out["mean_corr"].abs()
    out.sort_values(["positive_days", "abs_mean_corr"], ascending=[False, False]).to_csv(OUT / "lead_lag_summary.csv", index=False)


def pair_spreads(mids: dict[int, pd.DataFrame]) -> None:
    rows = []
    for a, b in itertools.combinations(P, 2):
        for day, pivot in mids.items():
            spread = (pivot[a] - pivot[b]).to_numpy()
            ds = np.diff(spread)
            z = (spread - np.mean(spread)) / max(np.std(spread), 1e-12)
            rows.append(
                {
                    "day": day,
                    "a": a,
                    "b": b,
                    "spread_mean": float(np.mean(spread)),
                    "spread_std": float(np.std(spread)),
                    "adf_t": adf_t(spread),
                    "half_life": half_life(spread),
                    "z_reversion_corr_20": corr(z[:-20], -(spread[20:] - spread[:-20])),
                    "return_corr": corr(np.diff(pivot[a].to_numpy()), np.diff(pivot[b].to_numpy())),
                }
            )
    pd.DataFrame(rows).to_csv(OUT / "pair_spread_summary.csv", index=False)


def basket_regressions(mids: dict[int, pd.DataFrame]) -> None:
    rows = []
    for target in P:
        others = [p for p in P if p != target]
        for train_day, train in mids.items():
            X = np.column_stack([train[p].to_numpy() for p in others] + [np.ones(len(train))])
            y = train[target].to_numpy()
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            train_resid = y - X @ beta
            for test_day, test in mids.items():
                if test_day == train_day:
                    continue
                Xt = np.column_stack([test[p].to_numpy() for p in others] + [np.ones(len(test))])
                yt = test[target].to_numpy()
                resid = yt - Xt @ beta
                rows.append(
                    {
                        "target": target,
                        "train_day": train_day,
                        "test_day": test_day,
                        "coef_json": dict(zip(others + ["intercept"], [round(float(v), 6) for v in beta])),
                        "train_resid_std": float(np.std(train_resid)),
                        "test_resid_std": float(np.std(resid)),
                        "test_adf_t": adf_t(resid),
                        "test_half_life": half_life(resid),
                        "test_z_reversion_corr_20": corr((resid[:-20] - np.mean(resid)) / max(np.std(resid), 1e-12), -(resid[20:] - resid[:-20])),
                    }
                )
    pd.DataFrame(rows).to_csv(OUT / "basket_regression_summary.csv", index=False)


def orderbook_signals(prices: pd.DataFrame, mids: dict[int, pd.DataFrame]) -> None:
    rows = []
    for horizon in [1, 5, 20, 100]:
        for signal_product, target in itertools.product(P, P):
            vals = {"top_imbalance": [], "book_imbalance": [], "spread": []}
            for day, group in prices.groupby("day"):
                sg = group[group["product"] == signal_product].sort_values("timestamp")
                future = (mids[int(day)][target].shift(-horizon) - mids[int(day)][target]).to_numpy()
                for col in vals:
                    x = sg[col].to_numpy()[:-horizon]
                    y = future[:-horizon]
                    vals[col].append(corr(x, y))
            rows.append(
                {
                    "horizon": horizon,
                    "signal_product": signal_product,
                    "target": target,
                    "top_imbalance_corr": float(np.nanmean(vals["top_imbalance"])),
                    "top_imbalance_positive_days": int(sum(v > 0 for v in vals["top_imbalance"] if np.isfinite(v))),
                    "book_imbalance_corr": float(np.nanmean(vals["book_imbalance"])),
                    "book_imbalance_positive_days": int(sum(v > 0 for v in vals["book_imbalance"] if np.isfinite(v))),
                    "spread_corr": float(np.nanmean(vals["spread"])),
                    "spread_positive_days": int(sum(v > 0 for v in vals["spread"] if np.isfinite(v))),
                }
            )
    pd.DataFrame(rows).to_csv(OUT / "orderbook_signal_summary.csv", index=False)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices = load_prices()
    trades = load_trades()
    mids = pivots(prices)
    product_diagnostics(prices, trades)
    curve_diagnostics(mids)
    correlation_tables(mids)
    lead_lag(mids)
    pair_spreads(mids)
    basket_regressions(mids)
    orderbook_signals(prices, mids)
    print(f"wrote Pebbles diagnostics to {OUT}")


if __name__ == "__main__":
    main()
