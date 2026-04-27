#!/usr/bin/env python3
"""Round 3 microprice fair-value strategy sweep.

This script tunes a small strategy family for only HYDROGEL_PACK and
VELVETFRUIT_EXTRACT.  The fair value under test is:

    fair_value = mid_price + k_micro * micro_edge - k_imbalance * imbalance

It generates inspectable Python trader variants, runs the same parameter grid
through the local Rust backtester when it is healthy, and always writes a
pure-Python fallback simulation plus signal hit-rate/correlation summaries.
The fallback is intentionally simpler than the Rust tape replay: it models
crossing visible top-of-book liquidity and marks inventory to the final mid.

Outputs are written under:

    analysis/round3_microprice_backtest/

Typical usage:

    python scripts/backtest_round3_microprice_fair_value.py

Fast fallback-only run:

    python scripts/backtest_round3_microprice_fair_value.py --engine fallback

Smaller Rust smoke sweep:

    python scripts/backtest_round3_microprice_fair_value.py \
        --k-micro 1.25,1.5,1.75 --k-imbalance 0.75,1.0,1.25 \
        --thresholds 0,0.25,0.5 --max-rust-variants 12
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
from textwrap import dedent
from typing import Iterable

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKTESTER_DIR = (REPO_ROOT / "prosperity_rust_backtester").resolve()
ROUND3_DIR = (BACKTESTER_DIR / "datasets" / "round3").resolve()
OUT_DIR = (REPO_ROOT / "round 3" / "analysis" / "round3_microprice_backtest").resolve()
GENERATED_TRADER_DIR = OUT_DIR / "generated_traders"
RUST_RUN_DIR = OUT_DIR / "rust_runs"

TARGET_PRODUCTS = ("HYDROGEL_PACK", "VELVETFRUIT_EXTRACT")
ROUND3_DAYS = (0, 1, 2)
PRICE_LEVELS = (1, 2, 3)
POSITION_LIMITS = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
}


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    k_micro: float
    k_imbalance: float
    threshold: float
    max_take_size: int = 40
    max_quote_size: int = 10


TRADER_TEMPLATE = """
from datamodel import Order, TradingState


class Trader:
    TARGET_PRODUCTS = {target_products}
    LIMITS = {limits}
    K_MICRO = {k_micro}
    K_IMBALANCE = {k_imbalance}
    THRESHOLD = {threshold}
    MAX_TAKE_SIZE = {max_take_size}
    MAX_QUOTE_SIZE = {max_quote_size}

    def run(self, state: TradingState):
        orders_by_product = {{product: [] for product in state.order_depths}}
        for product in self.TARGET_PRODUCTS:
            depth = state.order_depths.get(product)
            if depth is None:
                continue
            orders_by_product[product] = self.trade_product(
                product,
                depth,
                int(state.position.get(product, 0)),
            )
        return orders_by_product, 0, ""

    def trade_product(self, product, order_depth, position):
        buys = order_depth.buy_orders
        sells = order_depth.sell_orders
        if not buys or not sells:
            return []

        best_bid = max(buys)
        best_ask = min(sells)
        if best_bid >= best_ask:
            return []

        mid = 0.5 * (best_bid + best_ask)
        bid_vol_1 = max(0, int(buys.get(best_bid, 0)))
        ask_vol_1 = abs(int(sells.get(best_ask, 0)))
        top_total = bid_vol_1 + ask_vol_1
        if top_total > 0:
            microprice = (best_ask * bid_vol_1 + best_bid * ask_vol_1) / top_total
        else:
            microprice = mid

        bid_vol_sum = sum(max(0, int(volume)) for volume in buys.values())
        ask_vol_sum = sum(abs(int(volume)) for volume in sells.values())
        total_vol = bid_vol_sum + ask_vol_sum
        imbalance = (bid_vol_sum - ask_vol_sum) / total_vol if total_vol else 0.0

        micro_edge = microprice - mid
        fair = mid + self.K_MICRO * micro_edge - self.K_IMBALANCE * imbalance
        threshold = self.THRESHOLD
        orders = []

        limit = self.LIMITS[product]
        buy_room = max(0, limit - position)
        sell_room = max(0, limit + position)

        for ask_price, ask_volume in sorted(sells.items()):
            if buy_room <= 0:
                break
            ask_qty = abs(int(ask_volume))
            if ask_qty <= 0 or ask_price > fair - threshold:
                continue
            qty = min(ask_qty, buy_room, self.MAX_TAKE_SIZE)
            if qty > 0:
                orders.append(Order(product, int(ask_price), int(qty)))
                buy_room -= qty

        for bid_price, bid_volume in sorted(buys.items(), reverse=True):
            if sell_room <= 0:
                break
            bid_qty = max(0, int(bid_volume))
            if bid_qty <= 0 or bid_price < fair + threshold:
                continue
            qty = min(bid_qty, sell_room, self.MAX_TAKE_SIZE)
            if qty > 0:
                orders.append(Order(product, int(bid_price), -int(qty)))
                sell_room -= qty

        edge = fair - mid
        if edge > threshold and buy_room > 0:
            bid_price = self.directional_bid(best_bid, best_ask, fair, threshold)
            if bid_price < best_ask:
                orders.append(Order(product, int(bid_price), int(min(self.MAX_QUOTE_SIZE, buy_room))))
        elif edge < -threshold and sell_room > 0:
            ask_price = self.directional_ask(best_bid, best_ask, fair, threshold)
            if ask_price > best_bid:
                orders.append(Order(product, int(ask_price), -int(min(self.MAX_QUOTE_SIZE, sell_room))))

        return orders

    @staticmethod
    def directional_bid(best_bid, best_ask, fair, threshold):
        if best_ask - best_bid > 1:
            inside = best_bid + 1
        else:
            inside = best_bid
        fair_bid = int(math.floor(fair - threshold))
        return max(best_bid, min(best_ask - 1, max(inside, fair_bid)))

    @staticmethod
    def directional_ask(best_bid, best_ask, fair, threshold):
        if best_ask - best_bid > 1:
            inside = best_ask - 1
        else:
            inside = best_ask
        fair_ask = int(math.ceil(fair + threshold))
        return min(best_ask, max(best_bid + 1, min(inside, fair_ask)))
"""


def parse_float_list(raw: str) -> list[float]:
    values: list[float] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(float(part))
    if not values:
        raise argparse.ArgumentTypeError("expected at least one numeric value")
    return values


def fmt_param(value: float) -> str:
    sign = "m" if value < 0 else ""
    text = f"{abs(value):g}".replace(".", "p")
    return f"{sign}{text}"


def build_variants(
    k_micro_values: Iterable[float],
    k_imbalance_values: Iterable[float],
    threshold_values: Iterable[float],
) -> list[VariantSpec]:
    variants: list[VariantSpec] = []
    for k_micro, k_imbalance, threshold in product(k_micro_values, k_imbalance_values, threshold_values):
        variant_id = (
            f"micro_k{fmt_param(k_micro)}"
            f"_imb{fmt_param(k_imbalance)}"
            f"_thr{fmt_param(threshold)}"
        )
        variants.append(
            VariantSpec(
                variant_id=variant_id,
                k_micro=float(k_micro),
                k_imbalance=float(k_imbalance),
                threshold=float(threshold),
            )
        )
    return variants


def trader_source(spec: VariantSpec) -> str:
    source = TRADER_TEMPLATE.format(
        target_products=repr(list(TARGET_PRODUCTS)),
        limits=repr(POSITION_LIMITS),
        k_micro=repr(spec.k_micro),
        k_imbalance=repr(spec.k_imbalance),
        threshold=repr(spec.threshold),
        max_take_size=spec.max_take_size,
        max_quote_size=spec.max_quote_size,
    )
    return "import math\n" + dedent(source).strip() + "\n"


def write_generated_traders(variants: list[VariantSpec]) -> dict[str, Path]:
    GENERATED_TRADER_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for spec in variants:
        path = GENERATED_TRADER_DIR / f"{spec.variant_id}.py"
        path.write_text(trader_source(spec), encoding="utf-8")
        paths[spec.variant_id] = path
    return paths


def reset_generated_subdirs(keep_old_artifacts: bool) -> None:
    if keep_old_artifacts:
        return
    for path in (GENERATED_TRADER_DIR, RUST_RUN_DIR):
        if path.exists():
            shutil.rmtree(path)


def load_prices() -> pd.DataFrame:
    frames = []
    for day in ROUND3_DAYS:
        path = ROUND3_DIR / f"prices_round_3_day_{day}.csv"
        frames.append(pd.read_csv(path, sep=";"))
    prices = pd.concat(frames, ignore_index=True)
    prices = prices[prices["product"].isin(TARGET_PRODUCTS)].copy()
    prices = prices.sort_values(["day", "timestamp", "product"]).reset_index(drop=True)

    for level in PRICE_LEVELS:
        for side in ("bid", "ask"):
            price_col = f"{side}_price_{level}"
            volume_col = f"{side}_volume_{level}"
            if price_col not in prices:
                prices[price_col] = np.nan
            if volume_col not in prices:
                prices[volume_col] = 0
            prices[volume_col] = prices[volume_col].fillna(0)
    return prices


def enrich_prices(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    bid_volume_cols = [f"bid_volume_{level}" for level in PRICE_LEVELS]
    ask_volume_cols = [f"ask_volume_{level}" for level in PRICE_LEVELS]

    df["bid_vol_sum"] = df[bid_volume_cols].clip(lower=0).sum(axis=1)
    df["ask_vol_sum"] = df[ask_volume_cols].abs().sum(axis=1)
    total = (df["bid_vol_sum"] + df["ask_vol_sum"]).replace(0, np.nan)
    df["imbalance"] = ((df["bid_vol_sum"] - df["ask_vol_sum"]) / total).fillna(0.0)

    bid_top = df["bid_volume_1"].clip(lower=0)
    ask_top = df["ask_volume_1"].abs()
    top_total = (bid_top + ask_top).replace(0, np.nan)
    df["microprice"] = (
        df["ask_price_1"] * bid_top + df["bid_price_1"] * ask_top
    ) / top_total
    df["microprice"] = df["microprice"].fillna(df["mid_price"])
    df["micro_edge"] = df["microprice"] - df["mid_price"]

    grouped = df.groupby(["product", "day"], sort=False)
    df["mid_next"] = grouped["mid_price"].shift(-1)
    df["ret_next"] = df["mid_next"] - df["mid_price"]
    df["ret_next_pct"] = df["ret_next"] / df["mid_price"]
    return df


def corr(a: pd.Series, b: pd.Series) -> float:
    valid = a.notna() & b.notna()
    if valid.sum() < 3:
        return float("nan")
    left = a[valid]
    right = b[valid]
    if left.nunique() < 2 or right.nunique() < 2:
        return float("nan")
    return float(left.corr(right))


def sign_hit_rate(signal: pd.Series, future_return: pd.Series) -> float:
    valid = signal.notna() & future_return.notna() & (signal != 0)
    if valid.sum() == 0:
        return float("nan")
    signed = signal[valid] * future_return[valid]
    return float((signed > 0).mean())


def finite_or_none(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def signal_for_spec(df: pd.DataFrame, spec: VariantSpec) -> pd.Series:
    return spec.k_micro * df["micro_edge"].fillna(0.0) - spec.k_imbalance * df["imbalance"].fillna(0.0)


def metric_summary(prices: pd.DataFrame, variants: list[VariantSpec]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in variants:
        for product_name, product_df in prices.groupby("product", sort=True):
            signal = signal_for_spec(product_df, spec)
            triggered = signal.abs() >= spec.threshold
            rows.append(
                {
                    "variant_id": spec.variant_id,
                    "product": product_name,
                    "k_micro": spec.k_micro,
                    "k_imbalance": spec.k_imbalance,
                    "threshold": spec.threshold,
                    "n": int(product_df["ret_next"].notna().sum()),
                    "trigger_count": int((triggered & product_df["ret_next"].notna()).sum()),
                    "trigger_rate": finite_or_none(float(triggered.mean())),
                    "corr_signal_next_return": finite_or_none(corr(signal, product_df["ret_next"])),
                    "hit_rate_all": finite_or_none(sign_hit_rate(signal, product_df["ret_next"])),
                    "hit_rate_triggered": finite_or_none(
                        sign_hit_rate(signal.where(triggered, 0.0), product_df["ret_next"])
                    ),
                    "signal_x_return_proxy": finite_or_none(
                        float((signal.fillna(0.0) * product_df["ret_next"].fillna(0.0)).sum())
                    ),
                }
            )
    return rows


def buy_room(product_name: str, position: int) -> int:
    return max(0, POSITION_LIMITS[product_name] - position)


def sell_room(product_name: str, position: int) -> int:
    return max(0, POSITION_LIMITS[product_name] + position)


def fallback_day_product_pnl(df: pd.DataFrame, spec: VariantSpec, product_name: str) -> dict[str, object]:
    cash = 0.0
    position = 0
    trade_count = 0
    traded_qty = 0
    last_mid = float(df["mid_price"].iloc[-1]) if not df.empty else 0.0

    for row in df.itertuples(index=False):
        mid = float(row.mid_price)
        last_mid = mid
        signal = spec.k_micro * float(row.micro_edge) - spec.k_imbalance * float(row.imbalance)
        fair = mid + signal

        room = buy_room(product_name, position)
        for level in PRICE_LEVELS:
            if room <= 0:
                break
            ask_price = getattr(row, f"ask_price_{level}")
            ask_volume = abs(int(getattr(row, f"ask_volume_{level}")))
            if pd.isna(ask_price) or ask_volume <= 0:
                continue
            if float(ask_price) > fair - spec.threshold:
                continue
            qty = min(room, ask_volume, spec.max_take_size)
            if qty <= 0:
                continue
            cash -= float(ask_price) * qty
            position += qty
            room -= qty
            trade_count += 1
            traded_qty += qty

        room = sell_room(product_name, position)
        for level in PRICE_LEVELS:
            if room <= 0:
                break
            bid_price = getattr(row, f"bid_price_{level}")
            bid_volume = max(0, int(getattr(row, f"bid_volume_{level}")))
            if pd.isna(bid_price) or bid_volume <= 0:
                continue
            if float(bid_price) < fair + spec.threshold:
                continue
            qty = min(room, bid_volume, spec.max_take_size)
            if qty <= 0:
                continue
            cash += float(bid_price) * qty
            position -= qty
            room -= qty
            trade_count += 1
            traded_qty += qty

    pnl = cash + position * last_mid
    return {
        "variant_id": spec.variant_id,
        "product": product_name,
        "fallback_pnl": float(pnl),
        "fallback_trade_count": trade_count,
        "fallback_traded_qty": traded_qty,
        "fallback_final_position": position,
    }


def fallback_backtest(prices: pd.DataFrame, variants: list[VariantSpec]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    product_rows: list[dict[str, object]] = []
    day_rows: list[dict[str, object]] = []

    grouped = {
        (int(day), str(product_name)): frame.sort_values("timestamp").reset_index(drop=True)
        for (day, product_name), frame in prices.groupby(["day", "product"], sort=True)
    }
    for spec in variants:
        for day in ROUND3_DAYS:
            day_pnl = 0.0
            day_trades = 0
            day_qty = 0
            for product_name in TARGET_PRODUCTS:
                frame = grouped.get((day, product_name))
                if frame is None or frame.empty:
                    continue
                row = fallback_day_product_pnl(frame, spec, product_name)
                row.update(
                    {
                        "day": day,
                        "k_micro": spec.k_micro,
                        "k_imbalance": spec.k_imbalance,
                        "threshold": spec.threshold,
                    }
                )
                product_rows.append(row)
                day_pnl += float(row["fallback_pnl"])
                day_trades += int(row["fallback_trade_count"])
                day_qty += int(row["fallback_traded_qty"])
            day_rows.append(
                {
                    "variant_id": spec.variant_id,
                    "day": day,
                    "k_micro": spec.k_micro,
                    "k_imbalance": spec.k_imbalance,
                    "threshold": spec.threshold,
                    "engine": "fallback",
                    "final_pnl_total": day_pnl,
                    "own_trade_count": day_trades,
                    "traded_qty": day_qty,
                    "return_code": 0,
                }
            )
    return day_rows, product_rows


def run_rust_backtester(trader_path: Path, run_id: str) -> subprocess.CompletedProcess[str]:
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
    return subprocess.run(
        cmd,
        cwd=BACKTESTER_DIR,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=rust_subprocess_env(),
    )


def rust_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    library_dirs = python_library_dirs()
    if not library_dirs:
        return env
    for var_name in ("DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH"):
        existing = [part for part in env.get(var_name, "").split(os.pathsep) if part]
        merged = []
        for path in [*library_dirs, *existing]:
            if path not in merged:
                merged.append(path)
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


SUMMARY_ROW_RE = re.compile(
    r"^(?P<dataset>\S+)\s+"
    r"(?P<day>-?\d+|all|-)\s+"
    r"(?P<ticks>\d+)\s+"
    r"(?P<own_trades>\d+)\s+"
    r"(?P<pnl>-?\d+(?:\.\d+)?)\s+",
    re.MULTILINE,
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
            day = None
        else:
            day = int(day_label)
        rows.append(
            {
                "day": day,
                "tick_count": int(match.group("ticks")),
                "own_trade_count": int(match.group("own_trades")),
                "final_pnl_total": pnl,
            }
        )
    if total is None and rows:
        total = sum(float(row["final_pnl_total"]) for row in rows)
    return rows, total


def choose_rust_variants(
    variants: list[VariantSpec],
    fallback_day_rows: list[dict[str, object]],
    max_rust_variants: int,
) -> list[VariantSpec]:
    if max_rust_variants <= 0 or max_rust_variants >= len(variants):
        return variants
    fallback_totals: dict[str, float] = {}
    for row in fallback_day_rows:
        fallback_totals[row["variant_id"]] = fallback_totals.get(row["variant_id"], 0.0) + float(row["final_pnl_total"])
    by_id = {variant.variant_id: variant for variant in variants}
    ranked_ids = sorted(fallback_totals, key=lambda variant_id: fallback_totals[variant_id], reverse=True)
    selected = [by_id[variant_id] for variant_id in ranked_ids[:max_rust_variants]]
    center = min(
        variants,
        key=lambda spec: (
            abs(spec.k_micro - 1.5),
            abs(spec.k_imbalance - 1.0),
            abs(spec.threshold - 0.25),
        ),
    )
    if center.variant_id not in {spec.variant_id for spec in selected}:
        selected[-1] = center
    return selected


def rust_backtest(
    variants: list[VariantSpec],
    trader_paths: dict[str, Path],
    fallback_day_rows: list[dict[str, object]],
    max_rust_variants: int,
    engine: str,
) -> tuple[list[dict[str, object]], list[dict[str, object]], str | None]:
    if engine == "fallback":
        return [], [], None

    selected = choose_rust_variants(variants, fallback_day_rows, max_rust_variants)
    if not selected:
        return [], [], None

    RUST_RUN_DIR.mkdir(parents=True, exist_ok=True)
    rust_day_rows: list[dict[str, object]] = []
    rust_run_rows: list[dict[str, object]] = []
    failure_reason: str | None = None

    for index, spec in enumerate(selected, start=1):
        run_id = f"{spec.variant_id}-{int(time.time() * 1000)}"
        result = run_rust_backtester(trader_paths[spec.variant_id], run_id)
        parsed_rows, parsed_total = parse_rust_summary(result.stdout)
        run_row = {
            "variant_id": spec.variant_id,
            "k_micro": spec.k_micro,
            "k_imbalance": spec.k_imbalance,
            "threshold": spec.threshold,
            "return_code": result.returncode,
            "rust_final_pnl_total": parsed_total,
            "stdout_tail": result.stdout[-2000:].replace("\n", "\\n"),
            "stderr_tail": result.stderr[-2000:].replace("\n", "\\n"),
        }
        rust_run_rows.append(run_row)

        if result.returncode != 0 or not parsed_rows:
            message = (
                f"Rust backtester failed for {spec.variant_id} "
                f"(return_code={result.returncode})."
            )
            failure_reason = message + "\n\nSTDERR tail:\n" + result.stderr[-4000:]
            if engine == "auto" and index == 1:
                break
            continue

        for parsed in parsed_rows:
            if parsed["day"] is None:
                continue
            rust_day_rows.append(
                {
                    "variant_id": spec.variant_id,
                    "day": int(parsed["day"]),
                    "k_micro": spec.k_micro,
                    "k_imbalance": spec.k_imbalance,
                    "threshold": spec.threshold,
                    "engine": "rust",
                    "final_pnl_total": float(parsed["final_pnl_total"]),
                    "own_trade_count": int(parsed["own_trade_count"]),
                    "traded_qty": None,
                    "return_code": result.returncode,
                    "tick_count": int(parsed["tick_count"]),
                }
            )
        print(
            f"[rust {index}/{len(selected)}] {spec.variant_id}: "
            f"pnl={parsed_total} rc={result.returncode}",
            flush=True,
        )

    return rust_day_rows, rust_run_rows, failure_reason


def aggregate_summary(
    variants: list[VariantSpec],
    day_rows: list[dict[str, object]],
    metric_rows: list[dict[str, object]],
    engine_label: str,
) -> list[dict[str, object]]:
    metric_by_variant: dict[str, list[dict[str, object]]] = {}
    for row in metric_rows:
        metric_by_variant.setdefault(str(row["variant_id"]), []).append(row)

    days_by_variant: dict[str, dict[int, dict[str, object]]] = {}
    for row in day_rows:
        days_by_variant.setdefault(str(row["variant_id"]), {})[int(row["day"])] = row

    rows: list[dict[str, object]] = []
    for spec in variants:
        day_map = days_by_variant.get(spec.variant_id, {})
        pnl_by_day = [float(day_map[day]["final_pnl_total"]) for day in ROUND3_DAYS if day in day_map]
        if pnl_by_day:
            final_pnl = float(sum(pnl_by_day))
            mean = float(statistics.fmean(pnl_by_day))
            std = float(statistics.pstdev(pnl_by_day)) if len(pnl_by_day) > 1 else 0.0
            min_pnl = float(min(pnl_by_day))
            positive_days = int(sum(value > 0 for value in pnl_by_day))
            stability = mean / (std + 1e-9)
        else:
            final_pnl = float("nan")
            mean = float("nan")
            std = float("nan")
            min_pnl = float("nan")
            positive_days = 0
            stability = float("nan")

        metric_group = metric_by_variant.get(spec.variant_id, [])
        corr_values = [float(row["corr_signal_next_return"]) for row in metric_group if row["corr_signal_next_return"] is not None]
        hit_values = [float(row["hit_rate_triggered"]) for row in metric_group if row["hit_rate_triggered"] is not None]
        trigger_values = [float(row["trigger_rate"]) for row in metric_group if row["trigger_rate"] is not None]

        out = {
            "variant_id": spec.variant_id,
            "engine": engine_label,
            "k_micro": spec.k_micro,
            "k_imbalance": spec.k_imbalance,
            "threshold": spec.threshold,
            "final_pnl_total": finite_or_none(final_pnl),
            "day_0_pnl": finite_or_none(float(day_map[0]["final_pnl_total"])) if 0 in day_map else None,
            "day_1_pnl": finite_or_none(float(day_map[1]["final_pnl_total"])) if 1 in day_map else None,
            "day_2_pnl": finite_or_none(float(day_map[2]["final_pnl_total"])) if 2 in day_map else None,
            "mean_day_pnl": finite_or_none(mean),
            "std_day_pnl": finite_or_none(std),
            "min_day_pnl": finite_or_none(min_pnl),
            "positive_days": positive_days,
            "stability_score": finite_or_none(stability),
            "mean_corr_signal_next_return": finite_or_none(float(statistics.fmean(corr_values))) if corr_values else None,
            "mean_hit_rate_triggered": finite_or_none(float(statistics.fmean(hit_values))) if hit_values else None,
            "mean_trigger_rate": finite_or_none(float(statistics.fmean(trigger_values))) if trigger_values else None,
        }
        rows.append(out)
    rows.sort(
        key=lambda row: (
            float("-inf") if row["final_pnl_total"] is None else float(row["final_pnl_total"]),
            float("-inf") if row["stability_score"] is None else float(row["stability_score"]),
        ),
        reverse=True,
    )
    return rows


def walk_forward_selection(
    day_rows: list[dict[str, object]],
    variants: list[VariantSpec],
    engine_label: str,
) -> list[dict[str, object]]:
    by_variant_day: dict[str, dict[int, float]] = {}
    for row in day_rows:
        by_variant_day.setdefault(str(row["variant_id"]), {})[int(row["day"])] = float(row["final_pnl_total"])
    by_id = {spec.variant_id: spec for spec in variants}

    rows: list[dict[str, object]] = []
    for test_day in ROUND3_DAYS:
        train_days = [day for day in ROUND3_DAYS if day != test_day]
        candidates: list[tuple[float, str]] = []
        for variant_id, day_map in by_variant_day.items():
            if all(day in day_map for day in train_days) and test_day in day_map:
                train_pnl = sum(day_map[day] for day in train_days)
                candidates.append((train_pnl, variant_id))
        if not candidates:
            continue
        candidates.sort(reverse=True)
        train_pnl, selected_id = candidates[0]
        spec = by_id[selected_id]
        test_pnl = by_variant_day[selected_id][test_day]
        all_test_values = [
            day_map[test_day]
            for day_map in by_variant_day.values()
            if test_day in day_map
        ]
        test_rank = 1 + sum(value > test_pnl for value in all_test_values)
        rows.append(
            {
                "engine": engine_label,
                "test_day": test_day,
                "train_days": ",".join(str(day) for day in train_days),
                "selected_variant_id": selected_id,
                "k_micro": spec.k_micro,
                "k_imbalance": spec.k_imbalance,
                "threshold": spec.threshold,
                "train_pnl": train_pnl,
                "test_pnl": test_pnl,
                "test_rank": test_rank,
                "test_variant_count": len(all_test_values),
            }
        )
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
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    out = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    out.add_argument(
        "--k-micro",
        type=parse_float_list,
        default=parse_float_list("1.0,1.25,1.5,1.75,2.0"),
        help="Comma-separated k_micro values.",
    )
    out.add_argument(
        "--k-imbalance",
        type=parse_float_list,
        default=parse_float_list("0.5,0.75,1.0,1.25,1.5"),
        help="Comma-separated k_imbalance values.",
    )
    out.add_argument(
        "--thresholds",
        type=parse_float_list,
        default=parse_float_list("0,0.25,0.5,1.0"),
        help="Comma-separated trade threshold values.",
    )
    out.add_argument(
        "--engine",
        choices=("auto", "rust", "fallback"),
        default="auto",
        help="auto tries Rust and falls back if the first Rust run fails.",
    )
    out.add_argument(
        "--max-rust-variants",
        type=int,
        default=0,
        help="Limit Rust runs to top fallback variants. Use 0 for the full grid.",
    )
    out.add_argument(
        "--keep-old-artifacts",
        action="store_true",
        help="Do not clear generated_traders/ and rust_runs/ before writing this run.",
    )
    return out


def main() -> int:
    args = parser().parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    variants = build_variants(args.k_micro, args.k_imbalance, args.thresholds)
    reset_generated_subdirs(args.keep_old_artifacts)
    trader_paths = write_generated_traders(variants)
    prices = enrich_prices(load_prices())

    print(f"Target products: {', '.join(TARGET_PRODUCTS)}", flush=True)
    print(f"Variants: {len(variants)}", flush=True)
    print(f"Generated traders: {GENERATED_TRADER_DIR}", flush=True)

    fallback_day_rows, fallback_product_rows = fallback_backtest(prices, variants)
    metric_rows = metric_summary(prices, variants)
    fallback_summary_rows = aggregate_summary(variants, fallback_day_rows, metric_rows, "fallback")
    fallback_walk_rows = walk_forward_selection(fallback_day_rows, variants, "fallback")

    rust_day_rows: list[dict[str, object]] = []
    rust_run_rows: list[dict[str, object]] = []
    rust_failure: str | None = None
    if args.engine in ("auto", "rust"):
        rust_day_rows, rust_run_rows, rust_failure = rust_backtest(
            variants=variants,
            trader_paths=trader_paths,
            fallback_day_rows=fallback_day_rows,
            max_rust_variants=args.max_rust_variants,
            engine=args.engine,
        )

    rust_variant_ids = {str(row["variant_id"]) for row in rust_day_rows}
    rust_variants = [spec for spec in variants if spec.variant_id in rust_variant_ids]
    rust_summary_rows = aggregate_summary(rust_variants, rust_day_rows, metric_rows, "rust") if rust_variants else []
    rust_walk_rows = walk_forward_selection(rust_day_rows, rust_variants, "rust") if rust_variants else []

    primary_engine = "rust" if rust_summary_rows else "fallback"
    primary_summary_rows = rust_summary_rows if rust_summary_rows else fallback_summary_rows
    primary_day_rows = rust_day_rows if rust_summary_rows else fallback_day_rows
    primary_walk_rows = rust_walk_rows if rust_summary_rows else fallback_walk_rows

    write_csv(OUT_DIR / "fallback_per_day.csv", fallback_day_rows)
    write_csv(OUT_DIR / "fallback_per_product_day.csv", fallback_product_rows)
    write_csv(OUT_DIR / "fallback_summary.csv", fallback_summary_rows)
    write_csv(OUT_DIR / "metric_summary.csv", metric_rows)
    write_csv(OUT_DIR / "fallback_walk_forward.csv", fallback_walk_rows)
    write_json(OUT_DIR / "fallback_summary.json", fallback_summary_rows)
    write_json(OUT_DIR / "metric_summary.json", metric_rows)

    write_csv(OUT_DIR / "rust_runs.csv", rust_run_rows)
    write_csv(OUT_DIR / "rust_per_day.csv", rust_day_rows)
    write_csv(OUT_DIR / "rust_summary.csv", rust_summary_rows)
    write_csv(OUT_DIR / "rust_walk_forward.csv", rust_walk_rows)
    write_json(OUT_DIR / "rust_runs.json", rust_run_rows)
    write_json(OUT_DIR / "rust_summary.json", rust_summary_rows)

    write_csv(OUT_DIR / "primary_per_day.csv", primary_day_rows)
    write_csv(OUT_DIR / "primary_summary.csv", primary_summary_rows)
    write_csv(OUT_DIR / "primary_walk_forward.csv", primary_walk_rows)
    write_json(OUT_DIR / "primary_summary.json", primary_summary_rows)
    write_json(OUT_DIR / "primary_walk_forward.json", primary_walk_rows)

    run_summary = {
        "target_products": list(TARGET_PRODUCTS),
        "ignored_products": "all non-target products, including VEV_*",
        "variant_count": len(variants),
        "engine_requested": args.engine,
        "primary_engine": primary_engine,
        "k_micro": args.k_micro,
        "k_imbalance": args.k_imbalance,
        "thresholds": args.thresholds,
        "output_dir": str(OUT_DIR),
        "generated_trader_dir": str(GENERATED_TRADER_DIR),
        "rust_failure": rust_failure,
        "files": [
            "primary_summary.csv",
            "primary_per_day.csv",
            "primary_walk_forward.csv",
            "fallback_summary.csv",
            "fallback_per_day.csv",
            "fallback_per_product_day.csv",
            "metric_summary.csv",
            "rust_summary.csv",
            "rust_per_day.csv",
            "rust_runs.csv",
        ],
    }
    write_json(OUT_DIR / "run_summary.json", run_summary)
    if rust_failure:
        (OUT_DIR / "rust_failure.txt").write_text(rust_failure, encoding="utf-8")
    else:
        failure_path = OUT_DIR / "rust_failure.txt"
        if failure_path.exists():
            failure_path.unlink()

    best = primary_summary_rows[0] if primary_summary_rows else None
    print(f"Primary engine: {primary_engine}", flush=True)
    if best:
        print(
            "Best primary variant: "
            f"{best['variant_id']} pnl={best['final_pnl_total']} "
            f"days=({best['day_0_pnl']}, {best['day_1_pnl']}, {best['day_2_pnl']})",
            flush=True,
        )
    print(f"Wrote results to {OUT_DIR}", flush=True)
    if rust_failure and args.engine == "auto":
        print("Rust failed on the first attempted variant; fallback outputs are primary.", flush=True)
    elif rust_failure:
        print(f"Rust reported at least one failure; see {OUT_DIR / 'rust_failure.txt'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
