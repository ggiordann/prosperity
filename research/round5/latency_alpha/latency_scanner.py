from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5" / "latency_alpha"
HORIZONS = (1, 2, 3, 5, 10, 20, 50)

CATEGORIES = {
    "galaxy": (
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    ),
    "microchip": (
        "MICROCHIP_CIRCLE",
        "MICROCHIP_OVAL",
        "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
    ),
    "oxygen": (
        "OXYGEN_SHAKE_MORNING_BREATH",
        "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_MINT",
        "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
    ),
    "panel": ("PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"),
    "pebbles": ("PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"),
    "robot": ("ROBOT_VACUUMING", "ROBOT_MOPPING", "ROBOT_DISHES", "ROBOT_LAUNDRY", "ROBOT_IRONING"),
    "sleep": ("SLEEP_POD_SUEDE", "SLEEP_POD_LAMB_WOOL", "SLEEP_POD_POLYESTER", "SLEEP_POD_NYLON", "SLEEP_POD_COTTON"),
    "snack": (
        "SNACKPACK_CHOCOLATE",
        "SNACKPACK_VANILLA",
        "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY",
        "SNACKPACK_RASPBERRY",
    ),
    "translator": (
        "TRANSLATOR_SPACE_GRAY",
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_VOID_BLUE",
    ),
    "visor": ("UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"),
}
PRODUCT_TO_CATEGORY = {product: category for category, products in CATEGORIES.items() for product in products}
PRODUCTS = tuple(product for products in CATEGORIES.values() for product in products)


def load_prices() -> dict[int, dict[str, object]]:
    out: dict[int, dict[str, object]] = {}
    for path in sorted(DATA.glob("prices_round_5_day_*.csv")):
        frame = pd.read_csv(path, sep=";")
        day = int(frame["day"].iloc[0])
        pivots = {
            "mid": frame.pivot(index="timestamp", columns="product", values="mid_price").sort_index()[list(PRODUCTS)],
            "bid": frame.pivot(index="timestamp", columns="product", values="bid_price_1").sort_index()[list(PRODUCTS)],
            "ask": frame.pivot(index="timestamp", columns="product", values="ask_price_1").sort_index()[list(PRODUCTS)],
            "bid_vol": frame.pivot(index="timestamp", columns="product", values="bid_volume_1").sort_index()[list(PRODUCTS)].abs(),
            "ask_vol": frame.pivot(index="timestamp", columns="product", values="ask_volume_1").sort_index()[list(PRODUCTS)].abs(),
        }
        bid = pivots["bid"].to_numpy(float)
        ask = pivots["ask"].to_numpy(float)
        bid_vol = pivots["bid_vol"].to_numpy(float)
        ask_vol = pivots["ask_vol"].to_numpy(float)
        spread = ask - bid
        tradable = np.isfinite(bid) & np.isfinite(ask) & (bid_vol > 0) & (ask_vol > 0)
        imbalance = (bid_vol - ask_vol) / np.maximum(bid_vol + ask_vol, 1.0)
        out[day] = {
            "timestamps": pivots["mid"].index.to_numpy(int),
            "mid": pivots["mid"].to_numpy(float),
            "spread": spread,
            "tradable": tradable,
            "imbalance": imbalance,
        }
    return out


def load_trade_flow(price_data: dict[int, dict[str, object]]) -> dict[int, np.ndarray]:
    flows: dict[int, np.ndarray] = {}
    product_index = {product: idx for idx, product in enumerate(PRODUCTS)}
    for day, data in price_data.items():
        timestamps = data["timestamps"]
        ts_index = {int(ts): idx for idx, ts in enumerate(timestamps)}
        mids = data["mid"]
        flow = np.zeros((len(timestamps), len(PRODUCTS)), dtype=float)
        path = DATA / f"trades_round_5_day_{day}.csv"
        trades = pd.read_csv(path, sep=";")
        for row in trades.itertuples(index=False):
            product = row.symbol
            if product not in product_index:
                continue
            t_idx = ts_index.get(int(row.timestamp))
            if t_idx is None:
                continue
            p_idx = product_index[product]
            mid = mids[t_idx, p_idx]
            sign = 1.0 if float(row.price) > mid else -1.0 if float(row.price) < mid else 0.0
            flow[t_idx, p_idx] += sign * float(row.quantity)
        flows[day] = flow
    return flows


def make_category_indices(price_data: dict[int, dict[str, object]]) -> dict[int, np.ndarray]:
    cat_cols = []
    for category, products in CATEGORIES.items():
        idxs = [PRODUCTS.index(product) for product in products]
        cat_cols.append((category, idxs))
    out: dict[int, np.ndarray] = {}
    for day, data in price_data.items():
        mid = data["mid"]
        index = np.column_stack([mid[:, idxs].mean(axis=1) for _, idxs in cat_cols])
        out[day] = index
    return out


def make_basket_residuals(price_data: dict[int, dict[str, object]]) -> dict[int, np.ndarray]:
    residuals: dict[int, np.ndarray] = {}
    days = sorted(price_data)
    for test_day in days:
        resid = np.zeros_like(price_data[test_day]["mid"], dtype=float)
        for category, products in CATEGORIES.items():
            for product in products:
                target_idx = PRODUCTS.index(product)
                feature_idxs = [PRODUCTS.index(other) for other in products if other != product]
                x_train = np.vstack([price_data[day]["mid"][:, feature_idxs] for day in days if day != test_day])
                y_train = np.concatenate([price_data[day]["mid"][:, target_idx] for day in days if day != test_day])
                x_mu = x_train.mean(axis=0)
                x_sd = x_train.std(axis=0)
                x_sd[x_sd == 0] = 1.0
                y_mu = y_train.mean()
                xs = (x_train - x_mu) / x_sd
                lam = 2.0
                beta_s = np.linalg.solve(xs.T @ xs + lam * np.eye(xs.shape[1]), xs.T @ (y_train - y_mu))
                beta = beta_s / x_sd
                intercept = y_mu - x_mu @ beta
                pred = intercept + price_data[test_day]["mid"][:, feature_idxs] @ beta
                resid[:, target_idx] = price_data[test_day]["mid"][:, target_idx] - pred
        residuals[test_day] = resid
    return residuals


def corr_beta(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x0 = x - x.mean(axis=0)
    y0 = y - y.mean(axis=0)
    xss = (x0 * x0).sum(axis=0)
    yss = (y0 * y0).sum(axis=0)
    cov = x0.T @ y0
    denom = np.sqrt(xss[:, None] * yss[None, :])
    corr = np.divide(cov, denom, out=np.zeros_like(cov), where=denom > 0)
    beta = np.divide(cov, xss[:, None], out=np.zeros_like(cov), where=xss[:, None] > 0)
    return corr, beta


def product_category(label: str) -> str:
    if label.startswith("CAT:"):
        return label[4:]
    if label.startswith("RESID:"):
        return PRODUCT_TO_CATEGORY[label[6:]]
    return PRODUCT_TO_CATEGORY.get(label, "")


def scan_xy(
    *,
    kind: str,
    day: int,
    source_labels: tuple[str, ...],
    target_labels: tuple[str, ...],
    x: np.ndarray,
    y: np.ndarray,
    spread_y: np.ndarray,
    tradable_y: np.ndarray,
    source_horizon: int,
    target_horizon: int,
    skip_identical: bool = False,
) -> list[dict[str, object]]:
    corr, beta = corr_beta(x, y)
    abs_x = np.abs(x)
    thresholds = np.nanquantile(abs_x, 0.90, axis=0)
    thresholds = np.maximum(thresholds, 1e-9)
    rows: list[dict[str, object]] = []
    for i, source in enumerate(source_labels):
        event = abs_x[:, i] >= thresholds[i]
        event_count = int(event.sum())
        if event_count == 0:
            gross = np.zeros(len(target_labels))
            net = np.zeros(len(target_labels))
            wins = np.zeros(len(target_labels))
            tradable = np.zeros(len(target_labels))
        else:
            direction = np.sign(x[event, i])
            direction[direction == 0] = 1.0
            beta_sign = np.sign(beta[i])
            beta_sign[beta_sign == 0] = 1.0
            directional = y[event] * direction[:, None] * beta_sign[None, :]
            gross = directional.mean(axis=0)
            net = (directional - spread_y[event]).mean(axis=0)
            wins = (directional > 0).mean(axis=0)
            tradable = tradable_y[event].mean(axis=0)
        for j, target in enumerate(target_labels):
            if skip_identical and source == target:
                continue
            source_cat = product_category(source)
            target_cat = product_category(target)
            rows.append(
                {
                    "kind": kind,
                    "day": day,
                    "source": source,
                    "target": target,
                    "source_category": source_cat,
                    "target_category": target_cat,
                    "same_category": bool(source_cat and source_cat == target_cat),
                    "source_horizon": source_horizon,
                    "target_horizon": target_horizon,
                    "n": int(len(x)),
                    "corr": float(corr[i, j]),
                    "beta": float(beta[i, j]),
                    "event_threshold": float(thresholds[i]),
                    "event_count": event_count,
                    "tradable_rate": float(tradable[j]),
                    "event_gross_ticks": float(gross[j]),
                    "event_net_cross_ticks": float(net[j]),
                    "event_win_rate": float(wins[j]),
                }
            )
    return rows


def summarize(rows: pd.DataFrame, out_path: Path) -> pd.DataFrame:
    grouped = (
        rows.groupby(["kind", "source", "target", "source_category", "target_category", "same_category", "source_horizon", "target_horizon"])
        .agg(
            days=("day", "nunique"),
            n=("n", "sum"),
            corr_mean=("corr", "mean"),
            corr_min=("corr", "min"),
            corr_max=("corr", "max"),
            corr_std=("corr", "std"),
            beta_mean=("beta", "mean"),
            event_threshold_mean=("event_threshold", "mean"),
            event_count=("event_count", "sum"),
            tradable_rate=("tradable_rate", "mean"),
            event_gross_ticks=("event_gross_ticks", "mean"),
            event_net_cross_ticks=("event_net_cross_ticks", "mean"),
            event_win_rate=("event_win_rate", "mean"),
        )
        .reset_index()
    )
    sign = np.sign(grouped["corr_mean"].to_numpy(float))
    grouped["stable_sign"] = (grouped["corr_min"] * grouped["corr_max"] > 0) & (sign != 0)
    grouped["score"] = (
        grouped["corr_mean"].abs()
        * np.sqrt(np.maximum(grouped["event_count"], 1))
        * np.maximum(grouped["event_gross_ticks"], 0)
        * np.maximum(grouped["tradable_rate"], 0)
    )
    grouped = grouped.sort_values(["score", "event_net_cross_ticks", "corr_mean"], ascending=False)
    grouped.to_csv(out_path, index=False)
    return grouped


def scan_product_returns(price_data: dict[int, dict[str, object]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    max_h = max(HORIZONS)
    for day, data in price_data.items():
        mid = data["mid"]
        spread = data["spread"]
        tradable = data["tradable"]
        for hx in HORIZONS:
            for hy in HORIZONS:
                start = hx
                end = len(mid) - hy
                if end <= start:
                    continue
                x = mid[start:end] - mid[start - hx : end - hx]
                y = mid[start + hy : end + hy] - mid[start:end]
                rows.extend(
                    scan_xy(
                        kind="product_return",
                        day=day,
                        source_labels=PRODUCTS,
                        target_labels=PRODUCTS,
                        x=x,
                        y=y,
                        spread_y=spread[start:end],
                        tradable_y=tradable[start:end],
                        source_horizon=hx,
                        target_horizon=hy,
                        skip_identical=True,
                    )
                )
    raw = pd.DataFrame(rows)
    raw.to_csv(OUT / "product_pair_latency_by_day.csv", index=False)
    summary = summarize(raw, OUT / "product_pair_latency_summary.csv")
    robust = summary[(summary["days"] == 3) & (summary["stable_sign"]) & (summary["tradable_rate"] > 0.99)].copy()
    robust.to_csv(OUT / "product_pair_latency_robust.csv", index=False)
    print(f"product return scan: raw={len(raw):,}, robust={len(robust):,}, max_h={max_h}")
    return raw, summary


def scan_category_indices(price_data: dict[int, dict[str, object]], cat_index: dict[int, np.ndarray]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    cat_labels = tuple(f"CAT:{category}" for category in CATEGORIES)
    for day, data in price_data.items():
        mid = data["mid"]
        index = cat_index[day]
        spread = data["spread"]
        tradable = data["tradable"]
        for hx in HORIZONS:
            for hy in HORIZONS:
                start = hx
                end = len(mid) - hy
                if end <= start:
                    continue
                index_x = index[start:end] - index[start - hx : end - hx]
                product_x = mid[start:end] - mid[start - hx : end - hx]
                product_y = mid[start + hy : end + hy] - mid[start:end]
                index_y = index[start + hy : end + hy] - index[start:end]
                rows.extend(
                    scan_xy(
                        kind="category_to_product",
                        day=day,
                        source_labels=cat_labels,
                        target_labels=PRODUCTS,
                        x=index_x,
                        y=product_y,
                        spread_y=spread[start:end],
                        tradable_y=tradable[start:end],
                        source_horizon=hx,
                        target_horizon=hy,
                    )
                )
                rows.extend(
                    scan_xy(
                        kind="product_to_category",
                        day=day,
                        source_labels=PRODUCTS,
                        target_labels=cat_labels,
                        x=product_x,
                        y=index_y,
                        spread_y=np.zeros_like(index_y),
                        tradable_y=np.ones_like(index_y, dtype=bool),
                        source_horizon=hx,
                        target_horizon=hy,
                    )
                )
    raw = pd.DataFrame(rows)
    raw.to_csv(OUT / "category_index_latency_by_day.csv", index=False)
    return summarize(raw, OUT / "category_index_latency_summary.csv")


def rolling_sum(values: np.ndarray, window: int) -> np.ndarray:
    csum = np.vstack([np.zeros((1, values.shape[1])), np.cumsum(values, axis=0)])
    return csum[window:] - csum[:-window]


def scan_feature_to_product(
    *,
    kind: str,
    feature_by_day: dict[int, np.ndarray],
    source_labels: tuple[str, ...],
    price_data: dict[int, dict[str, object]],
    prefix_source: str = "",
    use_rolling_sum: bool = False,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    labels = tuple(prefix_source + label for label in source_labels)
    for day, data in price_data.items():
        mid = data["mid"]
        feature = feature_by_day[day]
        spread = data["spread"]
        tradable = data["tradable"]
        for hx in HORIZONS:
            for hy in HORIZONS:
                start = hx
                end = len(mid) - hy
                if end <= start:
                    continue
                if use_rolling_sum:
                    rolled = rolling_sum(feature, hx)
                    x = rolled[start - hx : end - hx]
                else:
                    x = feature[start:end] - feature[start - hx : end - hx]
                y = mid[start + hy : end + hy] - mid[start:end]
                rows.extend(
                    scan_xy(
                        kind=kind,
                        day=day,
                        source_labels=labels,
                        target_labels=PRODUCTS,
                        x=x,
                        y=y,
                        spread_y=spread[start:end],
                        tradable_y=tradable[start:end],
                        source_horizon=hx,
                        target_horizon=hy,
                    )
                )
    raw = pd.DataFrame(rows)
    raw.to_csv(OUT / f"{kind}_by_day.csv", index=False)
    return summarize(raw, OUT / f"{kind}_summary.csv")


def write_leader_laggard_scores(product_summary: pd.DataFrame) -> pd.DataFrame:
    robust = product_summary[(product_summary["days"] == 3) & (product_summary["stable_sign"]) & (product_summary["tradable_rate"] > 0.99)].copy()
    robust = robust[robust["event_gross_ticks"] > 0]
    leaders = robust.groupby(["source", "source_category"]).agg(leader_score=("score", "sum"), relationships=("score", "size")).reset_index()
    laggards = robust.groupby(["target", "target_category"]).agg(laggard_score=("score", "sum"), relationships=("score", "size")).reset_index()
    leaders = leaders.rename(columns={"source": "product", "source_category": "category"})
    laggards = laggards.rename(columns={"target": "product", "target_category": "category"})
    scores = pd.merge(leaders, laggards, on=["product", "category"], how="outer").fillna(0.0)
    if "relationships_x" in scores.columns or "relationships_y" in scores.columns:
        scores["relationships"] = scores.get("relationships_x", 0) + scores.get("relationships_y", 0)
        scores = scores.drop(columns=[col for col in ("relationships_x", "relationships_y") if col in scores.columns])
    scores = scores.sort_values(["leader_score", "laggard_score"], ascending=False)
    scores.to_csv(OUT / "leader_laggard_scores.csv", index=False)
    return scores


def write_selected_signal_preview(product_summary: pd.DataFrame) -> None:
    selected = product_summary[
        (product_summary["days"] == 3)
        & (product_summary["stable_sign"])
        & (product_summary["tradable_rate"] > 0.99)
        & (product_summary["event_gross_ticks"] > 0.25)
    ].copy()
    selected = selected.sort_values(["same_category", "score"], ascending=[False, False]).head(120)
    payload = []
    for row in selected.itertuples(index=False):
        payload.append(
            {
                "leader": row.source,
                "laggard": row.target,
                "leader_horizon": int(row.source_horizon),
                "target_horizon": int(row.target_horizon),
                "beta": round(float(row.beta_mean), 6),
                "corr": round(float(row.corr_mean), 6),
                "event_threshold": round(float(row.event_threshold_mean), 4),
                "same_category": bool(row.same_category),
                "score": round(float(row.score), 6),
            }
        )
    (OUT / "selected_latency_signal_preview.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown(
    product_summary: pd.DataFrame,
    category_summary: pd.DataFrame,
    imbalance_summary: pd.DataFrame,
    trade_flow_summary: pd.DataFrame,
    residual_summary: pd.DataFrame,
    scores: pd.DataFrame,
) -> None:
    def table(frame: pd.DataFrame, cols: list[str], n: int = 12) -> str:
        small = frame.loc[:, cols].head(n).copy()
        for col in small.columns:
            if pd.api.types.is_float_dtype(small[col]):
                small[col] = small[col].map(lambda x: f"{x:.4f}")
        if small.empty:
            return "_No rows._"
        values = [[str(value) for value in row] for row in small.to_numpy()]
        widths = [len(str(col)) for col in small.columns]
        for row in values:
            widths = [max(width, len(value)) for width, value in zip(widths, row)]
        header = "| " + " | ".join(str(col).ljust(width) for col, width in zip(small.columns, widths)) + " |"
        sep = "| " + " | ".join("-" * width for width in widths) + " |"
        body = ["| " + " | ".join(value.ljust(width) for value, width in zip(row, widths)) + " |" for row in values]
        return "\n".join([header, sep, *body])

    robust = product_summary[(product_summary["days"] == 3) & (product_summary["stable_sign"]) & (product_summary["tradable_rate"] > 0.99)].copy()
    cross = robust[~robust["same_category"]].sort_values("score", ascending=False)
    same = robust[robust["same_category"]].sort_values("score", ascending=False)
    rejected_day1 = product_summary[
        (product_summary["days"] < 3)
        | (~product_summary["stable_sign"])
        | (product_summary["event_gross_ticks"] <= 0)
        | (product_summary["tradable_rate"] <= 0.99)
    ].sort_values("score", ascending=False)

    lines = [
        "# Round 5 Latency Alpha Scan",
        "",
        "Generated by `research/round5/latency_alpha/latency_scanner.py` from public Round 5 days +2, +3, and +4.",
        "",
        "The scan covers all 50 products and every ordered product pair over leader-return horizons 1, 2, 3, 5, 10, 20, and 50 ticks against follower future-return horizons 1, 2, 3, 5, 10, 20, and 50 ticks. Event PnL columns mark the follower at future mid and subtract the full current spread for `event_net_cross_ticks`, so positive values are deliberately conservative.",
        "",
        "## Top Same-Category Product Pairs",
        "",
        table(same, ["source", "target", "source_horizon", "target_horizon", "corr_mean", "beta_mean", "event_gross_ticks", "event_net_cross_ticks", "score"]),
        "",
        "## Top Cross-Category Product Pairs",
        "",
        table(cross, ["source", "target", "source_category", "target_category", "source_horizon", "target_horizon", "corr_mean", "event_gross_ticks", "event_net_cross_ticks", "score"]),
        "",
        "## Top Leaders And Laggards",
        "",
        table(scores, ["product", "category", "leader_score", "laggard_score", "relationships"]),
        "",
        "## Category Index Signals",
        "",
        table(category_summary.sort_values("score", ascending=False), ["kind", "source", "target", "source_horizon", "target_horizon", "corr_mean", "event_gross_ticks", "score"]),
        "",
        "## Basket Residual Signals",
        "",
        table(residual_summary.sort_values("score", ascending=False), ["source", "target", "source_horizon", "target_horizon", "corr_mean", "event_gross_ticks", "score"]),
        "",
        "## Order Book Imbalance Signals",
        "",
        table(imbalance_summary.sort_values("score", ascending=False), ["source", "target", "source_horizon", "target_horizon", "corr_mean", "event_gross_ticks", "score"]),
        "",
        "## Trade Flow Signals",
        "",
        table(trade_flow_summary.sort_values("score", ascending=False), ["source", "target", "source_horizon", "target_horizon", "corr_mean", "event_gross_ticks", "score"]),
        "",
        "## Rejected Signal Patterns",
        "",
        table(rejected_day1, ["source", "target", "same_category", "source_horizon", "target_horizon", "days", "stable_sign", "event_gross_ticks", "tradable_rate", "score"]),
        "",
        "## Output Files",
        "",
        "- `product_pair_latency_by_day.csv`: full all-pairs by-day scanner.",
        "- `product_pair_latency_summary.csv`: aggregate product-pair statistics.",
        "- `category_index_latency_summary.csv`: category index to product and product to category index.",
        "- `basket_residual_change_summary.csv`: leave-one-day-out basket residual changes to product returns.",
        "- `orderbook_imbalance_summary.csv`: imbalance changes to product returns.",
        "- `trade_flow_summary.csv`: signed public trade-flow sums to product returns.",
        "- `leader_laggard_scores.csv`: robust leader and laggard rankings.",
    ]
    (OUT / "ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    price_data = load_prices()
    trade_flow = load_trade_flow(price_data)
    cat_index = make_category_indices(price_data)
    residuals = make_basket_residuals(price_data)

    _, product_summary = scan_product_returns(price_data)
    category_summary = scan_category_indices(price_data, cat_index)
    imbalance_summary = scan_feature_to_product(
        kind="orderbook_imbalance",
        feature_by_day={day: data["imbalance"] for day, data in price_data.items()},
        source_labels=PRODUCTS,
        price_data=price_data,
    )
    trade_flow_summary = scan_feature_to_product(
        kind="trade_flow",
        feature_by_day=trade_flow,
        source_labels=PRODUCTS,
        price_data=price_data,
        use_rolling_sum=True,
    )
    residual_summary = scan_feature_to_product(
        kind="basket_residual_change",
        feature_by_day=residuals,
        source_labels=PRODUCTS,
        price_data=price_data,
        prefix_source="RESID:",
    )
    scores = write_leader_laggard_scores(product_summary)
    write_selected_signal_preview(product_summary)
    write_markdown(product_summary, category_summary, imbalance_summary, trade_flow_summary, residual_summary, scores)
    print(f"wrote latency scan outputs to {OUT}")


if __name__ == "__main__":
    main()
