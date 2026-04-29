from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5"

CATEGORY_ORDER = [
    "galaxy",
    "sleep",
    "microchip",
    "pebbles",
    "robot",
    "visor",
    "translator",
    "panel",
    "oxygen",
    "snack",
]

CATEGORY_COLORS = {
    "galaxy": "#6d597a",
    "sleep": "#355070",
    "microchip": "#43aa8b",
    "pebbles": "#577590",
    "robot": "#f3722c",
    "visor": "#f9c74f",
    "translator": "#90be6d",
    "panel": "#277da1",
    "oxygen": "#f9844a",
    "snack": "#c1121f",
}


def load_mid_prices() -> dict[int, pd.DataFrame]:
    frames = []
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frames.append(pd.read_csv(path, sep=";", usecols=["day", "timestamp", "product", "mid_price"]))
    prices = pd.concat(frames, ignore_index=True)
    return {
        int(day): group.pivot(index="timestamp", columns="product", values="mid_price").sort_index()
        for day, group in prices.groupby("day")
    }


def load_category_lookup() -> dict[str, str]:
    metrics = pd.read_csv(OUT / "product_metrics.csv", usecols=["category", "product"])
    return dict(zip(metrics["product"], metrics["category"]))


def plot_correlation_method_comparison(pair_corr: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 8), constrained_layout=True)
    colors = np.where(pair_corr["same_category"], "#c1121f", "#8d99ae")
    ax.scatter(
        pair_corr["price_corr_mean"],
        pair_corr["return_corr_mean"],
        c=colors,
        s=np.where(pair_corr["same_category"], 42, 16),
        alpha=np.where(pair_corr["same_category"], 0.82, 0.28),
        edgecolors="none",
    )
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Raw Price Correlation Can Disagree With Return Correlation")
    ax.set_xlabel("Mean raw mid-price correlation")
    ax.set_ylabel("Mean same-timestamp mid-price return correlation")
    ax.text(
        0.02,
        0.96,
        "Use return correlation for movement relationships.\nUse raw price correlation only as a weak relative-value clue.",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.9},
    )
    top = pair_corr.reindex(pair_corr["return_corr_mean"].abs().sort_values(ascending=False).index).head(8)
    for _, row in top.iterrows():
        label = f"{row['a'].replace('_', ' ')} / {row['b'].replace('_', ' ')}"
        ax.annotate(
            label,
            (row["price_corr_mean"], row["return_corr_mean"]),
            xytext=(5, 4),
            textcoords="offset points",
            fontsize=7,
            alpha=0.82,
        )
    fig.savefig(OUT / "rook_hint_correlation_method_comparison.png", dpi=220)
    plt.close(fig)


def plot_category_segmentation(category_metrics: pd.DataFrame, final_pnl: pd.DataFrame, lookup: dict[str, str]) -> None:
    pnl = final_pnl.copy()
    pnl["category"] = pnl["product"].map(lookup)
    category_pnl = (
        pnl.groupby("category")
        .agg(total_pnl=("final_pnl", "sum"), mean_pnl=("final_pnl", "mean"))
        .reindex(CATEGORY_ORDER)
        .reset_index()
    )
    metrics = category_metrics.set_index("category").reindex(CATEGORY_ORDER).reset_index()
    merged = metrics.merge(category_pnl, on="category")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    bar_colors = [CATEGORY_COLORS[c] for c in merged["category"]]
    axes[0].bar(merged["category"], merged["total_pnl"], color=bar_colors)
    axes[0].set_title("Hint: Filter The Fifty Products Into Segments")
    axes[0].set_ylabel("Total final PnL by category")
    axes[0].tick_params(axis="x", rotation=45)

    sizes = 55 + (merged["mean_ret_vol"] / merged["mean_ret_vol"].max()) * 600
    axes[1].scatter(
        merged["mean_within_return_corr"],
        merged["mean_pnl"],
        s=sizes,
        c=bar_colors,
        alpha=0.78,
        edgecolors="black",
        linewidths=0.5,
    )
    for _, row in merged.iterrows():
        axes[1].annotate(row["category"], (row["mean_within_return_corr"], row["mean_pnl"]), xytext=(4, 3), textcoords="offset points", fontsize=8)
    axes[1].axvline(0, color="black", linewidth=0.8)
    axes[1].set_title("Cluster Quality: Performance vs Internal Return Correlation")
    axes[1].set_xlabel("Mean within-category return correlation")
    axes[1].set_ylabel("Mean final PnL per product")
    fig.savefig(OUT / "rook_hint_category_segmentation.png", dpi=220)
    plt.close(fig)


def plot_clustered_return_heatmap(return_matrix: pd.DataFrame, lookup: dict[str, str]) -> None:
    corr = return_matrix.fillna(0.0).copy()
    abs_corr = corr.abs().clip(upper=1.0)
    distance = 1.0 - abs_corr
    np.fill_diagonal(distance.values, 0.0)
    order = leaves_list(linkage(squareform(distance.to_numpy(float), checks=False), method="average"))
    ordered = corr.iloc[order, order]

    fig, ax = plt.subplots(figsize=(16, 14), constrained_layout=True)
    im = ax.imshow(ordered.to_numpy(float), cmap="RdBu_r", vmin=-1.0, vmax=1.0)
    labels = list(ordered.index)
    label_colors = [CATEGORY_COLORS.get(lookup.get(label, ""), "#444444") for label in labels]
    ax.set_xticks(range(len(labels)), labels=labels, rotation=90, fontsize=5)
    ax.set_yticks(range(len(labels)), labels=labels, fontsize=5)
    for tick, color in zip(ax.get_xticklabels(), label_colors):
        tick.set_color(color)
    for tick, color in zip(ax.get_yticklabels(), label_colors):
        tick.set_color(color)
    ax.set_title("Hint: Map Which Product Relationships Hold")
    colorbar = fig.colorbar(im, ax=ax, shrink=0.78)
    colorbar.set_label("Return correlation")
    fig.savefig(OUT / "rook_hint_clustered_return_heatmap.png", dpi=220)
    plt.close(fig)


def plot_pair_relationships(pair_corr: pd.DataFrame, lookup: dict[str, str]) -> None:
    edges = pair_corr[pair_corr["same_category"]].copy()
    edges["abs_corr"] = edges["return_corr_mean"].abs()
    edges = edges.sort_values("abs_corr", ascending=False).head(22)
    products = sorted(set(edges["a"]).union(edges["b"]), key=lambda p: (CATEGORY_ORDER.index(lookup[p]), p))

    by_category = {category: [p for p in products if lookup[p] == category] for category in CATEGORY_ORDER}
    positions = {}
    radius = 4.0
    category_angles = np.linspace(0, 2 * np.pi, len(CATEGORY_ORDER), endpoint=False)
    for angle, category in zip(category_angles, CATEGORY_ORDER):
        center = np.array([np.cos(angle), np.sin(angle)]) * radius
        members = by_category[category]
        if not members:
            continue
        offsets = np.linspace(-0.45, 0.45, len(members)) if len(members) > 1 else [0.0]
        tangent = np.array([-np.sin(angle), np.cos(angle)])
        for offset, product in zip(offsets, members):
            positions[product] = center + tangent * offset

    fig, ax = plt.subplots(figsize=(11, 11), constrained_layout=True)
    for _, row in edges.iterrows():
        a = positions[row["a"]]
        b = positions[row["b"]]
        color = "#b7094c" if row["return_corr_mean"] >= 0 else "#1d4e89"
        ax.plot([a[0], b[0]], [a[1], b[1]], color=color, linewidth=1.5 + 5 * row["abs_corr"], alpha=0.74)
        midpoint = (a + b) / 2
        ax.text(midpoint[0], midpoint[1], f"{row['return_corr_mean']:.2f}", fontsize=7, ha="center", va="center", color=color)

    for product, xy in positions.items():
        category = lookup[product]
        ax.scatter(xy[0], xy[1], s=180, color=CATEGORY_COLORS[category], edgecolor="black", linewidth=0.6, zorder=3)
        ax.text(xy[0], xy[1] - 0.17, product.replace("_", "\n"), fontsize=6.4, ha="center", va="top")

    ax.set_title("Hint: Pairing For Profit - Strongest Same-Category Return Relationships")
    ax.axis("off")
    fig.savefig(OUT / "rook_hint_pair_relationship_graph.png", dpi=220)
    plt.close(fig)


def plot_pair_relationship_bars(pair_corr: pd.DataFrame) -> None:
    top = pair_corr.copy()
    top["abs_corr"] = top["return_corr_mean"].abs()
    top = top.sort_values("abs_corr", ascending=False).head(18).iloc[::-1]
    labels = [f"{row.a}\n{row.b}" for row in top.itertuples()]
    colors = ["#b7094c" if value >= 0 else "#1d4e89" for value in top["return_corr_mean"]]

    fig, ax = plt.subplots(figsize=(11, 9), constrained_layout=True)
    ax.barh(labels, top["return_corr_mean"], color=colors, alpha=0.86)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Hint: Pairing For Profit - Strongest Same-Timestamp Return Correlations")
    ax.set_xlabel("Mean return correlation across days 2, 3, and 4")
    ax.tick_params(axis="y", labelsize=7)
    for index, value in enumerate(top["return_corr_mean"]):
        ax.text(value + (0.015 if value >= 0 else -0.015), index, f"{value:.3f}", va="center", ha="left" if value >= 0 else "right", fontsize=8)
    fig.savefig(OUT / "rook_hint_pair_relationship_bars.png", dpi=220)
    plt.close(fig)


def plot_stationary_spread_candidates(stationary_pairs: pd.DataFrame) -> None:
    top = stationary_pairs.sort_values("hedged_adf_t").head(20).iloc[::-1]
    labels = [f"{row.a}\n{row.b}" for row in top.itertuples()]
    colors = np.where(top["hedged_stationary_5pct"], "#2a9d8f", "#8d99ae")

    fig, ax = plt.subplots(figsize=(11, 9), constrained_layout=True)
    ax.barh(labels, top["hedged_adf_t"], color=colors, alpha=0.88)
    ax.axvline(-2.86, color="#c1121f", linestyle="--", linewidth=1.4, label="ADF 5% critical value")
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Notebook-Inspired Check: Most Stationary Hedged Pair Residuals")
    ax.set_xlabel("ADF t-statistic, lower is more mean-reverting")
    ax.tick_params(axis="y", labelsize=7)
    ax.legend(fontsize=8)
    for index, value in enumerate(top["hedged_adf_t"]):
        ax.text(value - 0.08, index, f"{value:.2f}", va="center", ha="right", fontsize=8)
    fig.savefig(OUT / "rook_hint_stationary_spreads.png", dpi=220)
    plt.close(fig)


def lagged_corr_series(mids: dict[int, pd.DataFrame], leader: str, follower: str, max_lag: int = 150) -> pd.Series:
    values = []
    for lag in range(1, max_lag + 1):
        per_day = []
        for piv in mids.values():
            returns = piv[[leader, follower]].diff().fillna(0.0).to_numpy(float)
            x = returns[:-lag, 0]
            y = returns[lag:, 1]
            if len(x) > 3 and x.std() > 0 and y.std() > 0:
                per_day.append(float(np.corrcoef(x, y)[0, 1]))
        values.append(np.nanmean(per_day) if per_day else np.nan)
    return pd.Series(values, index=range(1, max_lag + 1))


def plot_lead_lag_hints(lead_lag: pd.DataFrame, mids: dict[int, pd.DataFrame], lookup: dict[str, str]) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)

    if lead_lag.empty:
        axes[0].text(0.5, 0.5, "No stable lead-lag edges found", ha="center", va="center")
        axes[0].axis("off")
    else:
        stable = lead_lag.sort_values("score", ascending=False).head(8)
        products = sorted(set(stable["leader"]).union(stable["follower"]))
        positions = {
            product: np.array([i % 4, -(i // 4)], dtype=float)
            for i, product in enumerate(products)
        }
        for _, row in stable.iterrows():
            start = positions[row["leader"]]
            end = positions[row["follower"]]
            axes[0].annotate(
                "",
                xy=end,
                xytext=start,
                arrowprops={
                    "arrowstyle": "->",
                    "color": "#b7094c" if row["corr_mean"] > 0 else "#1d4e89",
                    "linewidth": 2.2,
                    "shrinkA": 18,
                    "shrinkB": 18,
                },
            )
            mid = (start + end) / 2
            axes[0].text(mid[0], mid[1] + 0.12, f"lag {int(row['lag'])}\nr={row['corr_mean']:.3f}", fontsize=9, ha="center")
        for product, xy in positions.items():
            category = lookup[product]
            axes[0].scatter(xy[0], xy[1], s=240, color=CATEGORY_COLORS[category], edgecolor="black", zorder=3)
            axes[0].text(xy[0], xy[1] - 0.18, product.replace("_", "\n"), fontsize=8, ha="center", va="top")
        axes[0].set_title("Hint: Same But Slower - Stable Lead-Lag Edges")
        xs = [xy[0] for xy in positions.values()]
        ys = [xy[1] for xy in positions.values()]
        axes[0].set_xlim(min(xs) - 0.45, max(xs) + 0.45)
        axes[0].set_ylim(min(ys) - 0.7, max(ys) + 0.35)
        axes[0].axis("off")

    if lead_lag.empty:
        axes[1].text(0.5, 0.5, "No lag scan available", ha="center", va="center")
    else:
        for _, row in lead_lag.sort_values("score", ascending=False).head(4).iterrows():
            series = lagged_corr_series(mids, row["leader"], row["follower"])
            label = f"{row['leader']} -> {row['follower']}"
            axes[1].plot(series.index, series.values, label=label, linewidth=1.7)
            axes[1].axvline(row["lag"], color="black", linewidth=0.5, alpha=0.35)
        axes[1].axhline(0, color="black", linewidth=0.8)
        axes[1].set_title("Lead-Lag Return Correlation By Delay")
        axes[1].set_xlabel("Follower delay in timestamps")
        axes[1].set_ylabel("Mean corr(leader return[t], follower return[t+lag])")
        axes[1].legend(fontsize=7)

    fig.savefig(OUT / "rook_hint_lead_lag.png", dpi=220)
    plt.close(fig)


def main() -> None:
    pair_corr = pd.read_csv(OUT / "pair_correlations.csv")
    category_metrics = pd.read_csv(OUT / "category_metrics.csv")
    final_pnl = pd.read_csv(OUT / "final_product_pnl.csv")
    return_matrix = pd.read_csv(OUT / "return_correlation_matrix.csv", index_col=0)
    lead_lag = pd.read_csv(OUT / "lead_lag_stable.csv")
    stationary_pairs = pd.read_csv(OUT / "stationary_spread_pairs.csv")
    lookup = load_category_lookup()
    mids = load_mid_prices()

    plot_correlation_method_comparison(pair_corr)
    plot_category_segmentation(category_metrics, final_pnl, lookup)
    plot_clustered_return_heatmap(return_matrix, lookup)
    plot_pair_relationships(pair_corr, lookup)
    plot_pair_relationship_bars(pair_corr)
    plot_stationary_spread_candidates(stationary_pairs)
    plot_lead_lag_hints(lead_lag, mids, lookup)
    print("wrote Rook-E1 Round 5 hint visuals")


if __name__ == "__main__":
    main()
