from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "prosperity_rust_backtester" / "datasets" / "round4"
OUT_DIR = ROOT / "analysis" / "round4_order_flow"
HORIZONS_TS = [100, 500, 1000, 2000, 5000]
ROLLING_WINDOWS = [1, 5, 10, 20, 50]


def load_round4() -> tuple[pd.DataFrame, pd.DataFrame]:
    prices = []
    trades = []
    for day in (1, 2, 3):
        price_day = pd.read_csv(DATA_DIR / f"prices_round_4_day_{day}.csv", sep=";")
        trade_day = pd.read_csv(DATA_DIR / f"trades_round_4_day_{day}.csv", sep=";")
        price_day["day"] = day
        trade_day["day"] = day
        prices.append(price_day)
        trades.append(trade_day)
    return pd.concat(prices, ignore_index=True), pd.concat(trades, ignore_index=True)


def build_trade_observations(prices: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    mid = prices.set_index(["day", "product", "timestamp"])["mid_price"].sort_index()
    rows = []
    for trade in trades.itertuples(index=False):
        day = int(trade.day)
        timestamp = int(trade.timestamp)
        mid_now = mid.get((day, trade.symbol, timestamp), np.nan)
        if pd.isna(mid_now):
            continue
        for trader, side in ((trade.buyer, 1), (trade.seller, -1)):
            if not isinstance(trader, str) or not trader.strip():
                continue
            row = {
                "day": day,
                "symbol": trade.symbol,
                "timestamp": timestamp,
                "trader": trader,
                "side": side,
                "quantity": int(trade.quantity),
                "trade_price": float(trade.price),
                "mid_price": float(mid_now),
            }
            for horizon in HORIZONS_TS:
                future_mid = mid.get((day, trade.symbol, timestamp + horizon), np.nan)
                row[f"signed_mid_move_{horizon}"] = (
                    np.nan if pd.isna(future_mid) else side * (float(future_mid) - float(mid_now))
                )
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_alpha(observations: pd.DataFrame, keys: list[str], metric: str) -> pd.DataFrame:
    source = observations.dropna(subset=[metric])
    grouped = source.groupby(keys, dropna=False)
    out = grouped.agg(
        count=(metric, "size"),
        quantity=("quantity", "sum"),
        mean=(metric, "mean"),
        std=(metric, "std"),
        total=(metric, "sum"),
        hit_rate=(metric, lambda x: float((x > 0).mean())),
        buys=("side", lambda x: int((x > 0).sum())),
        sells=("side", lambda x: int((x < 0).sum())),
    ).reset_index()
    out["t_stat"] = out["mean"] / (out["std"] / np.sqrt(out["count"]))
    return out.replace([np.inf, -np.inf], np.nan)


def build_order_flow(prices: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    price_grid = prices.rename(columns={"product": "symbol"}).copy()
    mid = price_grid.set_index(["day", "symbol", "timestamp"])["mid_price"].sort_index()
    trade_rows = []
    for trade in trades.itertuples(index=False):
        mid_now = mid.get((int(trade.day), trade.symbol, int(trade.timestamp)), np.nan)
        if pd.isna(mid_now):
            continue
        direction = 1 if trade.price > mid_now else -1 if trade.price < mid_now else 0
        trade_rows.append(
            {
                "day": int(trade.day),
                "symbol": trade.symbol,
                "timestamp": int(trade.timestamp),
                "signed_quantity": direction * int(trade.quantity),
            }
        )
    flow = pd.DataFrame(trade_rows).groupby(["day", "symbol", "timestamp"], as_index=False)["signed_quantity"].sum()
    columns = [
        "day",
        "symbol",
        "timestamp",
        "mid_price",
        "bid_price_1",
        "ask_price_1",
        "bid_volume_1",
        "bid_volume_2",
        "bid_volume_3",
        "ask_volume_1",
        "ask_volume_2",
        "ask_volume_3",
    ]
    grid = price_grid[columns].merge(flow, on=["day", "symbol", "timestamp"], how="left")
    grid["signed_quantity"] = grid["signed_quantity"].fillna(0.0)
    for column in [
        "bid_volume_1",
        "bid_volume_2",
        "bid_volume_3",
        "ask_volume_1",
        "ask_volume_2",
        "ask_volume_3",
    ]:
        grid[column] = pd.to_numeric(grid[column], errors="coerce").fillna(0.0).abs()
    grid["bid_depth"] = grid[["bid_volume_1", "bid_volume_2", "bid_volume_3"]].sum(axis=1)
    grid["ask_depth"] = grid[["ask_volume_1", "ask_volume_2", "ask_volume_3"]].sum(axis=1)
    depth = grid["bid_depth"] + grid["ask_depth"]
    grid["book_imbalance"] = np.where(depth > 0, (grid["bid_depth"] - grid["ask_depth"]) / depth, 0.0)
    grid["spread"] = grid["ask_price_1"] - grid["bid_price_1"]
    grouped = grid.groupby(["day", "symbol"], sort=False)
    for window in ROLLING_WINDOWS:
        grid[f"flow_{window}"] = grouped["signed_quantity"].transform(lambda x: x.rolling(window, min_periods=1).sum())
    for horizon in ROLLING_WINDOWS:
        grid[f"future_mid_move_{horizon}"] = grouped["mid_price"].shift(-horizon) - grid["mid_price"]
    return grid


def summarize_order_flow(flow: pd.DataFrame) -> pd.DataFrame:
    rows = []
    def safe_corr(left: pd.Series, right: pd.Series) -> float:
        valid = left.notna() & right.notna()
        if valid.sum() < 2:
            return np.nan
        left_valid = left[valid]
        right_valid = right[valid]
        if left_valid.std() == 0 or right_valid.std() == 0:
            return np.nan
        return float(left_valid.corr(right_valid))

    for symbol, symbol_frame in flow.groupby("symbol"):
        row = {"symbol": symbol}
        for window in ROLLING_WINDOWS:
            a = symbol_frame[f"flow_{window}"]
            b = symbol_frame[f"future_mid_move_{window}"]
            row[f"flow_{window}_corr"] = safe_corr(a, b)
        row["book_imbalance_h10_corr"] = safe_corr(symbol_frame["book_imbalance"], symbol_frame["future_mid_move_10"])
        row["mean_spread"] = symbol_frame["spread"].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def next_tick_spread_check(prices: pd.DataFrame, observations: pd.DataFrame, alpha: pd.DataFrame) -> pd.DataFrame:
    candidates = alpha[(alpha["count"] >= 50) & (alpha["t_stat"].abs() >= 3.0)].copy()
    candidates["alpha_sign"] = np.sign(candidates["mean"])
    candidate_map = {
        (row.symbol, row.trader): int(row.alpha_sign)
        for row in candidates.itertuples(index=False)
        if int(row.alpha_sign) != 0
    }
    if not candidate_map:
        return pd.DataFrame()
    grid = prices.rename(columns={"product": "symbol"}).set_index(["day", "symbol", "timestamp"]).sort_index()
    rows = []
    for trade in observations.itertuples(index=False):
        alpha_sign = candidate_map.get((trade.symbol, trade.trader))
        if alpha_sign is None:
            continue
        signal = alpha_sign * int(trade.side)
        entry_timestamp = int(trade.timestamp) + 100
        entry_row = grid.loc[(int(trade.day), trade.symbol, entry_timestamp)] if (int(trade.day), trade.symbol, entry_timestamp) in grid.index else None
        if entry_row is None:
            continue
        entry_price = float(entry_row.ask_price_1 if signal > 0 else entry_row.bid_price_1)
        for horizon in HORIZONS_TS:
            exit_key = (int(trade.day), trade.symbol, entry_timestamp + horizon)
            if exit_key not in grid.index:
                continue
            future_mid = float(grid.loc[exit_key].mid_price)
            rows.append(
                {
                    "symbol": trade.symbol,
                    "trader": trade.trader,
                    "horizon": horizon,
                    "signal": signal,
                    "edge_per_unit": signal * (future_mid - entry_price),
                    "quantity": int(trade.quantity),
                }
            )
    return pd.DataFrame(rows)


def write_report(
    trader_h1000: pd.DataFrame,
    symbol_trader_h1000: pd.DataFrame,
    order_flow: pd.DataFrame,
    spread_check: pd.DataFrame,
) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trader_h1000.to_csv(OUT_DIR / "trader_alpha_h1000.csv", index=False)
    symbol_trader_h1000.to_csv(OUT_DIR / "symbol_trader_alpha_h1000.csv", index=False)
    order_flow.to_csv(OUT_DIR / "order_flow_correlations.csv", index=False)
    if not spread_check.empty:
        spread_check.to_csv(OUT_DIR / "next_tick_spread_check.csv", index=False)
    top = trader_h1000[trader_h1000["count"] >= 20].sort_values("t_stat", ascending=False).head(8)
    product_top = symbol_trader_h1000[symbol_trader_h1000["count"] >= 8].sort_values("t_stat", ascending=False).head(12)
    flow_top = order_flow.sort_values("book_imbalance_h10_corr").head(12)
    spread_summary = (
        spread_check.groupby(["symbol", "trader", "horizon"], as_index=False)
        .agg(
            count=("edge_per_unit", "size"),
            mean_edge=("edge_per_unit", "mean"),
            total_edge=("edge_per_unit", "sum"),
            hit_rate=("edge_per_unit", lambda x: float((x > 0).mean())),
            quantity=("quantity", "sum"),
        )
        if not spread_check.empty
        else pd.DataFrame()
    )
    if not spread_summary.empty:
        spread_summary.to_csv(OUT_DIR / "next_tick_spread_summary.csv", index=False)
    def markdown_table(frame: pd.DataFrame) -> str:
        if frame.empty:
            return "_No rows._"
        text = frame.copy()
        for column in text.columns:
            if pd.api.types.is_float_dtype(text[column]):
                text[column] = text[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
            else:
                text[column] = text[column].map(lambda value: "" if pd.isna(value) else str(value))
        header = "| " + " | ".join(text.columns) + " |"
        divider = "| " + " | ".join(["---"] * len(text.columns)) + " |"
        rows = ["| " + " | ".join(row) + " |" for row in text.astype(str).to_numpy()]
        return "\n".join([header, divider, *rows])

    report = [
        "# Round 4 Informed Trader and Order Flow Analysis",
        "",
        "Trader alpha is signed future mid move: buys are positive if the future mid rises, sells are positive if the future mid falls.",
        "",
        "## Top Trader Alpha, 1000 Timestamp Horizon",
        "",
        markdown_table(top.round(4)),
        "",
        "## Top Symbol-Trader Alpha, 1000 Timestamp Horizon",
        "",
        markdown_table(product_top.round(4)),
        "",
        "## Order Flow Correlations",
        "",
        markdown_table(flow_top.round(4)),
    ]
    if not spread_summary.empty:
        report.extend(
            [
                "",
                "## Next-Tick Spread Check",
                "",
                markdown_table(spread_summary.sort_values(["symbol", "trader", "horizon"]).round(4)),
            ]
        )
    (OUT_DIR / "report.md").write_text("\n".join(report) + "\n")


def main() -> None:
    prices, trades = load_round4()
    observations = build_trade_observations(prices, trades)
    all_alpha = []
    for horizon in HORIZONS_TS:
        metric = f"signed_mid_move_{horizon}"
        summary = summarize_alpha(observations, ["trader"], metric)
        summary["horizon"] = horizon
        all_alpha.append(summary)
    pd.concat(all_alpha, ignore_index=True).to_csv(OUT_DIR / "trader_alpha_all_horizons.csv", index=False)
    trader_h1000 = summarize_alpha(observations, ["trader"], "signed_mid_move_1000")
    symbol_trader_h1000 = summarize_alpha(observations, ["symbol", "trader"], "signed_mid_move_1000")
    order_flow = summarize_order_flow(build_order_flow(prices, trades))
    spread_check = next_tick_spread_check(prices, observations, symbol_trader_h1000)
    write_report(trader_h1000, symbol_trader_h1000, order_flow, spread_check)
    print(f"wrote {OUT_DIR}")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    main()
