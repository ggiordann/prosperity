#!/usr/bin/env python3
"""Plot VEV implied volatility against time-scaled log moneyness."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = REPO_ROOT / "round 3" / "analysis" / "round3_velvet_volatility" / "velvet_implied_vol_by_strike.csv"
DEFAULT_OUTPUT = REPO_ROOT / "round 3" / "analysis" / "round3_velvet_volatility" / "velvet_iv_vs_moneyness.png"
DEFAULT_SUMMARY = REPO_ROOT / "round 3" / "analysis" / "round3_velvet_volatility" / "velvet_iv_vs_moneyness_fit.json"

TTE_YEARS = 5.0 / 365.0
PRODUCT_ORDER = ("VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500")
COLORS = {
    "VEV_5000": "#1f77b4",
    "VEV_5100": "#2ca02c",
    "VEV_5200": "#9467bd",
    "VEV_5300": "#e377c2",
    "VEV_5400": "#bcbd22",
    "VEV_5500": "#17becf",
}
DAY_ALPHA = {
    0: 0.35,
    1: 0.55,
    2: 0.85,
}

# Previous repository quadratic smile in x = ln(K / S) / sqrt(TTE).
OLD_FIT_A = 0.01305220
OLD_FIT_B = 0.01281602
OLD_FIT_C = 0.27669756


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--sample-frac", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def load_frame(path: Path, sample_frac: float, seed: int) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame[frame["product"].isin(PRODUCT_ORDER)].copy()
    frame["moneyness"] = np.log(frame["strike"] / frame["spot_mid"]) / math.sqrt(TTE_YEARS)
    frame["implied_vol"] = frame["implied_vol"].replace([np.inf, -np.inf], np.nan)
    frame = frame[frame["implied_vol"].notna()].copy()
    if 0.0 < sample_frac < 1.0:
        frame = frame.sample(frac=sample_frac, random_state=seed).sort_values(["day", "timestamp", "product"])
    return frame


def fit_cubic(frame: pd.DataFrame) -> np.ndarray:
    fit_frame = frame[(frame["implied_vol"] > 0.0) & (frame["implied_vol"] < 1.0)]
    return np.polyfit(fit_frame["moneyness"], fit_frame["implied_vol"], 3)


def plot(frame: pd.DataFrame, cubic_coefficients: np.ndarray, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    x_min = float(frame["moneyness"].quantile(0.001))
    x_max = float(frame["moneyness"].quantile(0.999))
    x_grid = np.linspace(x_min, x_max, 400)
    new_fit = np.polyval(cubic_coefficients, x_grid)
    old_fit = OLD_FIT_A * x_grid * x_grid + OLD_FIT_B * x_grid + OLD_FIT_C

    fig, ax = plt.subplots(figsize=(15.36, 7.68))
    for product in PRODUCT_ORDER:
        product_frame = frame[frame["product"] == product]
        first_label = True
        for day, day_frame in product_frame.groupby("day", sort=True):
            ax.scatter(
                day_frame["moneyness"],
                day_frame["implied_vol"],
                s=18,
                color=COLORS[product],
                alpha=DAY_ALPHA.get(int(day), 0.65),
                edgecolors="none",
                label=product if first_label else None,
            )
            first_label = False

    ax.plot(x_grid, new_fit, color="red", linewidth=3, label="NEW 3rd-Degree Fit")
    ax.plot(x_grid, old_fit, color="black", linewidth=3, linestyle="--", label="OLD Fit")

    ax.set_title(
        "Implied Volatility vs Time-Scaled Moneyness\n"
        "(Colors = Options, Opacity = Days)",
        fontsize=16,
        fontweight="bold",
    )
    ax.set_xlabel("Time-Scaled Log Moneyness: ln(K/S) / sqrt(TTE)", fontsize=12)
    ax.set_ylabel("Implied Volatility (IV)", fontsize=12)
    ax.grid(True, linestyle="--", alpha=0.55)
    ax.set_xlim(x_min - 0.05, x_max + 0.05)
    ax.set_ylim(0.0, max(0.30, float(frame["implied_vol"].quantile(0.999)) + 0.015))
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), borderaxespad=0.0)
    fig.tight_layout()
    fig.savefig(output, dpi=100)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    frame = load_frame(args.input, args.sample_frac, args.seed)
    cubic_coefficients = fit_cubic(frame)
    plot(frame, cubic_coefficients, args.output)

    summary = {
        "input": str(args.input),
        "output": str(args.output),
        "tte_years": TTE_YEARS,
        "rows": int(len(frame)),
        "new_3rd_degree_coefficients_high_to_low": [float(value) for value in cubic_coefficients],
        "old_quadratic_coefficients_a_b_c": [OLD_FIT_A, OLD_FIT_B, OLD_FIT_C],
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
