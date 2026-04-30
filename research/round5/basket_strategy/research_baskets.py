"""Round 5 basket/synthetic fair value research scan.

Run from the repository root:
    python3 research/round5/basket_strategy/research_baskets.py

The script intentionally uses only numpy/pandas and simple models so the chosen
baskets can be compressed into a sub-100KB Prosperity trader.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5" / "basket_strategy"


def category(product: str) -> str:
    for prefix, name in (
        ("GALAXY_SOUNDS", "GALAXY"),
        ("MICROCHIP", "MICROCHIP"),
        ("OXYGEN_SHAKE", "OXYGEN"),
        ("PANEL", "PANEL"),
        ("PEBBLES", "PEBBLES"),
        ("ROBOT", "ROBOT"),
        ("SLEEP_POD", "SLEEP"),
        ("SNACKPACK", "SNACKPACK"),
        ("TRANSLATOR", "TRANSLATOR"),
        ("UV_VISOR", "UV"),
    ):
        if product.startswith(prefix):
            return name
    raise ValueError(product)


def load_books():
    frames = [
        pd.read_csv(
            path,
            sep=";",
            usecols=["day", "timestamp", "product", "mid_price", "bid_price_1", "ask_price_1"],
        )
        for path in sorted(DATA.glob("prices_round_5_day_*.csv"))
    ]
    raw = pd.concat(frames, ignore_index=True)
    idx = ["day", "timestamp"]
    mid = raw.pivot_table(index=idx, columns="product", values="mid_price").sort_index()
    bid = raw.pivot_table(index=idx, columns="product", values="bid_price_1").sort_index()
    ask = raw.pivot_table(index=idx, columns="product", values="ask_price_1").sort_index()
    return mid, bid, ask


def fit_ols(y: np.ndarray, x: np.ndarray, ridge: float = 0.0):
    x1 = np.column_stack((np.ones(len(x)), x))
    if ridge:
        gram = x1.T @ x1
        penalty = np.eye(gram.shape[0]) * ridge
        penalty[0, 0] = 0.0
        beta = np.linalg.solve(gram + penalty, x1.T @ y)
    else:
        beta = np.linalg.lstsq(x1, y, rcond=None)[0]
    residual = y - x1 @ beta
    center = float(np.median(residual))
    mad = float(np.median(np.abs(residual - center)))
    scale = 1.4826 * mad or float(np.std(residual)) or 1.0
    left = residual[:-1] - residual[:-1].mean()
    right = residual[1:] - residual[1:].mean()
    phi = float((left @ right) / (left @ left)) if left @ left else 0.0
    half_life = -math.log(2) / math.log(phi) if 0 < phi < 0.99999 else 99999.0
    return beta[0] + center, beta[1:], scale, half_life, phi


def score_proxy(y_idx, leg_idx, intercept, beta, sd, day_index, mids, bids, asks, entry, margin, horizon=50):
    total = 0.0
    trades = 0
    per_day = {}
    for day, idx in day_index.items():
        now = idx[:-horizon]
        future = idx[horizon:]
        fair = intercept + mids[now][:, leg_idx] @ beta
        z = (mids[now, y_idx] - fair) / sd
        buy = (z < -entry) & ((fair - asks[now, y_idx]) > margin)
        sell = (z > entry) & ((bids[now, y_idx] - fair) > margin)
        pnl = np.where(buy, mids[future, y_idx] - asks[now, y_idx], 0.0)
        pnl += np.where(sell, bids[now, y_idx] - mids[future, y_idx], 0.0)
        per_day[day] = float(pnl.sum())
        total += per_day[day]
        trades += int(buy.sum() + sell.sum())
    return total, trades, per_day


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mid, bid, ask = load_books()
    products = list(mid.columns)
    prod_index = {p: i for i, p in enumerate(products)}
    cats = {p: category(p) for p in products}
    members = {c: [p for p in products if cats[p] == c] for c in sorted(set(cats.values()))}
    mids, bids, asks = mid.values, bid.values, ask.values
    days = mid.index.get_level_values(0).to_numpy()
    day_index = {day: np.flatnonzero(days == day) for day in sorted(set(days))}

    demeaned = mids.copy()
    for idx in day_index.values():
        demeaned[idx] -= demeaned[idx].mean(axis=0)
    level_corr = np.nan_to_num(np.corrcoef(demeaned, rowvar=False))
    returns = np.vstack([np.diff(mids[idx], axis=0) for idx in day_index.values()])
    return_corr = np.nan_to_num(np.corrcoef(returns, rowvar=False))

    def candidates(product: str):
        yi = prod_index[product]
        others = [p for p in products if p != product]
        by_level = sorted(others, key=lambda p: abs(level_corr[yi, prod_index[p]]), reverse=True)
        by_return = sorted(others, key=lambda p: abs(return_corr[yi, prod_index[p]]), reverse=True)
        cross_level = [p for p in by_level if cats[p] != cats[product]]
        cross_return = [p for p in by_return if cats[p] != cats[product]]
        out = [("cat4", [p for p in members[cats[product]] if p != product], 0.0)]
        for k in (2, 3, 4, 5):
            out.append((f"level{k}", by_level[:k], 0.0))
            out.append((f"return{k}", by_return[:k], 0.0))
        for k in (2, 3, 5):
            out.append((f"cross_level{k}", cross_level[:k], 0.0))
            out.append((f"cross_return{k}", cross_return[:k], 0.0))
        out.append(("ridge8", by_level[:8], 5000.0))
        seen = set()
        for name, legs, ridge in out:
            key = tuple(legs)
            if key and key not in seen:
                seen.add(key)
                yield name, legs, ridge

    folds = [
        ((2,), (3, 4), "train_day_2_test_3_4"),
        ((2, 3), (4,), "train_2_3_test_4"),
        ((3, 4), (2,), "train_3_4_test_2"),
        ((3,), (4,), "remove_day_2_train_3_test_4"),
    ]
    rows = []
    for train_days, test_days, fold_name in folds:
        train_idx = np.concatenate([day_index[d] for d in train_days])
        test_index = {d: day_index[d] for d in test_days}
        for product in products:
            yi = prod_index[product]
            y = mids[train_idx, yi]
            for model_name, legs, ridge in candidates(product):
                leg_idx = [prod_index[p] for p in legs]
                intercept, beta, sd, half_life, phi = fit_ols(y, mids[train_idx][:, leg_idx], ridge)
                if not 1.0 < sd < 2500.0:
                    continue
                best = None
                for entry in (0.8, 1.0, 1.2, 1.5, 1.8, 2.2):
                    for margin in (1.0, 3.0, 5.0, 8.0):
                        pnl, trades, per_day = score_proxy(
                            yi, leg_idx, intercept, beta, sd, test_index, mids, bids, asks, entry, margin
                        )
                        if trades < 20:
                            continue
                        score = pnl / trades
                        if best is None or score > best[0]:
                            best = score, pnl, trades, per_day, entry, margin
                if best is None:
                    continue
                avg, pnl, trades, per_day, entry, margin = best
                rows.append(
                    {
                        "fold": fold_name,
                        "y": product,
                        "name": model_name,
                        "legs": "|".join(legs),
                        "nlegs": len(legs),
                        "cross_legs": sum(cats[p] != cats[product] for p in legs),
                        "proxy_pnl": pnl,
                        "avg_edge": avg,
                        "trades": trades,
                        "sd": sd,
                        "half_life": half_life,
                        "phi": phi,
                        "entry": entry,
                        "margin": margin,
                        "per_day": per_day,
                    }
                )
    result = pd.DataFrame(rows)
    result.to_csv(OUT / "proxy_results.csv", index=False)
    robust = (
        result.groupby(["y", "name", "legs"])
        .agg(
            folds=("fold", "nunique"),
            sum_proxy=("proxy_pnl", "sum"),
            mean_proxy=("proxy_pnl", "mean"),
            min_proxy=("proxy_pnl", "min"),
            avg_edge=("avg_edge", "mean"),
            mean_trades=("trades", "mean"),
            sd=("sd", "mean"),
            half_life=("half_life", "mean"),
            cross_legs=("cross_legs", "first"),
            entry=("entry", "median"),
            margin=("margin", "median"),
        )
        .reset_index()
        .sort_values(["sum_proxy", "avg_edge"], ascending=False)
    )
    robust.to_csv(OUT / "robust_baskets.csv", index=False)
    print(robust.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
