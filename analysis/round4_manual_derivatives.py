from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from scipy import integrate, stats


TRADING_DAYS_PER_YEAR = 252
STEPS_PER_DAY = 4
STEPS_PER_YEAR = TRADING_DAYS_PER_YEAR * STEPS_PER_DAY
CONTRACT_SIZE = 3000


def weeks_to_years(weeks: float) -> float:
    return (weeks * 5) / TRADING_DAYS_PER_YEAR


def steps_for_weeks(weeks: float) -> int:
    return int(round(weeks * 5 * STEPS_PER_DAY))


@dataclass(frozen=True)
class Contract:
    symbol: str
    kind: Literal["underlying", "call", "put", "binary_put", "chooser", "ko_put"]
    expiry_weeks: float | None
    bid_size: int
    bid: float
    ask: float
    ask_size: int
    strike: float | None = None
    choice_weeks: float | None = None
    cash_payoff: float | None = None
    barrier: float | None = None


@dataclass(frozen=True)
class Position:
    symbol: str
    signed_volume: int


def build_contracts() -> list[Contract]:
    return [
        Contract("AC", "underlying", None, 200, 49.975, 50.025, 200),
        Contract("AC_50_P", "put", 3, 50, 12.00, 12.05, 50, strike=50),
        Contract("AC_50_C", "call", 3, 50, 12.00, 12.05, 50, strike=50),
        Contract("AC_35_P", "put", 3, 50, 4.33, 4.35, 50, strike=35),
        Contract("AC_40_P", "put", 3, 50, 6.50, 6.55, 50, strike=40),
        Contract("AC_45_P", "put", 3, 50, 9.05, 9.10, 50, strike=45),
        Contract("AC_60_C", "call", 3, 50, 8.80, 8.85, 50, strike=60),
        Contract("AC_50_P_2", "put", 2, 50, 9.70, 9.75, 50, strike=50),
        Contract("AC_50_C_2", "call", 2, 50, 9.70, 9.75, 50, strike=50),
        Contract("AC_50_CO", "chooser", 3, 50, 22.20, 22.30, 50, strike=50, choice_weeks=2),
        Contract("AC_40_BP", "binary_put", 3, 50, 5.00, 5.10, 50, strike=40, cash_payoff=10),
        Contract("AC_45_KO", "ko_put", 3, 500, 0.150, 0.175, 500, strike=45, barrier=35),
    ]


def norm_cdf(x: float | np.ndarray) -> float | np.ndarray:
    return stats.norm.cdf(x)


def black_scholes_call_put(s0: float, k: float, t: float, sigma: float) -> tuple[float, float]:
    if t <= 0:
        return max(s0 - k, 0.0), max(k - s0, 0.0)
    vol = sigma * math.sqrt(t)
    d1 = (math.log(s0 / k) + 0.5 * sigma * sigma * t) / vol
    d2 = d1 - vol
    call = s0 * norm_cdf(d1) - k * norm_cdf(d2)
    put = k * norm_cdf(-d2) - s0 * norm_cdf(-d1)
    return float(call), float(put)


def binary_put_closed_form(s0: float, k: float, t: float, sigma: float, cash_payoff: float) -> float:
    vol = sigma * math.sqrt(t)
    d1 = (math.log(s0 / k) + 0.5 * sigma * sigma * t) / vol
    d2 = d1 - vol
    return float(cash_payoff * norm_cdf(-d2))


def chooser_quadrature(s0: float, k: float, t_choice: float, t_expiry: float, sigma: float) -> float:
    remaining = t_expiry - t_choice
    mu = math.log(s0) - 0.5 * sigma * sigma * t_choice
    sd = sigma * math.sqrt(t_choice)

    def integrand(x: float) -> float:
        spot = math.exp(x)
        call, put = black_scholes_call_put(spot, k, remaining, sigma)
        value = call if spot >= k else put
        return value * stats.norm.pdf((x - mu) / sd) / sd

    lower = mu - 10.0 * sd
    upper = mu + 10.0 * sd
    value, error = integrate.quad(integrand, lower, upper, epsabs=1e-11, epsrel=1e-11, limit=300)
    if error > 1e-7:
        print(f"warning: chooser quadrature integration error estimate {error:.3g}")
    return float(value)


def simulate_states(
    *,
    s0: float,
    sigma: float,
    n_paths: int,
    seed: int,
    batch_pairs: int,
    steps_2w: int,
    steps_3w: int,
) -> dict[str, np.ndarray]:
    if n_paths % 2:
        raise ValueError("n_paths must be even for antithetic sampling")
    rng = np.random.default_rng(seed)
    n_pairs_total = n_paths // 2
    dt = 1.0 / STEPS_PER_YEAR
    drift = -0.5 * sigma * sigma * dt
    vol = sigma * math.sqrt(dt)
    times = np.arange(1, steps_3w + 1, dtype=np.float64)
    drift_grid = drift * times

    s2 = np.empty(n_paths, dtype=np.float64)
    s3 = np.empty(n_paths, dtype=np.float64)
    min3 = np.empty(n_paths, dtype=np.float64)

    out = 0
    pairs_done = 0
    while pairs_done < n_pairs_total:
        pairs = min(batch_pairs, n_pairs_total - pairs_done)
        z = rng.standard_normal((pairs, steps_3w))
        np.cumsum(z, axis=1, out=z)

        log_base = drift_grid + vol * z
        s2_base = s0 * np.exp(log_base[:, steps_2w - 1])
        s3_base = s0 * np.exp(log_base[:, -1])
        min_base = s0 * np.exp(np.minimum(log_base.min(axis=1), 0.0))

        log_anti = drift_grid - vol * z
        s2_anti = s0 * np.exp(log_anti[:, steps_2w - 1])
        s3_anti = s0 * np.exp(log_anti[:, -1])
        min_anti = s0 * np.exp(np.minimum(log_anti.min(axis=1), 0.0))

        sl = slice(out, out + pairs)
        s2[sl] = s2_base
        s3[sl] = s3_base
        min3[sl] = min_base
        sl = slice(out + pairs, out + 2 * pairs)
        s2[sl] = s2_anti
        s3[sl] = s3_anti
        min3[sl] = min_anti

        out += 2 * pairs
        pairs_done += pairs

    return {"S_2W": s2, "S_3W": s3, "MIN_3W": min3}


def payoff(contract: Contract, states: dict[str, np.ndarray], *, underlying_horizon: str = "3w", ko_leq: bool = False) -> np.ndarray:
    if contract.kind == "underlying":
        if underlying_horizon == "3w":
            return states["S_3W"]
        if underlying_horizon == "2w":
            return states["S_2W"]
        if underlying_horizon == "s0":
            return np.full_like(states["S_3W"], 50.0)
        raise ValueError(f"unknown underlying_horizon={underlying_horizon}")

    if contract.kind == "call":
        st = states["S_3W"] if contract.expiry_weeks == 3 else states["S_2W"]
        return np.maximum(st - float(contract.strike), 0.0)

    if contract.kind == "put":
        st = states["S_3W"] if contract.expiry_weeks == 3 else states["S_2W"]
        return np.maximum(float(contract.strike) - st, 0.0)

    if contract.kind == "binary_put":
        return float(contract.cash_payoff) * (states["S_3W"] < float(contract.strike))

    if contract.kind == "chooser":
        s2 = states["S_2W"]
        s3 = states["S_3W"]
        k = float(contract.strike)
        return np.where(s2 >= k, np.maximum(s3 - k, 0.0), np.maximum(k - s3, 0.0))

    if contract.kind == "ko_put":
        knocked = states["MIN_3W"] <= float(contract.barrier) if ko_leq else states["MIN_3W"] < float(contract.barrier)
        return np.where(knocked, 0.0, np.maximum(float(contract.strike) - states["S_3W"], 0.0))

    raise ValueError(contract.kind)


def payoff_matrix(
    contracts: list[Contract],
    states: dict[str, np.ndarray],
    *,
    underlying_horizon: str = "3w",
    ko_leq: bool = False,
) -> np.ndarray:
    return np.column_stack([payoff(c, states, underlying_horizon=underlying_horizon, ko_leq=ko_leq) for c in contracts])


def closed_form_fair(contract: Contract, s0: float, sigma: float, *, underlying_horizon: str = "3w") -> float | None:
    if contract.kind == "underlying":
        return s0
    if contract.kind in {"call", "put"}:
        t = weeks_to_years(float(contract.expiry_weeks))
        call, put = black_scholes_call_put(s0, float(contract.strike), t, sigma)
        return call if contract.kind == "call" else put
    if contract.kind == "binary_put":
        return binary_put_closed_form(s0, float(contract.strike), weeks_to_years(float(contract.expiry_weeks)), sigma, float(contract.cash_payoff))
    if contract.kind == "chooser":
        return chooser_quadrature(
            s0,
            float(contract.strike),
            weeks_to_years(float(contract.choice_weeks)),
            weeks_to_years(float(contract.expiry_weeks)),
            sigma,
        )
    return None


def fair_value_table(
    contracts: list[Contract],
    payoffs: np.ndarray,
    *,
    s0: float,
    sigma: float,
    n_paths: int,
) -> pd.DataFrame:
    rows = []
    means = payoffs.mean(axis=0)
    ses = payoffs.std(axis=0, ddof=1) / math.sqrt(n_paths)
    for i, contract in enumerate(contracts):
        analytic = closed_form_fair(contract, s0, sigma)
        if analytic is not None and contract.kind != "ko_put":
            fair = analytic
            source = "closed_form" if contract.kind != "chooser" else "quadrature"
            mc_se = float(ses[i])
        else:
            fair = float(means[i])
            source = "mc_antithetic"
            mc_se = float(ses[i])
        buy_edge = fair - contract.ask
        sell_edge = contract.bid - fair
        if buy_edge > max(sell_edge, 0):
            side = "BUY"
            volume = contract.ask_size
            pnl = buy_edge * volume * CONTRACT_SIZE
        elif sell_edge > max(buy_edge, 0):
            side = "SELL"
            volume = contract.bid_size
            pnl = sell_edge * volume * CONTRACT_SIZE
        else:
            side = "BUY"
            volume = 0
            pnl = 0.0
        rows.append(
            {
                "symbol": contract.symbol,
                "kind": contract.kind,
                "fair": fair,
                "source": source,
                "mc_mean": float(means[i]),
                "mc_se": mc_se,
                "ci95_lo": float(means[i] - 1.96 * ses[i]),
                "ci95_hi": float(means[i] + 1.96 * ses[i]),
                "bid": contract.bid,
                "ask": contract.ask,
                "buy_edge": buy_edge,
                "sell_edge": sell_edge,
                "max_buy": contract.ask_size,
                "max_sell": contract.bid_size,
                "pure_ev_side": side,
                "pure_ev_volume": volume,
                "pure_ev_expected_pnl": pnl,
                "edge_abs": max(buy_edge, sell_edge),
                "tiny_edge_flag": abs(max(buy_edge, sell_edge)) < max(2 * mc_se, 0.01),
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values("edge_abs", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def signed_volume_from_table(contracts: list[Contract], table: pd.DataFrame, *, min_edge: float = 0.0) -> np.ndarray:
    by_symbol = table.set_index("symbol")
    q = np.zeros(len(contracts), dtype=np.int64)
    for i, c in enumerate(contracts):
        row = by_symbol.loc[c.symbol]
        if row["pure_ev_side"] == "BUY" and row["buy_edge"] > min_edge:
            q[i] = c.ask_size
        elif row["pure_ev_side"] == "SELL" and row["sell_edge"] > min_edge:
            q[i] = -c.bid_size
    return q


def expected_pnl_from_q(contracts: list[Contract], fair_by_symbol: dict[str, float], q: np.ndarray) -> float:
    total = 0.0
    for c, qty in zip(contracts, q):
        if qty > 0:
            total += qty * (fair_by_symbol[c.symbol] - c.ask) * CONTRACT_SIZE
        elif qty < 0:
            total += (-qty) * (c.bid - fair_by_symbol[c.symbol]) * CONTRACT_SIZE
    return total


def build_position_pnl(contracts: list[Contract], payoffs: np.ndarray, q: np.ndarray) -> np.ndarray:
    pnl = np.zeros(payoffs.shape[0], dtype=np.float64)
    for i, (c, qty) in enumerate(zip(contracts, q)):
        if qty > 0:
            pnl += qty * (payoffs[:, i] - c.ask) * CONTRACT_SIZE
        elif qty < 0:
            pnl += (-qty) * (c.bid - payoffs[:, i]) * CONTRACT_SIZE
    return pnl


def summarize_100_path_average(path_pnl: np.ndarray, *, seed: int = 123, n_bootstrap: int = 200_000, sample_size: int = 100) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    n = len(path_pnl)
    chunks = []
    remaining = n_bootstrap
    while remaining:
        m = min(10_000, remaining)
        idx = rng.integers(0, n, size=(m, sample_size))
        chunks.append(path_pnl[idx].mean(axis=1))
        remaining -= m
    avg = np.concatenate(chunks)
    losses = avg[avg < 0]
    var5 = np.quantile(avg, 0.05)
    tail5 = avg[avg <= var5]
    var1 = np.quantile(avg, 0.01)
    tail1 = avg[avg <= var1]
    return {
        "mean_path": float(path_pnl.mean()),
        "std_path": float(path_pnl.std(ddof=1)),
        "std_100": float(path_pnl.std(ddof=1) / math.sqrt(sample_size)),
        "q01_100": float(np.quantile(avg, 0.01)),
        "q05_100": float(var5),
        "q50_100": float(np.quantile(avg, 0.50)),
        "q95_100": float(np.quantile(avg, 0.95)),
        "q99_100": float(np.quantile(avg, 0.99)),
        "prob_avg_lt_0": float(np.mean(avg < 0)),
        "cvar05_100": float(tail5.mean()) if len(tail5) else float("nan"),
        "cvar01_100": float(tail1.mean()) if len(tail1) else float("nan"),
        "bootstrap_reps": float(n_bootstrap),
    }


def portfolio_delta_gamma(
    contracts: list[Contract],
    q: np.ndarray,
    *,
    s0: float,
    sigma: float,
    h: float = 0.05,
    n_paths: int = 1_000_000,
    seed: int = 99,
) -> dict[str, float]:
    # Common random numbers make finite differences stable enough for portfolio diagnostics.
    steps_2w = steps_for_weeks(2)
    steps_3w = steps_for_weeks(3)
    vals = []
    for bump_s0 in (s0 - h, s0, s0 + h):
        states = simulate_states(
            s0=bump_s0,
            sigma=sigma,
            n_paths=n_paths,
            seed=seed,
            batch_pairs=100_000,
            steps_2w=steps_2w,
            steps_3w=steps_3w,
        )
        pay = payoff_matrix(contracts, states)
        pnl = build_position_pnl(contracts, pay, q)
        vals.append(float(pnl.mean()))
    delta = (vals[2] - vals[0]) / (2 * h)
    gamma = (vals[2] - 2 * vals[1] + vals[0]) / (h * h)
    return {"delta_pnl_per_s0": delta, "gamma_pnl_per_s0_sq": gamma, "value_down": vals[0], "value_mid": vals[1], "value_up": vals[2]}


def scenario_tables(states: dict[str, np.ndarray], path_pnl: np.ndarray) -> dict[str, list[dict[str, float | str]]]:
    s3 = states["S_3W"]
    bins = np.array([0, 20, 30, 35, 40, 45, 50, 55, 60, 70, 90, 120, np.inf], dtype=float)
    labels = ["<20", "20-30", "30-35", "35-40", "40-45", "45-50", "50-55", "55-60", "60-70", "70-90", "90-120", ">=120"]
    bucket = pd.cut(s3, bins=bins, labels=labels, right=False)
    df = pd.DataFrame({"bucket": bucket, "pnl": path_pnl, "S3": s3, "hit_barrier": states["MIN_3W"] < 35, "chooser_call": states["S_2W"] >= 50})
    by_bucket = (
        df.groupby("bucket", observed=False)
        .agg(paths=("pnl", "size"), prob=("pnl", lambda x: len(x) / len(df)), mean_pnl=("pnl", "mean"), p05=("pnl", lambda x: np.quantile(x, 0.05)), p95=("pnl", lambda x: np.quantile(x, 0.95)))
        .reset_index()
    )
    barrier = (
        df.groupby("hit_barrier")
        .agg(paths=("pnl", "size"), prob=("pnl", lambda x: len(x) / len(df)), mean_pnl=("pnl", "mean"), p05=("pnl", lambda x: np.quantile(x, 0.05)), p95=("pnl", lambda x: np.quantile(x, 0.95)))
        .reset_index()
    )
    chooser = (
        df.groupby("chooser_call")
        .agg(paths=("pnl", "size"), prob=("pnl", lambda x: len(x) / len(df)), mean_pnl=("pnl", "mean"), p05=("pnl", lambda x: np.quantile(x, 0.05)), p95=("pnl", lambda x: np.quantile(x, 0.95)))
        .reset_index()
    )
    worst_idx = np.argpartition(path_pnl, 10)[:10]
    worst = pd.DataFrame(
        {
            "rank": np.arange(1, 11),
            "path_pnl": path_pnl[worst_idx[np.argsort(path_pnl[worst_idx])]],
            "S2": states["S_2W"][worst_idx[np.argsort(path_pnl[worst_idx])]],
            "S3": states["S_3W"][worst_idx[np.argsort(path_pnl[worst_idx])]],
            "MIN3": states["MIN_3W"][worst_idx[np.argsort(path_pnl[worst_idx])]],
        }
    )
    return {
        "terminal_buckets": json.loads(by_bucket.to_json(orient="records")),
        "barrier": json.loads(barrier.to_json(orient="records")),
        "chooser": json.loads(chooser.to_json(orient="records")),
        "worst_paths": json.loads(worst.to_json(orient="records")),
    }


def optimize_risk_adjusted(
    contracts: list[Contract],
    table: pd.DataFrame,
    payoffs: np.ndarray,
    *,
    lambdas: tuple[float, ...] = (0, 0.25, 0.5, 1, 2),
) -> pd.DataFrame:
    pure = signed_volume_from_table(contracts, table)
    fair_by_symbol = dict(zip(table["symbol"], table["fair"]))
    candidates: list[tuple[str, np.ndarray]] = [("pure_max_positive_edge", pure)]

    for edge in (0.005, 0.01, 0.02, 0.05):
        candidates.append((f"pure_excluding_edge_below_{edge:g}", signed_volume_from_table(contracts, table, min_edge=edge)))

    ac_idx = [i for i, c in enumerate(contracts) if c.symbol == "AC"][0]
    base_no_ac = pure.copy()
    base_no_ac[ac_idx] = 0
    for ac_q in range(-200, 201):
        q = base_no_ac.copy()
        q[ac_idx] = ac_q
        candidates.append((f"ac_hedge_{ac_q:+d}", q))

    # Partial sweeps in the riskiest positive-edge exotic/large-size legs while keeping other pure-EV legs fixed.
    for sym in ("AC_50_CO", "AC_40_BP", "AC_45_KO"):
        idx = [i for i, c in enumerate(contracts) if c.symbol == sym][0]
        max_abs = contracts[idx].ask_size if pure[idx] > 0 else contracts[idx].bid_size
        direction = 1 if pure[idx] >= 0 else -1
        for vol in sorted(set([0, 5, 10, 20, 30, 40, 50, max_abs // 4, max_abs // 2, max_abs])):
            if vol <= max_abs:
                q = pure.copy()
                q[idx] = direction * vol
                candidates.append((f"partial_{sym}_{direction * vol:+d}", q))

    # Combine AC hedges with conservative KO sizes; this captures the largest quantity line without exploding the grid.
    ko_idx = [i for i, c in enumerate(contracts) if c.symbol == "AC_45_KO"][0]
    for ko_q in (0, 50, 100, 200, 300, 400, 500):
        for ac_q in range(-200, 201, 5):
            q = base_no_ac.copy()
            q[ko_idx] = ko_q
            q[ac_idx] = ac_q
            candidates.append((f"grid_ko_{ko_q}_ac_{ac_q:+d}", q))

    seen: set[tuple[int, ...]] = set()
    rows = []
    for name, q in candidates:
        key = tuple(int(x) for x in q)
        if key in seen:
            continue
        seen.add(key)
        pnl = build_position_pnl(contracts, payoffs, q)
        mean = expected_pnl_from_q(contracts, fair_by_symbol, q)
        # The MC mean uses the same simulated paths and is reported for risk/correlation diagnostics.
        rows.append(
            {
                "name": name,
                "q": key,
                "expected_pnl": mean,
                "mc_mean_path": float(pnl.mean()),
                "std_path": float(pnl.std(ddof=1)),
                "std_100": float(pnl.std(ddof=1) / 10.0),
                "p01_path": float(np.quantile(pnl, 0.01)),
                "p05_path": float(np.quantile(pnl, 0.05)),
                "prob_gt_0_norm": float(stats.norm.sf((0.0 - mean) / (pnl.std(ddof=1) / 10.0))) if pnl.std(ddof=1) > 0 else float(mean > 0),
                "prob_gt_250k_norm": float(stats.norm.sf((250_000.0 - mean) / (pnl.std(ddof=1) / 10.0))) if pnl.std(ddof=1) > 0 else float(mean > 250_000),
                "prob_gt_500k_norm": float(stats.norm.sf((500_000.0 - mean) / (pnl.std(ddof=1) / 10.0))) if pnl.std(ddof=1) > 0 else float(mean > 500_000),
                "prob_gt_1m_norm": float(stats.norm.sf((1_000_000.0 - mean) / (pnl.std(ddof=1) / 10.0))) if pnl.std(ddof=1) > 0 else float(mean > 1_000_000),
            }
        )
    df = pd.DataFrame(rows)
    for lam in lambdas:
        df[f"objective_lambda_{lam:g}"] = df["expected_pnl"] - lam * df["std_100"]
    return df.sort_values("expected_pnl", ascending=False).reset_index(drop=True)


def sensitivity_table(
    contracts: list[Contract],
    *,
    s0_values: tuple[float, ...] = (49.975, 50.0, 50.025),
    sigma_values: tuple[float, ...] = (2.50, 2.51, 2.52),
    n_paths: int = 1_000_000,
    seed: int = 20260427,
) -> pd.DataFrame:
    rows = []
    steps_2w = steps_for_weeks(2)
    steps_3w = steps_for_weeks(3)
    for s0 in s0_values:
        for sigma in sigma_values:
            states = simulate_states(
                s0=s0,
                sigma=sigma,
                n_paths=n_paths,
                seed=seed,
                batch_pairs=100_000,
                steps_2w=steps_2w,
                steps_3w=steps_3w,
            )
            pay = payoff_matrix(contracts, states)
            table = fair_value_table(contracts, pay, s0=s0, sigma=sigma, n_paths=n_paths)
            q = signed_volume_from_table(contracts, table)
            expected = expected_pnl_from_q(contracts, dict(zip(table["symbol"], table["fair"])), q)
            rows.append(
                {
                    "s0": s0,
                    "sigma": sigma,
                    "expected_pnl_pure": expected,
                    "orders": ", ".join(f"{c.symbol}:{int(v)}" for c, v in zip(contracts, q) if v != 0),
                    "ko_fair_mc": float(table.loc[table["symbol"] == "AC_45_KO", "fair"].iloc[0]),
                    "chooser_fair": float(table.loc[table["symbol"] == "AC_50_CO", "fair"].iloc[0]),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", type=int, default=5_000_000)
    parser.add_argument("--seed", type=int, default=20260427)
    parser.add_argument("--batch-pairs", type=int, default=100_000)
    parser.add_argument("--s0", type=float, default=50.0)
    parser.add_argument("--sigma", type=float, default=2.51)
    parser.add_argument("--output-dir", type=Path, default=Path("analysis/round4_manual_outputs"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    contracts = build_contracts()
    steps_2w = steps_for_weeks(2)
    steps_3w = steps_for_weeks(3)

    assumptions = {
        "S0": args.s0,
        "sigma": args.sigma,
        "zero_drift": True,
        "dt": 1 / STEPS_PER_YEAR,
        "trading_days_per_year": TRADING_DAYS_PER_YEAR,
        "steps_per_day": STEPS_PER_DAY,
        "steps_per_year": STEPS_PER_YEAR,
        "two_weeks_years": weeks_to_years(2),
        "three_weeks_years": weeks_to_years(3),
        "two_weeks_steps": steps_2w,
        "three_weeks_steps": steps_3w,
        "contract_size": CONTRACT_SIZE,
        "buy_uses": "ask",
        "sell_uses": "bid",
        "price_column": "ignored",
    }

    print("ASSUMPTIONS")
    print(json.dumps(assumptions, indent=2))

    states = simulate_states(
        s0=args.s0,
        sigma=args.sigma,
        n_paths=args.paths,
        seed=args.seed,
        batch_pairs=args.batch_pairs,
        steps_2w=steps_2w,
        steps_3w=steps_3w,
    )
    pay = payoff_matrix(contracts, states)
    table = fair_value_table(contracts, pay, s0=args.s0, sigma=args.sigma, n_paths=args.paths)
    table.to_csv(args.output_dir / "fair_values.csv", index=False)

    print("\nSANITY-CHECK FAIR VALUES")
    sanity_cols = ["symbol", "kind", "fair", "source", "mc_mean", "mc_se", "ci95_lo", "ci95_hi", "bid", "ask", "buy_edge", "sell_edge"]
    print(table[sanity_cols].to_string(index=False, float_format=lambda x: f"{x:,.6f}"))

    q_pure = signed_volume_from_table(contracts, table)
    q_rank = signed_volume_from_table(contracts, table, min_edge=0.01)
    fair_by_symbol = dict(zip(table["symbol"], table["fair"]))
    expected_pure = expected_pnl_from_q(contracts, fair_by_symbol, q_pure)
    expected_rank = expected_pnl_from_q(contracts, fair_by_symbol, q_rank)
    path_pnl = build_position_pnl(contracts, pay, q_pure)
    risk = summarize_100_path_average(path_pnl)
    pd.DataFrame([risk]).to_csv(args.output_dir / "pure_portfolio_risk.csv", index=False)

    rank_path_pnl = build_position_pnl(contracts, pay, q_rank)
    rank_risk = summarize_100_path_average(rank_path_pnl, seed=456)
    pd.DataFrame([rank_risk]).to_csv(args.output_dir / "rank_portfolio_risk.csv", index=False)

    search_n = min(args.paths, 500_000)
    search_rng = np.random.default_rng(args.seed + 101)
    search_idx = search_rng.choice(args.paths, size=search_n, replace=False) if search_n < args.paths else np.arange(args.paths)
    risk_search = optimize_risk_adjusted(contracts, table, pay[search_idx])
    risk_search.to_csv(args.output_dir / "risk_search.csv", index=False)

    best_by_lambda = []
    for col in [c for c in risk_search.columns if c.startswith("objective_lambda_")]:
        row = risk_search.loc[risk_search[col].idxmax()]
        best_by_lambda.append({"objective": col, "name": row["name"], "expected_pnl": row["expected_pnl"], "std_100": row["std_100"], "q": row["q"]})
    pd.DataFrame(best_by_lambda).to_csv(args.output_dir / "best_by_lambda.csv", index=False)

    scenarios = scenario_tables(states, path_pnl)
    with (args.output_dir / "scenario_tables.json").open("w") as f:
        json.dump(scenarios, f, indent=2)

    delta_gamma = portfolio_delta_gamma(contracts, q_pure, s0=args.s0, sigma=args.sigma)
    with (args.output_dir / "delta_gamma.json").open("w") as f:
        json.dump(delta_gamma, f, indent=2)

    sens = sensitivity_table(contracts)
    sens.to_csv(args.output_dir / "sensitivity.csv", index=False)

    # 14/21 trading-day sensitivity for the UI wording only.
    alt_states = simulate_states(
        s0=args.s0,
        sigma=args.sigma,
        n_paths=1_000_000,
        seed=args.seed + 7,
        batch_pairs=args.batch_pairs,
        steps_2w=14 * STEPS_PER_DAY,
        steps_3w=21 * STEPS_PER_DAY,
    )
    alt_pay = payoff_matrix(contracts, alt_states)
    alt_table = fair_value_table(contracts, alt_pay, s0=args.s0, sigma=args.sigma, n_paths=1_000_000)
    alt_table.to_csv(args.output_dir / "ui_14_21_trading_day_sensitivity.csv", index=False)

    # Equality sensitivities. These should be numerically identical because equality has zero probability.
    ko_leq_pay = payoff_matrix(contracts, states, ko_leq=True)
    ko_strict = float(table.loc[table["symbol"] == "AC_45_KO", "fair"].iloc[0])
    ko_leq = float(ko_leq_pay[:, [c.symbol for c in contracts].index("AC_45_KO")].mean())

    print("\nPURE EV ORDERS")
    order_rows = []
    for c, qty in zip(contracts, q_pure):
        side = "BUY" if qty >= 0 else "SELL"
        volume = abs(int(qty))
        edge = fair_by_symbol[c.symbol] - c.ask if qty > 0 else c.bid - fair_by_symbol[c.symbol] if qty < 0 else 0.0
        order_rows.append({"symbol": c.symbol, "side": side, "volume": volume, "signed_volume": int(qty), "edge": edge, "expected_pnl": edge * volume * CONTRACT_SIZE})
    order_df = pd.DataFrame(order_rows)
    order_df.to_csv(args.output_dir / "final_orders.csv", index=False)
    print(order_df.to_string(index=False, float_format=lambda x: f"{x:,.6f}"))
    print(f"Exact pure-EV expected PnL: {expected_pure:,.2f}")

    print("\nRANK-OPTIMIZED ORDERS (EXCLUDE EDGES BELOW 0.01)")
    rank_order_rows = []
    for c, qty in zip(contracts, q_rank):
        side = "BUY" if qty >= 0 else "SELL"
        volume = abs(int(qty))
        edge = fair_by_symbol[c.symbol] - c.ask if qty > 0 else c.bid - fair_by_symbol[c.symbol] if qty < 0 else 0.0
        rank_order_rows.append({"symbol": c.symbol, "side": side, "volume": volume, "signed_volume": int(qty), "edge": edge, "expected_pnl": edge * volume * CONTRACT_SIZE})
    rank_order_df = pd.DataFrame(rank_order_rows)
    rank_order_df.to_csv(args.output_dir / "rank_final_orders.csv", index=False)
    print(rank_order_df.to_string(index=False, float_format=lambda x: f"{x:,.6f}"))
    print(f"Rank-optimized expected PnL: {expected_rank:,.2f}")

    print("\nPURE PORTFOLIO RISK")
    print(json.dumps(risk, indent=2))
    print("\nRANK-OPTIMIZED PORTFOLIO RISK")
    print(json.dumps(rank_risk, indent=2))
    print("\nBEST RISK-ADJUSTED CANDIDATES BY LAMBDA")
    print(pd.DataFrame(best_by_lambda).to_string(index=False, float_format=lambda x: f"{x:,.2f}"))
    print("\nDELTA/GAMMA DIAGNOSTIC")
    print(json.dumps(delta_gamma, indent=2))
    print("\nEQUALITY / INTERPRETATION CHECKS")
    print(json.dumps({"ko_strict_fair": ko_strict, "ko_leq_fair": ko_leq, "ko_difference": ko_leq - ko_strict}, indent=2))
    print("\nSENSITIVITY")
    print(sens.to_string(index=False, float_format=lambda x: f"{x:,.6f}"))
    print(f"\nWrote outputs to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
