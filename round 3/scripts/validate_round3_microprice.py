from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
ROUND3_DIR = REPO_ROOT / "prosperity_rust_backtester" / "datasets" / "round3"
OUT_DIR = REPO_ROOT / "round 3" / "analysis" / "round3_microprice_validation"
ROUND3_DAYS = (0, 1, 2)
LEADS = (1, 2, 3, 5, 10)
BUCKETS = 5


def load_prices() -> pd.DataFrame:
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


def enrich(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df["bid_vol_sum"] = df[["bid_volume_1", "bid_volume_2", "bid_volume_3"]].sum(axis=1)
    df["ask_vol_sum"] = df[["ask_volume_1", "ask_volume_2", "ask_volume_3"]].abs().sum(axis=1)
    total = (df["bid_vol_sum"] + df["ask_vol_sum"]).replace(0, np.nan)
    df["imbalance"] = (df["bid_vol_sum"] - df["ask_vol_sum"]) / total
    df["microprice"] = (
        df["ask_price_1"] * df["bid_volume_1"]
        + df["bid_price_1"] * df["ask_volume_1"].abs()
    ) / (df["bid_volume_1"] + df["ask_volume_1"].abs())
    df["micro_edge"] = df["microprice"] - df["mid_price"]
    df["mid_next"] = df.groupby("product")["mid_price"].shift(-1)
    df["ret_next"] = df["mid_next"] - df["mid_price"]
    df["ret_next_pct"] = df["ret_next"] / df["mid_price"]
    df["ret_fwd_10"] = df.groupby("product")["mid_price"].shift(-10) - df["mid_price"]
    return df


def corr(a: pd.Series, b: pd.Series) -> float:
    valid = a.notna() & b.notna()
    if valid.sum() < 3:
        return float("nan")
    if a[valid].nunique() < 2 or b[valid].nunique() < 2:
        return float("nan")
    return float(a[valid].corr(b[valid]))


def sign_hit_rate(signal: pd.Series, future_return: pd.Series) -> float:
    valid = signal.notna() & future_return.notna() & (signal != 0)
    if valid.sum() == 0:
        return float("nan")
    s = signal[valid]
    r = future_return[valid]
    return float((((s > 0) & (r > 0)) | ((s < 0) & (r < 0))).mean())


def regression_beta(signal: pd.Series, future_return: pd.Series) -> float:
    valid = signal.notna() & future_return.notna()
    if valid.sum() < 3:
        return float("nan")
    x = signal[valid].to_numpy()
    y = future_return[valid].to_numpy()
    vx = np.var(x)
    if vx == 0:
        return float("nan")
    return float(np.cov(x, y, ddof=0)[0, 1] / vx)


def product_day_table(df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product, p in df.groupby("product", sort=True):
        for day, d in p.groupby("day", sort=True):
            rows.append(
                {
                    "product": product,
                    "day": int(day),
                    "n": int(len(d)),
                    "corr_micro_edge_next": corr(d["micro_edge"], d["ret_next"]),
                    "corr_micro_edge_pct_next": corr(d["micro_edge"], d["ret_next_pct"]),
                    "hit_rate": sign_hit_rate(d["micro_edge"], d["ret_next"]),
                    "beta_micro_edge_next": regression_beta(d["micro_edge"], d["ret_next"]),
                    "mean_micro_edge": float(d["micro_edge"].mean()),
                    "mean_future_return": float(d["ret_next"].mean()),
                }
            )
    return rows


def lead_lag_table(df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product, p in df.groupby("product", sort=True):
        for lead in LEADS:
            future = p["mid_price"].shift(-lead) - p["mid_price"]
            rows.append(
                {
                    "product": product,
                    "lead": lead,
                    "corr_micro_edge_future": corr(p["micro_edge"], future),
                    "corr_imbalance_future": corr(p["imbalance"], future),
                    "corr_flow_future": float("nan"),
                }
            )
    return rows


def bucket_table(df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product, p in df.groupby("product", sort=True):
        signal = p["micro_edge"].copy()
        try:
            buckets = pd.qcut(signal.rank(method="first"), BUCKETS, labels=False, duplicates="drop")
        except ValueError:
            continue
        p = p.assign(bucket=buckets)
        for bucket, b in p.groupby("bucket", sort=True):
            rows.append(
                {
                    "product": product,
                    "bucket": int(bucket),
                    "n": int(len(b)),
                    "avg_micro_edge": float(b["micro_edge"].mean()),
                    "avg_next_return": float(b["ret_next"].mean()),
                    "avg_next_return_pct": float(b["ret_next_pct"].mean()),
                }
            )
    return rows


def summary_table(df: pd.DataFrame) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product, p in df.groupby("product", sort=True):
        rows.append(
            {
                "product": product,
                "n": int(len(p)),
                "corr_micro_edge_next": corr(p["micro_edge"], p["ret_next"]),
                "corr_micro_edge_pct_next": corr(p["micro_edge"], p["ret_next_pct"]),
                "hit_rate": sign_hit_rate(p["micro_edge"], p["ret_next"]),
                "beta_micro_edge_next": regression_beta(p["micro_edge"], p["ret_next"]),
                "mean_micro_edge": float(p["micro_edge"].mean()),
                "std_micro_edge": float(p["micro_edge"].std()),
                "mean_future_return": float(p["ret_next"].mean()),
                "std_future_return": float(p["ret_next"].std()),
                "frac_micro_edge_positive": float((p["micro_edge"] > 0).mean()),
                "frac_micro_edge_negative": float((p["micro_edge"] < 0).mean()),
            }
        )
    return rows


def normalize_within_product(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["micro_edge_z"] = out.groupby("product")["micro_edge"].transform(
        lambda s: (s - s.mean()) / (s.std(ddof=0) if s.std(ddof=0) not in (0, np.nan) else np.nan)
    )
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prices = enrich(load_prices())
    prices = normalize_within_product(prices)

    summary = summary_table(prices)
    per_day = product_day_table(prices)
    lead_lag = lead_lag_table(prices)
    buckets = bucket_table(prices)

    (OUT_DIR / "round3_microprice_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_microprice_per_day.json").write_text(json.dumps(per_day, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_microprice_lead_lag.json").write_text(json.dumps(lead_lag, indent=2), encoding="utf-8")
    (OUT_DIR / "round3_microprice_buckets.json").write_text(json.dumps(buckets, indent=2), encoding="utf-8")

    def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    write_csv(OUT_DIR / "round3_microprice_summary.csv", summary)
    write_csv(OUT_DIR / "round3_microprice_per_day.csv", per_day)
    write_csv(OUT_DIR / "round3_microprice_lead_lag.csv", lead_lag)
    write_csv(OUT_DIR / "round3_microprice_buckets.csv", buckets)

    print(f"Wrote microprice validation to {OUT_DIR}")


if __name__ == "__main__":
    main()
