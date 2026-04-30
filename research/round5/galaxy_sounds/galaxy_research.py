from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5" / "galaxy_sounds"
PRODUCTS = [
    "GALAXY_SOUNDS_DARK_MATTER",
    "GALAXY_SOUNDS_BLACK_HOLES",
    "GALAXY_SOUNDS_PLANETARY_RINGS",
    "GALAXY_SOUNDS_SOLAR_WINDS",
    "GALAXY_SOUNDS_SOLAR_FLAMES",
]
ADF_5PCT = -2.86


def read_prices() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frame = pd.read_csv(path, sep=";")
        frames.append(frame[frame["product"].isin(PRODUCTS)].copy())
    df = pd.concat(frames, ignore_index=True)
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    bid_cols = [f"bid_volume_{i}" for i in range(1, 4)]
    ask_cols = [f"ask_volume_{i}" for i in range(1, 4)]
    for col in bid_cols + ask_cols:
        df[col] = df[col].fillna(0).abs()
    df["top_depth"] = df["bid_volume_1"] + df["ask_volume_1"]
    df["book_depth"] = df[bid_cols].sum(axis=1) + df[ask_cols].sum(axis=1)
    df["imbalance"] = (df[bid_cols].sum(axis=1) - df[ask_cols].sum(axis=1)) / df["book_depth"].replace(0, np.nan)
    return df


def read_trades() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("trades_round_5_day_*.csv")):
        day = int(path.stem.rsplit("_", 1)[1])
        frame = pd.read_csv(path, sep=";")
        frame["day"] = day
        frames.append(frame[frame["symbol"].isin(PRODUCTS)].copy())
    return pd.concat(frames, ignore_index=True)


def pivots(prices: pd.DataFrame) -> dict[int, pd.DataFrame]:
    return {
        int(day): g.pivot(index="timestamp", columns="product", values="mid_price").sort_index()[PRODUCTS]
        for day, g in prices.groupby("day")
    }


def corr(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 5:
        return float("nan")
    x = x[mask]
    y = y[mask]
    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def adf_t(values: np.ndarray, max_lag: int = 8) -> float:
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 50 or np.std(x) == 0:
        return float("nan")
    dx = np.diff(x)
    lagged = x[:-1]
    best = None
    for lag in range(max_lag + 1):
        n = len(dx) - lag
        if n < 40:
            continue
        y = dx[lag:]
        cols = [np.ones(n), lagged[lag:]]
        for j in range(1, lag + 1):
            cols.append(dx[lag - j : -j])
        X = np.column_stack(cols)
        try:
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            resid = y - X @ beta
            dof = n - X.shape[1]
            if dof <= 0:
                continue
            sse = float(resid @ resid)
            cov = (sse / dof) * np.linalg.pinv(X.T @ X)
            se = float(np.sqrt(max(cov[1, 1], 0.0)))
            if se == 0:
                continue
            t = float(beta[1] / se)
            aic = n * np.log(max(sse / n, 1e-12)) + 2 * X.shape[1]
        except np.linalg.LinAlgError:
            continue
        if best is None or aic < best[0]:
            best = (aic, t)
    return float("nan") if best is None else best[1]


def half_life(values: np.ndarray) -> float:
    x = np.asarray(values, dtype=float)
    if len(x) < 10 or np.std(x) == 0:
        return float("inf")
    y = np.diff(x)
    lag = x[:-1] - np.mean(x[:-1])
    denom = float(lag @ lag)
    if denom <= 0:
        return float("inf")
    beta = float((lag @ y) / denom)
    if beta >= 0:
        return float("inf")
    return float(-np.log(2) / beta)


def product_diagnostics(prices: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    vol = trades.groupby(["day", "symbol"])["quantity"].sum()
    count = trades.groupby(["day", "symbol"])["quantity"].size()
    rows = []
    for (day, product), g in prices.groupby(["day", "product"], sort=True):
        mid = g["mid_price"].to_numpy(float)
        ret = np.diff(mid)
        ac = {lag: corr(ret[:-lag], ret[lag:]) if len(ret) > lag else float("nan") for lag in (1, 2, 5, 10, 20, 50, 100)}
        jump_abs = np.abs(ret)
        rows.append(
            {
                "day": int(day),
                "product": product,
                "mid_start": float(mid[0]),
                "mid_end": float(mid[-1]),
                "net_move": float(mid[-1] - mid[0]),
                "ret_vol": float(np.std(ret)),
                "abs_ret_mean": float(np.mean(jump_abs)),
                "ret_ac1": ac[1],
                "ret_ac10": ac[10],
                "ret_ac50": ac[50],
                "mean_reversion_score": float(-np.nanmean([ac[1], ac[2], ac[5], ac[10]])),
                "momentum_score": float(np.nanmean([ac[20], ac[50], ac[100]])),
                "avg_spread": float(g["spread"].mean()),
                "median_spread": float(g["spread"].median()),
                "avg_top_depth": float(g["top_depth"].mean()),
                "avg_book_depth": float(g["book_depth"].mean()),
                "liquidity_score": float(g["top_depth"].mean() / max(g["spread"].mean(), 1e-9)),
                "jump_95": float(np.quantile(jump_abs, 0.95)),
                "jump_99": float(np.quantile(jump_abs, 0.99)),
                "max_jump": float(jump_abs.max()),
                "trade_volume": int(vol.get((day, product), 0)),
                "trade_count": int(count.get((day, product), 0)),
                "mid_adf_t": adf_t(mid),
                "return_adf_t": adf_t(ret),
                "market_making_feasible": bool(g["spread"].mean() >= 2 and g["top_depth"].mean() >= 20),
                "aggressive_crossing_feasible": bool(np.quantile(jump_abs, 0.95) > g["spread"].mean()),
            }
        )
    per_day = pd.DataFrame(rows)
    summary = (
        per_day.groupby("product")
        .agg(
            ret_vol=("ret_vol", "mean"),
            abs_ret_mean=("abs_ret_mean", "mean"),
            ret_ac1=("ret_ac1", "mean"),
            ret_ac10=("ret_ac10", "mean"),
            ret_ac50=("ret_ac50", "mean"),
            mean_reversion_score=("mean_reversion_score", "mean"),
            momentum_score=("momentum_score", "mean"),
            avg_spread=("avg_spread", "mean"),
            avg_top_depth=("avg_top_depth", "mean"),
            avg_book_depth=("avg_book_depth", "mean"),
            liquidity_score=("liquidity_score", "mean"),
            jump_95=("jump_95", "mean"),
            jump_99=("jump_99", "mean"),
            max_jump=("max_jump", "max"),
            trade_volume=("trade_volume", "sum"),
            trade_count=("trade_count", "sum"),
            mid_adf_t=("mid_adf_t", "mean"),
            return_adf_t=("return_adf_t", "mean"),
            market_making_feasible=("market_making_feasible", "mean"),
            aggressive_crossing_feasible=("aggressive_crossing_feasible", "mean"),
        )
        .reset_index()
    )
    summary["decision"] = np.where(summary["market_making_feasible"] > 0, "trade", "ignore")
    per_day.to_csv(OUT / "galaxy_product_diagnostics_by_day.csv", index=False)
    summary.to_csv(OUT / "galaxy_product_diagnostics.csv", index=False)
    return summary


def correlation_research(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for a, b in itertools.combinations(PRODUCTS, 2):
        for day, piv in mids.items():
            ret = piv[[a, b]].diff().dropna()
            rows.append(
                {
                    "day": day,
                    "a": a,
                    "b": b,
                    "price_corr": corr(piv[a], piv[b]),
                    "return_corr": corr(ret[a], ret[b]),
                    "rolling_return_corr_500_mean": float(ret[a].rolling(500).corr(ret[b]).mean()),
                    "rolling_return_corr_500_min": float(ret[a].rolling(500).corr(ret[b]).min()),
                    "rolling_return_corr_500_max": float(ret[a].rolling(500).corr(ret[b]).max()),
                }
            )
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(["a", "b"])
        .agg(
            price_corr_mean=("price_corr", "mean"),
            price_corr_min=("price_corr", "min"),
            price_corr_max=("price_corr", "max"),
            return_corr_mean=("return_corr", "mean"),
            return_corr_min=("return_corr", "min"),
            return_corr_max=("return_corr", "max"),
            rolling_return_corr_500_mean=("rolling_return_corr_500_mean", "mean"),
            rolling_return_corr_500_min=("rolling_return_corr_500_min", "min"),
            rolling_return_corr_500_max=("rolling_return_corr_500_max", "max"),
        )
        .reset_index()
        .sort_values("return_corr_mean", ascending=False)
    )
    detail.to_csv(OUT / "galaxy_correlations_by_day.csv", index=False)
    summary.to_csv(OUT / "galaxy_correlations.csv", index=False)
    return summary


def lead_lag_research(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    lags = list(range(1, 101)) + [150, 200, 300, 400, 500]
    horizons = [1, 5, 10, 20, 50, 100, 200, 500]
    for day, piv in mids.items():
        for leader, follower in itertools.permutations(PRODUCTS, 2):
            for lag in lags:
                leader_move = piv[leader] - piv[leader].shift(lag)
                for h in horizons:
                    future = piv[follower].shift(-h) - piv[follower]
                    rows.append(
                        {
                            "day": day,
                            "leader": leader,
                            "follower": follower,
                            "lag": lag,
                            "horizon": h,
                            "corr": corr(leader_move.to_numpy(), future.to_numpy()),
                            "slope": float(np.nan_to_num(np.cov(leader_move.fillna(0), future.fillna(0), ddof=0)[0, 1] / max(np.var(leader_move.fillna(0)), 1e-9))),
                        }
                    )
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(["leader", "follower", "lag", "horizon"])
        .agg(corr_mean=("corr", "mean"), corr_min=("corr", "min"), corr_max=("corr", "max"), corr_std=("corr", "std"), slope_mean=("slope", "mean"))
        .reset_index()
    )
    summary["consistent_sign_days"] = detail.groupby(["leader", "follower", "lag", "horizon"])["corr"].apply(lambda s: int((s > 0).all() or (s < 0).all())).to_numpy()
    summary["score"] = summary["corr_mean"].abs() * (1 + summary["consistent_sign_days"]) / (1 + summary["corr_std"].fillna(0) * 10)
    summary = summary.sort_values("score", ascending=False)
    detail.to_csv(OUT / "galaxy_leadlag_by_day.csv", index=False)
    summary.to_csv(OUT / "galaxy_leadlag.csv", index=False)
    return summary


def pair_research(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    panel = pd.concat([mids[d] for d in sorted(mids)], ignore_index=True)
    rows = []
    for a, b in itertools.combinations(PRODUCTS, 2):
        x = panel[a].to_numpy(float)
        y = panel[b].to_numpy(float)
        spread = x - y
        var_y = float(np.var(y))
        beta = float(np.cov(x, y, ddof=0)[0, 1] / var_y) if var_y > 0 else 0.0
        intercept = float(np.mean(x) - beta * np.mean(y))
        resid = x - (intercept + beta * y)
        rows.append(
            {
                "a": a,
                "b": b,
                "price_corr": corr(x, y),
                "return_corr": corr(np.diff(x), np.diff(y)),
                "spread_mean": float(np.mean(spread)),
                "spread_std": float(np.std(spread)),
                "spread_adf_t": adf_t(spread),
                "spread_half_life": half_life(spread),
                "hedge_beta": beta,
                "hedge_intercept": intercept,
                "hedged_resid_std": float(np.std(resid)),
                "hedged_adf_t": adf_t(resid),
                "hedged_half_life": half_life(resid),
            }
        )
    out = pd.DataFrame(rows).sort_values(["hedged_adf_t", "spread_adf_t"])
    out["hedged_stationary_5pct"] = out["hedged_adf_t"] < ADF_5PCT
    out.to_csv(OUT / "galaxy_pairs.csv", index=False)
    return out


def basket_research(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for target in PRODUCTS:
        feats = [p for p in PRODUCTS if p != target]
        for test_day in sorted(mids):
            train_days = [d for d in sorted(mids) if d != test_day]
            X = pd.concat([mids[d][feats] for d in train_days]).to_numpy(float)
            y = pd.concat([mids[d][target] for d in train_days]).to_numpy(float)
            Xt = mids[test_day][feats].to_numpy(float)
            yt = mids[test_day][target].to_numpy(float)
            xm = X.mean(axis=0)
            xs = X.std(axis=0)
            xs[xs == 0] = 1
            ym = y.mean()
            Xs = (X - xm) / xs
            lam = 2.0
            beta_s = np.linalg.solve(Xs.T @ Xs + lam * np.eye(Xs.shape[1]), Xs.T @ (y - ym))
            beta = beta_s / xs
            intercept = float(ym - xm @ beta)
            pred = intercept + Xt @ beta
            resid = yt - pred
            rows.append(
                {
                    "target": target,
                    "test_day": test_day,
                    "features": ",".join(feats),
                    "intercept": intercept,
                    "betas": json.dumps({f: float(b) for f, b in zip(feats, beta)}, separators=(",", ":")),
                    "resid_mean": float(np.mean(resid)),
                    "resid_std": float(np.std(resid)),
                    "resid_mae": float(np.mean(np.abs(resid))),
                    "resid_ac1": corr(resid[:-1], resid[1:]),
                    "resid_diff_ac1": corr(np.diff(resid)[:-1], np.diff(resid)[1:]),
                    "resid_adf_t": adf_t(resid),
                    "resid_half_life": half_life(resid),
                }
            )
    by_day = pd.DataFrame(rows)
    summary = (
        by_day.groupby(["target", "features"])
        .agg(
            resid_std=("resid_std", "mean"),
            resid_mae=("resid_mae", "mean"),
            resid_ac1=("resid_ac1", "mean"),
            resid_diff_ac1=("resid_diff_ac1", "mean"),
            resid_adf_t=("resid_adf_t", "mean"),
            resid_half_life=("resid_half_life", "mean"),
        )
        .reset_index()
        .sort_values("resid_mae")
    )
    by_day.to_csv(OUT / "galaxy_baskets_by_day.csv", index=False)
    summary.to_csv(OUT / "galaxy_baskets.csv", index=False)
    return summary


def orderbook_research(prices: pd.DataFrame, mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    horizons = [1, 5, 10, 20, 50, 100]
    for day, gday in prices.groupby("day"):
        imb = gday.pivot(index="timestamp", columns="product", values="imbalance").sort_index()[PRODUCTS]
        for signal, target in itertools.product(PRODUCTS, PRODUCTS):
            for h in horizons:
                future = mids[int(day)][target].shift(-h) - mids[int(day)][target]
                rows.append(
                    {
                        "day": int(day),
                        "signal_product": signal,
                        "target": target,
                        "horizon": h,
                        "imbalance_future_corr": corr(imb[signal].to_numpy(), future.to_numpy()),
                    }
                )
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby(["signal_product", "target", "horizon"])
        .agg(corr_mean=("imbalance_future_corr", "mean"), corr_min=("imbalance_future_corr", "min"), corr_max=("imbalance_future_corr", "max"))
        .reset_index()
    )
    summary["same_sign_days"] = detail.groupby(["signal_product", "target", "horizon"])["imbalance_future_corr"].apply(lambda s: int((s > 0).all() or (s < 0).all())).to_numpy()
    summary["score"] = summary["corr_mean"].abs() * (1 + summary["same_sign_days"])
    summary = summary.sort_values("score", ascending=False)
    detail.to_csv(OUT / "galaxy_orderbook_by_day.csv", index=False)
    summary.to_csv(OUT / "galaxy_orderbook.csv", index=False)
    return summary


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices = read_prices()
    trades = read_trades()
    mid = pivots(prices)
    diagnostics = product_diagnostics(prices, trades)
    correlations = correlation_research(mid)
    leadlag = lead_lag_research(mid)
    pairs = pair_research(mid)
    baskets = basket_research(mid)
    orderbook = orderbook_research(prices, mid)
    summary = {
        "products": PRODUCTS,
        "top_leadlag": leadlag.head(20).to_dict(orient="records"),
        "top_pairs": pairs.head(10).to_dict(orient="records"),
        "top_baskets": baskets.head(5).to_dict(orient="records"),
        "top_orderbook": orderbook.head(10).to_dict(orient="records"),
        "diagnostics": diagnostics.to_dict(orient="records"),
        "top_correlations": correlations.head(10).to_dict(orient="records"),
    }
    (OUT / "galaxy_research_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote Galaxy research outputs to {OUT}")


if __name__ == "__main__":
    main()
