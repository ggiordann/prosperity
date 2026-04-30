from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5" / "uv_visors"

PRODUCTS = [
    "UV_VISOR_YELLOW",
    "UV_VISOR_AMBER",
    "UV_VISOR_ORANGE",
    "UV_VISOR_RED",
    "UV_VISOR_MAGENTA",
]

ADJACENT = list(zip(PRODUCTS[:-1], PRODUCTS[1:]))
HORIZONS = [1, 2, 5, 10, 20, 50, 100]
LAGS = list(range(1, 101)) + [150, 200, 300, 400, 500]
ADF_5PCT_CRITICAL = -2.86


def load_prices() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frame = pd.read_csv(path, sep=";")
        frame = frame[frame["product"].isin(PRODUCTS)].copy()
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["bid_depth"] = df[[f"bid_volume_{i}" for i in range(1, 4)]].fillna(0).abs().sum(axis=1)
    df["ask_depth"] = df[[f"ask_volume_{i}" for i in range(1, 4)]].fillna(0).abs().sum(axis=1)
    df["top_depth"] = df["bid_volume_1"].fillna(0).abs() + df["ask_volume_1"].fillna(0).abs()
    df["total_depth"] = df["bid_depth"] + df["ask_depth"]
    df["imbalance"] = (df["bid_depth"] - df["ask_depth"]) / df["total_depth"].replace(0, np.nan)
    return df


def load_trades() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("trades_round_5_day_*.csv")):
        day = int(path.stem.rsplit("_", 1)[1])
        frame = pd.read_csv(path, sep=";")
        frame = frame[frame["symbol"].isin(PRODUCTS)].copy()
        frame["day"] = day
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def pivot(df: pd.DataFrame, value: str) -> dict[int, pd.DataFrame]:
    return {
        int(day): g.pivot(index="timestamp", columns="product", values=value).sort_index()[PRODUCTS]
        for day, g in df.groupby("day")
    }


def corr(x: np.ndarray, y: np.ndarray) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 10:
        return float("nan")
    xx = x[mask]
    yy = y[mask]
    if np.std(xx) == 0 or np.std(yy) == 0:
        return 0.0
    return float(np.corrcoef(xx, yy)[0, 1])


def _adf_t_stat(values: np.ndarray, max_lag: int = 8) -> float:
    series = np.asarray(values, dtype=float)
    series = series[np.isfinite(series)]
    if len(series) < 80 or np.std(series) == 0:
        return float("nan")
    diff = np.diff(series)
    lagged_level = series[:-1]
    best: tuple[float, float] | None = None
    for lag in range(max_lag + 1):
        n_obs = len(diff) - lag
        if n_obs < 50:
            continue
        y = diff[lag:]
        cols = [np.ones(n_obs), lagged_level[lag:]]
        for lag_index in range(1, lag + 1):
            cols.append(diff[lag - lag_index : -lag_index])
        x = np.column_stack(cols)
        try:
            beta, *_ = np.linalg.lstsq(x, y, rcond=None)
            resid = y - x @ beta
            dof = n_obs - x.shape[1]
            if dof <= 0:
                continue
            sse = float(resid @ resid)
            sigma2 = sse / dof
            cov = sigma2 * np.linalg.pinv(x.T @ x)
            se = float(np.sqrt(max(cov[1, 1], 0.0)))
        except np.linalg.LinAlgError:
            continue
        if se == 0:
            continue
        t_stat = float(beta[1] / se)
        aic = n_obs * np.log(max(sse / n_obs, 1e-12)) + 2 * x.shape[1]
        if best is None or aic < best[0]:
            best = (aic, t_stat)
    return float("nan") if best is None else best[1]


def half_life(values: np.ndarray) -> float:
    series = np.asarray(values, dtype=float)
    series = series[np.isfinite(series)]
    if len(series) < 50:
        return float("nan")
    y = np.diff(series)
    x = series[:-1] - np.mean(series[:-1])
    denom = float(x @ x)
    if denom == 0:
        return float("nan")
    beta = float((x @ y) / denom)
    if beta >= 0:
        return float("inf")
    return float(-np.log(2.0) / beta)


def product_metrics(prices: pd.DataFrame, trades: pd.DataFrame, mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    trade_volume = trades.groupby(["day", "symbol"])["quantity"].sum()
    trade_count = trades.groupby(["day", "symbol"])["quantity"].size()
    rows = []
    for (day, product), g in prices.groupby(["day", "product"]):
        mid = g["mid_price"].to_numpy(float)
        ret = np.diff(mid)
        ac = {f"ret_ac{lag}": corr(ret[:-lag], ret[lag:]) for lag in [1, 2, 5, 10, 20] if len(ret) > lag}
        mom = {}
        for horizon in [5, 20, 100]:
            if len(mid) > horizon + 2:
                mom[f"momentum_{horizon}"] = corr(np.diff(mid)[:-horizon], mid[horizon + 1 :] - mid[1:-horizon])
        rows.append(
            {
                "day": int(day),
                "product": product,
                "mid_start": float(mid[0]),
                "mid_end": float(mid[-1]),
                "net_move": float(mid[-1] - mid[0]),
                "mid_mean": float(np.mean(mid)),
                "mid_std": float(np.std(mid)),
                "ret_vol": float(np.std(ret)),
                "abs_ret_mean": float(np.mean(np.abs(ret))),
                "mean_reversion_score": float(-ac.get("ret_ac1", 0.0)),
                "avg_spread": float(g["spread"].mean()),
                "median_spread": float(g["spread"].median()),
                "avg_top_depth": float(g["top_depth"].mean()),
                "avg_total_depth": float(g["total_depth"].mean()),
                "avg_abs_imbalance": float(g["imbalance"].abs().mean()),
                "jump_95": float(np.quantile(np.abs(ret), 0.95)),
                "jump_99": float(np.quantile(np.abs(ret), 0.99)),
                "max_abs_jump": float(np.max(np.abs(ret))),
                "adf_t_mid": _adf_t_stat(mid),
                "stationary_mid_5pct": bool(_adf_t_stat(mid) < ADF_5PCT_CRITICAL),
                "trade_volume": int(trade_volume.get((day, product), 0)),
                "trade_count": int(trade_count.get((day, product), 0)),
                **ac,
                **mom,
            }
        )
    by_day = pd.DataFrame(rows)
    by_day.to_csv(OUT / "product_metrics_by_day.csv", index=False)
    summary = (
        by_day.groupby("product")
        .agg(
            mid_mean=("mid_mean", "mean"),
            mid_std=("mid_std", "mean"),
            ret_vol=("ret_vol", "mean"),
            abs_ret_mean=("abs_ret_mean", "mean"),
            ret_ac1=("ret_ac1", "mean"),
            mean_reversion_score=("mean_reversion_score", "mean"),
            momentum_20=("momentum_20", "mean"),
            avg_spread=("avg_spread", "mean"),
            avg_top_depth=("avg_top_depth", "mean"),
            avg_total_depth=("avg_total_depth", "mean"),
            avg_abs_imbalance=("avg_abs_imbalance", "mean"),
            jump_95=("jump_95", "mean"),
            jump_99=("jump_99", "mean"),
            max_abs_jump=("max_abs_jump", "max"),
            trade_volume=("trade_volume", "sum"),
            trade_count=("trade_count", "sum"),
            adf_t_mid=("adf_t_mid", "mean"),
        )
        .reset_index()
    )
    summary["market_making_feasible"] = (summary["avg_spread"] >= 6) & (summary["avg_top_depth"] >= 20)
    summary["aggressive_crossing_feasible"] = summary["jump_95"] > (summary["avg_spread"] * 0.45)
    summary["role"] = np.where(
        summary["trade_volume"] == 0,
        "signal_only",
        np.where(summary["market_making_feasible"], "trade_and_signal", "trade_selectively"),
    )
    summary.to_csv(OUT / "product_metrics.csv", index=False)
    return summary


def correlations(mids: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    price_rows = []
    return_rows = []
    rolling_rows = []
    for day, piv in mids.items():
        ret = piv.diff().dropna()
        for a, b in itertools.combinations(PRODUCTS, 2):
            price_rows.append({"day": day, "a": a, "b": b, "corr": float(piv[a].corr(piv[b]))})
            return_rows.append({"day": day, "a": a, "b": b, "corr": float(ret[a].corr(ret[b]))})
            for window in [100, 500, 1000]:
                rc = ret[a].rolling(window).corr(ret[b]).dropna()
                if len(rc):
                    rolling_rows.append(
                        {
                            "day": day,
                            "a": a,
                            "b": b,
                            "window": window,
                            "mean": float(rc.mean()),
                            "std": float(rc.std()),
                            "min": float(rc.min()),
                            "max": float(rc.max()),
                            "positive_fraction": float((rc > 0).mean()),
                        }
                    )
    price = pd.DataFrame(price_rows)
    ret = pd.DataFrame(return_rows)
    rolling = pd.DataFrame(rolling_rows)
    for name, frame in [("price_correlations_by_day.csv", price), ("return_correlations_by_day.csv", ret), ("rolling_return_correlations.csv", rolling)]:
        frame.to_csv(OUT / name, index=False)
    return (
        price.groupby(["a", "b"]).agg(mean=("corr", "mean"), min=("corr", "min"), max=("corr", "max"), std=("corr", "std")).reset_index(),
        ret.groupby(["a", "b"]).agg(mean=("corr", "mean"), min=("corr", "min"), max=("corr", "max"), std=("corr", "std")).reset_index(),
        rolling,
    )


def lead_lag(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for day, piv in mids.items():
        for leader, follower in itertools.permutations(PRODUCTS, 2):
            leader_mid = piv[leader].to_numpy(float)
            follower_mid = piv[follower].to_numpy(float)
            for lag in LAGS:
                if len(leader_mid) <= lag + max(HORIZONS) + 1:
                    continue
                signal = leader_mid[lag:] - leader_mid[:-lag]
                for horizon in HORIZONS:
                    target = follower_mid[lag + horizon :] - follower_mid[lag:-horizon]
                    sig = signal[:-horizon]
                    c = corr(sig, target)
                    if np.isfinite(c):
                        rows.append(
                            {
                                "day": day,
                                "leader": leader,
                                "follower": follower,
                                "lag": lag,
                                "horizon": horizon,
                                "corr": c,
                                "signed_edge_per_unit": float(np.mean(np.sign(sig) * target)) if len(sig) else 0.0,
                            }
                        )
    raw = pd.DataFrame(rows)
    raw.to_csv(OUT / "lead_lag_by_day.csv", index=False)
    summary = (
        raw.groupby(["leader", "follower", "lag", "horizon"])
        .agg(
            corr_mean=("corr", "mean"),
            corr_min=("corr", "min"),
            corr_max=("corr", "max"),
            corr_std=("corr", "std"),
            edge_mean=("signed_edge_per_unit", "mean"),
            edge_min=("signed_edge_per_unit", "min"),
            aligned_days=("corr", lambda s: int(max((s > 0).sum(), (s < 0).sum()))),
        )
        .reset_index()
    )
    summary["same_sign_all_days"] = summary["corr_min"] * summary["corr_max"] > 0
    summary["score"] = summary["corr_mean"].abs() * (1 + summary["same_sign_all_days"].astype(int)) / (1 + summary["corr_std"].fillna(0))
    summary = summary.sort_values(["score", "corr_mean"], ascending=False)
    summary.to_csv(OUT / "lead_lag_summary.csv", index=False)
    return summary


def spread_and_curve(mids: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    spread_rows = []
    curve_rows = []
    panel = pd.concat([mids[d].assign(day=d) for d in sorted(mids)], ignore_index=True)
    for a, b in itertools.combinations(PRODUCTS, 2):
        x = panel[a].to_numpy(float)
        y = panel[b].to_numpy(float)
        spread = x - y
        y_var = float(np.var(y))
        beta = float(np.cov(x, y, ddof=0)[0, 1] / y_var) if y_var > 0 else 0.0
        resid = x - (float(np.mean(x) - beta * np.mean(y)) + beta * y)
        spread_rows.append(
            {
                "a": a,
                "b": b,
                "adjacent": (a, b) in ADJACENT,
                "spread_mean": float(np.mean(spread)),
                "spread_std": float(np.std(spread)),
                "spread_adf_t": _adf_t_stat(spread),
                "spread_half_life": half_life(spread),
                "hedge_beta": beta,
                "resid_std": float(np.std(resid)),
                "resid_adf_t": _adf_t_stat(resid),
                "resid_half_life": half_life(resid),
            }
        )
    for left, mid, right in zip(PRODUCTS[:-2], PRODUCTS[1:-1], PRODUCTS[2:]):
        resid = panel[mid].to_numpy(float) - 0.5 * (panel[left].to_numpy(float) + panel[right].to_numpy(float))
        curve_rows.append(
            {
                "butterfly": f"{mid} - 0.5*({left}+{right})",
                "resid_mean": float(np.mean(resid)),
                "resid_std": float(np.std(resid)),
                "adf_t": _adf_t_stat(resid),
                "half_life": half_life(resid),
            }
        )
    spread_df = pd.DataFrame(spread_rows).sort_values(["resid_adf_t", "spread_adf_t"])
    curve_df = pd.DataFrame(curve_rows).sort_values("adf_t")
    spread_df.to_csv(OUT / "spread_stationarity.csv", index=False)
    curve_df.to_csv(OUT / "curve_butterflies.csv", index=False)
    return spread_df, curve_df


def basket_models(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for target in PRODUCTS:
        features = [p for p in PRODUCTS if p != target]
        for test_day in sorted(mids):
            train_days = [d for d in sorted(mids) if d != test_day]
            x_train = pd.concat([mids[d][features] for d in train_days]).to_numpy(float)
            y_train = pd.concat([mids[d][target] for d in train_days]).to_numpy(float)
            x_test = mids[test_day][features].to_numpy(float)
            y_test = mids[test_day][target].to_numpy(float)
            x_mu = x_train.mean(axis=0)
            y_mu = y_train.mean()
            x_std = x_train.std(axis=0)
            x_std[x_std == 0] = 1.0
            xs = (x_train - x_mu) / x_std
            lam = 2.0
            beta_s = np.linalg.solve(xs.T @ xs + lam * np.eye(xs.shape[1]), xs.T @ (y_train - y_mu))
            beta = beta_s / x_std
            intercept = float(y_mu - x_mu @ beta)
            pred = intercept + x_test @ beta
            resid = y_test - pred
            rows.append(
                {
                    "target": target,
                    "test_day": test_day,
                    "features": ",".join(features),
                    "intercept": intercept,
                    "betas": json.dumps({p: float(b) for p, b in zip(features, beta)}, separators=(",", ":")),
                    "resid_mean": float(np.mean(resid)),
                    "resid_std": float(np.std(resid)),
                    "resid_mae": float(np.mean(np.abs(resid))),
                    "resid_ac1": corr(resid[:-1], resid[1:]),
                    "resid_diff_ac1": corr(np.diff(resid)[:-1], np.diff(resid)[1:]),
                    "resid_adf_t": _adf_t_stat(resid),
                    "half_life": half_life(resid),
                }
            )
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "basket_models_by_day.csv", index=False)
    summary = (
        out.groupby(["target", "features"])
        .agg(
            resid_std=("resid_std", "mean"),
            resid_mae=("resid_mae", "mean"),
            resid_ac1=("resid_ac1", "mean"),
            resid_adf_t=("resid_adf_t", "mean"),
            max_abs_resid_mean=("resid_mean", lambda s: float(np.max(np.abs(s)))),
            half_life=("half_life", "mean"),
        )
        .reset_index()
        .sort_values("resid_mae")
    )
    summary.to_csv(OUT / "basket_models.csv", index=False)
    return summary


def imbalance(prices: pd.DataFrame, mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    imb = pivot(prices, "imbalance")
    rows = []
    for day in sorted(mids):
        for source, target in itertools.product(PRODUCTS, PRODUCTS):
            signal = imb[day][source].ffill().fillna(0).to_numpy(float)
            target_mid = mids[day][target].to_numpy(float)
            for horizon in HORIZONS:
                fut = target_mid[horizon:] - target_mid[:-horizon]
                sig = signal[:-horizon]
                rows.append(
                    {
                        "day": day,
                        "source": source,
                        "target": target,
                        "horizon": horizon,
                        "corr": corr(sig, fut),
                        "edge_per_sign": float(np.mean(np.sign(sig) * fut)),
                    }
                )
    raw = pd.DataFrame(rows)
    raw.to_csv(OUT / "imbalance_by_day.csv", index=False)
    summary = (
        raw.groupby(["source", "target", "horizon"])
        .agg(
            corr_mean=("corr", "mean"),
            corr_min=("corr", "min"),
            corr_max=("corr", "max"),
            edge_mean=("edge_per_sign", "mean"),
            edge_min=("edge_per_sign", "min"),
        )
        .reset_index()
    )
    summary["same_sign_all_days"] = summary["corr_min"] * summary["corr_max"] > 0
    summary["score"] = summary["corr_mean"].abs() * (1 + summary["same_sign_all_days"].astype(int))
    summary = summary.sort_values("score", ascending=False)
    summary.to_csv(OUT / "imbalance_summary.csv", index=False)
    return summary


def md_table(frame: pd.DataFrame, max_rows: int = 12, floatfmt: str = ".4f") -> str:
    frame = frame.head(max_rows)
    if frame.empty:
        return "_No rows._"
    cols = list(frame.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            val = row[col]
            if isinstance(val, float):
                vals.append(format(val, floatfmt))
            else:
                vals.append(str(val))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def write_analysis(
    products: pd.DataFrame,
    price_corr: pd.DataFrame,
    ret_corr: pd.DataFrame,
    lead: pd.DataFrame,
    spreads: pd.DataFrame,
    curves: pd.DataFrame,
    baskets: pd.DataFrame,
    imb: pd.DataFrame,
) -> None:
    adjacent_corr = ret_corr.merge(pd.DataFrame(ADJACENT, columns=["a", "b"]).assign(adjacent=True), how="left").fillna({"adjacent": False})
    lines = [
        "# UV-Visors Round 5 Analysis",
        "",
        "Scope: `UV_VISOR_YELLOW`, `UV_VISOR_AMBER`, `UV_VISOR_ORANGE`, `UV_VISOR_RED`, `UV_VISOR_MAGENTA` only.",
        "",
        "## Repository And Data",
        "",
        "- Rust backtester: `prosperity_rust_backtester/`.",
        "- Backtester command: `cd prosperity_rust_backtester && ./scripts/cargo_local.sh run --release -- --trader <file> --dataset round5 --products full`.",
        "- Round 5 data: `prosperity_rust_backtester/datasets/round5/prices_round_5_day_{2,3,4}.csv` and matching `trades_round_5_day_{2,3,4}.csv`.",
        "- Current submission path: `prosperity_rust_backtester/traders/latest_trader.py`.",
        "- Data format: semicolon-delimited price rows with three visible bid/ask levels plus `mid_price`; trade rows with `timestamp`, blank `buyer`/`seller`, `symbol`, `price`, and `quantity`.",
        "- Products: 50 total Round 5 products, grouped as 10 categories of 5; all Round 5 products have limit 10 in `prosperity_rust_backtester/src/runner.rs`.",
        "- Final constraints: one Python submission under 100KB with Prosperity `datamodel` imports and standard-library-only runtime code.",
        "",
        "## Product Diagnostics",
        "",
        md_table(products[[
            "product",
            "mid_mean",
            "mid_std",
            "ret_vol",
            "ret_ac1",
            "mean_reversion_score",
            "momentum_20",
            "avg_spread",
            "avg_top_depth",
            "trade_volume",
            "jump_95",
            "role",
        ]], 10),
        "",
        "All five UV-visors are tradeable. Spreads average around 13 ticks and visible top depth around 36 lots, so passive making is feasible. Aggressive crossing is useful only when a relationship signal moves fair value well beyond half-spread; blind crossing is too expensive.",
        "",
        "## Spectrum And Curve",
        "",
        "Adjacent return correlations are weak; the ordered colour spectrum is not a simple same-bar gradient. The exploitable structure is slower, with long-lag movements and product-specific offsets rather than tight adjacent spreads.",
        "",
        md_table(adjacent_corr[adjacent_corr["adjacent"]][["a", "b", "mean", "min", "max", "std"]], 8),
        "",
        "Butterfly residuals are persistent and not cleanly stationary, so curve trades are useful as diagnostics but not as the main live signal.",
        "",
        md_table(curves, 6),
        "",
        "## Correlation",
        "",
        "Price levels can look highly related or anti-related, but return correlations are small and unstable. This argues against plain pair z-score trading without a separate timing signal.",
        "",
        md_table(price_corr.sort_values("mean", ascending=False), 10),
        "",
        md_table(ret_corr.sort_values("mean", ascending=False), 10),
        "",
        "## Lead-Lag",
        "",
        "The strongest robust UV alpha is slow leader/follower fair-value shifting. `AMBER -> MAGENTA` at lag 500 and `RED -> AMBER` at lag 500 are the cleanest category relationships; `YELLOW -> MAGENTA` has a smaller but stable negative-sign effect.",
        "",
        md_table(lead[lead["same_sign_all_days"]][["leader", "follower", "lag", "horizon", "corr_mean", "corr_min", "corr_max", "edge_mean", "score"]], 14),
        "",
        "## Pair And Basket Tests",
        "",
        "Only `AMBER`/`MAGENTA` has a hedged residual passing the rough ADF 5% threshold. Even there, the half-life is long enough that passive execution around fair value beats explicit spread inventory bets.",
        "",
        md_table(spreads[["a", "b", "adjacent", "spread_std", "spread_adf_t", "spread_half_life", "hedge_beta", "resid_std", "resid_adf_t", "resid_half_life"]], 10),
        "",
        "Leave-one-day-out basket fair values reduce level error for some products, but residuals have near-unit autocorrelation and unstable intercepts. They are weaker than using the same relationships as lagged fair-value nudges.",
        "",
        md_table(baskets[["target", "resid_std", "resid_mae", "resid_ac1", "resid_adf_t", "half_life"]], 10),
        "",
        "## Order Book Signals",
        "",
        "Top-book imbalance has statistical signal, especially self-imbalance at short horizons, but the average edge is small versus the spread. I kept it out of the final compact strategy to reduce turnover and overfit risk.",
        "",
        md_table(imb[["source", "target", "horizon", "corr_mean", "corr_min", "corr_max", "edge_mean", "score"]], 12),
        "",
        "## Strategy Decision",
        "",
        "- Trade all five products.",
        "- Use static fair values plus small product-specific anchor shifts.",
        "- Add only validated same-category lead-lag fair-value shifts.",
        "- Use passive quotes and selective crossing when fair value is far enough through the touch.",
        "- Ignore direct basket residual and butterfly trades in the final category implementation.",
    ]
    (OUT / "ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices = load_prices()
    trades = load_trades()
    mids = pivot(prices, "mid_price")
    products = product_metrics(prices, trades, mids)
    price_corr, ret_corr, _ = correlations(mids)
    price_corr.to_csv(OUT / "price_correlations.csv", index=False)
    ret_corr.to_csv(OUT / "return_correlations.csv", index=False)
    lead = lead_lag(mids)
    spreads, curves = spread_and_curve(mids)
    baskets = basket_models(mids)
    imb = imbalance(prices, mids)
    write_analysis(products, price_corr, ret_corr, lead, spreads, curves, baskets, imb)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
