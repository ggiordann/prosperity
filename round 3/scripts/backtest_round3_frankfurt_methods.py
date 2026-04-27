from __future__ import annotations

import csv
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKTESTER_DIR = (REPO_ROOT / "prosperity_rust_backtester").resolve()
ROUND3_DATASET = (BACKTESTER_DIR / "datasets" / "round3").resolve()
ROUND3_DAYS = (0, 1, 2)


@dataclass(frozen=True)
class StrategySpec:
    name: str
    description: str
    mode: str
    take_edge: int = 1
    quote_edge: int = 1
    imbalance_threshold: float = 0.15
    max_quote_size: int = 5
    only_products: tuple[str, ...] = ()


STRATEGIES: tuple[StrategySpec, ...] = (
    StrategySpec(
        name="best_bid_ask_mid_quote",
        description="Quote around the visible best bid/ask and midpoint.",
        mode="best_bid_ask_mid",
    ),
    StrategySpec(
        name="wall_mid_reversion",
        description="Use wall_mid as the anchor and fade short-term deviations.",
        mode="wall_mid_reversion",
    ),
    StrategySpec(
        name="volume_imbalance",
        description="Trade only when top-of-book volume imbalance is strong.",
        mode="imbalance",
        imbalance_threshold=0.20,
    ),
    StrategySpec(
        name="microprice",
        description="Use the microprice edge from best bid/ask sizes.",
        mode="microprice",
        take_edge=0,
        quote_edge=0,
    ),
    StrategySpec(
        name="over_underbid",
        description="Improve the book by one tick where the spread allows it.",
        mode="over_underbid",
    ),
    StrategySpec(
        name="take_favorable_levels",
        description="Sweep visible liquidity when it is favorable versus fair value.",
        mode="take",
        take_edge=1,
    ),
    StrategySpec(
        name="hybrid_book_signal",
        description="Blend wall_mid, imbalance, and microprice into one signal.",
        mode="hybrid",
        imbalance_threshold=0.12,
        take_edge=1,
        quote_edge=1,
    ),
)


TRADER_TEMPLATE = """
from datamodel import Order, TradingState


class Trader:
    LIMITS = {limits}
    TARGET_PRODUCTS = {target_products}
    MODE = {mode!r}
    TAKE_EDGE = {take_edge}
    QUOTE_EDGE = {quote_edge}
    IMBALANCE_THRESHOLD = {imbalance_threshold}
    MAX_QUOTE_SIZE = {max_quote_size}

    def run(self, state: TradingState):
        orders_by_product = {{}}
        for product, order_depth in state.order_depths.items():
            if self.TARGET_PRODUCTS and product not in self.TARGET_PRODUCTS:
                orders_by_product[product] = []
                continue
            orders_by_product[product] = self.trade_product(
                product,
                order_depth,
                int(state.position.get(product, 0)),
            )
        return orders_by_product, 0, ""

    def trade_product(self, product, order_depth, position):
        buy = order_depth.buy_orders
        sell = order_depth.sell_orders
        if not buy or not sell:
            return []

        best_bid = max(buy)
        best_ask = min(sell)
        if best_bid >= best_ask:
            return []

        bid_vol = float(sum(max(0, v) for v in buy.values()))
        ask_vol = float(sum(abs(v) for v in sell.values()))
        total_vol = bid_vol + ask_vol
        imbalance = (bid_vol - ask_vol) / total_vol if total_vol else 0.0
        mid = 0.5 * (best_bid + best_ask)
        wall_mid = self._wall_mid(buy, sell, mid)
        microprice = self._microprice(best_bid, buy[best_bid], best_ask, abs(sell[best_ask]), mid)

        fair = self._fair_value(
            mode=self.MODE,
            mid=mid,
            wall_mid=wall_mid,
            imbalance=imbalance,
            microprice=microprice,
        )

        orders = []
        limit = self.LIMITS.get(product, 0)
        buy_room = max(0, limit - position)
        sell_room = max(0, limit + position)

        if self.MODE in ("take", "hybrid"):
            for ask_price, ask_volume in sorted(sell.items()):
                if ask_price <= fair - self.TAKE_EDGE and buy_room > 0:
                    qty = min(abs(ask_volume), buy_room)
                    if qty > 0:
                        orders.append(Order(product, ask_price, qty))
                        buy_room -= qty
            for bid_price, bid_volume in sorted(buy.items(), reverse=True):
                if bid_price >= fair + self.TAKE_EDGE and sell_room > 0:
                    qty = min(bid_volume, sell_room)
                    if qty > 0:
                        orders.append(Order(product, bid_price, -qty))
                        sell_room -= qty

        if self.MODE in ("best_bid_ask_mid", "wall_mid_reversion", "microprice", "imbalance", "hybrid", "over_underbid"):
            bid_price, ask_price = self._quote_prices(best_bid, best_ask, fair)
            if buy_room > 0 and bid_price < best_ask:
                qty = min(self.MAX_QUOTE_SIZE, buy_room)
                orders.append(Order(product, bid_price, qty))
            if sell_room > 0 and ask_price > best_bid:
                qty = min(self.MAX_QUOTE_SIZE, sell_room)
                orders.append(Order(product, ask_price, -qty))

        return orders

    def _fair_value(self, mode, mid, wall_mid, imbalance, microprice):
        if mode == "best_bid_ask_mid":
            return mid
        if mode == "wall_mid_reversion":
            return wall_mid
        if mode == "microprice":
            return microprice
        if mode == "imbalance":
            return mid + (imbalance * self.QUOTE_EDGE)
        if mode == "over_underbid":
            return mid
        if mode == "take":
            return mid
        return 0.5 * (wall_mid + microprice) + imbalance * self.QUOTE_EDGE

    def _quote_prices(self, best_bid, best_ask, fair):
        if best_ask - best_bid > 1:
            bid_price = best_bid + 1
            ask_price = best_ask - 1
        else:
            bid_price = best_bid
            ask_price = best_ask

        if self.MODE == "wall_mid_reversion":
            bid_price = min(int(round(fair - self.QUOTE_EDGE)), best_ask - 1)
            ask_price = max(int(round(fair + self.QUOTE_EDGE)), best_bid + 1)
        elif self.MODE == "microprice":
            bid_price = min(best_ask - 1, int(round(fair - 1)))
            ask_price = max(best_bid + 1, int(round(fair + 1)))
        elif self.MODE == "imbalance":
            bias = 1 if fair > 0.5 * (best_bid + best_ask) else -1
            bid_price = min(best_ask - 1, best_bid + max(0, bias))
            ask_price = max(best_bid + 1, best_ask - max(0, -bias))
        elif self.MODE == "over_underbid":
            bid_price = min(best_ask - 1, best_bid + 1)
            ask_price = max(best_bid + 1, best_ask - 1)

        return int(bid_price), int(ask_price)

    @staticmethod
    def _wall_mid(buy, sell, fallback_mid):
        bid_wall = min(buy) if buy else None
        ask_wall = max(sell) if sell else None
        if bid_wall is None or ask_wall is None:
            return fallback_mid
        return 0.5 * (bid_wall + ask_wall)

    @staticmethod
    def _microprice(best_bid, bid_vol, best_ask, ask_vol, fallback_mid):
        total = bid_vol + ask_vol
        if total <= 0:
            return fallback_mid
        return (best_ask * bid_vol + best_bid * ask_vol) / total
"""


def build_trader_source(spec: StrategySpec) -> str:
    limits = {
        "HYDROGEL_PACK": 200,
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
    return dedent(
        TRADER_TEMPLATE.format(
            limits=json.dumps(limits, indent=4, sort_keys=True),
            target_products=json.dumps(list(spec.only_products)),
            mode=spec.mode,
            take_edge=spec.take_edge,
            quote_edge=spec.quote_edge,
            imbalance_threshold=spec.imbalance_threshold,
            max_quote_size=spec.max_quote_size,
        )
    ).strip() + "\n"


def run_backtester(trader_path: Path, day: int | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [
        "cargo",
        "run",
        "--release",
        "--",
        "--trader",
        str(trader_path.resolve()),
        "--dataset",
        str(ROUND3_DATASET),
    ]
    if day is not None:
        cmd.extend(["--day", str(day)])
    result = subprocess.run(
        cmd,
        cwd=BACKTESTER_DIR,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0 and not result.stderr:
        print(f"Warning: cargo exited with code {result.returncode}", flush=True)
    return result


def parse_total_pnl(stdout: str) -> float | None:
    matches = re.findall(r"^TOTAL\s+\-\s+\d+\s+\d+\s+(-?\d+(?:\.\d+)?)", stdout, re.MULTILINE)
    if matches:
        return float(matches[-1])
    matches = re.findall(r"final_pnl_total[^0-9-]*(-?\d+(?:\.\d+)?)", stdout)
    if matches:
        return float(matches[-1])
    return None


def main() -> None:
    print(f"REPO_ROOT: {REPO_ROOT}", flush=True)
    print(f"BACKTESTER_DIR: {BACKTESTER_DIR}", flush=True)
    print(f"ROUND3_DATASET: {ROUND3_DATASET}", flush=True)
    print(f"ROUND3_DATASET exists: {ROUND3_DATASET.exists()}", flush=True)
    print(f"BACKTESTER_DIR exists: {BACKTESTER_DIR.exists()}", flush=True)
    
    out_dir = REPO_ROOT / "round 3" / "analysis" / "round3_frankfurt_methods"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows = []
    walk_forward_rows = []

    with tempfile.TemporaryDirectory(prefix="frankfurt_methods_", dir=str(out_dir)) as tmp:
        tmp_dir = Path(tmp)
        for spec in STRATEGIES:
            trader_path = tmp_dir / f"{spec.name}.py"
            trader_path.write_text(build_trader_source(spec), encoding="utf-8")

            result = run_backtester(trader_path)
            pnl = parse_total_pnl(result.stdout)
            print(f"✓ {spec.name}: PnL={pnl}, return_code={result.returncode}", flush=True)
            if result.returncode != 0 and result.stderr:
                print(f"  stderr: {result.stderr[:200]}", flush=True)
            summary_rows.append(
                {
                    "strategy": spec.name,
                    "description": spec.description,
                    "mode": spec.mode,
                    "return_code": result.returncode,
                    "final_pnl_total": pnl,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )

            cumulative = 0.0
            for day in ROUND3_DAYS:
                day_result = run_backtester(trader_path, day=day)
                day_pnl = parse_total_pnl(day_result.stdout)
                walk_forward_rows.append(
                    {
                        "strategy": spec.name,
                        "day": day,
                        "return_code": day_result.returncode,
                        "final_pnl_total": day_pnl,
                    }
                )
                if day_pnl is not None:
                    cumulative += day_pnl
                walk_forward_rows[-1]["cumulative_pnl"] = cumulative

    summary_path = out_dir / "round3_frankfurt_methods_summary.json"
    csv_path = out_dir / "round3_frankfurt_methods_summary.csv"
    walk_forward_json_path = out_dir / "round3_frankfurt_methods_walk_forward.json"
    walk_forward_csv_path = out_dir / "round3_frankfurt_methods_walk_forward.csv"

    summary_path.write_text(json.dumps(summary_rows, indent=2), encoding="utf-8")
    walk_forward_json_path.write_text(json.dumps(walk_forward_rows, indent=2), encoding="utf-8")
    print(f"\n✓ Results saved to: {out_dir}", flush=True)
    print(f"  - {summary_path.name}", flush=True)
    print(f"  - {csv_path.name}", flush=True)
    print(f"  - {walk_forward_json_path.name}", flush=True)
    print(f"  - {walk_forward_csv_path.name}", flush=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "strategy",
                "description",
                "mode",
                "return_code",
                "final_pnl_total",
            ],
        )
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(
                {
                    "strategy": row["strategy"],
                    "description": row["description"],
                    "mode": row["mode"],
                    "return_code": row["return_code"],
                    "final_pnl_total": row["final_pnl_total"],
                }
            )

    with walk_forward_csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "strategy",
                "day",
                "return_code",
                "final_pnl_total",
                "cumulative_pnl",
            ],
        )
        writer.writeheader()
        for row in walk_forward_rows:
            writer.writerow(row)

    print(f"Wrote {summary_path}")
    print(f"Wrote {csv_path}")
    print(f"Wrote {walk_forward_json_path}")
    print(f"Wrote {walk_forward_csv_path}")


if __name__ == "__main__":
    main()
