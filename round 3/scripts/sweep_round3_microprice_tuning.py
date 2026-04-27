from __future__ import annotations

import csv
import json
from itertools import product as cartesian_product
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUND3_DIR = REPO_ROOT / "prosperity_rust_backtester" / "datasets" / "round3"
OUT_DIR = REPO_ROOT / "round 3" / "analysis" / "round3_microprice_tuning"
ROUND3_DAYS = (0, 1, 2)
TARGET_PRODUCTS = ("HYDROGEL_PACK", "VELVETFRUIT_EXTRACT")

K_MICRO_VALUES = (0.25, 0.5, 0.75, 1.0, 1.5)
K_IMBALANCE_VALUES = (0.0, 0.25, 0.5, 0.75, 1.0)
THRESHOLDS = (0.0, 0.05, 0.10, 0.15, 0.20)


def load_prices() -> pd.DataFrame:
    frames = [pd.read_csv(ROUND3_DIR / f"prices_round_3_day_{day}.csv", sep=";") for day in ROUND3_DAYS]
    prices = pd.concat(frames, ignore_index=True)
    prices = prices.sort_values(["product", "day", "timestamp"]).reset_index(drop=True)
    for col in ["bid_volume_1", "bid_volume_2", "bid_volume_3", "ask_volume_1", "ask_volume_2", "ask_volume_3"]:
        prices[col] = prices[col].fillna(0)
    return prices


def enrich(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df["bid_vol_sum"] = df[["bid_volume_1", "bid_volume_2", "bid_volume_3"]].sum(axis=1)
    df["ask_vol_sum"] = df[["ask_volume_1", "ask_volume_2", "ask_volume_3"]].abs().sum(axis=1)
    total = (df["bid_vol_sum"] + df["ask_vol_sum"]).replace(0, np.nan)
    df["imbalance"] = (df["bid_vol_sum"] - df["ask_vol_sum"]) / total
    df["wall_mid"] = 0.5 * (df["bid_price_1"] + df["ask_price_1"])
    df["microprice"] = (
        df["ask_price_1"] * df["bid_volume_1"]
        + df["bid_price_1"] * df["ask_volume_1"].abs()
    ) / (df["bid_volume_1"] + df["ask_volume_1"].abs())
    df["micro_edge"] = df["microprice"] - df["mid_price"]
    df["mid_next"] = df.groupby("product")["mid_price"].shift(-1)
    df["ret_next"] = df["mid_next"] - df["mid_price"]
    df["ret_next_pct"] = df["ret_next"] / df["mid_price"]
    df["flow"] = 0.0
    return df


def corr(a: pd.Series, b: pd.Series) -> float:
    valid = a.notna() & b.notna()
    if valid.sum() < 3:
        return float("nan")
    if a[valid].nunique() < 2 or b[valid].nunique() < 2:
        return float("nan")
    return float(a[valid].corr(b[valid]))


def hit_rate(signal: pd.Series, future_return: pd.Series) -> float:
    valid = signal.notna() & future_return.notna() & (signal != 0)
    if valid.sum() == 0:
        return float("nan")
    s = signal[valid]
    r = future_return[valid]
    return float((((s > 0) & (r > 0)) | ((s < 0) & (r < 0))).mean())


def summarize_signal(df: pd.DataFrame, signal: pd.Series, threshold: float) -> dict[str, float]:
    active = signal.abs() >= threshold
    if active.sum() == 0:
        return {
            "active_rate": 0.0,
            "corr": float("nan"),
            "hit_rate": float("nan"),
            "proxy_pnl": 0.0,
            "mean_abs_signal": float(signal.abs().mean()),
        }
    selected = signal.where(active, 0.0)
    return {
        "active_rate": float(active.mean()),
        "corr": corr(selected, df["ret_next"]),
        "hit_rate": hit_rate(selected, df["ret_next"]),
        "proxy_pnl": float((selected.fillna(0) * df["ret_next"].fillna(0)).sum()),
        "mean_abs_signal": float(signal.abs().mean()),
    }


def tune_microprice(prices: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product_name, df in prices.groupby("product", sort=True):
        if product_name not in TARGET_PRODUCTS:
            continue
        for k_micro, k_imb, thr in cartesian_product(K_MICRO_VALUES, K_IMBALANCE_VALUES, THRESHOLDS):
            fair = df["mid_price"] + k_micro * df["micro_edge"] - k_imb * df["imbalance"]
            signal = fair - df["mid_price"]
            metrics = summarize_signal(df, signal, thr)
            rows.append(
                {
                    "product": product_name,
                    "k_micro": k_micro,
                    "k_imbalance": k_imb,
                    "threshold": thr,
                    **metrics,
                }
            )
    return rows


def tune_baselines(prices: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product, df in prices.groupby("product", sort=True):
        if product not in TARGET_PRODUCTS:
            continue
        candidates = {
            "micro_edge": df["micro_edge"],
            "imbalance": -df["imbalance"],
            "flow": df["flow"],
            "hybrid": 0.5 * df["micro_edge"] - 0.5 * df["imbalance"],
            "wall_mid": df["wall_mid"] - df["mid_price"],
        }
        for name, signal in candidates.items():
            rows.append(
                {
                    "product": product,
                    "signal": name,
                    "corr": corr(signal, df["ret_next"]),
                    "hit_rate": hit_rate(signal, df["ret_next"]),
                    "proxy_pnl": float((signal.fillna(0) * df["ret_next"].fillna(0)).sum()),
                }
            )
    return rows


def rank_overall(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    frame = pd.DataFrame(rows)
    grouped = (
        frame.groupby(["k_micro", "k_imbalance", "threshold"], as_index=False)
        .agg(
            mean_corr=("corr", "mean"),
            mean_hit_rate=("hit_rate", "mean"),
            mean_proxy_pnl=("proxy_pnl", "mean"),
            mean_active_rate=("active_rate", "mean"),
        )
        .sort_values(["mean_proxy_pnl", "mean_corr"], ascending=False)
    )
    return grouped.to_dict(orient="records")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prices = enrich(load_prices())
    prices = prices[prices["product"].isin(TARGET_PRODUCTS)].copy()

    micro_rows = tune_microprice(prices)
    baseline_rows = tune_baselines(prices)
    ranked = rank_overall(micro_rows)

    (OUT_DIR / "round3_micro_tuning.json").write_text(json.dumps(micro_rows, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_baseline_signals.json").write_text(json.dumps(baseline_rows, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_micro_tuning_ranked.json").write_text(json.dumps(ranked, indent=2), encoding="utf-8")

    def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(OUT_DIR / "round3_micro_tuning.csv", micro_rows)
    write_csv(OUT_DIR / "round3_baseline_signals.csv", baseline_rows)
    write_csv(OUT_DIR / "round3_micro_tuning_ranked.csv", ranked)

    print(f"Wrote tuning results to {OUT_DIR}")


if __name__ == "__main__":
    main()
