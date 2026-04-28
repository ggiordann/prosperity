from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("/Users/giordanmasen/Desktop/projects/prosperity")
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round4"
OUT = ROOT / "analysis" / "round4_structural_edges"
OUT.mkdir(parents=True, exist_ok=True)

UNDERLYING = "VELVETFRUIT_EXTRACT"
STRIKES = {
    "VEV_4000": 4000.0,
    "VEV_4500": 4500.0,
    "VEV_5000": 5000.0,
    "VEV_5100": 5100.0,
    "VEV_5200": 5200.0,
    "VEV_5300": 5300.0,
    "VEV_5400": 5400.0,
    "VEV_5500": 5500.0,
    "VEV_6000": 6000.0,
    "VEV_6500": 6500.0,
}


@dataclass(frozen=True)
class Score:
    signal: str
    product: str
    horizon: int
    threshold: float
    day: int
    count: int
    mean_edge: float
    total_edge: float
    hit_rate: float
    t_stat: float


@dataclass(frozen=True)
class PairScore:
    signal: str
    x_product: str
    y_product: str
    beta: float
    horizon: int
    threshold: float
    day: int
    count: int
    mean_edge: float
    total_edge: float
    hit_rate: float
    t_stat: float


def load_prices() -> pd.DataFrame:
    frames = []
    for day in (1, 2, 3):
        path = DATA / f"prices_round_4_day_{day}.csv"
        frame = pd.read_csv(path, sep=";")
        frame["day"] = day
        frames.append(frame)
    frame = pd.concat(frames, ignore_index=True)
    frame = frame.rename(
        columns={
            "bid_price_1": "bid",
            "ask_price_1": "ask",
            "bid_volume_1": "bid_qty",
            "ask_volume_1": "ask_qty",
        }
    )
    return frame.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)


def wide_prices(prices: pd.DataFrame, column: str) -> pd.DataFrame:
    return prices.pivot(index=["day", "timestamp"], columns="product", values=column).sort_index()


def rolling_z(values: pd.Series, window: int = 200) -> pd.Series:
    grouped = values.groupby(level=0, group_keys=False)
    mean = grouped.transform(lambda s: s.rolling(window, min_periods=40).mean())
    sd = grouped.transform(lambda s: s.rolling(window, min_periods=40).std(ddof=0))
    return (values - mean) / sd.replace(0.0, np.nan)


def score_signal(
    mids: pd.DataFrame,
    bids: pd.DataFrame,
    asks: pd.DataFrame,
    signal: pd.Series,
    product: str,
    name: str,
    horizon: int,
    threshold: float,
) -> list[Score]:
    product_mid = mids[product]
    product_bid = bids[product]
    product_ask = asks[product]
    future_mid = product_mid.groupby(level=0).shift(-horizon)
    side = pd.Series(0.0, index=signal.index)
    side[signal > threshold] = -1.0
    side[signal < -threshold] = 1.0
    entry = pd.Series(np.nan, index=signal.index)
    entry[side > 0] = product_ask[side > 0]
    entry[side < 0] = product_bid[side < 0]
    edge = pd.Series(np.nan, index=signal.index)
    edge[side > 0] = future_mid[side > 0] - entry[side > 0]
    edge[side < 0] = entry[side < 0] - future_mid[side < 0]
    rows: list[Score] = []
    for day in (1, 2, 3):
        day_edge = edge.xs(day, level=0).dropna()
        day_edge = day_edge[side.xs(day, level=0).reindex(day_edge.index).abs() > 0]
        count = int(day_edge.shape[0])
        if count == 0:
            rows.append(Score(name, product, horizon, threshold, day, 0, math.nan, 0.0, math.nan, math.nan))
            continue
        mean_edge = float(day_edge.mean())
        sd = float(day_edge.std(ddof=1)) if count > 1 else math.nan
        t_stat = mean_edge / sd * math.sqrt(count) if sd and sd > 0 else math.nan
        hit_rate = float((day_edge > 0).mean())
        rows.append(
            Score(
                name,
                product,
                horizon,
                threshold,
                day,
                count,
                mean_edge,
                float(day_edge.sum()),
                hit_rate,
                t_stat,
            )
        )
    return rows


def build_surface_signals(mids: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    signals: dict[tuple[str, str], pd.Series] = {}
    underlying = mids[UNDERLYING]
    vouchers = [product for product in STRIKES if product in mids.columns]

    premiums = pd.DataFrame(index=mids.index)
    for product in vouchers:
        premiums[product] = mids[product] - np.maximum(underlying - STRIKES[product], 0.0)

    for product in vouchers:
        premium_z = rolling_z(premiums[product])
        signals[("premium_rolling_z", product)] = premium_z

    strike_order = sorted(vouchers, key=lambda product: STRIKES[product])
    for i, product in enumerate(strike_order):
        if i == 0 or i == len(strike_order) - 1:
            continue
        left = strike_order[i - 1]
        right = strike_order[i + 1]
        k0, k1, k2 = STRIKES[left], STRIKES[product], STRIKES[right]
        weight = (k1 - k0) / (k2 - k0)
        interp_price = mids[left] * (1.0 - weight) + mids[right] * weight
        interp_premium = premiums[left] * (1.0 - weight) + premiums[right] * weight
        signals[(f"price_wing_{left}_{right}", product)] = rolling_z(mids[product] - interp_price)
        signals[(f"premium_wing_{left}_{right}", product)] = rolling_z(premiums[product] - interp_premium)

    return signals


def summarize_consistency(rows: list[Score]) -> pd.DataFrame:
    frame = pd.DataFrame([row.__dict__ for row in rows])
    grouped = (
        frame.groupby(["signal", "product", "horizon", "threshold"], dropna=False)
        .agg(
            days=("day", "count"),
            live_days=("count", lambda s: int((s > 0).sum())),
            total_count=("count", "sum"),
            mean_of_days=("mean_edge", "mean"),
            min_day_edge=("mean_edge", "min"),
            total_edge=("total_edge", "sum"),
            mean_hit_rate=("hit_rate", "mean"),
            min_t_stat=("t_stat", "min"),
        )
        .reset_index()
    )
    grouped["consistent"] = (grouped["live_days"].eq(3)) & (grouped["min_day_edge"] > 0)
    return grouped.sort_values(
        ["consistent", "total_edge", "mean_of_days", "total_count"],
        ascending=[False, False, False, False],
    )


def fit_pair(mids: pd.DataFrame, x_product: str, y_product: str, train_days: tuple[int, ...]) -> tuple[float, float, float] | None:
    subset = mids.loc[mids.index.get_level_values(0).isin(train_days), [x_product, y_product]].dropna()
    if subset.shape[0] < 100:
        return None
    x = subset[x_product].to_numpy(dtype=float)
    y = subset[y_product].to_numpy(dtype=float)
    x_var = float(np.var(x))
    if x_var <= 1e-9:
        return None
    beta = float(np.cov(x, y, ddof=0)[0, 1] / x_var)
    if not (0.05 <= beta <= 5.0):
        return None
    alpha = float(y.mean() - beta * x.mean())
    resid = y - (alpha + beta * x)
    sd = float(np.std(resid))
    if sd <= 1e-9:
        return None
    return alpha, beta, sd


def score_pair(
    mids: pd.DataFrame,
    bids: pd.DataFrame,
    asks: pd.DataFrame,
    x_product: str,
    y_product: str,
    alpha: float,
    beta: float,
    sd: float,
    name: str,
    horizon: int,
    threshold: float,
) -> list[PairScore]:
    fair_y = alpha + beta * mids[x_product]
    z = (mids[y_product] - fair_y) / sd
    future_x = mids[x_product].groupby(level=0).shift(-horizon)
    future_y = mids[y_product].groupby(level=0).shift(-horizon)
    side_y = pd.Series(0.0, index=z.index)
    side_y[z > threshold] = -1.0
    side_y[z < -threshold] = 1.0

    edge = pd.Series(np.nan, index=z.index)
    high = side_y < 0
    low = side_y > 0
    edge[high] = (
        bids[y_product][high]
        - future_y[high]
        + beta * (future_x[high] - asks[x_product][high])
    )
    edge[low] = (
        future_y[low]
        - asks[y_product][low]
        + beta * (bids[x_product][low] - future_x[low])
    )

    rows: list[PairScore] = []
    for day in (1, 2, 3):
        day_edge = edge.xs(day, level=0).dropna()
        day_edge = day_edge[side_y.xs(day, level=0).reindex(day_edge.index).abs() > 0]
        count = int(day_edge.shape[0])
        if count == 0:
            rows.append(
                PairScore(name, x_product, y_product, beta, horizon, threshold, day, 0, math.nan, 0.0, math.nan, math.nan)
            )
            continue
        mean_edge = float(day_edge.mean())
        sd_edge = float(day_edge.std(ddof=1)) if count > 1 else math.nan
        t_stat = mean_edge / sd_edge * math.sqrt(count) if sd_edge and sd_edge > 0 else math.nan
        rows.append(
            PairScore(
                name,
                x_product,
                y_product,
                beta,
                horizon,
                threshold,
                day,
                count,
                mean_edge,
                float(day_edge.sum()),
                float((day_edge > 0).mean()),
                t_stat,
            )
        )
    return rows


def summarize_pairs(rows: list[PairScore]) -> pd.DataFrame:
    frame = pd.DataFrame([row.__dict__ for row in rows])
    grouped = (
        frame.groupby(["signal", "x_product", "y_product", "horizon", "threshold"], dropna=False)
        .agg(
            beta=("beta", "first"),
            days=("day", "count"),
            live_days=("count", lambda s: int((s > 0).sum())),
            total_count=("count", "sum"),
            mean_of_days=("mean_edge", "mean"),
            min_day_edge=("mean_edge", "min"),
            total_edge=("total_edge", "sum"),
            mean_hit_rate=("hit_rate", "mean"),
            min_t_stat=("t_stat", "min"),
        )
        .reset_index()
    )
    grouped["consistent"] = (grouped["live_days"].eq(3)) & (grouped["min_day_edge"] > 0)
    return grouped.sort_values(
        ["consistent", "total_edge", "mean_of_days", "total_count"],
        ascending=[False, False, False, False],
    )


def main() -> None:
    prices = load_prices()
    mids = wide_prices(prices, "mid_price")
    bids = wide_prices(prices, "bid")
    asks = wide_prices(prices, "ask")

    signals = build_surface_signals(mids)
    rows: list[Score] = []
    for (name, product), signal in signals.items():
        if product not in bids or product not in asks:
            continue
        for horizon in (1, 5, 10, 20, 50, 100):
            for threshold in (1.0, 1.5, 2.0, 2.5):
                rows.extend(score_signal(mids, bids, asks, signal, product, name, horizon, threshold))

    detail = pd.DataFrame([row.__dict__ for row in rows])
    summary = summarize_consistency(rows)
    detail.to_csv(OUT / "surface_signal_day_detail.csv", index=False)
    summary.to_csv(OUT / "surface_signal_summary.csv", index=False)

    pair_products = [UNDERLYING, "HYDROGEL_PACK", *[p for p in STRIKES if p in mids.columns and p not in {"VEV_6000", "VEV_6500"}]]
    pair_rows: list[PairScore] = []
    for train_days, name in [((1,), "pair_train_d1"), ((1, 2), "pair_train_d12"), ((1, 2, 3), "pair_all_days_probe")]:
        for x_product in pair_products:
            for y_product in pair_products:
                if x_product == y_product:
                    continue
                params = fit_pair(mids, x_product, y_product, train_days)
                if params is None:
                    continue
                alpha, beta, resid_sd = params
                for horizon in (1, 5, 10, 20, 50, 100, 250):
                    for threshold in (1.0, 1.5, 2.0, 2.5):
                        pair_rows.extend(
                            score_pair(
                                mids,
                                bids,
                                asks,
                                x_product,
                                y_product,
                                alpha,
                                beta,
                                resid_sd,
                                name,
                                horizon,
                                threshold,
                            )
                        )
    pair_detail = pd.DataFrame([row.__dict__ for row in pair_rows])
    pair_summary = summarize_pairs(pair_rows)
    pair_detail.to_csv(OUT / "pair_signal_day_detail.csv", index=False)
    pair_summary.to_csv(OUT / "pair_signal_summary.csv", index=False)

    print("Top consistent surface signals after crossing spread:")
    print(summary[summary["consistent"]].head(30).to_string(index=False))
    print("\nTop overall surface signals after crossing spread:")
    print(summary.head(30).to_string(index=False))
    print("\nTop consistent pair signals after crossing both spreads:")
    print(pair_summary[pair_summary["consistent"]].head(30).to_string(index=False))
    print("\nTop overall pair signals after crossing both spreads:")
    print(pair_summary[pair_summary["total_count"] > 0].head(30).to_string(index=False))


if __name__ == "__main__":
    main()
