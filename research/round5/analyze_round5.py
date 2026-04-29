from __future__ import annotations

import itertools
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5"


CATEGORIES = {
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
    "visor": ["UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"],
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
PRODUCT_ORDER = [product for products in CATEGORIES.values() for product in products]
ADF_5PCT_CRITICAL = -2.86


def load_prices() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frames.append(pd.read_csv(path, sep=";"))
    df = pd.concat(frames, ignore_index=True)
    df["category"] = df["product"].map(PRODUCT_TO_CATEGORY)
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["best_bid_vol"] = df["bid_volume_1"].abs()
    df["best_ask_vol"] = df["ask_volume_1"].abs()
    df["top_depth"] = df["best_bid_vol"] + df["best_ask_vol"]
    return df


def load_trades() -> pd.DataFrame:
    frames = []
    for path in sorted(DATA.glob("trades_round_5_day_*.csv")):
        day = int(path.stem.rsplit("_", 1)[1])
        frame = pd.read_csv(path, sep=";")
        frame["day"] = day
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def pivot_mid(df: pd.DataFrame) -> dict[int, pd.DataFrame]:
    out = {}
    for day, g in df.groupby("day"):
        piv = g.pivot(index="timestamp", columns="product", values="mid_price").sort_index()
        out[int(day)] = piv
    return out


def product_metrics(df: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    rows = []
    trade_volume = trades.groupby(["day", "symbol"])["quantity"].sum()
    trade_count = trades.groupby(["day", "symbol"])["quantity"].size()
    for (day, product), g in df.groupby(["day", "product"], sort=True):
        mid = g["mid_price"].to_numpy(float)
        ret = np.diff(mid)
        ret_lag = ret[:-1]
        ret_next = ret[1:]
        ac1 = np.corrcoef(ret_lag, ret_next)[0, 1] if len(ret_lag) > 3 and np.std(ret_lag) > 0 and np.std(ret_next) > 0 else 0.0
        trend_10 = np.corrcoef(ret[:-10], mid[10:] - mid[:-10][:-0 or None])[0, 1] if False else 0.0
        rows.append(
            {
                "day": int(day),
                "category": PRODUCT_TO_CATEGORY[product],
                "product": product,
                "mid_start": float(mid[0]),
                "mid_end": float(mid[-1]),
                "net_move": float(mid[-1] - mid[0]),
                "ret_vol": float(np.std(ret)),
                "abs_ret_mean": float(np.mean(np.abs(ret))),
                "ret_ac1": float(ac1),
                "mean_reversion_score": float(-ac1),
                "avg_spread": float(g["spread"].mean()),
                "avg_top_depth": float(g["top_depth"].mean()),
                "liquidity_score": float(g["top_depth"].mean() / max(g["spread"].mean(), 1e-9)),
                "jump_95": float(np.quantile(np.abs(ret), 0.95)),
                "jump_99": float(np.quantile(np.abs(ret), 0.99)),
                "trade_volume": int(trade_volume.get((day, product), 0)),
                "trade_count": int(trade_count.get((day, product), 0)),
                "passive_mm_feasible": bool(g["spread"].mean() >= 2 and g["top_depth"].mean() >= 20),
                "aggressive_feasible": bool(np.quantile(np.abs(ret), 0.95) > g["spread"].mean()),
            }
        )
    per_day = pd.DataFrame(rows)
    agg = (
        per_day.groupby(["category", "product"])
        .agg(
            ret_vol=("ret_vol", "mean"),
            abs_ret_mean=("abs_ret_mean", "mean"),
            ret_ac1=("ret_ac1", "mean"),
            mean_reversion_score=("mean_reversion_score", "mean"),
            avg_spread=("avg_spread", "mean"),
            avg_top_depth=("avg_top_depth", "mean"),
            liquidity_score=("liquidity_score", "mean"),
            jump_95=("jump_95", "mean"),
            jump_99=("jump_99", "mean"),
            trade_volume=("trade_volume", "sum"),
            trade_count=("trade_count", "sum"),
            passive_mm_feasible=("passive_mm_feasible", "mean"),
            aggressive_feasible=("aggressive_feasible", "mean"),
        )
        .reset_index()
    )
    per_day.to_csv(OUT / "product_metrics_by_day.csv", index=False)
    agg.to_csv(OUT / "product_metrics.csv", index=False)
    return agg


def category_metrics(df: pd.DataFrame, mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for cat, products in CATEGORIES.items():
        per_day = df[df["category"] == cat].groupby("day").agg(avg_spread=("spread", "mean"), avg_depth=("top_depth", "mean"))
        corrs = []
        vols = []
        same_bar = []
        for day, piv in mids.items():
            rets = piv[products].diff().dropna()
            corr = rets.corr()
            mask = ~np.eye(len(products), dtype=bool)
            corrs.append(float(corr.to_numpy()[mask].mean()))
            vols.append(float(rets.std().mean()))
            same_bar.append(float(rets.mean(axis=1).abs().mean()))
        rows.append(
            {
                "category": cat,
                "products": ",".join(products),
                "avg_spread": float(per_day["avg_spread"].mean()),
                "avg_depth": float(per_day["avg_depth"].mean()),
                "mean_within_return_corr": float(np.mean(corrs)),
                "mean_ret_vol": float(np.mean(vols)),
                "category_move_score": float(np.mean(same_bar)),
            }
        )
    out = pd.DataFrame(rows).sort_values(["mean_within_return_corr", "mean_ret_vol"], ascending=False)
    out.to_csv(OUT / "category_metrics.csv", index=False)
    return out


def correlation_tables(mids: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    products = list(next(iter(mids.values())).columns)
    for a, b in itertools.combinations(products, 2):
        values = []
        price_values = []
        for piv in mids.values():
            rets = piv[[a, b]].diff().dropna()
            values.append(float(rets[a].corr(rets[b])))
            price_values.append(float(piv[a].corr(piv[b])))
        rows.append(
            {
                "a": a,
                "b": b,
                "category_a": PRODUCT_TO_CATEGORY[a],
                "category_b": PRODUCT_TO_CATEGORY[b],
                "same_category": PRODUCT_TO_CATEGORY[a] == PRODUCT_TO_CATEGORY[b],
                "return_corr_mean": float(np.nanmean(values)),
                "return_corr_min": float(np.nanmin(values)),
                "return_corr_max": float(np.nanmax(values)),
                "return_corr_std": float(np.nanstd(values)),
                "price_corr_mean": float(np.nanmean(price_values)),
                "price_corr_min": float(np.nanmin(price_values)),
            }
        )
    out = pd.DataFrame(rows).sort_values("return_corr_mean", ascending=False)
    out.to_csv(OUT / "pair_correlations.csv", index=False)
    top = out[(out["same_category"]) | (out["return_corr_mean"].abs() > 0.08)].head(250)
    top.to_csv(OUT / "pair_correlations_top.csv", index=False)
    return out, top


def correlation_matrices(mids: dict[int, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    first = next(iter(mids.values()))
    products = [product for product in PRODUCT_ORDER if product in first.columns]
    missing = sorted(set(first.columns) - set(products))
    products.extend(missing)

    return_corrs = []
    price_corrs = []
    for piv in mids.values():
        day_prices = piv[products]
        return_corrs.append(day_prices.diff().dropna().corr())
        price_corrs.append(day_prices.corr())

    return_matrix = sum(return_corrs) / len(return_corrs)
    price_matrix = sum(price_corrs) / len(price_corrs)
    np.fill_diagonal(return_matrix.values, 1.0)
    np.fill_diagonal(price_matrix.values, 1.0)

    return_matrix.to_csv(OUT / "return_correlation_matrix.csv")
    price_matrix.to_csv(OUT / "price_correlation_matrix.csv")
    return return_matrix, price_matrix


def _adf_t_stat(values: np.ndarray, max_lag: int = 8) -> float:
    series = np.asarray(values, dtype=float)
    series = series[np.isfinite(series)]
    if len(series) < 50 or np.std(series) == 0:
        return float("nan")

    diff = np.diff(series)
    lagged_level = series[:-1]
    best: tuple[float, float] | None = None
    for lag in range(max_lag + 1):
        n_obs = len(diff) - lag
        if n_obs < 20:
            continue
        y = diff[lag:]
        columns = [np.ones(n_obs), lagged_level[lag:]]
        for lag_index in range(1, lag + 1):
            columns.append(diff[lag - lag_index : -lag_index])
        x = np.column_stack(columns)
        try:
            coef, *_ = np.linalg.lstsq(x, y, rcond=None)
            residual = y - x @ coef
            degrees = n_obs - x.shape[1]
            if degrees <= 0:
                continue
            sse = float(residual @ residual)
            sigma2 = sse / degrees
            cov = sigma2 * np.linalg.pinv(x.T @ x)
            se = float(np.sqrt(max(cov[1, 1], 0.0)))
        except np.linalg.LinAlgError:
            continue
        if se == 0:
            continue
        t_stat = float(coef[1] / se)
        aic = n_obs * np.log(max(sse / n_obs, 1e-12)) + 2 * x.shape[1]
        if best is None or aic < best[0]:
            best = (aic, t_stat)

    return float("nan") if best is None else best[1]


def stationary_spread_pairs(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    panel = pd.concat([mids[day] for day in sorted(mids)], ignore_index=True)
    rows = []
    for category, products in CATEGORIES.items():
        for a, b in itertools.combinations(products, 2):
            x = panel[a].to_numpy(float)
            y = panel[b].to_numpy(float)
            spread = x - y
            y_var = float(np.var(y))
            beta = float(np.cov(x, y, ddof=0)[0, 1] / y_var) if y_var > 0 else 0.0
            intercept = float(np.mean(x) - beta * np.mean(y))
            residual = x - (intercept + beta * y)
            spread_t = _adf_t_stat(spread)
            residual_t = _adf_t_stat(residual)
            rows.append(
                {
                    "category": category,
                    "a": a,
                    "b": b,
                    "level_corr": float(np.corrcoef(x, y)[0, 1]),
                    "return_corr": float(panel[[a, b]].diff().dropna()[a].corr(panel[[a, b]].diff().dropna()[b])),
                    "spread_mean": float(np.mean(spread)),
                    "spread_std": float(np.std(spread)),
                    "spread_adf_t": spread_t,
                    "spread_stationary_5pct": bool(np.isfinite(spread_t) and spread_t < ADF_5PCT_CRITICAL),
                    "hedge_beta": beta,
                    "hedge_intercept": intercept,
                    "hedged_resid_std": float(np.std(residual)),
                    "hedged_adf_t": residual_t,
                    "hedged_stationary_5pct": bool(np.isfinite(residual_t) and residual_t < ADF_5PCT_CRITICAL),
                }
            )
    out = pd.DataFrame(rows).sort_values(["hedged_adf_t", "spread_adf_t"], ascending=True)
    out.to_csv(OUT / "stationary_spread_pairs.csv", index=False)
    return out


def plot_correlation_heatmap(matrix: pd.DataFrame, path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(18, 16), constrained_layout=True)
    im = ax.imshow(matrix.to_numpy(float), cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    products = list(matrix.index)
    ax.set_xticks(range(len(products)), labels=products, rotation=90, fontsize=5)
    ax.set_yticks(range(len(products)), labels=products, fontsize=5)
    ax.set_title(title)

    start = 0
    centers = []
    category_labels = []
    for category, category_products in CATEGORIES.items():
        width = sum(1 for product in category_products if product in products)
        if width == 0:
            continue
        end = start + width
        ax.axhline(end - 0.5, color="black", linewidth=0.35)
        ax.axvline(end - 0.5, color="black", linewidth=0.35)
        centers.append(start + (width - 1) / 2)
        category_labels.append(category)
        start = end

    category_axis = ax.secondary_xaxis("top")
    category_axis.set_xticks(centers, labels=category_labels, rotation=45, fontsize=8)
    category_axis.tick_params(length=0)

    colorbar = fig.colorbar(im, ax=ax, shrink=0.82)
    colorbar.set_label("Correlation")
    fig.savefig(path, dpi=240)
    plt.close(fig)


def _corr_matrix(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x0 = x - x.mean(axis=0)
    y0 = y - y.mean(axis=0)
    denom = np.sqrt((x0 * x0).sum(axis=0))[:, None] * np.sqrt((y0 * y0).sum(axis=0))[None, :]
    denom[denom == 0] = np.nan
    return (x0.T @ y0) / denom


def lead_lag(mids: dict[int, pd.DataFrame], max_lag: int = 100) -> pd.DataFrame:
    products = list(next(iter(mids.values())).columns)
    per_day = []
    for day, piv in mids.items():
        r = piv[products].diff().fillna(0.0).to_numpy(float)
        for lag in range(1, max_lag + 1):
            c = _corr_matrix(r[:-lag], r[lag:])
            for i, leader in enumerate(products):
                for j, follower in enumerate(products):
                    if i == j:
                        continue
                    val = c[i, j]
                    if np.isfinite(val) and abs(val) >= 0.025:
                        per_day.append((day, leader, follower, lag, float(val)))
    raw = pd.DataFrame(per_day, columns=["day", "leader", "follower", "lag", "corr"])
    grouped = (
        raw.groupby(["leader", "follower", "lag"])
        .agg(corr_mean=("corr", "mean"), corr_min=("corr", "min"), corr_max=("corr", "max"), corr_std=("corr", "std"), n_days=("corr", "size"))
        .reset_index()
    )
    grouped["same_category"] = grouped["leader"].map(PRODUCT_TO_CATEGORY) == grouped["follower"].map(PRODUCT_TO_CATEGORY)
    grouped["category_leader"] = grouped["leader"].map(PRODUCT_TO_CATEGORY)
    grouped["category_follower"] = grouped["follower"].map(PRODUCT_TO_CATEGORY)
    grouped["score"] = grouped["corr_mean"].abs() * grouped["n_days"] / (1.0 + grouped["corr_std"].fillna(0.0) * 10.0)
    stable = grouped[(grouped["n_days"] == 3) & (grouped["corr_min"] * grouped["corr_max"] > 0)].copy()
    stable = stable.sort_values("score", ascending=False)
    raw.to_csv(OUT / "lead_lag_raw.csv", index=False)
    stable.to_csv(OUT / "lead_lag_stable.csv", index=False)
    return stable


def basket_models(mids: dict[int, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for cat, products in CATEGORIES.items():
        for target in products:
            feats = [p for p in products if p != target]
            for test_day in sorted(mids):
                train_days = [d for d in sorted(mids) if d != test_day]
                x_train = pd.concat([mids[d][feats] for d in train_days]).to_numpy(float)
                y_train = pd.concat([mids[d][target] for d in train_days]).to_numpy(float)
                x_test = mids[test_day][feats].to_numpy(float)
                y_test = mids[test_day][target].to_numpy(float)
                x_mu = x_train.mean(axis=0)
                y_mu = y_train.mean()
                x_std = x_train.std(axis=0)
                x_std[x_std == 0] = 1.0
                xs = (x_train - x_mu) / x_std
                lam = 2.0
                beta_s = np.linalg.solve(xs.T @ xs + lam * np.eye(xs.shape[1]), xs.T @ (y_train - y_mu))
                beta = beta_s / x_std
                intercept = y_mu - x_mu @ beta
                pred = intercept + x_test @ beta
                resid = y_test - pred
                dr = np.diff(resid)
                ac1 = np.corrcoef(resid[:-1], resid[1:])[0, 1] if np.std(resid[:-1]) > 0 and np.std(resid[1:]) > 0 else 0.0
                rows.append(
                    {
                        "category": cat,
                        "target": target,
                        "test_day": test_day,
                        "features": ",".join(feats),
                        "intercept": float(intercept),
                        "betas": json.dumps({f: float(b) for f, b in zip(feats, beta)}, separators=(",", ":")),
                        "resid_std": float(np.std(resid)),
                        "resid_mae": float(np.mean(np.abs(resid))),
                        "resid_ac1": float(ac1),
                        "resid_diff_ac1": float(np.corrcoef(dr[:-1], dr[1:])[0, 1]) if len(dr) > 2 and np.std(dr[:-1]) > 0 and np.std(dr[1:]) > 0 else 0.0,
                    }
                )
    by_day = pd.DataFrame(rows)
    summary = (
        by_day.groupby(["category", "target", "features"])
        .agg(
            resid_std=("resid_std", "mean"),
            resid_mae=("resid_mae", "mean"),
            resid_ac1=("resid_ac1", "mean"),
            resid_std_max=("resid_std", "max"),
            stable_days=("resid_std", "size"),
        )
        .reset_index()
    )
    summary = summary.sort_values(["resid_mae", "resid_std"])
    by_day.to_csv(OUT / "basket_models_by_day.csv", index=False)
    summary.to_csv(OUT / "basket_models.csv", index=False)
    return summary


def md_table(frame: pd.DataFrame, floatfmt: str = ".4f") -> str:
    if frame.empty:
        return "_No rows._"
    cols = list(frame.columns)
    rows = []
    for _, row in frame.iterrows():
        vals = []
        for col in cols:
            value = row[col]
            if isinstance(value, float):
                vals.append(format(value, floatfmt))
            else:
                vals.append(str(value))
        rows.append(vals)
    out = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    out.extend("| " + " | ".join(vals) + " |" for vals in rows)
    return "\n".join(out)


def make_relationship_md(category: pd.DataFrame, corr: pd.DataFrame, lag: pd.DataFrame, baskets: pd.DataFrame) -> None:
    lines = [
        "# Round 5 Relationship Map",
        "",
        "Generated from bundled Round 5 days 2, 3, and 4. Return units are mid-price tick changes per timestamp.",
        "",
        "## Category Filter",
        "",
        md_table(category),
        "",
        "## Strong Same-Category Return Correlations",
        "",
        md_table(corr[corr["same_category"]].head(40)),
        "",
        "## Stable Lead-Lag Edges",
        "",
        md_table(lag.head(60)),
        "",
        "## Basket Residual Candidates",
        "",
        md_table(baskets.head(50)),
        "",
        "## Notes",
        "",
        "- Trade CSV buyer/seller fields are blank in the bundled data, so no counterparty edge is available.",
        "- Stable lead-lag rows require all three days to have the same sign at the same lag.",
        "- Basket rows are leave-one-day-out ridge fits using only same-category products.",
    ]
    (OUT / "RELATIONSHIP_MAP.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices = load_prices()
    trades = load_trades()
    mids = pivot_mid(prices)
    product_metrics(prices, trades)
    cat = category_metrics(prices, mids)
    return_matrix, price_matrix = correlation_matrices(mids)
    stationary_spread_pairs(mids)
    plot_correlation_heatmap(return_matrix, OUT / "return_correlation_heatmap.png", "Round 5 Return Correlation Matrix")
    plot_correlation_heatmap(price_matrix, OUT / "price_correlation_heatmap.png", "Round 5 Price Correlation Matrix")
    corr, _ = correlation_tables(mids)
    lag = lead_lag(mids)
    baskets = basket_models(mids)
    make_relationship_md(cat, corr, lag, baskets)
    print("wrote research/round5 relationship outputs")


if __name__ == "__main__":
    main()
