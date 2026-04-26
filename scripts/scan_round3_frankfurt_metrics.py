from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUND3_DIR = REPO_ROOT / "prosperity_rust_backtester" / "datasets" / "round3"
OUT_DIR = REPO_ROOT / "analysis" / "round3_frankfurt_metrics"
ROUND3_DAYS = (0, 1, 2)


@dataclass(frozen=True)
class StrategySpec:
    name: str
    description: str
    mode: str
    take_edge: float = 1.0
    quote_edge: float = 1.0
    imbalance_threshold: float = 0.15
    only_products: tuple[str, ...] = ()


STRATEGIES: tuple[StrategySpec, ...] = (
    StrategySpec("best_bid_ask_mid_quote", "Midpoint / inside spread quoting.", "mid"),
    StrategySpec("wall_mid_reversion", "Wall-mid reversion anchor.", "wall_mid"),
    StrategySpec("volume_imbalance", "Top-of-book imbalance signal.", "imbalance", imbalance_threshold=0.20),
    StrategySpec("microprice", "Microprice edge signal.", "microprice"),
    StrategySpec("over_underbid", "One-tick book improvement logic.", "quote_improve"),
    StrategySpec("take_favorable_levels", "Take favorable visible liquidity.", "take"),
    StrategySpec("hybrid_book_signal", "Blend wall-mid, imbalance, and microprice.", "hybrid", imbalance_threshold=0.12),
)

BLEND_WEIGHTS = (0.25, 0.5, 0.75, 1.0, 1.5)


def load_round3_prices() -> pd.DataFrame:
    frames = [pd.read_csv(ROUND3_DIR / f"prices_round_3_day_{day}.csv", sep=";") for day in ROUND3_DAYS]
    prices = pd.concat(frames, ignore_index=True)
    prices = prices.sort_values(["product", "day", "timestamp"]).reset_index(drop=True)
    for col in [
        "bid_volume_1",
        "bid_volume_2",
        "bid_volume_3",
        "ask_volume_1",
        "ask_volume_2",
        "ask_volume_3",
    ]:
        prices[col] = prices[col].fillna(0)
    return prices


def load_round3_trades() -> pd.DataFrame:
    frames = [pd.read_csv(ROUND3_DIR / f"trades_round_3_day_{day}.csv", sep=";") for day in ROUND3_DAYS]
    trades = pd.concat(frames, ignore_index=True)
    trades = trades.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
    return trades


def enrich_prices(prices: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    prices = prices.copy()
    prices["bid_vol_sum"] = prices[["bid_volume_1", "bid_volume_2", "bid_volume_3"]].sum(axis=1)
    prices["ask_vol_sum"] = prices[["ask_volume_1", "ask_volume_2", "ask_volume_3"]].abs().sum(axis=1)
    denom = (prices["bid_vol_sum"] + prices["ask_vol_sum"]).replace(0, np.nan)
    prices["imbalance"] = (prices["bid_vol_sum"] - prices["ask_vol_sum"]) / denom
    prices["microprice"] = (
        prices["ask_price_1"] * prices["bid_volume_1"]
        + prices["bid_price_1"] * prices["ask_volume_1"].abs()
    ) / (prices["bid_volume_1"] + prices["ask_volume_1"].abs())
    prices["wall_mid"] = 0.5 * (prices["bid_price_1"] + prices["ask_price_1"])
    prices["mid_next"] = prices.groupby("product")["mid_price"].shift(-1)
    prices["ret_next"] = prices["mid_next"] - prices["mid_price"]
    prices["ret_next_pct"] = prices["ret_next"] / prices["mid_price"]
    prices["micro_edge"] = prices["microprice"] - prices["mid_price"]

    trade_mid = trades.merge(
        prices[["day", "timestamp", "product", "mid_price", "bid_price_1", "ask_price_1"]],
        left_on=["timestamp", "symbol"],
        right_on=["timestamp", "product"],
        how="left",
    )
    trade_mid["signed_vol"] = np.where(
        trade_mid["price"] >= trade_mid["mid_price"],
        trade_mid["quantity"],
        -trade_mid["quantity"],
    )
    flow = (
        trade_mid.groupby(["day", "timestamp", "symbol"], as_index=False)
        .agg(flow=("signed_vol", "sum"), trade_qty=("quantity", "sum"))
        .rename(columns={"symbol": "product"})
    )
    prices = prices.merge(flow, on=["day", "timestamp", "product"], how="left")
    prices["flow"] = prices["flow"].fillna(0)
    prices["trade_qty"] = prices["trade_qty"].fillna(0)
    return prices


def corr(a: pd.Series, b: pd.Series) -> float:
    if a.nunique(dropna=True) < 2 or b.nunique(dropna=True) < 2:
        return float("nan")
    return float(a.corr(b))


def sign_hit_rate(signal: pd.Series, future_return: pd.Series) -> float:
    valid = signal.notna() & future_return.notna() & (signal != 0)
    if valid.sum() == 0:
        return float("nan")
    s = signal[valid]
    r = future_return[valid]
    return float((((s > 0) & (r > 0)) | ((s < 0) & (r < 0))).mean())


def evaluate_feature_frame(df: pd.DataFrame, feature: str) -> dict[str, float]:
    out: dict[str, float] = {}
    out["pearson_fwd1"] = corr(df[feature], df["ret_next"])
    out["pearson_fwd1_pct"] = corr(df[feature], df["ret_next_pct"])
    out["hit_rate"] = sign_hit_rate(df[feature], df["ret_next"])
    for lag in (1, 2, 3, 5, 10):
        future = df["mid_price"].shift(-lag) - df["mid_price"]
        out[f"corr_lag_{lag}"] = corr(df[feature], future)
    return out


def per_product_metrics(prices: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product, df in prices.groupby("product", sort=True):
        for feature in ("flow", "imbalance", "micro_edge", "wall_mid"):
            metrics = evaluate_feature_frame(df, feature)
            rows.append(
                {
                    "product": product,
                    "feature": feature,
                    "n": int(df["ret_next"].notna().sum()),
                    **metrics,
                }
            )
    return rows


def per_day_metrics(prices: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for day, df in prices.groupby("day", sort=True):
        for feature in ("flow", "imbalance", "micro_edge", "wall_mid"):
            metrics = evaluate_feature_frame(df, feature)
            rows.append(
                {
                    "day": int(day),
                    "feature": feature,
                    "n": int(df["ret_next"].notna().sum()),
                    **metrics,
                }
            )
    return rows


def walk_forward_metrics(prices: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product, df in prices.groupby("product", sort=True):
        for feature in ("flow", "imbalance", "micro_edge", "wall_mid"):
            cumulative = 0.0
            for day in ROUND3_DAYS:
                day_df = df[df["day"] == day]
                if day_df.empty:
                    continue
                metrics = evaluate_feature_frame(day_df, feature)
                day_pnl_proxy = float((day_df[feature].fillna(0) * day_df["ret_next"].fillna(0)).sum())
                cumulative += day_pnl_proxy
                rows.append(
                    {
                        "product": product,
                        "day": day,
                        "feature": feature,
                        "pearson_fwd1": metrics["pearson_fwd1"],
                        "hit_rate": metrics["hit_rate"],
                        "signal_x_return_proxy": day_pnl_proxy,
                        "cumulative_proxy": cumulative,
                    }
                )
    return rows


def strategy_scores(prices: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in STRATEGIES:
        df = prices if not spec.only_products else prices[prices["product"].isin(spec.only_products)]
        if df.empty:
            continue
        if spec.mode == "mid":
            signal = df["mid_price"] - df["mid_price"].groupby(df["product"]).transform("median")
        elif spec.mode == "wall_mid":
            signal = df["wall_mid"] - df["mid_price"]
        elif spec.mode == "imbalance":
            signal = df["imbalance"]
        elif spec.mode == "microprice":
            signal = df["micro_edge"]
        elif spec.mode == "quote_improve":
            signal = (df["ask_price_1"] - df["bid_price_1"]).clip(lower=0)
            signal = -signal
        elif spec.mode == "take":
            signal = np.where(df["micro_edge"] > spec.take_edge, 1.0, np.where(df["micro_edge"] < -spec.take_edge, -1.0, 0.0))
            signal = pd.Series(signal, index=df.index)
        else:
            signal = 0.5 * df["micro_edge"] + 0.5 * df["wall_mid"].sub(df["mid_price"]) + df["imbalance"] * spec.quote_edge

        rows.append(
            {
                "strategy": spec.name,
                "description": spec.description,
                "mode": spec.mode,
                "n": int(df["ret_next"].notna().sum()),
                "corr_signal_next_return": corr(pd.Series(signal, index=df.index), df["ret_next"]),
                "corr_signal_next_return_pct": corr(pd.Series(signal, index=df.index), df["ret_next_pct"]),
                "hit_rate": sign_hit_rate(pd.Series(signal, index=df.index), df["ret_next"]),
                "proxy_pnl": float((pd.Series(signal, index=df.index).fillna(0) * df["ret_next"].fillna(0)).sum()),
            }
        )

    for w_micro in BLEND_WEIGHTS:
        for w_inv_imb in BLEND_WEIGHTS:
            blend = w_micro * prices["micro_edge"].fillna(0) - w_inv_imb * prices["imbalance"].fillna(0)
            rows.append(
                {
                    "strategy": f"micro_invimb_{w_micro:g}_{w_inv_imb:g}",
                    "description": "Blend microprice edge with inverted imbalance.",
                    "mode": "blend",
                    "n": int(prices["ret_next"].notna().sum()),
                    "corr_signal_next_return": corr(blend, prices["ret_next"]),
                    "corr_signal_next_return_pct": corr(blend, prices["ret_next_pct"]),
                    "hit_rate": sign_hit_rate(blend, prices["ret_next"]),
                    "proxy_pnl": float((blend.fillna(0) * prices["ret_next"].fillna(0)).sum()),
                }
            )
    return rows


def best_blend_by_product(prices: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product, df in prices.groupby("product", sort=True):
        best: dict[str, object] | None = None
        for w_micro in BLEND_WEIGHTS:
            for w_inv_imb in BLEND_WEIGHTS:
                blend = w_micro * df["micro_edge"].fillna(0) - w_inv_imb * df["imbalance"].fillna(0)
                score = float((blend * df["ret_next"].fillna(0)).sum())
                row = {
                    "product": product,
                    "w_micro": w_micro,
                    "w_inv_imb": w_inv_imb,
                    "corr_signal_next_return": corr(blend, df["ret_next"]),
                    "hit_rate": sign_hit_rate(blend, df["ret_next"]),
                    "proxy_pnl": score,
                }
                if best is None or score > float(best["proxy_pnl"]):
                    best = row
        if best is not None:
            rows.append(best)
    return rows


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prices = enrich_prices(load_round3_prices(), load_round3_trades())

    product_rows = per_product_metrics(prices)
    day_rows = per_day_metrics(prices)
    walk_rows = walk_forward_metrics(prices)
    strategy_rows = strategy_scores(prices)
    blend_rows = best_blend_by_product(prices)

    (OUT_DIR / "round3_product_metrics.json").write_text(json.dumps(product_rows, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_day_metrics.json").write_text(json.dumps(day_rows, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_walk_forward_metrics.json").write_text(json.dumps(walk_rows, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_strategy_scores.json").write_text(json.dumps(strategy_rows, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_best_blend_by_product.json").write_text(json.dumps(blend_rows, indent=2), encoding="utf-8")

    def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(OUT_DIR / "round3_product_metrics.csv", product_rows)
    write_csv(OUT_DIR / "round3_day_metrics.csv", day_rows)
    write_csv(OUT_DIR / "round3_walk_forward_metrics.csv", walk_rows)
    write_csv(OUT_DIR / "round3_strategy_scores.csv", strategy_rows)
    write_csv(OUT_DIR / "round3_best_blend_by_product.csv", blend_rows)

    print(f"Wrote metrics to {OUT_DIR}")


if __name__ == "__main__":
    main()
