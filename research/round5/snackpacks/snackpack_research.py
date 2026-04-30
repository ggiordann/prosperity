from __future__ import annotations

import json
import math
from itertools import combinations, permutations
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
PRODUCTS = [
    "SNACKPACK_CHOCOLATE",
    "SNACKPACK_VANILLA",
    "SNACKPACK_PISTACHIO",
    "SNACKPACK_STRAWBERRY",
    "SNACKPACK_RASPBERRY",
]
DAYS = [2, 3, 4]


def load_prices() -> pd.DataFrame:
    frames = []
    for day in DAYS:
        df = pd.read_csv(DATA / f"prices_round_5_day_{day}.csv", sep=";")
        df = df[df["product"].isin(PRODUCTS)].copy()
        df["day"] = day
        frames.append(df)
    out = pd.concat(frames, ignore_index=True)
    out["best_bid"] = out["bid_price_1"]
    out["best_ask"] = out["ask_price_1"]
    out["spread"] = out["best_ask"] - out["best_bid"]
    out["top_depth"] = out["bid_volume_1"].fillna(0) + out["ask_volume_1"].fillna(0).abs()
    bid_depth = sum(out.get(f"bid_volume_{i}", 0).fillna(0) for i in range(1, 4))
    ask_depth = sum(out.get(f"ask_volume_{i}", 0).fillna(0).abs() for i in range(1, 4))
    out["book_depth"] = bid_depth + ask_depth
    out["top_imbalance"] = (
        (out["bid_volume_1"].fillna(0) - out["ask_volume_1"].fillna(0).abs())
        / out["top_depth"].replace(0, np.nan)
    )
    out["total_imbalance"] = ((bid_depth - ask_depth) / out["book_depth"].replace(0, np.nan)).fillna(0.0)
    out = out.sort_values(["day", "timestamp", "product"])
    return out


def load_trades() -> pd.DataFrame:
    frames = []
    for day in DAYS:
        path = DATA / f"trades_round_5_day_{day}.csv"
        df = pd.read_csv(path, sep=";")
        df = df[df["symbol"].isin(PRODUCTS)].copy()
        df["day"] = day
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["day", "timestamp", "symbol", "price", "quantity"])
    return pd.concat(frames, ignore_index=True)


def wide_mid(prices: pd.DataFrame) -> pd.DataFrame:
    w = prices.pivot_table(index=["day", "timestamp"], columns="product", values="mid_price")
    return w.sort_index()


def by_day_series(wide: pd.DataFrame, day: int) -> pd.DataFrame:
    return wide.loc[day].sort_index()


def autocorr(values: np.ndarray, lag: int = 1) -> float:
    if len(values) <= lag + 2:
        return float("nan")
    a = values[:-lag]
    b = values[lag:]
    if np.std(a) == 0 or np.std(b) == 0:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def ols(y: np.ndarray, x: np.ndarray) -> tuple[float, np.ndarray, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    pred = x @ beta
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 0.0
    return float(beta[-1]) if x.shape[1] > 1 else float(beta[0]), pred, r2


def ar1_half_life(series: np.ndarray) -> tuple[float, float]:
    s = np.asarray(series, dtype=float)
    s = s[np.isfinite(s)]
    if len(s) < 20:
        return float("nan"), float("nan")
    y = s[1:]
    x = np.column_stack([np.ones(len(s) - 1), s[:-1]])
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    phi = float(beta[1])
    if 0 < phi < 1:
        half_life = -math.log(2.0) / math.log(phi)
    else:
        half_life = float("inf")
    return phi, half_life


def zero_cross_rate(series: np.ndarray) -> float:
    s = np.asarray(series, dtype=float)
    s = s - np.nanmean(s)
    if len(s) < 2:
        return 0.0
    return float(np.mean(np.signbit(s[1:]) != np.signbit(s[:-1])))


def product_metrics(prices: pd.DataFrame, trades: pd.DataFrame) -> list[dict]:
    rows = []
    tvol = trades.groupby(["day", "symbol"])["quantity"].sum()
    tcount = trades.groupby(["day", "symbol"])["quantity"].count()
    for product in PRODUCTS:
        pdf = prices[prices["product"] == product].sort_values(["day", "timestamp"])
        rets = pdf.groupby("day")["mid_price"].diff().dropna()
        rows.append(
            {
                "product": product,
                "mid_mean": pdf["mid_price"].mean(),
                "mid_std": pdf["mid_price"].std(),
                "vol": rets.std(),
                "abs_ret_mean": rets.abs().mean(),
                "ret_ac1": autocorr(rets.to_numpy(), 1),
                "ret_ac5": autocorr(rets.to_numpy(), 5),
                "ret_ac20": autocorr(rets.to_numpy(), 20),
                "avg_spread": pdf["spread"].mean(),
                "spread_p90": pdf["spread"].quantile(0.9),
                "avg_top_depth": pdf["top_depth"].mean(),
                "avg_book_depth": pdf["book_depth"].mean(),
                "jump_95": rets.abs().quantile(0.95),
                "jump_99": rets.abs().quantile(0.99),
                "trade_volume": int(sum(tvol.get((d, product), 0) for d in DAYS)),
                "trade_count": int(sum(tcount.get((d, product), 0) for d in DAYS)),
                "level_ar1": ar1_half_life(pdf["mid_price"].to_numpy())[0],
                "level_half_life": ar1_half_life(pdf["mid_price"].to_numpy())[1],
            }
        )
    return rows


def day_product_metrics(prices: pd.DataFrame, trades: pd.DataFrame) -> list[dict]:
    rows = []
    tvol = trades.groupby(["day", "symbol"])["quantity"].sum()
    tcount = trades.groupby(["day", "symbol"])["quantity"].count()
    for day in DAYS:
        for product in PRODUCTS:
            pdf = prices[(prices["day"] == day) & (prices["product"] == product)].sort_values("timestamp")
            rets = pdf["mid_price"].diff().dropna()
            rows.append(
                {
                    "day": day,
                    "product": product,
                    "start": pdf["mid_price"].iloc[0],
                    "end": pdf["mid_price"].iloc[-1],
                    "move": pdf["mid_price"].iloc[-1] - pdf["mid_price"].iloc[0],
                    "vol": rets.std(),
                    "ret_ac1": autocorr(rets.to_numpy(), 1),
                    "avg_spread": pdf["spread"].mean(),
                    "avg_top_depth": pdf["top_depth"].mean(),
                    "trade_volume": int(tvol.get((day, product), 0)),
                    "trade_count": int(tcount.get((day, product), 0)),
                }
            )
    return rows


def correlations(wide: pd.DataFrame) -> dict:
    all_price_corr = wide.corr()
    all_ret_corr = wide.groupby(level=0).diff().dropna().corr()
    by_day = {}
    roll = {}
    for day in DAYS:
        day_mid = by_day_series(wide, day)
        day_ret = day_mid.diff().dropna()
        by_day[str(day)] = {
            "price": day_mid.corr().round(4).to_dict(),
            "return": day_ret.corr().round(4).to_dict(),
        }
        rolling_rows = []
        for a, b in combinations(PRODUCTS, 2):
            r = day_ret[a].rolling(500).corr(day_ret[b]).dropna()
            rolling_rows.append(
                {
                    "pair": f"{a}/{b}",
                    "mean": float(r.mean()) if len(r) else float("nan"),
                    "min": float(r.min()) if len(r) else float("nan"),
                    "max": float(r.max()) if len(r) else float("nan"),
                }
            )
        roll[str(day)] = rolling_rows
    return {
        "price_corr": all_price_corr.round(4).to_dict(),
        "return_corr": all_ret_corr.round(4).to_dict(),
        "by_day": by_day,
        "rolling": roll,
    }


def lead_lag_scan(wide: pd.DataFrame, max_lag: int = 100) -> list[dict]:
    lags = list(range(1, max_lag + 1)) + [150, 200, 300, 500]
    horizons = [1, 2, 5, 10, 20, 50, 100]
    rows = []
    for follower, leader in permutations(PRODUCTS, 2):
        for lag in lags:
            for horizon in horizons:
                day_corrs = []
                day_signs = []
                nobs = []
                for day in DAYS:
                    mid = by_day_series(wide, day)
                    signal = mid[leader] - mid[leader].shift(lag)
                    target = mid[follower].shift(-horizon) - mid[follower]
                    aligned = pd.concat([signal, target], axis=1).dropna()
                    nobs.append(len(aligned))
                    if len(aligned) < 100 or aligned.iloc[:, 0].std() == 0 or aligned.iloc[:, 1].std() == 0:
                        day_corrs.append(np.nan)
                        day_signs.append(0)
                    else:
                        c = float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
                        day_corrs.append(c)
                        day_signs.append(1 if c > 0 else -1 if c < 0 else 0)
                finite = [c for c in day_corrs if np.isfinite(c)]
                if not finite:
                    continue
                pos = sum(c > 0 for c in finite)
                neg = sum(c < 0 for c in finite)
                same = max(pos, neg)
                rows.append(
                    {
                        "follower": follower,
                        "leader": leader,
                        "lag": lag,
                        "horizon": horizon,
                        "mean_corr": float(np.nanmean(day_corrs)),
                        "min_abs_corr": float(np.nanmin(np.abs(day_corrs))),
                        "sign": 1 if pos >= neg else -1,
                        "same_sign_days": same,
                        "day_corrs": [None if not np.isfinite(c) else round(float(c), 5) for c in day_corrs],
                        "nobs": nobs,
                        "score": same * 10 + abs(float(np.nanmean(day_corrs))),
                    }
                )
    rows.sort(key=lambda r: (r["same_sign_days"], abs(r["mean_corr"]), r["min_abs_corr"]), reverse=True)
    return rows


def pair_spreads(wide: pd.DataFrame) -> list[dict]:
    rows = []
    for y_name, x_name in permutations(PRODUCTS, 2):
        y = wide[y_name].to_numpy(dtype=float)
        x = wide[x_name].to_numpy(dtype=float)
        mat = np.column_stack([np.ones(len(x)), x])
        _, pred, r2 = ols(y, mat)
        spread = y - pred
        phi, hl = ar1_half_life(spread)
        by_day_std = []
        by_day_phi = []
        for day in DAYS:
            mid = by_day_series(wide, day)
            yd = mid[y_name].to_numpy(dtype=float)
            xd = mid[x_name].to_numpy(dtype=float)
            beta, pred_d, r2d = ols(yd, np.column_stack([np.ones(len(xd)), xd]))
            sd = yd - pred_d
            by_day_std.append(float(np.std(sd)))
            by_day_phi.append(ar1_half_life(sd)[0])
        rows.append(
            {
                "y": y_name,
                "x": x_name,
                "r2": r2,
                "beta": float(np.linalg.lstsq(mat, y, rcond=None)[0][1]),
                "spread_std": float(np.std(spread)),
                "spread_ar1": phi,
                "half_life": hl,
                "zero_cross": zero_cross_rate(spread),
                "day_std": [round(v, 3) for v in by_day_std],
                "day_ar1": [round(v, 5) for v in by_day_phi],
            }
        )
    rows.sort(key=lambda r: (r["r2"], -r["half_life"]), reverse=True)
    return rows


def basket_models(wide: pd.DataFrame) -> list[dict]:
    rows = []
    for target in PRODUCTS:
        xs = [p for p in PRODUCTS if p != target]
        y = wide[target].to_numpy(dtype=float)
        x = wide[xs].to_numpy(dtype=float)
        x = np.column_stack([np.ones(len(x)), x])
        beta, *_ = np.linalg.lstsq(x, y, rcond=None)
        pred = x @ beta
        residual = y - pred
        phi, hl = ar1_half_life(residual)
        fold = []
        for test_day in DAYS:
            train_days = [d for d in DAYS if d != test_day]
            train = wide.loc[train_days]
            test = wide.loc[test_day]
            xt = np.column_stack([np.ones(len(train)), train[xs].to_numpy(dtype=float)])
            yt = train[target].to_numpy(dtype=float)
            b, *_ = np.linalg.lstsq(xt, yt, rcond=None)
            xv = np.column_stack([np.ones(len(test)), test[xs].to_numpy(dtype=float)])
            yv = test[target].to_numpy(dtype=float)
            predv = xv @ b
            ss_res = float(np.sum((yv - predv) ** 2))
            ss_tot = float(np.sum((yv - yv.mean()) ** 2))
            r2 = 1.0 - ss_res / ss_tot if ss_tot else 0.0
            fold.append({"test_day": test_day, "r2": r2, "resid_std": float(np.std(yv - predv))})
        rows.append(
            {
                "target": target,
                "r2_all": float(1.0 - np.sum(residual**2) / np.sum((y - y.mean()) ** 2)),
                "resid_std": float(np.std(residual)),
                "resid_ar1": phi,
                "half_life": hl,
                "coefficients": {xs[i]: float(beta[i + 1]) for i in range(len(xs))},
                "loo": fold,
            }
        )
    rows.sort(key=lambda r: r["r2_all"], reverse=True)
    return rows


def imbalance_scan(prices: pd.DataFrame, wide: pd.DataFrame) -> list[dict]:
    imb = prices.pivot_table(index=["day", "timestamp"], columns="product", values="total_imbalance").sort_index()
    rows = []
    for signal_product in PRODUCTS:
        for target in PRODUCTS:
            for horizon in [1, 5, 10, 20, 50, 100]:
                day_corrs = []
                for day in DAYS:
                    sig = imb.loc[day, signal_product]
                    mid = wide.loc[day, target]
                    fut = mid.shift(-horizon) - mid
                    aligned = pd.concat([sig, fut], axis=1).dropna()
                    if len(aligned) < 100 or aligned.iloc[:, 0].std() == 0 or aligned.iloc[:, 1].std() == 0:
                        day_corrs.append(np.nan)
                    else:
                        day_corrs.append(float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1])))
                finite = [c for c in day_corrs if np.isfinite(c)]
                if finite:
                    rows.append(
                        {
                            "signal": signal_product,
                            "target": target,
                            "horizon": horizon,
                            "mean_corr": float(np.nanmean(day_corrs)),
                            "same_sign_days": max(sum(c > 0 for c in finite), sum(c < 0 for c in finite)),
                            "day_corrs": [None if not np.isfinite(c) else round(float(c), 5) for c in day_corrs],
                        }
                    )
    rows.sort(key=lambda r: (r["same_sign_days"], abs(r["mean_corr"])), reverse=True)
    return rows


def main() -> None:
    prices = load_prices()
    trades = load_trades()
    wide = wide_mid(prices)
    out = {
        "rows": {
            "prices": int(len(prices)),
            "trades": int(len(trades)),
            "days": DAYS,
            "products": PRODUCTS,
        },
        "product_metrics": product_metrics(prices, trades),
        "day_product_metrics": day_product_metrics(prices, trades),
        "correlations": correlations(wide),
        "lead_lag_top": lead_lag_scan(wide, 100)[:80],
        "pair_spreads": pair_spreads(wide),
        "basket_models": basket_models(wide),
        "imbalance_top": imbalance_scan(prices, wide)[:60],
    }
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
