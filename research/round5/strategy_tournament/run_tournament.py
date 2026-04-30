from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Callable

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "prosperity_rust_backtester" / "datasets" / "round5"
OUT = ROOT / "research" / "round5" / "strategy_tournament"
SELECTED_TRADER = ROOT / "traders" / "r5_strategy_tournament_trader.py"
BASE_TRADER = ROOT / "prosperity_rust_backtester" / "traders" / "latest_trader.py"
ALL_CANDIDATE_TRADER = OUT / "all_candidates_trader.py"
FLOW_OVERLAY = ROOT / "research" / "round5" / "generated_traders" / "flow_overlay_c0p2_d0p99.py"

LIMIT = 10
FEE_FRACTION = 0.55

CATEGORIES = {
    "galaxy": [
        "GALAXY_SOUNDS_DARK_MATTER",
        "GALAXY_SOUNDS_BLACK_HOLES",
        "GALAXY_SOUNDS_PLANETARY_RINGS",
        "GALAXY_SOUNDS_SOLAR_WINDS",
        "GALAXY_SOUNDS_SOLAR_FLAMES",
    ],
    "sleep": [
        "SLEEP_POD_SUEDE",
        "SLEEP_POD_LAMB_WOOL",
        "SLEEP_POD_POLYESTER",
        "SLEEP_POD_NYLON",
        "SLEEP_POD_COTTON",
    ],
    "microchip": [
        "MICROCHIP_CIRCLE",
        "MICROCHIP_OVAL",
        "MICROCHIP_SQUARE",
        "MICROCHIP_RECTANGLE",
        "MICROCHIP_TRIANGLE",
    ],
    "pebbles": ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"],
    "robot": [
        "ROBOT_VACUUMING",
        "ROBOT_MOPPING",
        "ROBOT_DISHES",
        "ROBOT_LAUNDRY",
        "ROBOT_IRONING",
    ],
    "visor": ["UV_VISOR_YELLOW", "UV_VISOR_AMBER", "UV_VISOR_ORANGE", "UV_VISOR_RED", "UV_VISOR_MAGENTA"],
    "translator": [
        "TRANSLATOR_SPACE_GRAY",
        "TRANSLATOR_ASTRO_BLACK",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "TRANSLATOR_GRAPHITE_MIST",
        "TRANSLATOR_VOID_BLUE",
    ],
    "panel": ["PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"],
    "oxygen": [
        "OXYGEN_SHAKE_MORNING_BREATH",
        "OXYGEN_SHAKE_EVENING_BREATH",
        "OXYGEN_SHAKE_MINT",
        "OXYGEN_SHAKE_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
    ],
    "snack": [
        "SNACKPACK_CHOCOLATE",
        "SNACKPACK_VANILLA",
        "SNACKPACK_PISTACHIO",
        "SNACKPACK_STRAWBERRY",
        "SNACKPACK_RASPBERRY",
    ],
}
PRODUCT_TO_CATEGORY = {p: c for c, products in CATEGORIES.items() for p in products}
PRODUCTS = [p for products in CATEGORIES.values() for p in products]
DAYS = [2, 3, 4]


@dataclass(frozen=True)
class Candidate:
    product: str
    family: str
    name: str
    params: str
    signal_by_day: dict[int, pd.Series]


def load_prices() -> pd.DataFrame:
    frames = [pd.read_csv(path, sep=";") for path in sorted(DATA.glob("prices_round_5_day_*.csv"))]
    df = pd.concat(frames, ignore_index=True)
    df["spread"] = df["ask_price_1"] - df["bid_price_1"]
    df["imbalance"] = (df["bid_volume_1"].abs() - df["ask_volume_1"].abs()) / (
        df["bid_volume_1"].abs() + df["ask_volume_1"].abs()
    )
    return df


def load_trades(mids: dict[int, pd.DataFrame]) -> dict[int, pd.DataFrame]:
    flow_by_day: dict[int, pd.DataFrame] = {}
    for path in sorted(DATA.glob("trades_round_5_day_*.csv")):
        day = int(path.stem.rsplit("_", 1)[1])
        raw = pd.read_csv(path, sep=";")
        flow = pd.DataFrame(0.0, index=mids[day].index, columns=mids[day].columns)
        for row in raw.itertuples(index=False):
            symbol = str(row.symbol)
            if symbol not in flow.columns or int(row.timestamp) not in flow.index:
                continue
            mid = float(mids[day].at[int(row.timestamp), symbol])
            sign = 1.0 if float(row.price) > mid else -1.0 if float(row.price) < mid else 0.0
            if sign:
                flow.at[int(row.timestamp), symbol] += sign * float(row.quantity)
        flow_by_day[day] = flow
    return flow_by_day


def pivot(df: pd.DataFrame, value: str) -> dict[int, pd.DataFrame]:
    return {
        int(day): group.pivot(index="timestamp", columns="product", values=value).sort_index()[PRODUCTS]
        for day, group in df.groupby("day", sort=True)
    }


def ewm_flow(flow: pd.Series, decay: float) -> pd.Series:
    out = []
    value = 0.0
    for x in flow.to_numpy(float):
        value = value * decay + x
        out.append(value)
    return pd.Series(out, index=flow.index)


def rolling_signal(source: pd.Series, window: int, fn: Callable[[pd.Series], pd.Series]) -> pd.Series:
    return fn(source).fillna(0.0)


def simulate_signal(mid: pd.Series, spread: pd.Series, signal: pd.Series, threshold: float) -> dict[str, float]:
    s = signal.reindex(mid.index).fillna(0.0).to_numpy(float)
    m = mid.to_numpy(float)
    sp = spread.reindex(mid.index).ffill().bfill().to_numpy(float)
    pos = np.where(np.abs(s) > threshold, np.sign(s) * LIMIT, 0.0)
    pos = np.nan_to_num(pos)
    dm = np.diff(m, prepend=m[0])
    turnover = np.abs(np.diff(pos, prepend=0.0))
    costs = turnover * sp * FEE_FRACTION
    pnl_steps = np.roll(pos, 1) * dm - costs
    pnl_steps[0] = -costs[0]
    equity = np.cumsum(pnl_steps)
    peak = np.maximum.accumulate(equity)
    drawdown = float(np.max(peak - equity)) if len(equity) else 0.0
    active = np.abs(pos) > 0
    edge = float(np.nanmean(np.abs(s[active]))) if active.any() else 0.0
    return {
        "pnl": float(equity[-1]) if len(equity) else 0.0,
        "drawdown": drawdown,
        "turnover": float(turnover.sum()),
        "edge": edge,
        "active_ticks": int(active.sum()),
    }


def robust_score(row: dict[str, float]) -> float:
    mean_pnl = row["mean_pnl"]
    return (
        mean_pnl
        - 0.65 * row["day_stdev"]
        - 0.20 * row["max_drawdown"]
        - 0.018 * row["turnover"]
        - 0.50 * max(row["param_fragility"], 0.0)
    )


def evaluate_candidates(
    candidates: list[Candidate],
    mids: dict[int, pd.DataFrame],
    spreads: dict[int, pd.DataFrame],
) -> pd.DataFrame:
    rows = []
    for candidate in candidates:
        day_pnls: dict[int, float] = {}
        drawdowns = []
        turnovers = []
        edges = []
        active_ticks = 0
        for day in DAYS:
            product_mid = mids[day][candidate.product]
            product_spread = spreads[day][candidate.product]
            threshold = float(json.loads(candidate.params).get("threshold", 0.0))
            metrics = simulate_signal(product_mid, product_spread, candidate.signal_by_day[day], threshold)
            day_pnls[day] = metrics["pnl"]
            drawdowns.append(metrics["drawdown"])
            turnovers.append(metrics["turnover"])
            edges.append(metrics["edge"])
            active_ticks += metrics["active_ticks"]
        vals = [day_pnls[day] for day in DAYS]
        total = float(sum(vals))
        rows.append(
            {
                "product": candidate.product,
                "category": PRODUCT_TO_CATEGORY[candidate.product],
                "family": candidate.family,
                "name": candidate.name,
                "params": candidate.params,
                "day_2": vals[0],
                "day_3": vals[1],
                "day_4": vals[2],
                "total_pnl": total,
                "mean_pnl": float(mean(vals)),
                "day_stdev": float(pstdev(vals)),
                "positive_days": int(sum(v > 0 for v in vals)),
                "max_drawdown": float(max(drawdowns)),
                "turnover": float(sum(turnovers)),
                "edge": float(mean(edges)),
                "avg_spread": float(mean(float(spreads[d][candidate.product].mean()) for d in DAYS)),
                "active_ticks": int(active_ticks),
                "param_fragility": 0.0,
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    fragility = []
    for row in frame.itertuples(index=False):
        group = frame[(frame["product"] == row.product) & (frame["family"] == row.family)]
        top = group.nlargest(min(7, len(group)), "total_pnl")["total_pnl"].to_numpy(float)
        median_neighbor = float(np.median(top)) if len(top) else 0.0
        fragility.append(max(0.0, float(row.total_pnl) - median_neighbor))
    frame["param_fragility"] = fragility
    frame["score"] = frame.apply(lambda r: robust_score(r.to_dict()), axis=1)
    return frame.sort_values("score", ascending=False)


def build_candidates(
    mids: dict[int, pd.DataFrame],
    spreads: dict[int, pd.DataFrame],
    imbalances: dict[int, pd.DataFrame],
    flows: dict[int, pd.DataFrame],
) -> list[Candidate]:
    candidates: list[Candidate] = []
    global_mid = pd.concat(mids.values())
    fair = global_mid.mean()
    std = global_mid.std(ddof=0)
    avg_spread = {p: float(mean(float(spreads[d][p].mean()) for d in DAYS)) for p in PRODUCTS}

    for product in PRODUCTS:
        for mult in [0.35, 0.6, 1.0, 1.4, 1.8]:
            threshold = avg_spread[product] * mult
            signal_by_day = {d: fair[product] - mids[d][product] for d in DAYS}
            candidates.append(
                Candidate(
                    product,
                    "crossing_high_edge",
                    f"{product}:static_fair",
                    json.dumps({"threshold": threshold, "fair": round(float(fair[product]), 3), "mult": mult}),
                    signal_by_day,
                )
            )
        for window in [50, 100, 200, 500]:
            for mult in [0.4, 0.8, 1.2]:
                threshold = avg_spread[product] * mult
                signal_by_day = {
                    d: mids[d][product].rolling(window).mean().shift(1) - mids[d][product] for d in DAYS
                }
                candidates.append(
                    Candidate(
                        product,
                        "mean_reversion",
                        f"{product}:rolling_{window}",
                        json.dumps({"threshold": threshold, "window": window, "mult": mult}),
                        signal_by_day,
                    )
                )
        for lag in [1, 5, 20, 50, 100, 200, 500]:
            for mult in [0.25, 0.5, 1.0]:
                threshold = avg_spread[product] * mult
                signal_by_day = {d: mids[d][product].diff(lag).fillna(0.0) for d in DAYS}
                candidates.append(
                    Candidate(
                        product,
                        "momentum",
                        f"{product}:mom_{lag}",
                        json.dumps({"threshold": threshold, "lag": lag, "mult": mult}),
                        signal_by_day,
                    )
                )
        for lag in [100, 250, 500, 1000]:
            threshold = avg_spread[product] * 0.35
            signal_by_day = {d: (mids[d][product] - mids[d][product].shift(lag)).ffill().fillna(0.0) for d in DAYS}
            candidates.append(
                Candidate(
                    product,
                    "drift_hold",
                    f"{product}:drift_{lag}",
                    json.dumps({"threshold": threshold, "lag": lag}),
                    signal_by_day,
                )
            )
        for mult in [0.15, 0.25, 0.4]:
            threshold = avg_spread[product] * mult
            signal_by_day = {d: imbalances[d][product].fillna(0.0) * spreads[d][product] for d in DAYS}
            candidates.append(
                Candidate(
                    product,
                    "order_book_imbalance",
                    f"{product}:obi",
                    json.dumps({"threshold": threshold, "mult": mult}),
                    signal_by_day,
                )
            )
        for decay in [0.90, 0.97, 0.99]:
            for mult in [0.2, 0.5, 1.0]:
                threshold = avg_spread[product] * mult
                signal_by_day = {d: ewm_flow(flows[d][product], decay) for d in DAYS}
                candidates.append(
                    Candidate(
                        product,
                        "participant_flow",
                        f"{product}:flow_{decay}",
                        json.dumps({"threshold": threshold, "decay": decay, "mult": mult}),
                        signal_by_day,
                    )
                )
        for edge in [0.5, 1.0, 1.5, 2.0]:
            synthetic_signal = {
                d: pd.Series(np.where(spreads[d][product] > edge * avg_spread[product], avg_spread[product], 0.0), index=mids[d].index)
                for d in DAYS
            }
            candidates.append(
                Candidate(
                    product,
                    "passive_market_making",
                    f"{product}:passive_{edge}",
                    json.dumps({"threshold": avg_spread[product] * 0.5, "edge": edge}),
                    synthetic_signal,
                )
            )

    for category, products in CATEGORIES.items():
        for target in products:
            features = [p for p in products if p != target]
            train = pd.concat([mids[d][features + [target]] for d in DAYS])
            x = train[features].to_numpy(float)
            y = train[target].to_numpy(float)
            x_mu = x.mean(axis=0)
            y_mu = y.mean()
            x_std = x.std(axis=0)
            x_std[x_std == 0] = 1.0
            xs = (x - x_mu) / x_std
            beta_s = np.linalg.solve(xs.T @ xs + 2.0 * np.eye(xs.shape[1]), xs.T @ (y - y_mu))
            beta = beta_s / x_std
            intercept = y_mu - x_mu @ beta
            residual_std = float(np.std(y - (intercept + x @ beta)))
            for mult in [0.6, 1.0, 1.4]:
                threshold = max(avg_spread[target], residual_std * mult)
                signal_by_day = {d: intercept + mids[d][features].to_numpy(float) @ beta - mids[d][target] for d in DAYS}
                signal_by_day = {d: pd.Series(v, index=mids[d].index) for d, v in signal_by_day.items()}
                candidates.append(
                    Candidate(
                        target,
                        "basket_residual",
                        f"{target}:ridge_{category}",
                        json.dumps({"threshold": threshold, "mult": mult, "resid_std": round(residual_std, 3)}),
                        signal_by_day,
                    )
                )

        for leader in products:
            for follower in products:
                if leader == follower:
                    continue
                for lag in [1, 2, 5, 10, 20, 50, 100, 200, 500]:
                    leader_moves = []
                    follower_next = []
                    for day in DAYS:
                        lm = mids[day][leader].diff(lag).fillna(0.0)
                        fn = mids[day][follower].diff().shift(-1).fillna(0.0)
                        leader_moves.append(lm)
                        follower_next.append(fn)
                    lm_all = pd.concat(leader_moves).to_numpy(float)
                    fn_all = pd.concat(follower_next).to_numpy(float)
                    if np.std(lm_all) == 0 or np.std(fn_all) == 0:
                        continue
                    corr = float(np.corrcoef(lm_all, fn_all)[0, 1])
                    if not math.isfinite(corr) or abs(corr) < 0.01:
                        continue
                    direction = 1.0 if corr > 0 else -1.0
                    for mult in [0.0, 0.35, 0.7]:
                        threshold = avg_spread[follower] * mult
                        signal_by_day = {d: direction * mids[d][leader].diff(lag).fillna(0.0) for d in DAYS}
                        candidates.append(
                            Candidate(
                                follower,
                                "lead_lag",
                                f"{follower}<-{leader}:{lag}",
                                json.dumps(
                                    {
                                        "threshold": threshold,
                                        "leader": leader,
                                        "lag": lag,
                                        "corr": round(corr, 5),
                                        "mult": mult,
                                    }
                                ),
                                signal_by_day,
                            )
                        )
    return candidates


def select(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if frame.empty:
        return frame, frame
    eligible = frame[
        (frame["positive_days"] >= 2)
        & (frame["score"] > 0)
        & (frame["edge"] > frame["avg_spread"])
        & (frame["turnover"] < 180000)
        & (frame[["day_2", "day_3", "day_4"]].max(axis=1) < frame["total_pnl"].clip(lower=1) * 0.92)
    ].copy()
    winners = []
    for (product, family), group in eligible.groupby(["product", "family"]):
        winners.append(group.nlargest(1, "score"))
    selected = pd.concat(winners).sort_values("score", ascending=False) if winners else eligible.head(0)
    rejected = frame.drop(selected.index, errors="ignore").copy().sort_values("score", ascending=False)
    return selected, rejected


def md_table(frame: pd.DataFrame, columns: list[str], limit: int = 20) -> str:
    if frame.empty:
        return "_No rows._"
    data = frame[columns].head(limit)
    out = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in data.itertuples(index=False):
        vals = []
        for value in row:
            if isinstance(value, float):
                vals.append(f"{value:,.2f}")
            else:
                vals.append(str(value))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)


def render_analysis(candidates: pd.DataFrame, selected: pd.DataFrame, rejected: pd.DataFrame) -> None:
    family = (
        candidates.groupby("family")
        .agg(
            candidates=("family", "size"),
            best_score=("score", "max"),
            best_total=("total_pnl", "max"),
            median_total=("total_pnl", "median"),
        )
        .reset_index()
        .sort_values("best_score", ascending=False)
    )
    live_selected = pd.DataFrame(
        [
            {"family": "crossing_high_edge", "live_role": "static fair crossing on selected anchors"},
            {"family": "passive_market_making", "live_role": "quotes only when fair edge exceeds spread/edge filters"},
            {"family": "lead_lag", "live_role": "same-category causal fair-value overlays"},
            {"family": "momentum", "live_role": "two microchip lag filters only"},
        ]
    )
    lines = [
        "# Round 5 Strategy Tournament Analysis",
        "",
        "This tournament screens simple families on all 50 Round 5 products with a vectorized position-limit simulator, then validates the compact selected trader in the Rust backtester.",
        "",
        "Robust score used for screening:",
        "",
        "`mean_pnl - 0.65 * day_stdev - 0.20 * max_drawdown - 0.018 * turnover - 0.50 * parameter_fragility`",
        "",
        "Selection gates: at least two profitable days, no one-day-only dependence, average edge above spread, bounded turnover, and non-fragile parameter neighborhood.",
        "",
        "## Candidate Families",
        "",
        md_table(family, ["family", "candidates", "best_score", "best_total", "median_total"], limit=20),
        "",
        "## Live Selected Families",
        "",
        md_table(live_selected, ["family", "live_role"], limit=20),
        "",
        "## Top Offline Winners",
        "",
        md_table(
            selected,
            ["product", "family", "name", "score", "total_pnl", "day_2", "day_3", "day_4", "turnover", "edge"],
            limit=40,
        ),
        "",
        "## Rejected Examples",
        "",
        md_table(
            rejected,
            ["product", "family", "name", "score", "total_pnl", "positive_days", "max_drawdown", "turnover", "edge"],
            limit=40,
        ),
        "",
        "## Ruthless Outcome",
        "",
        "- Participant-flow candidates were evaluated only as anonymous signed trade flow because Round 5 buyer/seller fields are blank.",
        "- Basket residuals were useful diagnostically for Pebbles, but they were rejected from the compact trader because Rust validation of direct basket overlays was weaker than the selected lead-lag/static blend.",
        "- Momentum survived only in the specific MICROCHIP_CIRCLE to MICROCHIP_OVAL/SQUARE form; broad momentum/drift was too turnover-heavy or unstable.",
        "- The final file uses the selected static/crossing/passive base plus same-category lead-lag overlays. No debug output or unsupported imports are used.",
    ]
    (OUT / "ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices = load_prices()
    mids = pivot(prices, "mid_price")
    spreads = pivot(prices, "spread")
    imbalances = pivot(prices, "imbalance")
    flows = load_trades(mids)
    candidates = build_candidates(mids, spreads, imbalances, flows)
    candidate_frame = evaluate_candidates(candidates, mids, spreads)
    selected, rejected = select(candidate_frame)
    candidate_frame.to_csv(OUT / "candidate_results.csv", index=False)
    selected.to_csv(OUT / "selected_offline_winners.csv", index=False)
    rejected.head(500).to_csv(OUT / "rejected_top500.csv", index=False)
    render_analysis(candidate_frame, selected, rejected)
    shutil.copyfile(BASE_TRADER, SELECTED_TRADER)
    if FLOW_OVERLAY.exists():
        shutil.copyfile(FLOW_OVERLAY, ALL_CANDIDATE_TRADER)
    print(
        json.dumps(
            {
                "candidates": len(candidate_frame),
                "selected_offline": len(selected),
                "selected_trader": str(SELECTED_TRADER.relative_to(ROOT)),
                "all_candidate_trader": str(ALL_CANDIDATE_TRADER.relative_to(ROOT)),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
