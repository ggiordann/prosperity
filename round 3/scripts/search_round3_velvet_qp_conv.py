#!/usr/bin/env python3
"""QP-supervised causal-conv search for long-gamma Velvetfruit stat arb.

This is an experimental research layer for VELVETFRUIT_EXTRACT and VEV
vouchers.  It builds causal convolutional features from the underlying return
tape and the option IV surface, fits an exact ridge quadratic program to a
delta-hedged long-option residual target, then writes dependency-free trader
variants for Rust verification.

The generated strategies are long gamma only: they may buy VEV calls when the
QP score is high and hedge the option delta with VELVETFRUIT_EXTRACT.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import time
from dataclasses import dataclass
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKTESTER_DIR = REPO_ROOT / "prosperity_rust_backtester"
ROUND3_DIR = BACKTESTER_DIR / "datasets" / "round3"
RUST_BINARY = BACKTESTER_DIR / "target" / "release" / "rust_backtester"
OUT_DIR = REPO_ROOT / "analysis" / "round3_velvet_qp_conv"
GENERATED_TRADER_DIR = OUT_DIR / "generated_traders"
RUST_RUN_DIR = OUT_DIR / "rust_runs"

UNDERLYING = "VELVETFRUIT_EXTRACT"
STRIKES = (5000, 5100, 5200, 5300, 5400, 5500)
ROUND3_DAYS = (0, 1, 2)
TTE_YEARS = 5.0 / 365.0
OBSERVATIONS_PER_DAY = 10_000
ANNUALIZATION = OBSERVATIONS_PER_DAY * 365.0
MIN_IV = 0.01
MAX_IV = 5.0

FEATURE_NAMES = (
    "bias",
    "rv_edge",
    "anchor_edge",
    "iv_skew",
    "moneyness",
    "abs_moneyness",
    "delta",
    "gamma_notional",
    "vega",
    "spread",
    "ret_k3",
    "ret_k12",
    "ret_fast_slow",
    "absret_k12",
    "anchor_k3",
    "anchor_fast_slow",
    "anchor_momo",
)

KERNELS = {
    "ret_k3": (0.50, 0.30, 0.20),
    "ret_k12": tuple([1.0 / 12.0] * 12),
    "ret_fast_slow": (
        0.35,
        0.25,
        0.15,
        0.10,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
    ),
    "absret_k12": tuple([1.0 / 12.0] * 12),
    "anchor_k3": (0.50, 0.30, 0.20),
    "anchor_fast_slow": (
        0.35,
        0.25,
        0.15,
        0.10,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
        -0.05,
    ),
    "anchor_momo": (1.0, -1.0),
}


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    rv_alpha: float
    horizon: int
    ridge_lambda: float
    threshold_quantile: float
    min_score: float
    moneyness_limit: float
    max_option_clip: int
    max_long_option_position: int
    delta_hedge_threshold: int
    hedge_interval_ticks: int
    max_hedge_clip: int


@dataclass(frozen=True)
class FittedModel:
    spec: VariantSpec
    means: list[float]
    scales: list[float]
    weights: list[float]
    threshold: float
    exit_threshold: float


SUMMARY_ROW_RE = re.compile(
    r"^(?P<dataset>\S+)\s+"
    r"(?P<day>-?\d+|all|-)\s+"
    r"(?P<ticks>\d+)\s+"
    r"(?P<own_trades>\d+)\s+"
    r"(?P<pnl>-?\d+(?:\.\d+)?)\s+",
    re.MULTILINE,
)


def normal_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def normal_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes_call(spot: float, strike: float, volatility: float) -> float:
    if volatility <= 0.0:
        return max(spot - strike, 0.0)
    vol_sqrt_t = volatility * math.sqrt(TTE_YEARS)
    if vol_sqrt_t <= 0.0:
        return max(spot - strike, 0.0)
    d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * TTE_YEARS) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return spot * normal_cdf(d1) - strike * normal_cdf(d2)


def black_scholes_delta(spot: float, strike: float, volatility: float) -> float:
    volatility = max(MIN_IV, volatility)
    vol_sqrt_t = volatility * math.sqrt(TTE_YEARS)
    if vol_sqrt_t <= 0.0:
        return 1.0 if spot > strike else 0.0
    d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * TTE_YEARS) / vol_sqrt_t
    return normal_cdf(d1)


def black_scholes_vega(spot: float, strike: float, volatility: float) -> float:
    volatility = max(MIN_IV, volatility)
    vol_sqrt_t = volatility * math.sqrt(TTE_YEARS)
    if spot <= 0.0 or strike <= 0.0 or vol_sqrt_t <= 0.0:
        return 0.0
    d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * TTE_YEARS) / vol_sqrt_t
    return spot * math.sqrt(TTE_YEARS) * normal_pdf(d1)


def black_scholes_gamma(spot: float, strike: float, volatility: float) -> float:
    volatility = max(MIN_IV, volatility)
    vol_sqrt_t = volatility * math.sqrt(TTE_YEARS)
    if spot <= 0.0 or strike <= 0.0 or vol_sqrt_t <= 0.0:
        return 0.0
    d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * TTE_YEARS) / vol_sqrt_t
    return normal_pdf(d1) / (spot * vol_sqrt_t)


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
    high = MAX_IV
    while black_scholes_call(spot, strike, high) < call_price and high < 20.0:
        high *= 2.0
    if high >= 20.0 and black_scholes_call(spot, strike, high) < call_price:
        return float("nan")

    for _ in range(50):
        mid = 0.5 * (low + high)
        model_price = black_scholes_call(spot, strike, mid)
        if abs(model_price - call_price) <= 1e-7:
            return mid
        if model_price < call_price:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def parse_float_list(raw: str) -> list[float]:
    values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one float")
    return values


def parse_int_list(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return values


def fmt_param(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    sign = "m" if value < 0 else ""
    return f"{sign}{abs(value):g}".replace(".", "p")


def causal_conv(values: np.ndarray, kernel: tuple[float, ...]) -> np.ndarray:
    out = np.zeros(len(values), dtype=float)
    weights = np.asarray(kernel, dtype=float)
    for index in range(len(values)):
        count = min(len(weights), index + 1)
        window = values[index - count + 1 : index + 1][::-1]
        out[index] = float(np.dot(window, weights[:count]))
    return out


def add_conv_by_day(frame: pd.DataFrame, source: str, target: str, kernel: tuple[float, ...]) -> None:
    pieces: list[pd.Series] = []
    for _, group in frame.groupby("day", sort=False):
        values = group[source].fillna(0.0).to_numpy(dtype=float)
        pieces.append(pd.Series(causal_conv(values, kernel), index=group.index))
    frame[target] = pd.concat(pieces).sort_index()


def load_prices() -> pd.DataFrame:
    needed = {UNDERLYING, *(f"VEV_{strike}" for strike in STRIKES)}
    frames = []
    for day in ROUND3_DAYS:
        path = ROUND3_DIR / f"prices_round_3_day_{day}.csv"
        frame = pd.read_csv(path, sep=";")
        frames.append(frame[frame["product"].isin(needed)].copy())
    prices = pd.concat(frames, ignore_index=True)
    prices = prices.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)
    for col in ("bid_volume_1", "ask_volume_1"):
        prices[col] = prices[col].fillna(0)
    return prices


def parse_strike(product_name: str) -> int | None:
    match = re.fullmatch(r"VEV_(\d+)", product_name)
    return int(match.group(1)) if match else None


def build_base_frame() -> pd.DataFrame:
    prices = load_prices()
    underlying = prices[prices["product"] == UNDERLYING].copy()
    underlying = underlying.rename(columns={"mid_price": "spot_mid"})
    underlying["log_return"] = underlying.groupby("day")["spot_mid"].transform(
        lambda series: np.log(series.astype(float)).diff().fillna(0.0)
    )
    underlying["abs_log_return"] = underlying["log_return"].abs()
    for name in ("ret_k3", "ret_k12", "ret_fast_slow"):
        add_conv_by_day(underlying, "log_return", name, KERNELS[name])
    add_conv_by_day(underlying, "abs_log_return", "absret_k12", KERNELS["absret_k12"])

    options = prices[prices["product"].str.startswith("VEV_")].copy()
    options["strike"] = options["product"].map(parse_strike)
    options = options[options["strike"].isin(STRIKES)].copy()
    options = options.rename(columns={"mid_price": "option_mid"})
    merged = options.merge(
        underlying[
            [
                "day",
                "timestamp",
                "spot_mid",
                "log_return",
                "ret_k3",
                "ret_k12",
                "ret_fast_slow",
                "absret_k12",
            ]
        ],
        on=["day", "timestamp"],
        how="inner",
    )

    rows = []
    for row in merged.itertuples(index=False):
        best_bid = getattr(row, "bid_price_1")
        best_ask = getattr(row, "ask_price_1")
        if pd.isna(best_bid) or pd.isna(best_ask) or float(best_bid) >= float(best_ask):
            continue
        spot = float(row.spot_mid)
        strike = float(row.strike)
        bid_iv = implied_volatility(float(best_bid), spot, strike)
        ask_iv = implied_volatility(float(best_ask), spot, strike)
        mid_iv = implied_volatility(float(row.option_mid), spot, strike)
        if not (math.isfinite(bid_iv) and math.isfinite(ask_iv) and math.isfinite(mid_iv)):
            continue
        delta = black_scholes_delta(spot, strike, mid_iv)
        gamma = black_scholes_gamma(spot, strike, mid_iv)
        vega = black_scholes_vega(spot, strike, mid_iv)
        rows.append(
            {
                "day": int(row.day),
                "timestamp": int(row.timestamp),
                "product": str(row.product),
                "strike": int(row.strike),
                "spot_mid": spot,
                "option_mid": float(row.option_mid),
                "best_bid": int(best_bid),
                "best_ask": int(best_ask),
                "bid_volume": max(0, int(getattr(row, "bid_volume_1"))),
                "ask_volume": abs(int(getattr(row, "ask_volume_1"))),
                "bid_iv": bid_iv,
                "ask_iv": ask_iv,
                "mid_iv": mid_iv,
                "delta": delta,
                "gamma": gamma,
                "vega": vega,
                "moneyness": math.log(strike / spot) / math.sqrt(TTE_YEARS),
                "spread": float(best_ask) - float(best_bid),
                "log_return": float(row.log_return),
                "ret_k3": float(row.ret_k3),
                "ret_k12": float(row.ret_k12),
                "ret_fast_slow": float(row.ret_fast_slow),
                "absret_k12": float(row.absret_k12),
            }
        )

    frame = pd.DataFrame(rows)
    frame["iv_anchor"] = frame.groupby(["day", "timestamp"])["mid_iv"].transform("median")

    anchor = frame[["day", "timestamp", "iv_anchor"]].drop_duplicates().sort_values(["day", "timestamp"])
    add_conv_by_day(anchor, "iv_anchor", "anchor_k3", KERNELS["anchor_k3"])
    add_conv_by_day(anchor, "iv_anchor", "anchor_fast_slow", KERNELS["anchor_fast_slow"])
    add_conv_by_day(anchor, "iv_anchor", "anchor_momo", KERNELS["anchor_momo"])
    frame = frame.merge(anchor, on=["day", "timestamp", "iv_anchor"], how="left")
    return frame.sort_values(["day", "timestamp", "strike"]).reset_index(drop=True)


def add_rv_feature(frame: pd.DataFrame, rv_alpha: float) -> pd.DataFrame:
    underlying = frame[["day", "timestamp", "spot_mid", "log_return"]].drop_duplicates().copy()
    pieces = []
    for _, group in underlying.groupby("day", sort=False):
        group = group.sort_values("timestamp").copy()
        squared = group["log_return"].astype(float) ** 2
        group["rv_var"] = squared.ewm(alpha=rv_alpha, adjust=False).mean()
        group["returns_seen"] = np.arange(len(group))
        group["rv_forecast"] = np.where(
            group["returns_seen"] >= 50,
            np.sqrt(group["rv_var"].clip(lower=0.0) * ANNUALIZATION),
            np.nan,
        )
        pieces.append(group[["day", "timestamp", "rv_forecast"]])
    rv = pd.concat(pieces, ignore_index=True)
    return frame.merge(rv, on=["day", "timestamp"], how="left")


def add_target(frame: pd.DataFrame, horizon: int) -> pd.DataFrame:
    out = frame.sort_values(["day", "product", "timestamp"]).copy()
    out["future_option_mid"] = out.groupby(["day", "product"])["option_mid"].shift(-horizon)
    out["future_spot_mid"] = out.groupby(["day", "product"])["spot_mid"].shift(-horizon)
    out["target"] = (
        out["future_option_mid"]
        - out["best_ask"]
        - out["delta"] * (out["future_spot_mid"] - out["spot_mid"])
    )
    return out


def feature_frame(base_frame: pd.DataFrame, spec: VariantSpec) -> pd.DataFrame:
    frame = add_target(add_rv_feature(base_frame, spec.rv_alpha), spec.horizon)
    frame["bias"] = 1.0
    frame["rv_edge"] = frame["rv_forecast"] - frame["ask_iv"]
    frame["anchor_edge"] = frame["iv_anchor"] - frame["ask_iv"]
    frame["iv_skew"] = frame["mid_iv"] - frame["iv_anchor"]
    frame["abs_moneyness"] = frame["moneyness"].abs()
    frame["gamma_notional"] = frame["gamma"] * frame["spot_mid"] * frame["spot_mid"]
    return frame.replace([np.inf, -np.inf], np.nan)


def clean_training_rows(frame: pd.DataFrame, spec: VariantSpec, days: tuple[int, ...]) -> pd.DataFrame:
    mask = (
        frame["day"].isin(days)
        & frame["target"].notna()
        & frame["rv_forecast"].notna()
        & (frame["abs_moneyness"] <= spec.moneyness_limit)
        & (frame["ask_volume"] > 0)
    )
    rows = frame.loc[mask, [*FEATURE_NAMES, "target", "ask_volume", "day"]].dropna()
    return rows


def fit_model(frame: pd.DataFrame, spec: VariantSpec, days: tuple[int, ...]) -> FittedModel | None:
    rows = clean_training_rows(frame, spec, days)
    if len(rows) < 200:
        return None
    x = rows[list(FEATURE_NAMES)].to_numpy(dtype=float)
    y = rows["target"].to_numpy(dtype=float)
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    means[0] = 0.0
    scales[0] = 1.0
    scales = np.where(scales < 1e-9, 1.0, scales)
    xs = (x - means) / scales
    gram = xs.T @ xs + spec.ridge_lambda * np.eye(xs.shape[1])
    rhs = xs.T @ y
    try:
        weights = np.linalg.solve(gram, rhs)
    except np.linalg.LinAlgError:
        weights = np.linalg.lstsq(gram, rhs, rcond=None)[0]
    train_scores = xs @ weights
    threshold = max(float(np.quantile(train_scores, spec.threshold_quantile)), spec.min_score)
    return FittedModel(
        spec=spec,
        means=[float(value) for value in means],
        scales=[float(value) for value in scales],
        weights=[float(value) for value in weights],
        threshold=threshold,
        exit_threshold=max(0.0, threshold * 0.25),
    )


def score_frame(frame: pd.DataFrame, fitted: FittedModel) -> np.ndarray:
    x = frame[list(FEATURE_NAMES)].to_numpy(dtype=float)
    means = np.asarray(fitted.means, dtype=float)
    scales = np.asarray(fitted.scales, dtype=float)
    weights = np.asarray(fitted.weights, dtype=float)
    return ((x - means) / scales) @ weights


def evaluate_model(frame: pd.DataFrame, fitted: FittedModel, days: tuple[int, ...]) -> dict[str, object]:
    spec = fitted.spec
    rows = clean_training_rows(frame, spec, days)
    if rows.empty:
        return {
            "proxy_pnl": 0.0,
            "trade_count": 0,
            "unit_count": 0,
            "hit_rate": float("nan"),
            "avg_score": float("nan"),
        }
    scores = score_frame(rows, fitted)
    active = scores > fitted.threshold
    if not active.any():
        return {
            "proxy_pnl": 0.0,
            "trade_count": 0,
            "unit_count": 0,
            "hit_rate": float("nan"),
            "avg_score": float("nan"),
        }
    active_rows = rows.loc[active].copy()
    qty = np.minimum(spec.max_option_clip, active_rows["ask_volume"].to_numpy(dtype=int))
    target = active_rows["target"].to_numpy(dtype=float)
    return {
        "proxy_pnl": float(np.dot(target, qty)),
        "trade_count": int(len(active_rows)),
        "unit_count": int(qty.sum()),
        "hit_rate": float((target > 0.0).mean()),
        "avg_score": float(scores[active].mean()),
    }


def build_variants(args: argparse.Namespace) -> list[VariantSpec]:
    variants: list[VariantSpec] = []
    for values in product(
        args.rv_alpha,
        args.horizon,
        args.ridge_lambda,
        args.threshold_quantile,
        args.min_score,
        args.moneyness_limit,
        args.max_option_clip,
        args.max_long_option_position,
        args.delta_hedge_threshold,
        args.hedge_interval_ticks,
        args.max_hedge_clip,
    ):
        (
            rv_alpha,
            horizon,
            ridge_lambda,
            threshold_quantile,
            min_score,
            moneyness_limit,
            max_option_clip,
            max_long_option_position,
            delta_hedge_threshold,
            hedge_interval_ticks,
            max_hedge_clip,
        ) = values
        variant_id = (
            f"qpconv_a{fmt_param(rv_alpha)}"
            f"_h{horizon}"
            f"_l{fmt_param(ridge_lambda)}"
            f"_q{fmt_param(threshold_quantile)}"
            f"_s{fmt_param(min_score)}"
            f"_m{fmt_param(moneyness_limit)}"
            f"_clip{max_option_clip}"
            f"_pos{max_long_option_position}"
            f"_dh{delta_hedge_threshold}"
            f"_hi{hedge_interval_ticks}"
            f"_hc{max_hedge_clip}"
        )
        variants.append(
            VariantSpec(
                variant_id=variant_id,
                rv_alpha=float(rv_alpha),
                horizon=int(horizon),
                ridge_lambda=float(ridge_lambda),
                threshold_quantile=float(threshold_quantile),
                min_score=float(min_score),
                moneyness_limit=float(moneyness_limit),
                max_option_clip=int(max_option_clip),
                max_long_option_position=int(max_long_option_position),
                delta_hedge_threshold=int(delta_hedge_threshold),
                hedge_interval_ticks=int(hedge_interval_ticks),
                max_hedge_clip=int(max_hedge_clip),
            )
        )
    return variants


def python_screen(base_frame: pd.DataFrame, variants: list[VariantSpec]) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, FittedModel]]:
    summary_rows: list[dict[str, object]] = []
    walk_rows: list[dict[str, object]] = []
    fitted_all: dict[str, FittedModel] = {}
    feature_cache: dict[tuple[float, int], pd.DataFrame] = {}
    started = time.time()

    for index, spec in enumerate(variants, start=1):
        key = (spec.rv_alpha, spec.horizon)
        frame = feature_cache.get(key)
        if frame is None:
            frame = feature_frame(base_frame, spec)
            feature_cache[key] = frame

        fitted = fit_model(frame, spec, ROUND3_DAYS)
        if fitted is None:
            continue
        fitted_all[spec.variant_id] = fitted

        day_results = {}
        for day in ROUND3_DAYS:
            day_results[day] = evaluate_model(frame, fitted, (day,))
        pnls = [float(day_results[day]["proxy_pnl"]) for day in ROUND3_DAYS]
        hit_rates = [
            float(day_results[day]["hit_rate"])
            for day in ROUND3_DAYS
            if math.isfinite(float(day_results[day]["hit_rate"]))
        ]
        summary_rows.append(
            {
                "variant_id": spec.variant_id,
                "proxy_pnl": float(sum(pnls)),
                "day_0_proxy_pnl": pnls[0],
                "day_1_proxy_pnl": pnls[1],
                "day_2_proxy_pnl": pnls[2],
                "min_day_proxy_pnl": float(min(pnls)),
                "positive_days": int(sum(value > 0.0 for value in pnls)),
                "trade_count": int(sum(int(day_results[day]["trade_count"]) for day in ROUND3_DAYS)),
                "unit_count": int(sum(int(day_results[day]["unit_count"]) for day in ROUND3_DAYS)),
                "mean_hit_rate": float(sum(hit_rates) / len(hit_rates)) if hit_rates else float("nan"),
                "threshold": fitted.threshold,
                **spec.__dict__,
            }
        )

        for test_day in ROUND3_DAYS:
            train_days = tuple(day for day in ROUND3_DAYS if day != test_day)
            wf_fitted = fit_model(frame, spec, train_days)
            if wf_fitted is None:
                continue
            result = evaluate_model(frame, wf_fitted, (test_day,))
            walk_rows.append(
                {
                    "variant_id": spec.variant_id,
                    "test_day": test_day,
                    "train_days": ",".join(str(day) for day in train_days),
                    "test_proxy_pnl": result["proxy_pnl"],
                    "test_trade_count": result["trade_count"],
                    "test_hit_rate": result["hit_rate"],
                    "threshold": wf_fitted.threshold,
                    **spec.__dict__,
                }
            )

        if index % 10 == 0 or index == len(variants):
            print(f"[qp {index}/{len(variants)}] elapsed={time.time() - started:.1f}s", flush=True)

    summary_rows.sort(
        key=lambda row: (
            row["positive_days"],
            row["min_day_proxy_pnl"],
            row["proxy_pnl"],
            row["mean_hit_rate"],
        ),
        reverse=True,
    )
    return summary_rows, walk_rows, fitted_all


TRADER_TEMPLATE = r'''
import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    """Generated QP-conv long-gamma Velvetfruit stat-arb trader."""

    UNDERLYING = "VELVETFRUIT_EXTRACT"
    STRIKES = (5000, 5100, 5200, 5300, 5400, 5500)
    LIMITS: Dict[str, int] = {
        "VELVETFRUIT_EXTRACT": 200,
        "VEV_4000": 300,
        "VEV_4500": 300,
        "VEV_5000": 300,
        "VEV_5100": 300,
        "VEV_5200": 300,
        "VEV_5300": 300,
        "VEV_5400": 300,
        "VEV_5500": 300,
        "VEV_6000": 300,
        "VEV_6500": 300,
    }

    TTE_YEARS = 5.0 / 365.0
    OBSERVATIONS_PER_DAY = 10_000
    ANNUALIZATION = OBSERVATIONS_PER_DAY * 365.0
    MIN_IV = 0.01
    MAX_IV = 5.0

    RV_ALPHA = __RV_ALPHA__
    MONEYNESS_LIMIT = __MONEYNESS_LIMIT__
    MAX_OPTION_CLIP = __MAX_OPTION_CLIP__
    MAX_LONG_OPTION_POSITION = __MAX_LONG_OPTION_POSITION__
    DELTA_HEDGE_THRESHOLD = __DELTA_HEDGE_THRESHOLD__
    HEDGE_INTERVAL_TICKS = __HEDGE_INTERVAL_TICKS__
    MAX_HEDGE_CLIP = __MAX_HEDGE_CLIP__
    THRESHOLD = __THRESHOLD__
    EXIT_THRESHOLD = __EXIT_THRESHOLD__
    FEATURE_MEANS = __FEATURE_MEANS__
    FEATURE_SCALES = __FEATURE_SCALES__
    FEATURE_WEIGHTS = __FEATURE_WEIGHTS__
    KERNELS = __KERNELS__

    def run(self, state: TradingState):
        orders_by_product: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        data = self.load_state(state.traderData)

        underlying_depth = state.order_depths.get(self.UNDERLYING)
        spot = self.mid_price(underlying_depth)
        if spot is None:
            return orders_by_product, 0, self.dump_state(data)

        self.update_spot_state(data, spot)
        option_marks = self.option_marks(state.order_depths, spot)
        anchor = self.iv_anchor(option_marks)
        if anchor is None:
            return orders_by_product, 0, self.dump_state(data)
        self.update_anchor_state(data, anchor)

        rv = self.rv_forecast(data)
        if rv is not None:
            for mark in option_marks:
                if abs(mark["moneyness"]) > self.MONEYNESS_LIMIT:
                    continue
                product = mark["product"]
                depth = state.order_depths.get(product)
                if depth is None:
                    continue
                position = int(state.position.get(product, 0))
                score = self.score_mark(data, mark, rv, anchor)
                orders_by_product[product] = self.trade_option(depth, product, position, score)

            hedge_orders, hedged = self.hedge_delta(
                state=state,
                underlying_depth=underlying_depth,
                spot=spot,
                vol_for_delta=max(self.MIN_IV, anchor),
                last_hedge_timestamp=int(data.get("last_hedge_timestamp", -10**9)),
            )
            orders_by_product[self.UNDERLYING] = hedge_orders
            if hedged:
                data["last_hedge_timestamp"] = int(state.timestamp)

        return orders_by_product, 0, self.dump_state(data)

    @staticmethod
    def load_state(raw: str):
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def dump_state(data) -> str:
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def best_bid_ask(order_depth: Optional[OrderDepth]) -> Tuple[Optional[int], Optional[int]]:
        if order_depth is None:
            return None, None
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    @classmethod
    def mid_price(cls, order_depth: Optional[OrderDepth]) -> Optional[float]:
        best_bid, best_ask = cls.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None or best_bid >= best_ask:
            return None
        return 0.5 * (best_bid + best_ask)

    @staticmethod
    def normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def normal_pdf(x: float) -> float:
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    @classmethod
    def black_scholes_call(cls, spot: float, strike: float, volatility: float) -> float:
        if volatility <= 0.0:
            return max(spot - strike, 0.0)
        vol_sqrt_t = volatility * math.sqrt(cls.TTE_YEARS)
        if vol_sqrt_t <= 0.0:
            return max(spot - strike, 0.0)
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * cls.TTE_YEARS) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        return spot * cls.normal_cdf(d1) - strike * cls.normal_cdf(d2)

    @classmethod
    def black_scholes_delta(cls, spot: float, strike: float, volatility: float) -> float:
        volatility = max(cls.MIN_IV, volatility)
        vol_sqrt_t = volatility * math.sqrt(cls.TTE_YEARS)
        if vol_sqrt_t <= 0.0:
            return 1.0 if spot > strike else 0.0
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * cls.TTE_YEARS) / vol_sqrt_t
        return cls.normal_cdf(d1)

    @classmethod
    def black_scholes_vega(cls, spot: float, strike: float, volatility: float) -> float:
        volatility = max(cls.MIN_IV, volatility)
        vol_sqrt_t = volatility * math.sqrt(cls.TTE_YEARS)
        if spot <= 0.0 or strike <= 0.0 or vol_sqrt_t <= 0.0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * cls.TTE_YEARS) / vol_sqrt_t
        return spot * math.sqrt(cls.TTE_YEARS) * cls.normal_pdf(d1)

    @classmethod
    def black_scholes_gamma(cls, spot: float, strike: float, volatility: float) -> float:
        volatility = max(cls.MIN_IV, volatility)
        vol_sqrt_t = volatility * math.sqrt(cls.TTE_YEARS)
        if spot <= 0.0 or strike <= 0.0 or vol_sqrt_t <= 0.0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * cls.TTE_YEARS) / vol_sqrt_t
        return cls.normal_pdf(d1) / (spot * vol_sqrt_t)

    @classmethod
    def implied_volatility(cls, call_price: float, spot: float, strike: float) -> float:
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
        high = cls.MAX_IV
        while cls.black_scholes_call(spot, strike, high) < call_price and high < 20.0:
            high *= 2.0
        if high >= 20.0 and cls.black_scholes_call(spot, strike, high) < call_price:
            return float("nan")
        for _ in range(50):
            mid = 0.5 * (low + high)
            price = cls.black_scholes_call(spot, strike, mid)
            if abs(price - call_price) <= 1e-7:
                return mid
            if price < call_price:
                low = mid
            else:
                high = mid
        return 0.5 * (low + high)

    @classmethod
    def update_spot_state(cls, data, spot: float) -> None:
        previous_mid = data.get("previous_mid")
        log_return = 0.0
        if previous_mid is not None and previous_mid > 0.0 and spot > 0.0:
            log_return = math.log(spot / float(previous_mid))
            squared = log_return * log_return
            previous_var = data.get("rv_var")
            if previous_var is None:
                data["rv_var"] = squared
            else:
                data["rv_var"] = cls.RV_ALPHA * squared + (1.0 - cls.RV_ALPHA) * float(previous_var)
            data["returns_seen"] = int(data.get("returns_seen", 0)) + 1
        data["previous_mid"] = float(spot)
        returns = data.get("returns", [])
        returns.append(float(log_return))
        data["returns"] = returns[-32:]

    @classmethod
    def update_anchor_state(cls, data, anchor: float) -> None:
        anchors = data.get("anchors", [])
        anchors.append(float(anchor))
        data["anchors"] = anchors[-32:]

    @classmethod
    def rv_forecast(cls, data) -> Optional[float]:
        if int(data.get("returns_seen", 0)) < 50 or data.get("rv_var") is None:
            return None
        return math.sqrt(max(0.0, float(data["rv_var"])) * cls.ANNUALIZATION)

    @classmethod
    def moneyness(cls, spot: float, strike: float) -> float:
        return math.log(strike / spot) / math.sqrt(cls.TTE_YEARS)

    @classmethod
    def option_marks(cls, order_depths: Dict[str, OrderDepth], spot: float) -> List[dict]:
        marks = []
        for strike in cls.STRIKES:
            product = f"VEV_{strike}"
            depth = order_depths.get(product)
            best_bid, best_ask = cls.best_bid_ask(depth)
            if best_bid is None or best_ask is None or best_bid >= best_ask:
                continue
            bid_iv = cls.implied_volatility(float(best_bid), spot, float(strike))
            ask_iv = cls.implied_volatility(float(best_ask), spot, float(strike))
            mid_iv = cls.implied_volatility(0.5 * (best_bid + best_ask), spot, float(strike))
            if not math.isfinite(bid_iv) or not math.isfinite(ask_iv) or not math.isfinite(mid_iv):
                continue
            delta = cls.black_scholes_delta(spot, float(strike), mid_iv)
            gamma = cls.black_scholes_gamma(spot, float(strike), mid_iv)
            vega = cls.black_scholes_vega(spot, float(strike), mid_iv)
            marks.append(
                {
                    "product": product,
                    "strike": strike,
                    "best_bid": int(best_bid),
                    "best_ask": int(best_ask),
                    "bid_iv": bid_iv,
                    "ask_iv": ask_iv,
                    "mid_iv": mid_iv,
                    "delta": delta,
                    "gamma": gamma,
                    "vega": vega,
                    "moneyness": cls.moneyness(spot, float(strike)),
                    "spread": float(best_ask - best_bid),
                    "spot": spot,
                }
            )
        return marks

    @staticmethod
    def iv_anchor(option_marks: List[dict]) -> Optional[float]:
        vols = sorted(mark["mid_iv"] for mark in option_marks if mark["mid_iv"] > 0.0)
        if not vols:
            return None
        midpoint = len(vols) // 2
        if len(vols) % 2:
            return float(vols[midpoint])
        return 0.5 * (vols[midpoint - 1] + vols[midpoint])

    @classmethod
    def conv(cls, values, kernel_name: str) -> float:
        kernel = cls.KERNELS[kernel_name]
        out = 0.0
        for offset, weight in enumerate(kernel):
            index = len(values) - 1 - offset
            if index < 0:
                break
            out += float(values[index]) * float(weight)
        return out

    @classmethod
    def score_mark(cls, data, mark: dict, rv: float, anchor: float) -> float:
        returns = data.get("returns", [])
        anchors = data.get("anchors", [])
        features = [
            1.0,
            rv - mark["ask_iv"],
            anchor - mark["ask_iv"],
            mark["mid_iv"] - anchor,
            mark["moneyness"],
            abs(mark["moneyness"]),
            mark["delta"],
            mark["gamma"] * mark["spot"] * mark["spot"],
            mark["vega"],
            mark["spread"],
            cls.conv(returns, "ret_k3"),
            cls.conv(returns, "ret_k12"),
            cls.conv(returns, "ret_fast_slow"),
            cls.conv([abs(value) for value in returns], "absret_k12"),
            cls.conv(anchors, "anchor_k3"),
            cls.conv(anchors, "anchor_fast_slow"),
            cls.conv(anchors, "anchor_momo"),
        ]
        score = 0.0
        for value, mean, scale, weight in zip(features, cls.FEATURE_MEANS, cls.FEATURE_SCALES, cls.FEATURE_WEIGHTS):
            score += ((value - mean) / scale) * weight
        return float(score)

    @classmethod
    def buy_capacity(cls, product: str, position: int) -> int:
        return max(0, min(cls.LIMITS[product], cls.MAX_LONG_OPTION_POSITION) - position)

    @classmethod
    def trade_option(cls, depth: OrderDepth, product: str, position: int, score: float) -> List[Order]:
        orders = []
        if position > 0 and score < cls.EXIT_THRESHOLD and depth.buy_orders:
            best_bid = max(depth.buy_orders)
            qty = min(position, cls.MAX_OPTION_CLIP, max(0, int(depth.buy_orders[best_bid])))
            if qty > 0:
                orders.append(Order(product, int(best_bid), -int(qty)))
            return orders
        if score <= cls.THRESHOLD or not depth.sell_orders:
            return orders
        best_ask = min(depth.sell_orders)
        qty = min(cls.MAX_OPTION_CLIP, cls.buy_capacity(product, position), abs(int(depth.sell_orders[best_ask])))
        if qty > 0:
            orders.append(Order(product, int(best_ask), int(qty)))
        return orders

    @classmethod
    def option_delta_position(cls, state: TradingState, spot: float, vol_for_delta: float) -> float:
        total = 0.0
        for strike in cls.STRIKES:
            product = f"VEV_{strike}"
            position = int(state.position.get(product, 0))
            if position:
                total += position * cls.black_scholes_delta(spot, float(strike), vol_for_delta)
        return total

    @classmethod
    def hedge_delta(
        cls,
        *,
        state: TradingState,
        underlying_depth: OrderDepth,
        spot: float,
        vol_for_delta: float,
        last_hedge_timestamp: int,
    ) -> Tuple[List[Order], bool]:
        option_delta = cls.option_delta_position(state, spot, vol_for_delta)
        underlying_position = int(state.position.get(cls.UNDERLYING, 0))
        target_underlying = int(round(-option_delta))
        target_underlying = max(-cls.LIMITS[cls.UNDERLYING], min(cls.LIMITS[cls.UNDERLYING], target_underlying))
        adjustment = target_underlying - underlying_position
        if abs(adjustment) < cls.DELTA_HEDGE_THRESHOLD:
            return [], False
        if int(state.timestamp) - last_hedge_timestamp < cls.HEDGE_INTERVAL_TICKS:
            return [], False
        orders = []
        if adjustment > 0:
            remaining = min(adjustment, cls.MAX_HEDGE_CLIP, cls.LIMITS[cls.UNDERLYING] - underlying_position)
            for ask_price, ask_volume in sorted(underlying_depth.sell_orders.items()):
                if remaining <= 0:
                    break
                qty = min(remaining, abs(int(ask_volume)))
                if qty > 0:
                    orders.append(Order(cls.UNDERLYING, int(ask_price), int(qty)))
                    remaining -= qty
        elif adjustment < 0:
            remaining = min(-adjustment, cls.MAX_HEDGE_CLIP, cls.LIMITS[cls.UNDERLYING] + underlying_position)
            for bid_price, bid_volume in sorted(underlying_depth.buy_orders.items(), reverse=True):
                if remaining <= 0:
                    break
                qty = min(remaining, max(0, int(bid_volume)))
                if qty > 0:
                    orders.append(Order(cls.UNDERLYING, int(bid_price), -int(qty)))
                    remaining -= qty
        return orders, bool(orders)
'''


def trader_source(fitted: FittedModel) -> str:
    replacements = {
        "__RV_ALPHA__": repr(fitted.spec.rv_alpha),
        "__MONEYNESS_LIMIT__": repr(fitted.spec.moneyness_limit),
        "__MAX_OPTION_CLIP__": repr(fitted.spec.max_option_clip),
        "__MAX_LONG_OPTION_POSITION__": repr(fitted.spec.max_long_option_position),
        "__DELTA_HEDGE_THRESHOLD__": repr(fitted.spec.delta_hedge_threshold),
        "__HEDGE_INTERVAL_TICKS__": repr(fitted.spec.hedge_interval_ticks),
        "__MAX_HEDGE_CLIP__": repr(fitted.spec.max_hedge_clip),
        "__THRESHOLD__": repr(fitted.threshold),
        "__EXIT_THRESHOLD__": repr(fitted.exit_threshold),
        "__FEATURE_MEANS__": repr(fitted.means),
        "__FEATURE_SCALES__": repr(fitted.scales),
        "__FEATURE_WEIGHTS__": repr(fitted.weights),
        "__KERNELS__": repr({key: list(value) for key, value in KERNELS.items()}),
    }
    source = TRADER_TEMPLATE
    for key, value in replacements.items():
        source = source.replace(key, value)
    return source.strip() + "\n"


def write_generated_traders(fitted_models: list[FittedModel]) -> dict[str, Path]:
    GENERATED_TRADER_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for fitted in fitted_models:
        path = GENERATED_TRADER_DIR / f"{fitted.spec.variant_id}.py"
        path.write_text(trader_source(fitted), encoding="utf-8")
        paths[fitted.spec.variant_id] = path
    return paths


def python_library_dirs() -> list[str]:
    candidates: list[Path] = []
    for key in ("LIBDIR", "LIBPL"):
        value = sysconfig.get_config_var(key)
        if value:
            candidates.append(Path(str(value)))
    executable = Path(sys.executable).resolve()
    candidates.extend(
        [
            executable.parent.parent / "lib",
            Path("/Library/Frameworks/Python.framework/Versions/3.11/lib"),
            Path("/opt/anaconda3/lib"),
            Path("/opt/homebrew/opt/python@3.11/lib"),
            Path("/usr/local/opt/python@3.11/lib"),
        ]
    )
    out: list[str] = []
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if not (
            (candidate / "libpython3.11.dylib").exists()
            or (candidate / "libpython3.11.so").exists()
            or (candidate / "libpython3.11.a").exists()
        ):
            continue
        text = str(candidate)
        if text not in out:
            out.append(text)
    return out


def rust_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    library_dirs = python_library_dirs()
    for var_name in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
        existing = [part for part in env.get(var_name, "").split(os.pathsep) if part]
        merged = []
        for path in [*library_dirs, *existing]:
            if path not in merged:
                merged.append(path)
        if merged:
            env[var_name] = os.pathsep.join(merged)
    return env


def run_rust_backtester(trader_path: Path, run_id: str) -> subprocess.CompletedProcess[str]:
    if RUST_BINARY.exists():
        cmd = [
            str(RUST_BINARY),
            "--trader",
            str(trader_path.resolve()),
            "--dataset",
            str(ROUND3_DIR),
            "--run-id",
            run_id,
            "--output-root",
            str(RUST_RUN_DIR),
            "--artifact-mode",
            "none",
            "--products",
            "off",
        ]
        cwd = BACKTESTER_DIR
    else:
        cmd = [
            "cargo",
            "run",
            "--release",
            "--quiet",
            "--",
            "--trader",
            str(trader_path.resolve()),
            "--dataset",
            str(ROUND3_DIR),
            "--run-id",
            run_id,
            "--output-root",
            str(RUST_RUN_DIR),
            "--artifact-mode",
            "none",
            "--products",
            "off",
        ]
        cwd = BACKTESTER_DIR
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=rust_subprocess_env(),
    )


def parse_rust_summary(stdout: str) -> tuple[list[dict[str, object]], float | None]:
    rows: list[dict[str, object]] = []
    total: float | None = None
    for match in SUMMARY_ROW_RE.finditer(stdout):
        dataset = match.group("dataset")
        day_label = match.group("day")
        pnl = float(match.group("pnl"))
        if dataset == "TOTAL":
            total = pnl
            continue
        if day_label in ("all", "-"):
            continue
        rows.append(
            {
                "day": int(day_label),
                "tick_count": int(match.group("ticks")),
                "own_trade_count": int(match.group("own_trades")),
                "final_pnl_total": pnl,
            }
        )
    if total is None and rows:
        total = sum(float(row["final_pnl_total"]) for row in rows)
    return rows, total


def rust_verify(fitted_models: list[FittedModel]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    RUST_RUN_DIR.mkdir(parents=True, exist_ok=True)
    paths = write_generated_traders(fitted_models)
    day_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []
    for index, fitted in enumerate(fitted_models, start=1):
        spec = fitted.spec
        run_id = f"{spec.variant_id}-rust-{int(time.time() * 1000)}"
        result = run_rust_backtester(paths[spec.variant_id], run_id)
        parsed_rows, parsed_total = parse_rust_summary(result.stdout)
        run_rows.append(
            {
                "variant_id": spec.variant_id,
                "return_code": result.returncode,
                "rust_final_pnl_total": parsed_total,
                "stdout_tail": result.stdout[-2000:].replace("\n", "\\n"),
                "stderr_tail": result.stderr[-2000:].replace("\n", "\\n"),
                "threshold": fitted.threshold,
                "exit_threshold": fitted.exit_threshold,
                **spec.__dict__,
            }
        )
        for parsed in parsed_rows:
            day_rows.append(
                {
                    "variant_id": spec.variant_id,
                    "day": int(parsed["day"]),
                    "final_pnl_total": float(parsed["final_pnl_total"]),
                    "own_trade_count": int(parsed["own_trade_count"]),
                    "tick_count": int(parsed["tick_count"]),
                    "return_code": result.returncode,
                    "threshold": fitted.threshold,
                    "exit_threshold": fitted.exit_threshold,
                    **spec.__dict__,
                }
            )
        print(
            f"[rust {index}/{len(fitted_models)}] {spec.variant_id}: pnl={parsed_total} rc={result.returncode}",
            flush=True,
        )
    return day_rows, run_rows


def aggregate_rust(day_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in day_rows:
        grouped.setdefault(str(row["variant_id"]), []).append(row)
    rows: list[dict[str, object]] = []
    for variant_id, group in grouped.items():
        by_day = {int(row["day"]): float(row["final_pnl_total"]) for row in group}
        pnls = [by_day[day] for day in ROUND3_DAYS if day in by_day]
        if not pnls:
            continue
        first = group[0]
        rows.append(
            {
                "variant_id": variant_id,
                "final_pnl_total": float(sum(pnls)),
                "day_0_pnl": by_day.get(0),
                "day_1_pnl": by_day.get(1),
                "day_2_pnl": by_day.get(2),
                "min_day_pnl": float(min(pnls)),
                "positive_days": int(sum(value > 0.0 for value in pnls)),
                "own_trade_count": int(sum(int(row["own_trade_count"]) for row in group)),
                **{key: first[key] for key in first if key not in {"day", "final_pnl_total", "own_trade_count", "tick_count", "return_code"}},
            }
        )
    rows.sort(key=lambda row: (row["positive_days"], row["min_day_pnl"], row["final_pnl_total"]), reverse=True)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    out.add_argument("--rv-alpha", type=parse_float_list, default=parse_float_list("0.008,0.015,0.03"))
    out.add_argument("--horizon", type=parse_int_list, default=parse_int_list("50,100,200"))
    out.add_argument("--ridge-lambda", type=parse_float_list, default=parse_float_list("0.1,1,10"))
    out.add_argument("--threshold-quantile", type=parse_float_list, default=parse_float_list("0.94,0.97"))
    out.add_argument("--min-score", type=parse_float_list, default=parse_float_list("0"))
    out.add_argument("--moneyness-limit", type=parse_float_list, default=parse_float_list("1.0,1.25"))
    out.add_argument("--max-option-clip", type=parse_int_list, default=parse_int_list("4,8"))
    out.add_argument("--max-long-option-position", type=parse_int_list, default=parse_int_list("120"))
    out.add_argument("--delta-hedge-threshold", type=parse_int_list, default=parse_int_list("20"))
    out.add_argument("--hedge-interval-ticks", type=parse_int_list, default=parse_int_list("300"))
    out.add_argument("--max-hedge-clip", type=parse_int_list, default=parse_int_list("60"))
    out.add_argument("--max-rust-variants", type=int, default=6)
    out.add_argument("--skip-rust", action="store_true")
    out.add_argument("--keep-old-artifacts", action="store_true")
    return out


def main() -> None:
    args = parser().parse_args()
    variants = build_variants(args)
    if not args.keep_old_artifacts:
        for path in (GENERATED_TRADER_DIR, RUST_RUN_DIR):
            if path.exists():
                shutil.rmtree(path)

    print(f"Building QP-conv feature tape for {len(variants)} variants...", flush=True)
    base_frame = build_base_frame()
    summary_rows, walk_rows, fitted_all = python_screen(base_frame, variants)
    write_csv(OUT_DIR / "python_summary.csv", summary_rows)
    write_csv(OUT_DIR / "python_walk_forward.csv", walk_rows)

    selected_ids = [str(row["variant_id"]) for row in summary_rows[: args.max_rust_variants]]
    selected = [fitted_all[variant_id] for variant_id in selected_ids if variant_id in fitted_all]
    rust_day_rows: list[dict[str, object]] = []
    rust_run_rows: list[dict[str, object]] = []
    rust_summary: list[dict[str, object]] = []
    if selected and not args.skip_rust:
        print(f"Rust-verifying top {len(selected)} QP-conv variants...", flush=True)
        rust_day_rows, rust_run_rows = rust_verify(selected)
        rust_summary = aggregate_rust(rust_day_rows)
        write_csv(OUT_DIR / "rust_day_rows.csv", rust_day_rows)
        write_csv(OUT_DIR / "rust_runs.csv", rust_run_rows)
        write_csv(OUT_DIR / "rust_summary.csv", rust_summary)
    elif selected:
        write_generated_traders(selected)

    metadata = {
        "variant_count": len(variants),
        "feature_names": list(FEATURE_NAMES),
        "python_best": summary_rows[0] if summary_rows else None,
        "rust_best": rust_summary[0] if rust_summary else None,
        "outputs": {
            "python_summary": str(OUT_DIR / "python_summary.csv"),
            "python_walk_forward": str(OUT_DIR / "python_walk_forward.csv"),
            "rust_summary": str(OUT_DIR / "rust_summary.csv"),
            "rust_day_rows": str(OUT_DIR / "rust_day_rows.csv"),
            "rust_runs": str(OUT_DIR / "rust_runs.csv"),
            "generated_trader_dir": str(GENERATED_TRADER_DIR),
        },
    }
    write_json(OUT_DIR / "qp_conv_metadata.json", metadata)
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main()
