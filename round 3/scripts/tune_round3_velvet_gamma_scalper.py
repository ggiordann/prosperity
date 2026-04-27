#!/usr/bin/env python3
"""Tune the no-lookahead Round 3 Velvetfruit gamma scalper.

The script uses a two-stage workflow:

1. A pure-Python event simulation screens a parameter grid across the RV alpha,
   RV/IV beta blend, optional forecast rho memory, vega-normalized price edge,
   gamma-sensitive hedge cadence, and hedge periodicity.  It preserves the
   no-lookahead contract: realized-volatility state is read before trading and
   updated after the tick's orders are evaluated.
2. The best Python-screened variants are written as standalone trader files and
   verified with the local Rust backtester.

Outputs are written under:

    analysis/round3_velvet_gamma_scalper/

Typical usage:

    python3 scripts/tune_round3_velvet_gamma_scalper.py
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import sysconfig
import time
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Iterable

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_TRADER_PATH = REPO_ROOT / "round 3" / "strategies" / "round3_velvet_gamma_scalper.py"
BACKTESTER_DIR = REPO_ROOT / "prosperity_rust_backtester"
RUST_BINARY = BACKTESTER_DIR / "target" / "release" / "rust_backtester"
ROUND3_DIR = BACKTESTER_DIR / "datasets" / "round3"
OUT_DIR = REPO_ROOT / "round 3" / "analysis" / "round3_velvet_gamma_scalper"
GENERATED_TRADER_DIR = OUT_DIR / "generated_traders"
RUST_RUN_DIR = OUT_DIR / "rust_runs"

UNDERLYING = "VELVETFRUIT_EXTRACT"
STRIKES = (5000, 5100, 5200, 5300, 5400, 5500)
ROUND3_DAYS = (0, 1, 2)
OBSERVATIONS_PER_DAY = 10_000
ANNUALIZATION = OBSERVATIONS_PER_DAY * 365.0
TTE_YEARS = 5.0 / 365.0
UNDERLYING_LIMIT = 200
MIN_IV = 0.01
MAX_IV = 5.0
PRICE_LEVELS = (1, 2, 3)


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    rv_alpha: float
    rv_weight: float
    forecast_rho: float
    min_vol_edge: float
    min_price_edge: float
    cost_buffer: float
    exit_vol_edge: float
    vega_clip_scale: float
    moneyness_limit: float
    max_option_clip: int
    max_long_option_position: int
    delta_hedge_threshold: int
    hedge_interval_ticks: int
    max_hedge_clip: int
    gamma_hedge_sensitivity: float
    gamma_hedge_min_threshold: int


@dataclass(frozen=True)
class OptionMark:
    product: str
    strike: int
    abs_moneyness: float
    best_bid: int
    best_ask: int
    bid_volume: int
    ask_volume: int
    bid_iv: float
    ask_iv: float
    mid_iv: float
    bid_vega: float
    ask_vega: float


@dataclass(frozen=True)
class TickEvent:
    day: int
    timestamp: int
    spot_mid: float
    underlying_bids: tuple[tuple[int, int], ...]
    underlying_asks: tuple[tuple[int, int], ...]
    option_marks: tuple[OptionMark, ...]


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


def build_variants(args: argparse.Namespace) -> list[VariantSpec]:
    variants: list[VariantSpec] = []
    for values in product(
        args.rv_alpha,
        args.rv_weight,
        args.forecast_rho,
        args.min_vol_edge,
        args.min_price_edge,
        args.cost_buffer,
        args.exit_vol_edge,
        args.vega_clip_scale,
        args.moneyness_limit,
        args.max_option_clip,
        args.max_long_option_position,
        args.delta_hedge_threshold,
        args.hedge_interval_ticks,
        args.max_hedge_clip,
        args.gamma_hedge_sensitivity,
        args.gamma_hedge_min_threshold,
    ):
        (
            rv_alpha,
            rv_weight,
            forecast_rho,
            min_vol_edge,
            min_price_edge,
            cost_buffer,
            exit_vol_edge,
            vega_clip_scale,
            moneyness_limit,
            max_option_clip,
            max_long_option_position,
            delta_hedge_threshold,
            hedge_interval_ticks,
            max_hedge_clip,
            gamma_hedge_sensitivity,
            gamma_hedge_min_threshold,
        ) = values
        variant_id = (
            f"gamma_a{fmt_param(rv_alpha)}"
            f"_w{fmt_param(rv_weight)}"
            f"_rho{fmt_param(forecast_rho)}"
            f"_e{fmt_param(min_vol_edge)}"
            f"_pe{fmt_param(min_price_edge)}"
            f"_c{fmt_param(cost_buffer)}"
            f"_vs{fmt_param(vega_clip_scale)}"
            f"_m{fmt_param(moneyness_limit)}"
            f"_clip{max_option_clip}"
            f"_pos{max_long_option_position}"
            f"_dh{delta_hedge_threshold}"
            f"_hi{hedge_interval_ticks}"
            f"_hc{max_hedge_clip}"
            f"_gh{fmt_param(gamma_hedge_sensitivity)}"
            f"_gm{gamma_hedge_min_threshold}"
        )
        variants.append(
            VariantSpec(
                variant_id=variant_id,
                rv_alpha=rv_alpha,
                rv_weight=rv_weight,
                forecast_rho=forecast_rho,
                min_vol_edge=min_vol_edge,
                min_price_edge=min_price_edge,
                cost_buffer=cost_buffer,
                exit_vol_edge=exit_vol_edge,
                vega_clip_scale=vega_clip_scale,
                moneyness_limit=moneyness_limit,
                max_option_clip=max_option_clip,
                max_long_option_position=max_long_option_position,
                delta_hedge_threshold=delta_hedge_threshold,
                hedge_interval_ticks=hedge_interval_ticks,
                max_hedge_clip=max_hedge_clip,
                gamma_hedge_sensitivity=gamma_hedge_sensitivity,
                gamma_hedge_min_threshold=gamma_hedge_min_threshold,
            )
        )
    return variants


def load_round3_prices() -> pd.DataFrame:
    frames = []
    needed = {UNDERLYING, *(f"VEV_{strike}" for strike in STRIKES)}
    for day in ROUND3_DAYS:
        path = ROUND3_DIR / f"prices_round_3_day_{day}.csv"
        frame = pd.read_csv(path, sep=";")
        frames.append(frame[frame["product"].isin(needed)].copy())
    prices = pd.concat(frames, ignore_index=True)
    prices = prices.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)
    for level in PRICE_LEVELS:
        for side in ("bid", "ask"):
            volume_col = f"{side}_volume_{level}"
            price_col = f"{side}_price_{level}"
            if volume_col not in prices:
                prices[volume_col] = 0
            if price_col not in prices:
                prices[price_col] = math.nan
            prices[volume_col] = prices[volume_col].fillna(0)
    return prices


def book_levels(row, side: str) -> tuple[tuple[int, int], ...]:
    levels: list[tuple[int, int]] = []
    for level in PRICE_LEVELS:
        price = getattr(row, f"{side}_price_{level}")
        volume = getattr(row, f"{side}_volume_{level}")
        if pd.isna(price):
            continue
        qty = abs(int(volume)) if side == "ask" else max(0, int(volume))
        if qty <= 0:
            continue
        levels.append((int(price), qty))
    if side == "bid":
        levels.sort(reverse=True)
    else:
        levels.sort()
    return tuple(levels)


def prepare_events(prices: pd.DataFrame, max_moneyness_limit: float) -> dict[int, list[TickEvent]]:
    by_day: dict[int, list[TickEvent]] = {}
    for day, day_frame in prices.groupby("day", sort=True):
        events: list[TickEvent] = []
        rows_by_timestamp = {
            int(timestamp): frame
            for timestamp, frame in day_frame.groupby("timestamp", sort=True)
        }
        for timestamp, frame in rows_by_timestamp.items():
            underlying = frame[frame["product"] == UNDERLYING]
            if underlying.empty:
                continue
            underlying_row = underlying.iloc[0]
            spot = float(underlying_row["mid_price"])
            if not math.isfinite(spot) or spot <= 0.0:
                continue

            option_marks: list[OptionMark] = []
            for strike in STRIKES:
                product = f"VEV_{strike}"
                option = frame[frame["product"] == product]
                if option.empty:
                    continue
                option_row = option.iloc[0]
                best_bid = option_row["bid_price_1"]
                best_ask = option_row["ask_price_1"]
                if pd.isna(best_bid) or pd.isna(best_ask) or float(best_bid) >= float(best_ask):
                    continue
                abs_moneyness = abs(math.log(strike / spot) / math.sqrt(TTE_YEARS))
                if abs_moneyness > max_moneyness_limit:
                    continue
                bid_iv = implied_volatility(float(best_bid), spot, float(strike))
                ask_iv = implied_volatility(float(best_ask), spot, float(strike))
                mid_iv = implied_volatility(0.5 * (float(best_bid) + float(best_ask)), spot, float(strike))
                if not math.isfinite(bid_iv) or not math.isfinite(ask_iv) or not math.isfinite(mid_iv):
                    continue
                bid_vega = black_scholes_vega(spot, float(strike), bid_iv)
                ask_vega = black_scholes_vega(spot, float(strike), ask_iv)
                option_marks.append(
                    OptionMark(
                        product=product,
                        strike=strike,
                        abs_moneyness=abs_moneyness,
                        best_bid=int(best_bid),
                        best_ask=int(best_ask),
                        bid_volume=max(0, int(option_row["bid_volume_1"])),
                        ask_volume=abs(int(option_row["ask_volume_1"])),
                        bid_iv=bid_iv,
                        ask_iv=ask_iv,
                        mid_iv=mid_iv,
                        bid_vega=bid_vega,
                        ask_vega=ask_vega,
                    )
                )

            events.append(
                TickEvent(
                    day=int(day),
                    timestamp=timestamp,
                    spot_mid=spot,
                    underlying_bids=book_levels(underlying_row, "bid"),
                    underlying_asks=book_levels(underlying_row, "ask"),
                    option_marks=tuple(option_marks),
                )
            )
        by_day[int(day)] = events
    return by_day


def median(values: Iterable[float]) -> float | None:
    sorted_values = sorted(value for value in values if value > 0.0 and math.isfinite(value))
    if not sorted_values:
        return None
    midpoint = len(sorted_values) // 2
    if len(sorted_values) % 2:
        return float(sorted_values[midpoint])
    return 0.5 * (sorted_values[midpoint - 1] + sorted_values[midpoint])


def rv_forecast(data: dict[str, float], spec: VariantSpec) -> float | None:
    if int(data.get("returns_seen", 0)) < 50 or "rv_var" not in data:
        return None
    return math.sqrt(max(0.0, float(data["rv_var"])) * ANNUALIZATION)


def smoothed_forecast(data: dict[str, float], raw_forecast_vol: float, spec: VariantSpec) -> float:
    previous = data.get("forecast_vol")
    forecast = raw_forecast_vol
    if (
        spec.forecast_rho > 0.0
        and previous is not None
        and math.isfinite(float(previous))
        and float(previous) > 0.0
    ):
        rho = max(0.0, min(0.99, spec.forecast_rho))
        forecast = rho * float(previous) + (1.0 - rho) * raw_forecast_vol
    data["forecast_vol"] = float(forecast)
    return float(forecast)


def update_rv_state(data: dict[str, float], spot: float, spec: VariantSpec) -> None:
    previous_mid = data.get("previous_mid")
    if previous_mid is not None and previous_mid > 0.0 and spot > 0.0:
        log_return = math.log(spot / previous_mid)
        squared_return = log_return * log_return
        previous_var = data.get("rv_var")
        if previous_var is None:
            data["rv_var"] = squared_return
        else:
            data["rv_var"] = spec.rv_alpha * squared_return + (1.0 - spec.rv_alpha) * previous_var
        data["returns_seen"] = int(data.get("returns_seen", 0)) + 1
    data["previous_mid"] = spot


def option_delta_position(positions: dict[str, int], spot: float, vol_for_delta: float) -> float:
    total = 0.0
    for strike in STRIKES:
        product_name = f"VEV_{strike}"
        position = positions.get(product_name, 0)
        if position:
            total += position * black_scholes_delta(spot, float(strike), vol_for_delta)
    return total


def option_abs_gamma_position(positions: dict[str, int], spot: float, vol_for_delta: float) -> float:
    total = 0.0
    for strike in STRIKES:
        product_name = f"VEV_{strike}"
        position = positions.get(product_name, 0)
        if position:
            total += abs(position) * black_scholes_gamma(spot, float(strike), vol_for_delta)
    return total


def dynamic_hedge_threshold(abs_gamma_position: float, spec: VariantSpec) -> int:
    threshold = spec.delta_hedge_threshold
    if spec.gamma_hedge_sensitivity > 0.0 and abs_gamma_position > 0.0:
        threshold = int(round(threshold / (1.0 + spec.gamma_hedge_sensitivity * abs_gamma_position)))
    return max(spec.gamma_hedge_min_threshold, threshold)


def simulate_day(events: list[TickEvent], spec: VariantSpec) -> dict[str, object]:
    data: dict[str, float] = {}
    cash_by_product = {UNDERLYING: 0.0, **{f"VEV_{strike}": 0.0 for strike in STRIKES}}
    positions = {UNDERLYING: 0, **{f"VEV_{strike}": 0 for strike in STRIKES}}
    trade_count = 0
    traded_qty = 0
    last_hedge_timestamp = -10**9
    last_prices = {UNDERLYING: 0.0, **{f"VEV_{strike}": 0.0 for strike in STRIKES}}

    for event in events:
        last_prices[UNDERLYING] = event.spot_mid
        for mark in event.option_marks:
            last_prices[mark.product] = 0.5 * (mark.best_bid + mark.best_ask)

        current_rv = rv_forecast(data, spec)
        marks = [mark for mark in event.option_marks if mark.abs_moneyness <= spec.moneyness_limit]
        iv_anchor = median(mark.mid_iv for mark in marks)

        option_orders: list[tuple[str, int, int]] = []
        hedge_orders: list[tuple[str, int, int]] = []
        if current_rv is not None and iv_anchor is not None:
            raw_forecast_vol = spec.rv_weight * current_rv + (1.0 - spec.rv_weight) * iv_anchor
            forecast_vol = smoothed_forecast(data, raw_forecast_vol, spec)
            for mark in marks:
                position = positions[mark.product]
                if position > 0 and forecast_vol - mark.bid_iv < spec.exit_vol_edge:
                    qty = min(position, spec.max_option_clip, mark.bid_volume)
                    if qty > 0:
                        option_orders.append((mark.product, mark.best_bid, -qty))
                    continue

                vol_edge = forecast_vol - mark.ask_iv
                long_edge = vol_edge - spec.cost_buffer
                price_edge = max(0.0, mark.ask_vega * vol_edge)
                if long_edge > spec.min_vol_edge and price_edge >= spec.min_price_edge:
                    room = max(0, min(300, spec.max_long_option_position) - position)
                    clip = spec.max_option_clip
                    if spec.vega_clip_scale > 0.0:
                        clip = min(clip, max(1, 1 + int(price_edge * spec.vega_clip_scale)))
                    qty = min(clip, room, mark.ask_volume)
                    if qty > 0:
                        option_orders.append((mark.product, mark.best_ask, qty))

            option_delta = option_delta_position(positions, event.spot_mid, max(MIN_IV, iv_anchor))
            abs_gamma_position = option_abs_gamma_position(positions, event.spot_mid, max(MIN_IV, iv_anchor))
            underlying_position = positions[UNDERLYING]
            target_underlying = int(round(-option_delta))
            target_underlying = max(-UNDERLYING_LIMIT, min(UNDERLYING_LIMIT, target_underlying))
            adjustment = target_underlying - underlying_position
            if (
                abs(adjustment) >= dynamic_hedge_threshold(abs_gamma_position, spec)
                and event.timestamp - last_hedge_timestamp >= spec.hedge_interval_ticks
            ):
                if adjustment > 0:
                    remaining = min(
                        adjustment,
                        spec.max_hedge_clip,
                        UNDERLYING_LIMIT - underlying_position,
                    )
                    for ask_price, ask_qty in event.underlying_asks:
                        if remaining <= 0:
                            break
                        qty = min(remaining, ask_qty)
                        if qty > 0:
                            hedge_orders.append((UNDERLYING, ask_price, qty))
                            remaining -= qty
                elif adjustment < 0:
                    remaining = min(
                        -adjustment,
                        spec.max_hedge_clip,
                        UNDERLYING_LIMIT + underlying_position,
                    )
                    for bid_price, bid_qty in event.underlying_bids:
                        if remaining <= 0:
                            break
                        qty = min(remaining, bid_qty)
                        if qty > 0:
                            hedge_orders.append((UNDERLYING, bid_price, -qty))
                            remaining -= qty
                if hedge_orders:
                    last_hedge_timestamp = event.timestamp

        for product_name, price, quantity in [*option_orders, *hedge_orders]:
            cash_by_product[product_name] -= price * quantity
            positions[product_name] += quantity
            trade_count += 1
            traded_qty += abs(quantity)

        update_rv_state(data, event.spot_mid, spec)

    pnl_by_product = {
        product_name: cash + positions[product_name] * last_prices[product_name]
        for product_name, cash in cash_by_product.items()
    }
    return {
        "final_pnl_total": float(sum(pnl_by_product.values())),
        "own_trade_count": trade_count,
        "traded_qty": traded_qty,
        "final_position_underlying": positions[UNDERLYING],
        "pnl_underlying": float(pnl_by_product[UNDERLYING]),
        "pnl_options": float(sum(value for key, value in pnl_by_product.items() if key != UNDERLYING)),
    }


def simulate_variants(events_by_day: dict[int, list[TickEvent]], variants: list[VariantSpec]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    started = time.time()
    for index, spec in enumerate(variants, start=1):
        for day in ROUND3_DAYS:
            result = simulate_day(events_by_day[day], spec)
            rows.append(
                {
                    "variant_id": spec.variant_id,
                    "day": day,
                    **spec.__dict__,
                    **result,
                }
            )
        if index % 50 == 0 or index == len(variants):
            elapsed = time.time() - started
            print(f"[python {index}/{len(variants)}] elapsed={elapsed:.1f}s", flush=True)
    return rows


def aggregate_summary(day_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in day_rows:
        grouped.setdefault(str(row["variant_id"]), []).append(row)

    rows: list[dict[str, object]] = []
    for variant_id, group in grouped.items():
        pnl_by_day = {int(row["day"]): float(row["final_pnl_total"]) for row in group}
        pnls = [pnl_by_day[day] for day in ROUND3_DAYS if day in pnl_by_day]
        if not pnls:
            continue
        first = group[0]
        mean = statistics.fmean(pnls)
        std = statistics.pstdev(pnls) if len(pnls) > 1 else 0.0
        rows.append(
            {
                "variant_id": variant_id,
                "final_pnl_total": float(sum(pnls)),
                "day_0_pnl": pnl_by_day.get(0),
                "day_1_pnl": pnl_by_day.get(1),
                "day_2_pnl": pnl_by_day.get(2),
                "mean_day_pnl": float(mean),
                "std_day_pnl": float(std),
                "min_day_pnl": float(min(pnls)),
                "positive_days": int(sum(value > 0 for value in pnls)),
                "stability_score": float(mean / (std + 1e-9)),
                "own_trade_count": int(sum(int(row["own_trade_count"]) for row in group)),
                "traded_qty": int(sum(int(row.get("traded_qty", 0) or 0) for row in group)),
                **{
                    key: first[key]
                    for key in (
                        "rv_alpha",
                        "rv_weight",
                        "forecast_rho",
                        "min_vol_edge",
                        "min_price_edge",
                        "cost_buffer",
                        "exit_vol_edge",
                        "vega_clip_scale",
                        "moneyness_limit",
                        "max_option_clip",
                        "max_long_option_position",
                        "delta_hedge_threshold",
                        "hedge_interval_ticks",
                        "max_hedge_clip",
                        "gamma_hedge_sensitivity",
                        "gamma_hedge_min_threshold",
                    )
                },
            }
        )
    rows.sort(
        key=lambda row: (
            row["positive_days"],
            row["min_day_pnl"],
            row["final_pnl_total"],
            row["stability_score"],
        ),
        reverse=True,
    )
    return rows


def walk_forward_rows(day_rows: list[dict[str, object]], variants_by_id: dict[str, VariantSpec]) -> list[dict[str, object]]:
    by_variant_day: dict[str, dict[int, float]] = {}
    for row in day_rows:
        by_variant_day.setdefault(str(row["variant_id"]), {})[int(row["day"])] = float(row["final_pnl_total"])

    rows: list[dict[str, object]] = []
    for test_day in ROUND3_DAYS:
        train_days = [day for day in ROUND3_DAYS if day != test_day]
        candidates = []
        for variant_id, day_map in by_variant_day.items():
            if all(day in day_map for day in train_days) and test_day in day_map:
                train_pnl = sum(day_map[day] for day in train_days)
                train_min = min(day_map[day] for day in train_days)
                candidates.append((train_min, train_pnl, variant_id))
        if not candidates:
            continue
        candidates.sort(reverse=True)
        train_min, train_pnl, selected_id = candidates[0]
        spec = variants_by_id[selected_id]
        test_pnl = by_variant_day[selected_id][test_day]
        all_test = [day_map[test_day] for day_map in by_variant_day.values() if test_day in day_map]
        rows.append(
            {
                "test_day": test_day,
                "train_days": ",".join(str(day) for day in train_days),
                "selected_variant_id": selected_id,
                "train_pnl": float(train_pnl),
                "train_min_day_pnl": float(train_min),
                "test_pnl": float(test_pnl),
                "test_rank": 1 + sum(value > test_pnl for value in all_test),
                "test_variant_count": len(all_test),
                **spec.__dict__,
            }
        )
    return rows


def replacement_map(spec: VariantSpec) -> dict[str, str]:
    return {
        "RV_ALPHA": repr(spec.rv_alpha),
        "RV_WEIGHT": repr(spec.rv_weight),
        "FORECAST_RHO": repr(spec.forecast_rho),
        "MIN_VOL_EDGE": repr(spec.min_vol_edge),
        "MIN_PRICE_EDGE": repr(spec.min_price_edge),
        "COST_BUFFER": repr(spec.cost_buffer),
        "EXIT_VOL_EDGE": repr(spec.exit_vol_edge),
        "VEGA_CLIP_SCALE": repr(spec.vega_clip_scale),
        "MONEYNESS_LIMIT": repr(spec.moneyness_limit),
        "MAX_OPTION_CLIP": repr(spec.max_option_clip),
        "MAX_LONG_OPTION_POSITION": repr(spec.max_long_option_position),
        "DELTA_HEDGE_THRESHOLD": repr(spec.delta_hedge_threshold),
        "HEDGE_INTERVAL_TICKS": repr(spec.hedge_interval_ticks),
        "MAX_HEDGE_CLIP": repr(spec.max_hedge_clip),
        "GAMMA_HEDGE_SENSITIVITY": repr(spec.gamma_hedge_sensitivity),
        "GAMMA_HEDGE_MIN_THRESHOLD": repr(spec.gamma_hedge_min_threshold),
    }


def trader_source_for(spec: VariantSpec) -> str:
    source = BASE_TRADER_PATH.read_text(encoding="utf-8")
    for name, value in replacement_map(spec).items():
        source = re.sub(rf"^    {name} = .*$", f"    {name} = {value}", source, flags=re.MULTILINE)
    return source


def write_generated_traders(selected: list[VariantSpec]) -> dict[str, Path]:
    GENERATED_TRADER_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for spec in selected:
        path = GENERATED_TRADER_DIR / f"{spec.variant_id}.py"
        path.write_text(trader_source_for(spec), encoding="utf-8")
        paths[spec.variant_id] = path
    return paths


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


def rust_verify(selected: list[VariantSpec]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    RUST_RUN_DIR.mkdir(parents=True, exist_ok=True)
    trader_paths = write_generated_traders(selected)
    day_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []
    for index, spec in enumerate(selected, start=1):
        run_id = f"{spec.variant_id}-rust-{int(time.time() * 1000)}"
        result = run_rust_backtester(trader_paths[spec.variant_id], run_id)
        parsed_rows, parsed_total = parse_rust_summary(result.stdout)
        run_rows.append(
            {
                "variant_id": spec.variant_id,
                "return_code": result.returncode,
                "rust_final_pnl_total": parsed_total,
                "stdout_tail": result.stdout[-2000:].replace("\n", "\\n"),
                "stderr_tail": result.stderr[-2000:].replace("\n", "\\n"),
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
                    **spec.__dict__,
                }
            )
        print(
            f"[rust {index}/{len(selected)}] {spec.variant_id}: "
            f"pnl={parsed_total} rc={result.returncode}",
            flush=True,
        )
    return day_rows, run_rows


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
    out.add_argument("--rv-weight", type=parse_float_list, default=parse_float_list("0.55,0.75,0.95"))
    out.add_argument("--forecast-rho", type=parse_float_list, default=parse_float_list("0"))
    out.add_argument("--min-vol-edge", type=parse_float_list, default=parse_float_list("0.015,0.035,0.055"))
    out.add_argument("--min-price-edge", type=parse_float_list, default=parse_float_list("0"))
    out.add_argument("--cost-buffer", type=parse_float_list, default=parse_float_list("0.01,0.02"))
    out.add_argument("--exit-vol-edge", type=parse_float_list, default=parse_float_list("0.005"))
    out.add_argument("--vega-clip-scale", type=parse_float_list, default=parse_float_list("0"))
    out.add_argument("--moneyness-limit", type=parse_float_list, default=parse_float_list("1.0,1.25"))
    out.add_argument("--max-option-clip", type=parse_int_list, default=parse_int_list("4,8"))
    out.add_argument("--max-long-option-position", type=parse_int_list, default=parse_int_list("120"))
    out.add_argument("--delta-hedge-threshold", type=parse_int_list, default=parse_int_list("20,35"))
    out.add_argument("--hedge-interval-ticks", type=parse_int_list, default=parse_int_list("300"))
    out.add_argument("--max-hedge-clip", type=parse_int_list, default=parse_int_list("60"))
    out.add_argument("--gamma-hedge-sensitivity", type=parse_float_list, default=parse_float_list("0"))
    out.add_argument("--gamma-hedge-min-threshold", type=parse_int_list, default=parse_int_list("8"))
    out.add_argument("--max-rust-variants", type=int, default=6)
    out.add_argument("--keep-old-artifacts", action="store_true")
    out.add_argument("--skip-rust", action="store_true")
    return out


def main() -> None:
    args = parser().parse_args()
    variants = build_variants(args)
    variants_by_id = {spec.variant_id: spec for spec in variants}
    if not args.keep_old_artifacts:
        for path in (GENERATED_TRADER_DIR, RUST_RUN_DIR):
            if path.exists():
                shutil.rmtree(path)

    print(f"Preparing event tape for {len(variants)} variants...", flush=True)
    prices = load_round3_prices()
    events_by_day = prepare_events(prices, max(args.moneyness_limit))
    print("Running Python screening simulation...", flush=True)
    python_day_rows = simulate_variants(events_by_day, variants)
    python_summary = aggregate_summary(python_day_rows)
    python_walk_forward = walk_forward_rows(python_day_rows, variants_by_id)

    write_csv(OUT_DIR / "python_day_rows.csv", python_day_rows)
    write_csv(OUT_DIR / "python_summary.csv", python_summary)
    write_csv(OUT_DIR / "python_walk_forward.csv", python_walk_forward)

    selected_ids = [row["variant_id"] for row in python_summary[: args.max_rust_variants]]
    selected = [variants_by_id[str(variant_id)] for variant_id in selected_ids]
    rust_day_rows: list[dict[str, object]] = []
    rust_run_rows: list[dict[str, object]] = []
    rust_summary: list[dict[str, object]] = []
    rust_walk_forward: list[dict[str, object]] = []
    if selected and not args.skip_rust:
        print(f"Rust-verifying top {len(selected)} screened variants...", flush=True)
        rust_day_rows, rust_run_rows = rust_verify(selected)
        rust_summary = aggregate_summary(rust_day_rows)
        rust_walk_forward = walk_forward_rows(rust_day_rows, {spec.variant_id: spec for spec in selected})
        write_csv(OUT_DIR / "rust_day_rows.csv", rust_day_rows)
        write_csv(OUT_DIR / "rust_runs.csv", rust_run_rows)
        write_csv(OUT_DIR / "rust_summary.csv", rust_summary)
        write_csv(OUT_DIR / "rust_walk_forward.csv", rust_walk_forward)

    metadata = {
        "variant_count": len(variants),
        "max_rust_variants": args.max_rust_variants,
        "python_best": python_summary[0] if python_summary else None,
        "rust_best": rust_summary[0] if rust_summary else None,
        "outputs": {
            "python_summary": str(OUT_DIR / "python_summary.csv"),
            "python_day_rows": str(OUT_DIR / "python_day_rows.csv"),
            "python_walk_forward": str(OUT_DIR / "python_walk_forward.csv"),
            "rust_summary": str(OUT_DIR / "rust_summary.csv"),
            "rust_day_rows": str(OUT_DIR / "rust_day_rows.csv"),
            "rust_runs": str(OUT_DIR / "rust_runs.csv"),
            "rust_walk_forward": str(OUT_DIR / "rust_walk_forward.csv"),
        },
    }
    write_json(OUT_DIR / "tuning_metadata.json", metadata)
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main()
