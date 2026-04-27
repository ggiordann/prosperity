#!/usr/bin/env python3
"""Fine-tune the Round 3 HYDROGEL_PACK microprice strategy.

This is a finite, batch-style Rust-backtester sweep for HYDROGEL_PACK only.
It never trades VELVETFRUIT_EXTRACT, any VEV_* voucher, or the manual Bio-Pod
challenge.  The generated trader returns empty orders for every non-target
product and respects the HYDROGEL_PACK position limit of 200.

Fair value shape:

    fair_value = mid_price + k_micro * micro_edge - k_imbalance * imbalance

The script writes generated traders, runs each through the local Rust
backtester on prosperity_rust_backtester/datasets/round3, ranks by actual Rust
PnL first, and writes inspectable outputs to:

    analysis/round3_hydrogel_fine_tuning/

Typical run:

    python scripts/tune_round3_hydrogel_fine.py

Smaller smoke run:

    python scripts/tune_round3_hydrogel_fine.py \
        --k-micro 1.25 --k-imbalance 1.25 --thresholds 0 --max-order-clips 40
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


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKTESTER_DIR = (REPO_ROOT / "prosperity_rust_backtester").resolve()
ROUND3_DIR = (BACKTESTER_DIR / "datasets" / "round3").resolve()
OUT_DIR = (REPO_ROOT / "analysis" / "round3_hydrogel_fine_tuning").resolve()
GENERATED_TRADER_DIR = OUT_DIR / "generated_traders"
RUST_RUN_DIR = OUT_DIR / "rust_runs"

TARGET_PRODUCT = "HYDROGEL_PACK"
ROUND3_DAYS = (0, 1, 2)
POSITION_LIMIT = 200
PREVIOUS_COARSE_COMBINED_PNL = 8143.0


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    k_micro: float
    k_imbalance: float
    threshold: float
    max_order_clip: int
    passive_offset: int


TRADER_TEMPLATE = """
from datamodel import Order, TradingState


class Trader:
    TARGET_PRODUCT = "HYDROGEL_PACK"
    LIMIT = 200
    K_MICRO = {k_micro}
    K_IMBALANCE = {k_imbalance}
    THRESHOLD = {threshold}
    MAX_ORDER_CLIP = {max_order_clip}
    PASSIVE_OFFSET = {passive_offset}

    def run(self, state: TradingState):
        orders_by_product = {{product: [] for product in state.order_depths}}
        depth = state.order_depths.get(self.TARGET_PRODUCT)
        if depth is not None:
            orders_by_product[self.TARGET_PRODUCT] = self.trade_hydrogel(
                depth,
                int(state.position.get(self.TARGET_PRODUCT, 0)),
            )
        return orders_by_product, 0, ""

    def trade_hydrogel(self, order_depth, position):
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
        microprice = (
            (best_ask * bid_vol_1 + best_bid * ask_vol_1) / top_total
            if top_total > 0
            else mid
        )

        bid_vol_sum = sum(max(0, int(volume)) for volume in buys.values())
        ask_vol_sum = sum(abs(int(volume)) for volume in sells.values())
        total_vol = bid_vol_sum + ask_vol_sum
        imbalance = (bid_vol_sum - ask_vol_sum) / total_vol if total_vol else 0.0

        fair = mid + self.K_MICRO * (microprice - mid) - self.K_IMBALANCE * imbalance
        threshold = self.THRESHOLD
        orders = []

        buy_room = max(0, self.LIMIT - position)
        sell_room = max(0, self.LIMIT + position)

        for ask_price, ask_volume in sorted(sells.items()):
            if buy_room <= 0:
                break
            available = abs(int(ask_volume))
            if available <= 0 or ask_price > fair - threshold:
                continue
            qty = min(available, buy_room, self.MAX_ORDER_CLIP)
            if qty > 0:
                orders.append(Order(self.TARGET_PRODUCT, int(ask_price), int(qty)))
                buy_room -= qty

        for bid_price, bid_volume in sorted(buys.items(), reverse=True):
            if sell_room <= 0:
                break
            available = max(0, int(bid_volume))
            if available <= 0 or bid_price < fair + threshold:
                continue
            qty = min(available, sell_room, self.MAX_ORDER_CLIP)
            if qty > 0:
                orders.append(Order(self.TARGET_PRODUCT, int(bid_price), -int(qty)))
                sell_room -= qty

        edge = fair - mid
        if edge > threshold and buy_room > 0:
            bid_price = self.passive_bid(best_bid, best_ask)
            if bid_price < best_ask:
                qty = min(self.MAX_ORDER_CLIP, buy_room)
                orders.append(Order(self.TARGET_PRODUCT, int(bid_price), int(qty)))
        elif edge < -threshold and sell_room > 0:
            ask_price = self.passive_ask(best_bid, best_ask)
            if ask_price > best_bid:
                qty = min(self.MAX_ORDER_CLIP, sell_room)
                orders.append(Order(self.TARGET_PRODUCT, int(ask_price), -int(qty)))

        return orders

    def passive_bid(self, best_bid, best_ask):
        if self.PASSIVE_OFFSET <= 0:
            return best_bid
        return min(best_ask - 1, best_bid + self.PASSIVE_OFFSET)

    def passive_ask(self, best_bid, best_ask):
        if self.PASSIVE_OFFSET <= 0:
            return best_ask
        return max(best_bid + 1, best_ask - self.PASSIVE_OFFSET)
"""


SUMMARY_ROW_RE = re.compile(
    r"^(?P<dataset>\S+)\s+"
    r"(?P<day>-?\d+|all|-)\s+"
    r"(?P<ticks>\d+)\s+"
    r"(?P<own_trades>\d+)\s+"
    r"(?P<pnl>-?\d+(?:\.\d+)?)\s+",
    re.MULTILINE,
)


def parse_float_list(raw: str) -> list[float]:
    values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one numeric value")
    return values


def parse_int_list(raw: str) -> list[int]:
    values = [int(part.strip()) for part in raw.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one integer value")
    return values


def fmt_param(value: float | int) -> str:
    sign = "m" if float(value) < 0 else ""
    text = f"{abs(float(value)):g}".replace(".", "p")
    return f"{sign}{text}"


def build_variants(
    k_micro_values: Iterable[float],
    k_imbalance_values: Iterable[float],
    threshold_values: Iterable[float],
    max_order_clips: Iterable[int],
    passive_offsets: Iterable[int],
) -> list[VariantSpec]:
    variants: list[VariantSpec] = []
    for k_micro, k_imbalance, threshold, max_order_clip, passive_offset in product(
        k_micro_values,
        k_imbalance_values,
        threshold_values,
        max_order_clips,
        passive_offsets,
    ):
        variant_id = (
            f"hydro_k{fmt_param(k_micro)}"
            f"_imb{fmt_param(k_imbalance)}"
            f"_thr{fmt_param(threshold)}"
            f"_clip{fmt_param(max_order_clip)}"
            f"_po{fmt_param(passive_offset)}"
        )
        variants.append(
            VariantSpec(
                variant_id=variant_id,
                k_micro=float(k_micro),
                k_imbalance=float(k_imbalance),
                threshold=float(threshold),
                max_order_clip=int(max_order_clip),
                passive_offset=int(passive_offset),
            )
        )
    return variants


def trader_source(spec: VariantSpec) -> str:
    return dedent(
        TRADER_TEMPLATE.format(
            k_micro=repr(spec.k_micro),
            k_imbalance=repr(spec.k_imbalance),
            threshold=repr(spec.threshold),
            max_order_clip=spec.max_order_clip,
            passive_offset=spec.passive_offset,
        )
    ).strip() + "\n"


def reset_output_dirs(keep_old_artifacts: bool) -> None:
    if keep_old_artifacts:
        return
    for path in (GENERATED_TRADER_DIR, RUST_RUN_DIR):
        if path.exists():
            shutil.rmtree(path)


def write_generated_traders(variants: list[VariantSpec]) -> dict[str, Path]:
    GENERATED_TRADER_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for spec in variants:
        path = GENERATED_TRADER_DIR / f"{spec.variant_id}.py"
        path.write_text(trader_source(spec), encoding="utf-8")
        paths[spec.variant_id] = path
    return paths


def rust_env() -> dict[str, str]:
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


def ensure_rust_binary(env: dict[str, str]) -> Path:
    binary = BACKTESTER_DIR / "target" / "release" / "rust_backtester"
    if binary.exists():
        return binary
    result = subprocess.run(
        ["cargo", "build", "--release", "--quiet"],
        cwd=BACKTESTER_DIR,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "cargo build failed\n\nSTDOUT:\n"
            + result.stdout[-4000:]
            + "\n\nSTDERR:\n"
            + result.stderr[-4000:]
        )
    return binary


def run_rust_variant(
    binary: Path,
    env: dict[str, str],
    spec: VariantSpec,
    trader_path: Path,
    keep_rust_artifacts: bool,
    artifact_mode: str,
    run_kind: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    run_id = f"{spec.variant_id}-{run_kind}-{int(time.time() * 1000)}"
    flat_dir = RUST_RUN_DIR / run_id
    cmd = [
        str(binary),
        "--trader",
        str(trader_path.resolve()),
        "--dataset",
        str(ROUND3_DIR),
        "--run-id",
        run_id,
        "--output-root",
        str(RUST_RUN_DIR),
        "--artifact-mode",
        artifact_mode,
        "--products",
        "off",
        "--flat",
    ]
    result = subprocess.run(
        cmd,
        cwd=BACKTESTER_DIR,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )

    run_row = {
        "variant_id": spec.variant_id,
        "k_micro": spec.k_micro,
        "k_imbalance": spec.k_imbalance,
        "threshold": spec.threshold,
        "max_order_clip": spec.max_order_clip,
        "passive_offset": spec.passive_offset,
        "return_code": result.returncode,
        "run_kind": run_kind,
        "artifact_mode": artifact_mode,
        "run_id": run_id,
        "flat_dir": str(flat_dir),
        "stdout_tail": result.stdout[-2000:].replace("\n", "\\n"),
        "stderr_tail": result.stderr[-2000:].replace("\n", "\\n"),
    }

    if result.returncode != 0:
        raise RuntimeError(
            f"Rust backtester failed for {spec.variant_id} with code {result.returncode}\n\n"
            + result.stderr[-4000:]
        )

    day_rows = parse_flat_artifacts(flat_dir, spec, collect_turnover=(artifact_mode == "full"))
    if len(day_rows) != len(ROUND3_DAYS):
        parsed_stdout = parse_stdout_summary(result.stdout, spec)
        if parsed_stdout:
            day_rows = parsed_stdout
        else:
            raise RuntimeError(f"Expected 3 day metrics for {spec.variant_id}, found {len(day_rows)}")

    run_row["rust_final_pnl_total"] = sum(float(row["final_pnl_total"]) for row in day_rows)
    run_row["own_trade_count"] = sum(int(row["own_trade_count"]) for row in day_rows)
    turnover_values = [row["turnover_units"] for row in day_rows if row["turnover_units"] is not None]
    notional_values = [row["notional_turnover"] for row in day_rows if row["notional_turnover"] is not None]
    run_row["turnover_units"] = sum(int(value) for value in turnover_values) if turnover_values else None
    run_row["notional_turnover"] = sum(float(value) for value in notional_values) if notional_values else None

    if not keep_rust_artifacts and flat_dir.exists():
        shutil.rmtree(flat_dir)

    return day_rows, run_row


def parse_flat_artifacts(flat_dir: Path, spec: VariantSpec, collect_turnover: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not flat_dir.exists():
        return rows
    for metrics_path in sorted(flat_dir.glob("*-metrics.json")):
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        day = int(metrics["day"])
        trades_path = metrics_path.with_name(metrics_path.name.replace("-metrics.json", "-trades.csv"))
        turnover_units, notional_turnover = (
            parse_turnover(trades_path) if collect_turnover else (None, None)
        )
        pnl_by_product = metrics.get("final_pnl_by_product", {})
        hydrogel_pnl = float(pnl_by_product.get(TARGET_PRODUCT, metrics["final_pnl_total"]))
        rows.append(
            {
                "variant_id": spec.variant_id,
                "day": day,
                "k_micro": spec.k_micro,
                "k_imbalance": spec.k_imbalance,
                "threshold": spec.threshold,
                "max_order_clip": spec.max_order_clip,
                "passive_offset": spec.passive_offset,
                "final_pnl_total": float(metrics["final_pnl_total"]),
                "hydrogel_pnl": hydrogel_pnl,
                "own_trade_count": int(metrics["own_trade_count"]),
                "turnover_units": turnover_units,
                "notional_turnover": notional_turnover,
                "tick_count": int(metrics["tick_count"]),
                "return_code": 0,
            }
        )
    rows.sort(key=lambda row: int(row["day"]))
    return rows


def parse_turnover(trades_path: Path) -> tuple[int, float]:
    if not trades_path.exists():
        return 0, 0.0
    units = 0
    notional = 0.0
    with trades_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter=";")
        for row in reader:
            if row.get("symbol") != TARGET_PRODUCT:
                continue
            qty = abs(int(float(row["quantity"])))
            price = float(row["price"])
            units += qty
            notional += qty * price
    return units, notional


def parse_stdout_summary(stdout: str, spec: VariantSpec) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for match in SUMMARY_ROW_RE.finditer(stdout):
        dataset = match.group("dataset")
        if dataset == "TOTAL":
            continue
        day_label = match.group("day")
        if day_label in ("all", "-"):
            continue
        rows.append(
            {
                "variant_id": spec.variant_id,
                "day": int(day_label),
                "k_micro": spec.k_micro,
                "k_imbalance": spec.k_imbalance,
                "threshold": spec.threshold,
                "max_order_clip": spec.max_order_clip,
                "passive_offset": spec.passive_offset,
                "final_pnl_total": float(match.group("pnl")),
                "hydrogel_pnl": float(match.group("pnl")),
                "own_trade_count": int(match.group("own_trades")),
                "turnover_units": None,
                "notional_turnover": None,
                "tick_count": int(match.group("ticks")),
                "return_code": 0,
            }
        )
    rows.sort(key=lambda row: int(row["day"]))
    return rows


def aggregate_summary(variants: list[VariantSpec], day_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    by_variant: dict[str, dict[int, dict[str, object]]] = {}
    for row in day_rows:
        by_variant.setdefault(str(row["variant_id"]), {})[int(row["day"])] = row

    rows: list[dict[str, object]] = []
    for spec in variants:
        day_map = by_variant.get(spec.variant_id, {})
        pnl_by_day = [float(day_map[day]["hydrogel_pnl"]) for day in ROUND3_DAYS if day in day_map]
        if not pnl_by_day:
            continue
        total_pnl = float(sum(pnl_by_day))
        mean_day_pnl = float(statistics.fmean(pnl_by_day))
        std_day_pnl = float(statistics.pstdev(pnl_by_day)) if len(pnl_by_day) > 1 else 0.0
        stability_score = mean_day_pnl / (std_day_pnl + 1e-9)
        trade_count = sum(int(day_map[day]["own_trade_count"]) for day in ROUND3_DAYS if day in day_map)
        turnover_values = [
            day_map[day]["turnover_units"]
            for day in ROUND3_DAYS
            if day in day_map and day_map[day]["turnover_units"] is not None
        ]
        notional_values = [
            day_map[day]["notional_turnover"]
            for day in ROUND3_DAYS
            if day in day_map and day_map[day]["notional_turnover"] is not None
        ]
        turnover_units = sum(int(value) for value in turnover_values) if turnover_values else None
        notional_turnover = sum(float(value) for value in notional_values) if notional_values else None
        rows.append(
            {
                "variant_id": spec.variant_id,
                "k_micro": spec.k_micro,
                "k_imbalance": spec.k_imbalance,
                "threshold": spec.threshold,
                "max_order_clip": spec.max_order_clip,
                "passive_offset": spec.passive_offset,
                "final_pnl_total": total_pnl,
                "day_0_pnl": float(day_map[0]["hydrogel_pnl"]) if 0 in day_map else None,
                "day_1_pnl": float(day_map[1]["hydrogel_pnl"]) if 1 in day_map else None,
                "day_2_pnl": float(day_map[2]["hydrogel_pnl"]) if 2 in day_map else None,
                "mean_day_pnl": mean_day_pnl,
                "std_day_pnl": std_day_pnl,
                "min_day_pnl": float(min(pnl_by_day)),
                "positive_days": sum(1 for value in pnl_by_day if value > 0),
                "stability_score": stability_score,
                "own_trade_count": trade_count,
                "turnover_units": turnover_units,
                "notional_turnover": notional_turnover,
                "turnover_units_per_trade": (
                    turnover_units / trade_count if turnover_units is not None and trade_count else None
                ),
                "turnover_collected": turnover_units is not None,
                "beats_previous_coarse_combined": total_pnl > PREVIOUS_COARSE_COMBINED_PNL,
            }
        )
    rows.sort(
        key=lambda row: (
            float(row["final_pnl_total"]),
            float(row["stability_score"]),
        ),
        reverse=True,
    )
    return rows


def walk_forward_selection(day_rows: list[dict[str, object]], variants: list[VariantSpec]) -> list[dict[str, object]]:
    by_variant_day: dict[str, dict[int, float]] = {}
    by_id = {spec.variant_id: spec for spec in variants}
    for row in day_rows:
        by_variant_day.setdefault(str(row["variant_id"]), {})[int(row["day"])] = float(row["hydrogel_pnl"])

    rows: list[dict[str, object]] = []
    for test_day in ROUND3_DAYS:
        train_days = [day for day in ROUND3_DAYS if day != test_day]
        candidates: list[tuple[float, str]] = []
        for variant_id, day_map in by_variant_day.items():
            if test_day in day_map and all(day in day_map for day in train_days):
                candidates.append((sum(day_map[day] for day in train_days), variant_id))
        if not candidates:
            continue
        candidates.sort(reverse=True)
        train_pnl, selected_id = candidates[0]
        selected = by_id[selected_id]
        test_pnl = by_variant_day[selected_id][test_day]
        all_test_values = [day_map[test_day] for day_map in by_variant_day.values() if test_day in day_map]
        rows.append(
            {
                "test_day": test_day,
                "train_days": ",".join(str(day) for day in train_days),
                "selected_variant_id": selected_id,
                "k_micro": selected.k_micro,
                "k_imbalance": selected.k_imbalance,
                "threshold": selected.threshold,
                "max_order_clip": selected.max_order_clip,
                "passive_offset": selected.passive_offset,
                "train_pnl": train_pnl,
                "test_pnl": test_pnl,
                "test_rank": 1 + sum(value > test_pnl for value in all_test_values),
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
        default=parse_float_list("1.0,1.1,1.2,1.25,1.3,1.4"),
        help="Comma-separated k_micro values.",
    )
    out.add_argument(
        "--k-imbalance",
        type=parse_float_list,
        default=parse_float_list("1.0,1.15,1.25,1.35,1.5"),
        help="Comma-separated k_imbalance values.",
    )
    out.add_argument(
        "--thresholds",
        type=parse_float_list,
        default=parse_float_list("0,0.1,0.2"),
        help="Comma-separated fair-value edge thresholds.",
    )
    out.add_argument(
        "--max-order-clips",
        type=parse_int_list,
        default=parse_int_list("20"),
        help="Comma-separated max clip sizes per order.",
    )
    out.add_argument(
        "--passive-offsets",
        type=parse_int_list,
        default=parse_int_list("0,1"),
        help="Comma-separated passive quote offsets from best bid/ask.",
    )
    out.add_argument(
        "--keep-old-artifacts",
        action="store_true",
        help="Do not clear generated_traders/ and rust_runs/ before writing this run.",
    )
    out.add_argument(
        "--keep-rust-artifacts",
        action="store_true",
        help="Keep per-variant full Rust artifact folders after turnover is parsed.",
    )
    out.add_argument(
        "--turnover-top-n",
        type=int,
        default=25,
        help="Rerun the top N PnL-ranked variants with full artifacts to collect exact turnover.",
    )
    return out


def main() -> int:
    args = parser().parse_args()
    start = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    variants = build_variants(
        args.k_micro,
        args.k_imbalance,
        args.thresholds,
        args.max_order_clips,
        args.passive_offsets,
    )
    reset_output_dirs(args.keep_old_artifacts)
    trader_paths = write_generated_traders(variants)
    RUST_RUN_DIR.mkdir(parents=True, exist_ok=True)

    env = rust_env()
    binary = ensure_rust_binary(env)

    per_day_rows: list[dict[str, object]] = []
    run_rows: list[dict[str, object]] = []

    print(f"Target product: {TARGET_PRODUCT}", flush=True)
    print(f"Variants: {len(variants)}", flush=True)
    print(f"Generated traders: {GENERATED_TRADER_DIR}", flush=True)
    print(f"Rust binary: {binary}", flush=True)

    for index, spec in enumerate(variants, start=1):
        day_rows, run_row = run_rust_variant(
            binary=binary,
            env=env,
            spec=spec,
            trader_path=trader_paths[spec.variant_id],
            keep_rust_artifacts=args.keep_rust_artifacts,
            artifact_mode="none",
            run_kind="rank",
        )
        per_day_rows.extend(day_rows)
        run_rows.append(run_row)
        print(
            f"[{index}/{len(variants)}] {spec.variant_id}: "
            f"pnl={run_row['rust_final_pnl_total']} "
            f"trades={run_row['own_trade_count']}",
            flush=True,
        )

    preliminary_summary = aggregate_summary(variants, per_day_rows)
    turnover_ids: set[str] = set()
    for row in preliminary_summary[: max(0, args.turnover_top_n)]:
        turnover_ids.add(str(row["variant_id"]))
    for spec in variants:
        if (
            spec.k_micro == 1.25
            and spec.k_imbalance == 1.25
            and spec.threshold == 0.0
            and spec.max_order_clip == 40
            and spec.passive_offset == 1
        ):
            turnover_ids.add(spec.variant_id)

    if turnover_ids:
        full_rows: list[dict[str, object]] = []
        turnover_specs = [spec for spec in variants if spec.variant_id in turnover_ids]
        print(f"Collecting exact turnover for top/baseline variants: {len(turnover_specs)}", flush=True)
        for index, spec in enumerate(turnover_specs, start=1):
            day_rows, run_row = run_rust_variant(
                binary=binary,
                env=env,
                spec=spec,
                trader_path=trader_paths[spec.variant_id],
                keep_rust_artifacts=args.keep_rust_artifacts,
                artifact_mode="full",
                run_kind="turnover",
            )
            full_rows.extend(day_rows)
            run_rows.append(run_row)
            print(
                f"[turnover {index}/{len(turnover_specs)}] {spec.variant_id}: "
                f"pnl={run_row['rust_final_pnl_total']} "
                f"turnover={run_row['turnover_units']}",
                flush=True,
            )
        per_day_rows = [row for row in per_day_rows if str(row["variant_id"]) not in turnover_ids]
        per_day_rows.extend(full_rows)
        per_day_rows.sort(key=lambda row: (str(row["variant_id"]), int(row["day"])))

    summary_rows = aggregate_summary(variants, per_day_rows)
    walk_rows = walk_forward_selection(per_day_rows, variants)
    best = summary_rows[0] if summary_rows else None
    coarse_baseline = next(
        (
            row
            for row in summary_rows
            if float(row["k_micro"]) == 1.25
            and float(row["k_imbalance"]) == 1.25
            and float(row["threshold"]) == 0.0
            and int(row["passive_offset"]) == 1
        ),
        None,
    )

    metadata = {
        "target_product": TARGET_PRODUCT,
        "ignored_products": "VELVETFRUIT_EXTRACT, all VEV_* vouchers, and every non-Hydrogel product",
        "manual_bio_pod_challenge": "not implemented or simulated",
        "round3_position_limit": {TARGET_PRODUCT: POSITION_LIMIT},
        "inventory_carry_between_days": False,
        "end_of_round_liquidation": "handled by Rust backtester",
        "dataset": str(ROUND3_DIR),
        "output_dir": str(OUT_DIR),
        "generated_trader_dir": str(GENERATED_TRADER_DIR),
        "rust_binary": str(binary),
        "variant_count": len(variants),
        "k_micro": args.k_micro,
        "k_imbalance": args.k_imbalance,
        "thresholds": args.thresholds,
        "max_order_clips": args.max_order_clips,
        "passive_offsets": args.passive_offsets,
        "turnover_top_n": args.turnover_top_n,
        "turnover_note": "Exact turnover is collected for top-ranked variants and the coarse Hydrogel baseline; other rows retain trade counts and blank turnover fields.",
        "previous_coarse_combined_total_pnl": PREVIOUS_COARSE_COMBINED_PNL,
        "best_variant": best,
        "coarse_hydrogel_baseline_variant": coarse_baseline,
        "elapsed_seconds": time.time() - start,
        "files": [
            "summary.csv",
            "per_day.csv",
            "walk_forward.csv",
            "rust_runs.csv",
            "run_metadata.json",
        ],
    }

    write_csv(OUT_DIR / "summary.csv", summary_rows)
    write_csv(OUT_DIR / "per_day.csv", per_day_rows)
    write_csv(OUT_DIR / "walk_forward.csv", walk_rows)
    write_csv(OUT_DIR / "rust_runs.csv", run_rows)
    write_json(OUT_DIR / "run_metadata.json", metadata)

    print(f"Wrote results to {OUT_DIR}", flush=True)
    if best:
        print(
            "Best Hydrogel variant: "
            f"{best['variant_id']} pnl={best['final_pnl_total']} "
            f"days=({best['day_0_pnl']}, {best['day_1_pnl']}, {best['day_2_pnl']})",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
