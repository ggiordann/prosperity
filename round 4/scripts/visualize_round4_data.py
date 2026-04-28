#!/usr/bin/env python3
"""Create Round 4 Prosperity data visualizations.

The script reads the official Round 4 price/trade CSVs, writes summary tables,
and generates a small visual report focused on:

- mid-price paths and normalized moves
- spread/depth microstructure
- public trade activity
- return correlations
- VEV voucher implied-volatility smile
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path("/Users/giordanmasen/Downloads/ROUND_4")
DEFAULT_OUTPUT_DIR = REPO_ROOT / "analysis" / "round4_visualizations"
ROUND4_DAYS = (1, 2, 3)
OBSERVATIONS_PER_DAY = 10_000
ANNUALIZATION = OBSERVATIONS_PER_DAY * 365.0
TTE_YEARS = 5.0 / 365.0
UNDERLYING = "VELVETFRUIT_EXTRACT"

PRODUCT_ORDER = (
    "HYDROGEL_PACK",
    "VELVETFRUIT_EXTRACT",
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
    "VEV_6000",
    "VEV_6500",
)

VEV_PRODUCTS = tuple(product for product in PRODUCT_ORDER if product.startswith("VEV_"))
VEV_COLORS = {
    "VEV_4000": "#4c78a8",
    "VEV_4500": "#72b7b2",
    "VEV_5000": "#54a24b",
    "VEV_5100": "#eeca3b",
    "VEV_5200": "#f58518",
    "VEV_5300": "#e45756",
    "VEV_5400": "#b279a2",
    "VEV_5500": "#ff9da6",
    "VEV_6000": "#9d755d",
    "VEV_6500": "#bab0ac",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--sample-every", type=int, default=4, help="Decimation for heavy scatter plots.")
    return parser.parse_args()


def load_prices(data_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for day in ROUND4_DAYS:
        path = data_dir / f"prices_round_4_day_{day}.csv"
        frame = pd.read_csv(path, sep=";")
        frame["source_file"] = path.name
        frames.append(frame)
    prices = pd.concat(frames, ignore_index=True)
    prices["product"] = pd.Categorical(prices["product"], categories=PRODUCT_ORDER, ordered=True)
    prices = prices.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)
    prices["best_bid"] = prices["bid_price_1"]
    prices["best_ask"] = prices["ask_price_1"]
    prices["spread"] = prices["best_ask"] - prices["best_bid"]
    prices["rel_spread_bps"] = prices["spread"] / prices["mid_price"].replace(0, np.nan) * 10_000.0
    prices["depth_l1"] = prices["bid_volume_1"].fillna(0).abs() + prices["ask_volume_1"].fillna(0).abs()
    bid_depth = sum(prices[f"bid_volume_{level}"].fillna(0).abs() for level in (1, 2, 3))
    ask_depth = sum(prices[f"ask_volume_{level}"].fillna(0).abs() for level in (1, 2, 3))
    prices["depth_l3"] = bid_depth + ask_depth
    prices["book_imbalance_l1"] = (
        prices["bid_volume_1"].fillna(0).abs() - prices["ask_volume_1"].fillna(0).abs()
    ) / prices["depth_l1"].replace(0, np.nan)
    prices["microprice_l1"] = (
        prices["best_bid"] * prices["ask_volume_1"].fillna(0).abs()
        + prices["best_ask"] * prices["bid_volume_1"].fillna(0).abs()
    ) / prices["depth_l1"].replace(0, np.nan)
    prices["micro_edge_l1"] = prices["microprice_l1"] - prices["mid_price"]
    prices["log_mid"] = np.where(prices["mid_price"] > 0, np.log(prices["mid_price"]), np.nan)
    prices["log_return"] = prices.groupby(["day", "product"], observed=True)["log_mid"].diff()
    prices["mid_diff"] = prices.groupby(["day", "product"], observed=True)["mid_price"].diff()
    return prices


def load_trades(data_dir: Path) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for day in ROUND4_DAYS:
        path = data_dir / f"trades_round_4_day_{day}.csv"
        frame = pd.read_csv(path, sep=";")
        frame["day"] = day
        frame["source_file"] = path.name
        frames.append(frame)
    trades = pd.concat(frames, ignore_index=True)
    trades["symbol"] = pd.Categorical(trades["symbol"], categories=PRODUCT_ORDER, ordered=True)
    trades["notional"] = trades["price"] * trades["quantity"]
    return trades.sort_values(["day", "timestamp", "symbol"]).reset_index(drop=True)


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_call(spot: float, strike: float, volatility: float) -> float:
    if volatility <= 0.0:
        return max(spot - strike, 0.0)
    vol_sqrt_t = volatility * math.sqrt(TTE_YEARS)
    if vol_sqrt_t <= 0.0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * TTE_YEARS) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return spot * normal_cdf(d1) - strike * normal_cdf(d2)


def implied_volatility(call_price: float, spot: float, strike: float) -> float:
    if not all(math.isfinite(value) for value in (call_price, spot, strike)):
        return float("nan")
    if call_price < 0.0 or spot <= 0.0 or strike <= 0.0:
        return float("nan")
    intrinsic = max(spot - strike, 0.0)
    if call_price < intrinsic - 1e-7 or call_price > spot + 1e-7:
        return float("nan")
    if abs(call_price - intrinsic) <= 1e-7:
        return 0.0

    low = 1e-6
    high = 5.0
    while black_scholes_call(spot, strike, high) < call_price and high < 20.0:
        high *= 2.0
    if high >= 20.0 and black_scholes_call(spot, strike, high) < call_price:
        return float("nan")

    for _ in range(48):
        mid = 0.5 * (low + high)
        price = black_scholes_call(spot, strike, mid)
        if abs(price - call_price) <= 1e-7:
            return mid
        if price < call_price:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def build_summaries(prices: pd.DataFrame, trades: pd.DataFrame, output_dir: Path) -> dict[str, object]:
    product_summary = (
        prices.groupby(["day", "product"], observed=True)
        .agg(
            ticks=("timestamp", "count"),
            start_mid=("mid_price", "first"),
            end_mid=("mid_price", "last"),
            min_mid=("mid_price", "min"),
            max_mid=("mid_price", "max"),
            mean_mid=("mid_price", "mean"),
            mean_spread=("spread", "mean"),
            median_spread=("spread", "median"),
            mean_rel_spread_bps=("rel_spread_bps", "mean"),
            mean_depth_l1=("depth_l1", "mean"),
            mean_depth_l3=("depth_l3", "mean"),
            realized_vol=("log_return", lambda value: float(value.std(skipna=True) * math.sqrt(ANNUALIZATION))),
            micro_edge_std=("micro_edge_l1", "std"),
        )
        .reset_index()
    )
    product_summary["day_return_pct"] = (
        (product_summary["end_mid"] / product_summary["start_mid"] - 1.0) * 100.0
    )

    trade_summary = (
        trades.groupby(["day", "symbol"], observed=True)
        .agg(
            trades=("price", "size"),
            quantity=("quantity", "sum"),
            notional=("notional", "sum"),
            vwap=("price", lambda value: float(np.average(value, weights=trades.loc[value.index, "quantity"]))),
            min_price=("price", "min"),
            max_price=("price", "max"),
        )
        .reset_index()
    )

    participant_summary = pd.concat(
        [
            trades[["day", "buyer", "symbol", "quantity", "notional"]].rename(columns={"buyer": "participant"}),
            trades[["day", "seller", "symbol", "quantity", "notional"]].rename(columns={"seller": "participant"}),
        ],
        ignore_index=True,
    )
    participant_summary = (
        participant_summary.groupby(["day", "participant"], observed=True)
        .agg(trades=("quantity", "size"), quantity=("quantity", "sum"), notional=("notional", "sum"))
        .sort_values(["day", "quantity"], ascending=[True, False])
        .reset_index()
    )

    product_summary.to_csv(output_dir / "round4_product_summary.csv", index=False)
    trade_summary.to_csv(output_dir / "round4_trade_summary.csv", index=False)
    participant_summary.to_csv(output_dir / "round4_participant_summary.csv", index=False)

    return {
        "products": [str(product) for product in prices["product"].dropna().unique()],
        "price_rows": int(len(prices)),
        "trade_rows": int(len(trades)),
        "product_summary": "round4_product_summary.csv",
        "trade_summary": "round4_trade_summary.csv",
        "participant_summary": "round4_participant_summary.csv",
    }


def compute_iv_frame(prices: pd.DataFrame, sample_every: int) -> pd.DataFrame:
    underlying = prices[prices["product"] == UNDERLYING][["day", "timestamp", "mid_price"]].rename(
        columns={"mid_price": "spot_mid"}
    )
    options = prices[prices["product"].isin(VEV_PRODUCTS)].copy()
    options["strike"] = options["product"].astype(str).str.split("_").str[-1].astype(float)
    merged = options.merge(underlying, on=["day", "timestamp"], how="inner")
    if sample_every > 1:
        merged = merged.groupby(["day", "product"], observed=True).nth(slice(None, None, sample_every)).reset_index()
    iv_values = [
        implied_volatility(float(row.mid_price), float(row.spot_mid), float(row.strike))
        for row in merged.itertuples(index=False)
    ]
    merged["implied_vol"] = iv_values
    merged["scaled_moneyness"] = np.log(merged["strike"] / merged["spot_mid"]) / math.sqrt(TTE_YEARS)
    merged = merged.replace([np.inf, -np.inf], np.nan)
    return merged[merged["implied_vol"].notna()].copy()


def save_price_panels(prices: pd.DataFrame, output_dir: Path) -> Path:
    fig, axes = plt.subplots(4, 3, figsize=(18, 14), sharex=True)
    axes_flat = axes.ravel()
    for ax, product in zip(axes_flat, PRODUCT_ORDER, strict=False):
        product_frame = prices[prices["product"] == product]
        for day, day_frame in product_frame.groupby("day", observed=True, sort=True):
            ax.plot(day_frame["timestamp"], day_frame["mid_price"], linewidth=1.1, label=f"Day {day}")
        ax.set_title(product, fontsize=10, fontweight="bold")
        ax.grid(True, alpha=0.25)
        ax.tick_params(axis="both", labelsize=8)
    for ax in axes_flat[len(PRODUCT_ORDER) :]:
        ax.axis("off")
    axes_flat[0].legend(loc="best", fontsize=8)
    fig.suptitle("Round 4 Mid-Price Paths", fontsize=18, fontweight="bold")
    fig.supxlabel("Timestamp")
    fig.supylabel("Mid Price")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    path = output_dir / "round4_mid_price_panels.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def save_normalized_paths(prices: pd.DataFrame, output_dir: Path) -> Path:
    pivots = []
    for day, day_frame in prices.groupby("day", observed=True, sort=True):
        pivot = day_frame.pivot(index="timestamp", columns="product", values="mid_price")
        normalized = pivot / pivot.iloc[0] - 1.0
        normalized["day"] = day
        pivots.append(normalized.reset_index())

    fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)
    for ax, frame in zip(axes, pivots, strict=True):
        day = int(frame["day"].iloc[0])
        for product in PRODUCT_ORDER:
            linewidth = 1.8 if product in ("HYDROGEL_PACK", "VELVETFRUIT_EXTRACT") else 0.9
            alpha = 0.95 if product in ("HYDROGEL_PACK", "VELVETFRUIT_EXTRACT") else 0.55
            ax.plot(frame["timestamp"], frame[product] * 100.0, linewidth=linewidth, alpha=alpha, label=product)
        ax.axhline(0, color="#555555", linewidth=0.8)
        ax.set_title(f"Day {day}", fontweight="bold")
        ax.grid(True, alpha=0.25)
        ax.set_xlabel("Timestamp")
    axes[0].set_ylabel("Move From Open (%)")
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    fig.suptitle("Round 4 Normalized Intraday Moves", fontsize=18, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 0.91, 0.93))
    path = output_dir / "round4_normalized_paths.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def save_microstructure_summary(prices: pd.DataFrame, output_dir: Path) -> Path:
    summary = (
        prices.groupby(["day", "product"], observed=True)
        .agg(mean_spread=("spread", "mean"), mean_depth_l1=("depth_l1", "mean"), mean_rel_spread_bps=("rel_spread_bps", "mean"))
        .reset_index()
    )

    fig, axes = plt.subplots(3, 1, figsize=(16, 14), sharex=True)
    metrics = [
        ("mean_spread", "Mean Bid/Ask Spread"),
        ("mean_rel_spread_bps", "Mean Relative Spread (bps)"),
        ("mean_depth_l1", "Mean Top-of-Book Depth"),
    ]
    x = np.arange(len(PRODUCT_ORDER))
    width = 0.24
    for ax, (metric, title) in zip(axes, metrics, strict=True):
        for offset_index, day in enumerate(ROUND4_DAYS):
            day_values = (
                summary[summary["day"] == day]
                .set_index("product")
                .reindex(PRODUCT_ORDER)[metric]
                .to_numpy(dtype=float)
            )
            ax.bar(x + (offset_index - 1) * width, day_values, width=width, label=f"Day {day}")
        ax.set_title(title, fontweight="bold")
        ax.grid(True, axis="y", alpha=0.25)
        ax.tick_params(axis="y", labelsize=8)
    axes[0].legend(loc="best")
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(PRODUCT_ORDER, rotation=35, ha="right")
    fig.suptitle("Round 4 Liquidity and Spread Summary", fontsize=18, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    path = output_dir / "round4_microstructure_summary.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def save_trade_activity(trades: pd.DataFrame, output_dir: Path) -> Path:
    binned = trades.copy()
    bin_size = 10_000
    binned["time_bin"] = (binned["timestamp"] // bin_size) * bin_size
    pivot = (
        binned.groupby(["day", "symbol", "time_bin"], observed=True)["quantity"]
        .sum()
        .reset_index()
        .pivot_table(index=["day", "symbol"], columns="time_bin", values="quantity", fill_value=0, observed=True)
        .reindex(pd.MultiIndex.from_product([ROUND4_DAYS, PRODUCT_ORDER], names=["day", "symbol"]))
        .fillna(0)
    )

    fig, ax = plt.subplots(figsize=(18, 9))
    matrix = pivot.to_numpy(dtype=float)
    image = ax.imshow(matrix, aspect="auto", cmap="viridis")
    labels = [f"D{day} {product}" for day, product in pivot.index]
    ax.set_yticks(np.arange(len(labels)))
    ax.set_yticklabels(labels, fontsize=7)
    col_labels = [int(col) for col in pivot.columns]
    tick_step = max(1, len(col_labels) // 10)
    tick_positions = np.arange(0, len(col_labels), tick_step)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([str(col_labels[index]) for index in tick_positions], rotation=45, ha="right")
    ax.set_title("Public Trade Quantity by Product and Time Bin", fontsize=16, fontweight="bold")
    ax.set_xlabel("Timestamp Bin")
    fig.colorbar(image, ax=ax, label="Quantity")
    fig.tight_layout()
    path = output_dir / "round4_trade_activity_heatmap.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def save_return_correlation(prices: pd.DataFrame, output_dir: Path) -> Path:
    pivot = prices.pivot_table(
        index=["day", "timestamp"], columns="product", values="mid_diff", observed=True
    ).reindex(columns=PRODUCT_ORDER)
    corr = pivot.corr()

    fig, ax = plt.subplots(figsize=(10, 8))
    image = ax.imshow(corr.to_numpy(dtype=float), cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(np.arange(len(PRODUCT_ORDER)))
    ax.set_yticks(np.arange(len(PRODUCT_ORDER)))
    ax.set_xticklabels(PRODUCT_ORDER, rotation=45, ha="right", fontsize=8)
    ax.set_yticklabels(PRODUCT_ORDER, fontsize=8)
    ax.set_title("Mid-Price Change Correlation", fontsize=16, fontweight="bold")
    for row in range(len(PRODUCT_ORDER)):
        for col in range(len(PRODUCT_ORDER)):
            value = corr.iloc[row, col]
            ax.text(col, row, f"{value:.2f}", ha="center", va="center", fontsize=7, color="black")
    fig.colorbar(image, ax=ax, label="Correlation")
    fig.tight_layout()
    path = output_dir / "round4_return_correlation.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def save_iv_smile(iv_frame: pd.DataFrame, output_dir: Path) -> Path:
    plot_frame = iv_frame[(iv_frame["implied_vol"] > 0.0) & (iv_frame["implied_vol"] < 2.0)].copy()
    fig, axes = plt.subplots(1, 3, figsize=(18, 5.5), sharey=True)
    fit_rows: list[dict[str, object]] = []

    for ax, day in zip(axes, ROUND4_DAYS, strict=True):
        day_frame = plot_frame[plot_frame["day"] == day]
        for product in VEV_PRODUCTS:
            product_frame = day_frame[day_frame["product"].astype(str) == product]
            if product_frame.empty:
                continue
            ax.scatter(
                product_frame["scaled_moneyness"],
                product_frame["implied_vol"],
                s=7,
                alpha=0.35,
                color=VEV_COLORS[product],
                edgecolors="none",
                label=product if day == ROUND4_DAYS[0] else None,
            )
        fit_frame = day_frame[
            day_frame["scaled_moneyness"].between(-1.0, 1.0) & day_frame["implied_vol"].between(0.01, 1.0)
        ]
        if len(fit_frame) >= 10:
            coeffs = np.polyfit(fit_frame["scaled_moneyness"], fit_frame["implied_vol"], 3)
            x_grid = np.linspace(
                float(fit_frame["scaled_moneyness"].quantile(0.005)),
                float(fit_frame["scaled_moneyness"].quantile(0.995)),
                300,
            )
            ax.plot(x_grid, np.polyval(coeffs, x_grid), color="black", linewidth=2.2)
            fit_rows.append({"day": day, "cubic_coefficients_high_to_low": [float(v) for v in coeffs]})
        ax.set_title(f"Day {day}", fontweight="bold")
        ax.grid(True, alpha=0.25)
        ax.set_xlabel("ln(K/S) / sqrt(TTE)")
    axes[0].set_ylabel("Black-Scholes Implied Volatility")
    handles, labels = axes[0].get_legend_handles_labels()
    axes[-1].legend(handles, labels, loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=8)
    fig.suptitle("VEV Implied Volatility vs Time-Scaled Moneyness", fontsize=18, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 0.91, 0.93))
    path = output_dir / "round4_vev_iv_smile.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)

    iv_summary = (
        plot_frame.groupby(["day", "product"], observed=True)
        .agg(
            rows=("implied_vol", "size"),
            mean_iv=("implied_vol", "mean"),
            median_iv=("implied_vol", "median"),
            std_iv=("implied_vol", "std"),
            mean_moneyness=("scaled_moneyness", "mean"),
        )
        .reset_index()
    )
    iv_summary.to_csv(output_dir / "round4_vev_iv_summary.csv", index=False)
    (output_dir / "round4_vev_iv_fit.json").write_text(
        json.dumps({"tte_years": TTE_YEARS, "fits": fit_rows}, indent=2), encoding="utf-8"
    )
    return path


def write_report(output_dir: Path, image_paths: list[Path], summary: dict[str, object]) -> Path:
    rows = [
        "# Round 4 Data Visual Report",
        "",
        f"- Price rows: {summary['price_rows']:,}",
        f"- Public trade rows: {summary['trade_rows']:,}",
        f"- Products: {', '.join(summary['products'])}",
        "",
        "## Visuals",
        "",
    ]
    for path in image_paths:
        rows.append(f"### {path.stem.replace('_', ' ').title()}")
        rows.append("")
        rows.append(f"![{path.stem}]({path.name})")
        rows.append("")
    report_path = output_dir / "round4_visual_report.md"
    report_path.write_text("\n".join(rows), encoding="utf-8")
    return report_path


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    prices = load_prices(args.data_dir)
    trades = load_trades(args.data_dir)
    summary = build_summaries(prices, trades, output_dir)
    iv_frame = compute_iv_frame(prices, max(1, args.sample_every))

    image_paths = [
        save_price_panels(prices, output_dir),
        save_normalized_paths(prices, output_dir),
        save_microstructure_summary(prices, output_dir),
        save_trade_activity(trades, output_dir),
        save_return_correlation(prices, output_dir),
        save_iv_smile(iv_frame, output_dir),
    ]
    report_path = write_report(output_dir, image_paths, summary)

    summary = {
        **summary,
        "output_dir": str(output_dir),
        "report": report_path.name,
        "images": [path.name for path in image_paths],
        "iv_summary": "round4_vev_iv_summary.csv",
        "iv_fit": "round4_vev_iv_fit.json",
    }
    (output_dir / "round4_visualization_manifest.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
