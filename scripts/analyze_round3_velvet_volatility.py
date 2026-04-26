from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
ROUND3_DIR = REPO_ROOT / "prosperity_rust_backtester" / "datasets" / "round3"
OUT_DIR = REPO_ROOT / "analysis" / "round3_velvet_volatility"

UNDERLYING = "VELVETFRUIT_EXTRACT"
DEFAULT_DAYS = (0, 1, 2)
DEFAULT_STRIKES = (5000, 5100, 5200, 5300, 5400, 5500)
DEFAULT_TTE_YEARS = 5.0 / 365.0


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_call(spot: float, strike: float, volatility: float, tte_years: float) -> float:
    if spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0:
        return float("nan")
    if volatility <= 0.0:
        return max(spot - strike, 0.0)

    vol_sqrt_t = volatility * math.sqrt(tte_years)
    if vol_sqrt_t <= 0.0:
        return max(spot - strike, 0.0)

    d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * tte_years) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return spot * normal_cdf(d1) - strike * normal_cdf(d2)


def implied_volatility(
    call_price: float,
    spot: float,
    strike: float,
    tte_years: float,
    *,
    low: float = 1e-6,
    high: float = 5.0,
    tolerance: float = 1e-7,
    max_iterations: int = 80,
) -> float:
    """Invert Black-Scholes with a monotonic bisection search."""

    if not all(math.isfinite(value) for value in (call_price, spot, strike, tte_years)):
        return float("nan")
    if call_price < 0.0 or spot <= 0.0 or strike <= 0.0 or tte_years <= 0.0:
        return float("nan")

    intrinsic = max(spot - strike, 0.0)
    if call_price < intrinsic - tolerance or call_price > spot + tolerance:
        return float("nan")
    if abs(call_price - intrinsic) <= tolerance:
        return 0.0

    upper_price = black_scholes_call(spot, strike, high, tte_years)
    while math.isfinite(upper_price) and upper_price < call_price and high < 20.0:
        high *= 2.0
        upper_price = black_scholes_call(spot, strike, high, tte_years)
    if not math.isfinite(upper_price) or upper_price < call_price:
        return float("nan")

    for _ in range(max_iterations):
        mid = 0.5 * (low + high)
        mid_price = black_scholes_call(spot, strike, mid, tte_years)
        if not math.isfinite(mid_price):
            return float("nan")
        if abs(mid_price - call_price) <= tolerance:
            return mid
        if mid_price < call_price:
            low = mid
        else:
            high = mid

    return 0.5 * (low + high)


def load_round3_prices(days: tuple[int, ...]) -> pd.DataFrame:
    frames = []
    for day in days:
        path = ROUND3_DIR / f"prices_round_3_day_{day}.csv"
        if not path.exists():
            raise FileNotFoundError(path)
        frames.append(pd.read_csv(path, sep=";"))
    prices = pd.concat(frames, ignore_index=True)
    return prices.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)


def infer_observations_per_day(underlying: pd.DataFrame) -> int:
    counts = underlying.groupby("day")["timestamp"].nunique()
    if counts.empty:
        raise ValueError(f"No {UNDERLYING} rows were found.")
    return int(counts.max())


def add_realized_volatility(
    underlying: pd.DataFrame,
    *,
    window: int,
    min_periods: int,
    observations_per_day: int,
) -> pd.DataFrame:
    underlying = underlying.sort_values(["day", "timestamp"]).copy()
    underlying["time_day"] = underlying["day"] + underlying["timestamp"] / 1_000_000.0
    underlying["spot_mid"] = underlying["mid_price"].astype(float)
    underlying["log_return"] = underlying.groupby("day")["spot_mid"].transform(
        lambda prices: np.log(prices).diff()
    )

    rolling_std = (
        underlying.groupby("day")["log_return"]
        .rolling(window=window, min_periods=min_periods)
        .std(ddof=0)
        .reset_index(level=0, drop=True)
    )
    underlying["realized_vol"] = rolling_std * math.sqrt(observations_per_day * 365.0)
    return underlying[["day", "timestamp", "time_day", "spot_mid", "realized_vol"]]


def parse_strike(product: str) -> int | None:
    match = re.fullmatch(r"VEV_(\d+)", product)
    return int(match.group(1)) if match else None


def build_implied_vol_frame(
    prices: pd.DataFrame,
    underlying: pd.DataFrame,
    *,
    strikes: tuple[int, ...],
    tte_years: float,
) -> pd.DataFrame:
    options = prices.copy()
    options["strike"] = options["product"].map(parse_strike)
    options = options[options["strike"].isin(strikes)].copy()
    options = options.rename(columns={"mid_price": "option_mid"})

    merged = options.merge(
        underlying[["day", "timestamp", "time_day", "spot_mid", "realized_vol"]],
        on=["day", "timestamp"],
        how="inner",
    )
    merged = merged.sort_values(["day", "timestamp", "strike"]).reset_index(drop=True)
    merged["implied_vol"] = [
        implied_volatility(
            call_price=float(row.option_mid),
            spot=float(row.spot_mid),
            strike=float(row.strike),
            tte_years=tte_years,
        )
        for row in merged.itertuples(index=False)
    ]
    return merged[
        [
            "day",
            "timestamp",
            "time_day",
            "product",
            "strike",
            "spot_mid",
            "option_mid",
            "realized_vol",
            "implied_vol",
        ]
    ]


def aggregate_implied_volatility(implied_by_strike: pd.DataFrame) -> pd.DataFrame:
    valid = implied_by_strike.replace([np.inf, -np.inf], np.nan)
    valid = valid[valid["implied_vol"].notna() & (valid["implied_vol"] > 0.0)]
    implied = (
        valid.groupby(["day", "timestamp", "time_day"], as_index=False)
        .agg(
            implied_vol_median=("implied_vol", "median"),
            implied_vol_mean=("implied_vol", "mean"),
            implied_vol_count=("implied_vol", "count"),
        )
        .sort_values(["day", "timestamp"])
        .reset_index(drop=True)
    )
    return implied


def plot_volatility(timeseries: pd.DataFrame, output_path: Path) -> None:
    plot_frame = timeseries.dropna(subset=["realized_vol", "implied_vol_median"])

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(
        plot_frame["time_day"],
        plot_frame["realized_vol"],
        label="Realized volatility",
        color="#1f77b4",
        linewidth=1.4,
        alpha=0.9,
    )
    ax.plot(
        plot_frame["time_day"],
        plot_frame["implied_vol_median"],
        label="Implied volatility, median VEV option",
        color="#d62728",
        linewidth=1.4,
        alpha=0.9,
    )
    ax.set_title("VELVETFRUIT_EXTRACT Realized vs Implied Volatility")
    ax.set_xlabel("Round 3 day")
    ax.set_ylabel("Annualized volatility")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate rolling realized volatility for VELVETFRUIT_EXTRACT, "
            "invert VEV option mids to Black-Scholes implied volatility, and plot both."
        )
    )
    parser.add_argument("--days", nargs="+", type=int, default=list(DEFAULT_DAYS))
    parser.add_argument("--window", type=int, default=200, help="Rolling return window in ticks.")
    parser.add_argument(
        "--min-periods",
        type=int,
        default=50,
        help="Minimum observations before realized volatility is emitted.",
    )
    parser.add_argument(
        "--strikes",
        nargs="+",
        type=int,
        default=list(DEFAULT_STRIKES),
        help="VEV strikes to include in the implied-volatility median.",
    )
    parser.add_argument(
        "--tte-years",
        type=float,
        default=DEFAULT_TTE_YEARS,
        help="Black-Scholes time to expiry in years.",
    )
    parser.add_argument(
        "--observations-per-day",
        type=int,
        default=None,
        help="Annualization scale. Defaults to inferred underlying ticks per day.",
    )
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    days = tuple(args.days)
    strikes = tuple(args.strikes)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    prices = load_round3_prices(days)
    underlying_raw = prices[prices["product"] == UNDERLYING].copy()
    observations_per_day = args.observations_per_day or infer_observations_per_day(underlying_raw)
    underlying = add_realized_volatility(
        underlying_raw,
        window=args.window,
        min_periods=args.min_periods,
        observations_per_day=observations_per_day,
    )
    implied_by_strike = build_implied_vol_frame(
        prices,
        underlying,
        strikes=strikes,
        tte_years=float(args.tte_years),
    )
    implied = aggregate_implied_volatility(implied_by_strike)
    timeseries = underlying.merge(implied, on=["day", "timestamp", "time_day"], how="left")

    by_strike_path = out_dir / "velvet_implied_vol_by_strike.csv"
    timeseries_path = out_dir / "velvet_realized_vs_implied_vol.csv"
    chart_path = out_dir / "velvet_realized_vs_implied_vol.png"
    summary_path = out_dir / "velvet_volatility_summary.json"

    implied_by_strike.to_csv(by_strike_path, index=False)
    timeseries.to_csv(timeseries_path, index=False)
    plot_volatility(timeseries, chart_path)

    summary = {
        "underlying": UNDERLYING,
        "days": list(days),
        "strikes": list(strikes),
        "rolling_window_ticks": int(args.window),
        "min_periods": int(args.min_periods),
        "observations_per_day": int(observations_per_day),
        "tte_years": float(args.tte_years),
        "rows": int(len(timeseries)),
        "implied_vol_rows": int(implied_by_strike["implied_vol"].notna().sum()),
        "realized_vol_mean": float(timeseries["realized_vol"].mean()),
        "implied_vol_median_mean": float(timeseries["implied_vol_median"].mean()),
        "outputs": {
            "timeseries": str(timeseries_path),
            "implied_by_strike": str(by_strike_path),
            "chart": str(chart_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
