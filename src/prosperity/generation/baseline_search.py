from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from pathlib import Path

from prosperity.backtester.datasets import resolve_dataset_argument
from prosperity.backtester.runner import BacktesterRunner, BacktestRequest
from prosperity.paths import RepoPaths
from prosperity.settings import AppSettings, load_settings
from prosperity.utils import ensure_dir, json_dumps, slugify, utcnow_iso


@dataclass(frozen=True)
class BaselineVariant:
    name: str
    em_style: str
    em_quote_size: int
    em_anchor_half_spread: int
    tomato_filter_volume: int
    tomato_take_width: int
    tomato_take_max: int
    tomato_take_levels: int
    tomato_quote_style: str
    tomato_quote_width: int
    tomato_quote_size: int
    tomato_clear_width: int
    tomato_micro_weight: float
    tomato_momentum_weight: float
    tomato_imbalance_weight: float
    tomato_inventory_skew: float
    tomato_quote_skew_weight: float
    tomato_history_w0: float
    tomato_history_w2: float
    tomato_history_w4: float


@dataclass
class VariantResult:
    variant: BaselineVariant
    trader_path: Path
    submission_pnl: float
    tutorial_pnl: float | None = None
    tutorial_worst_day: float | None = None

    @property
    def composite_score(self) -> float:
        tutorial_bonus = 0.0 if self.tutorial_pnl is None else 0.15 * self.tutorial_pnl
        downside_penalty = 0.0 if self.tutorial_worst_day is None else min(0.0, self.tutorial_worst_day) * 0.35
        return self.submission_pnl + tutorial_bonus + downside_penalty


BASELINE_SUBMISSION_PNL = 2770.5


def _normalized_weights(w2: float, w4: float) -> tuple[float, float, float]:
    w0 = max(0.0, 1.0 - w2 - w4)
    total = w0 + w2 + w4
    if total <= 0:
        return 1.0, 0.0, 0.0
    return w0 / total, w2 / total, w4 / total


def _variant_code(variant: BaselineVariant) -> str:
    return f"""from __future__ import annotations

import json
from typing import Dict, List

from datamodel import Order, OrderDepth, TradingState


class Trader:
    LIMITS = {{"EMERALDS": 80, "TOMATOES": 80}}
    EM_STYLE = "{variant.em_style}"
    EM_QUOTE_SIZE = {variant.em_quote_size}
    EM_ANCHOR_HALF_SPREAD = {variant.em_anchor_half_spread}
    TOMATO_FILTER_VOLUME = {variant.tomato_filter_volume}
    TOMATO_TAKE_WIDTH = {variant.tomato_take_width}
    TOMATO_TAKE_MAX = {variant.tomato_take_max}
    TOMATO_TAKE_LEVELS = {variant.tomato_take_levels}
    TOMATO_QUOTE_STYLE = "{variant.tomato_quote_style}"
    TOMATO_QUOTE_WIDTH = {variant.tomato_quote_width}
    TOMATO_QUOTE_SIZE = {variant.tomato_quote_size}
    TOMATO_CLEAR_WIDTH = {variant.tomato_clear_width}
    TOMATO_MICRO_WEIGHT = {variant.tomato_micro_weight}
    TOMATO_MOMENTUM_WEIGHT = {variant.tomato_momentum_weight}
    TOMATO_IMBALANCE_WEIGHT = {variant.tomato_imbalance_weight}
    TOMATO_INVENTORY_SKEW = {variant.tomato_inventory_skew}
    TOMATO_QUOTE_SKEW_WEIGHT = {variant.tomato_quote_skew_weight}
    TOMATO_HISTORY_W0 = {variant.tomato_history_w0}
    TOMATO_HISTORY_W2 = {variant.tomato_history_w2}
    TOMATO_HISTORY_W4 = {variant.tomato_history_w4}
    TOMATO_HISTORY_LIMIT = 20

    def bid(self):
        return 15

    def run(self, state: TradingState):
        trader_state = self._load_state(state.traderData)
        result: Dict[str, List[Order]] = {{}}

        for product, order_depth in state.order_depths.items():
            if not order_depth.buy_orders or not order_depth.sell_orders:
                result[product] = []
                continue

            position = state.position.get(product, 0)
            if product == "EMERALDS":
                result[product] = self._trade_emeralds(order_depth, position)
            elif product == "TOMATOES":
                history = trader_state.get("tomato_fair_history", [])
                orders, history = self._trade_tomatoes(order_depth, position, history)
                trader_state["tomato_fair_history"] = history[-self.TOMATO_HISTORY_LIMIT :]
                result[product] = orders
            else:
                result[product] = []

        return result, 0, json.dumps(trader_state, separators=(",", ":"))

    def _trade_emeralds(self, order_depth: OrderDepth, position: int) -> List[Order]:
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        spread = best_ask - best_bid

        if self.EM_STYLE == "anchor":
            fair = 10000
            bid_price = min(best_ask - 1, max(best_bid + 1, fair - self.EM_ANCHOR_HALF_SPREAD))
            ask_price = max(best_bid + 1, min(best_ask - 1, fair + self.EM_ANCHOR_HALF_SPREAD))
        else:
            bid_price = best_bid + 1 if spread > 1 else best_bid
            ask_price = best_ask - 1 if spread > 1 else best_ask

        buy_size = min(self.EM_QUOTE_SIZE, max(0, self.LIMITS["EMERALDS"] - position))
        sell_size = min(self.EM_QUOTE_SIZE, max(0, self.LIMITS["EMERALDS"] + position))
        orders: List[Order] = []
        if buy_size > 0 and bid_price < best_ask:
            orders.append(Order("EMERALDS", bid_price, buy_size))
        if sell_size > 0 and ask_price > best_bid:
            orders.append(Order("EMERALDS", ask_price, -sell_size))
        return orders

    def _trade_tomatoes(self, order_depth: OrderDepth, position: int, history: List[float]):
        best_bid = max(order_depth.buy_orders)
        best_ask = min(order_depth.sell_orders)
        best_bid_volume = order_depth.buy_orders[best_bid]
        best_ask_volume = abs(order_depth.sell_orders[best_ask])
        total_volume = best_bid_volume + best_ask_volume
        microprice = (best_ask * best_bid_volume + best_bid * best_ask_volume) / total_volume if total_volume else 0.5 * (best_bid + best_ask)
        imbalance = (best_bid_volume - best_ask_volume) / total_volume if total_volume else 0.0

        filtered_asks = [
            price for price, volume in order_depth.sell_orders.items()
            if abs(volume) >= self.TOMATO_FILTER_VOLUME
        ]
        filtered_bids = [
            price for price, volume in order_depth.buy_orders.items()
            if volume >= self.TOMATO_FILTER_VOLUME
        ]
        mm_ask = min(filtered_asks) if filtered_asks else best_ask
        mm_bid = max(filtered_bids) if filtered_bids else best_bid
        fair = 0.5 * (mm_ask + mm_bid)
        fair = (1.0 - self.TOMATO_MICRO_WEIGHT) * fair + self.TOMATO_MICRO_WEIGHT * microprice

        last_fair = history[-1] if history else fair
        history.append(fair)
        if len(history) >= 4:
            fair = (
                self.TOMATO_HISTORY_W0 * fair
                + self.TOMATO_HISTORY_W2 * history[-2]
                + self.TOMATO_HISTORY_W4 * history[-4]
            )
        elif len(history) >= 2:
            base = self.TOMATO_HISTORY_W0 + self.TOMATO_HISTORY_W2
            if base > 0:
                fair = (self.TOMATO_HISTORY_W0 / base) * fair + (self.TOMATO_HISTORY_W2 / base) * history[-2]
        trend = fair - last_fair

        reservation = (
            fair
            + self.TOMATO_MOMENTUM_WEIGHT * trend
            + self.TOMATO_IMBALANCE_WEIGHT * imbalance
            - self.TOMATO_INVENTORY_SKEW * (position / self.LIMITS["TOMATOES"])
        )
        quote_anchor = reservation + self.TOMATO_QUOTE_SKEW_WEIGHT * trend

        orders: List[Order] = []
        buy_volume = 0
        sell_volume = 0

        asks = sorted(order_depth.sell_orders.items())
        bids = sorted(order_depth.buy_orders.items(), reverse=True)
        for price, volume in asks[: self.TOMATO_TAKE_LEVELS]:
            if price > reservation - self.TOMATO_TAKE_WIDTH:
                break
            quantity = min(abs(volume), self.TOMATO_TAKE_MAX - buy_volume, self.LIMITS["TOMATOES"] - position - buy_volume)
            if quantity > 0:
                orders.append(Order("TOMATOES", price, quantity))
                buy_volume += quantity

        for price, volume in bids[: self.TOMATO_TAKE_LEVELS]:
            if price < reservation + self.TOMATO_TAKE_WIDTH:
                break
            quantity = min(volume, self.TOMATO_TAKE_MAX - sell_volume, self.LIMITS["TOMATOES"] + position - sell_volume)
            if quantity > 0:
                orders.append(Order("TOMATOES", price, -quantity))
                sell_volume += quantity

        position_after_take = position + buy_volume - sell_volume
        fair_bid = round(reservation - self.TOMATO_CLEAR_WIDTH)
        fair_ask = round(reservation + self.TOMATO_CLEAR_WIDTH)

        if position_after_take > 0 and fair_ask in order_depth.buy_orders:
            quantity = min(order_depth.buy_orders[fair_ask], position_after_take, self.LIMITS["TOMATOES"] + position - sell_volume)
            if quantity > 0:
                orders.append(Order("TOMATOES", fair_ask, -quantity))
                sell_volume += quantity
                position_after_take -= quantity
        elif position_after_take < 0 and fair_bid in order_depth.sell_orders:
            quantity = min(abs(order_depth.sell_orders[fair_bid]), -position_after_take, self.LIMITS["TOMATOES"] - position - buy_volume)
            if quantity > 0:
                orders.append(Order("TOMATOES", fair_bid, quantity))
                buy_volume += quantity
                position_after_take += quantity

        buy_remaining = min(self.TOMATO_QUOTE_SIZE, self.LIMITS["TOMATOES"] - position - buy_volume)
        sell_remaining = min(self.TOMATO_QUOTE_SIZE, self.LIMITS["TOMATOES"] + position - sell_volume)

        if self.TOMATO_QUOTE_STYLE == "gap_join":
            ask_candidates = [price for price in order_depth.sell_orders if price > quote_anchor + self.TOMATO_QUOTE_WIDTH]
            bid_candidates = [price for price in order_depth.buy_orders if price < quote_anchor - self.TOMATO_QUOTE_WIDTH]
            ask_price = min(ask_candidates) - 1 if ask_candidates else int(round(quote_anchor + self.TOMATO_QUOTE_WIDTH + 1))
            bid_price = max(bid_candidates) + 1 if bid_candidates else int(round(quote_anchor - self.TOMATO_QUOTE_WIDTH - 1))
        else:
            bid_price = min(best_ask - 1, max(best_bid + 1, int(round(quote_anchor - self.TOMATO_QUOTE_WIDTH))))
            ask_price = max(best_bid + 1, min(best_ask - 1, int(round(quote_anchor + self.TOMATO_QUOTE_WIDTH))))

        if buy_remaining > 0 and bid_price < best_ask:
            orders.append(Order("TOMATOES", bid_price, buy_remaining))
        if sell_remaining > 0 and ask_price > best_bid:
            orders.append(Order("TOMATOES", ask_price, -sell_remaining))

        return orders, history

    @staticmethod
    def _load_state(trader_data: str):
        if not trader_data:
            return {{}}
        try:
            payload = json.loads(trader_data)
        except json.JSONDecodeError:
            return {{}}
        return payload if isinstance(payload, dict) else {{}}
"""


def _random_variant(index: int, rng: random.Random) -> BaselineVariant:
    history_w2 = rng.choice([0.15, 0.20, 0.25, 0.30, 0.35])
    history_w4 = rng.choice([0.0, 0.05, 0.10, 0.15])
    w0, w2, w4 = _normalized_weights(history_w2, history_w4)
    return BaselineVariant(
        name=f"baseline-search-{index:03d}",
        em_style=rng.choice(["baseline", "anchor"]),
        em_quote_size=rng.choice([3, 5, 7, 9]),
        em_anchor_half_spread=rng.choice([1, 2, 3]),
        tomato_filter_volume=rng.choice([8, 10, 12, 14, 16, 20]),
        tomato_take_width=rng.choice([0, 1, 2]),
        tomato_take_max=rng.choice([10, 20, 40, 80]),
        tomato_take_levels=rng.choice([1, 2, 3]),
        tomato_quote_style=rng.choice(["gap_join", "fixed"]),
        tomato_quote_width=rng.choice([1, 2, 3, 4]),
        tomato_quote_size=rng.choice([20, 40, 60, 80]),
        tomato_clear_width=rng.choice([0, 1]),
        tomato_micro_weight=rng.choice([0.0, 0.1, 0.2, 0.3]),
        tomato_momentum_weight=rng.choice([0.0, 0.2, 0.4, 0.6, 0.8]),
        tomato_imbalance_weight=rng.choice([0.0, 0.25, 0.5, 1.0]),
        tomato_inventory_skew=rng.choice([0.0, 0.5, 1.0, 2.0, 3.0]),
        tomato_quote_skew_weight=rng.choice([0.0, 0.25, 0.5, 0.75, 1.0]),
        tomato_history_w0=w0,
        tomato_history_w2=w2,
        tomato_history_w4=w4,
    )


def _baseline_like_variant() -> BaselineVariant:
    return BaselineVariant(
        name="baseline-control",
        em_style="baseline",
        em_quote_size=5,
        em_anchor_half_spread=1,
        tomato_filter_volume=12,
        tomato_take_width=1,
        tomato_take_max=80,
        tomato_take_levels=1,
        tomato_quote_style="gap_join",
        tomato_quote_width=1,
        tomato_quote_size=80,
        tomato_clear_width=0,
        tomato_micro_weight=0.0,
        tomato_momentum_weight=0.0,
        tomato_imbalance_weight=0.0,
        tomato_inventory_skew=0.0,
        tomato_quote_skew_weight=0.0,
        tomato_history_w0=0.6,
        tomato_history_w2=0.25,
        tomato_history_w4=0.15,
    )


def _run_variant(
    runner: BacktesterRunner,
    variant: BaselineVariant,
    strategy_dir: Path,
) -> VariantResult:
    strategy_path = strategy_dir / f"{slugify(variant.name)}.py"
    strategy_path.write_text(_variant_code(variant), encoding="utf-8")
    submission = runner.run(
        BacktestRequest(
            trader_path=str(strategy_path),
            dataset=resolve_dataset_argument("submission"),
            products_mode="summary",
        )
    )
    return VariantResult(
        variant=variant,
        trader_path=strategy_path,
        submission_pnl=submission.summary.total_final_pnl,
    )


def _evaluate_tutorial(runner: BacktesterRunner, result: VariantResult) -> VariantResult:
    tutorial = runner.run(
        BacktestRequest(
            trader_path=str(result.trader_path),
            dataset=resolve_dataset_argument("tutorial"),
            products_mode="summary",
        )
    )
    pnls = [row.final_pnl for row in tutorial.summary.day_results]
    result.tutorial_pnl = sum(pnls)
    result.tutorial_worst_day = min(pnls) if pnls else None
    return result


def search_baseline_variants(
    sample_count: int = 64,
    finalist_count: int = 8,
    seed: int = 7,
    settings: AppSettings | None = None,
    paths: RepoPaths | None = None,
) -> dict:
    resolved_paths = paths or RepoPaths.discover()
    resolved_settings = settings or load_settings(resolved_paths)
    runner = BacktesterRunner(resolved_paths, resolved_settings)
    strategy_dir = ensure_dir(resolved_paths.strategies / "baseline_search")
    report_dir = ensure_dir(resolved_paths.reports / "baseline_search")
    rng = random.Random(seed)

    variants = [_baseline_like_variant()]
    variants.extend(_random_variant(index, rng) for index in range(sample_count - 1))

    results = [_run_variant(runner, variant, strategy_dir) for variant in variants]
    results.sort(key=lambda item: item.submission_pnl, reverse=True)

    finalists = [_evaluate_tutorial(runner, result) for result in results[:finalist_count]]
    finalists.sort(key=lambda item: item.composite_score, reverse=True)
    best = finalists[0]

    best_path = resolved_paths.strategies / f"{slugify(best.variant.name)}-best.py"
    best_path.write_text(best.trader_path.read_text(encoding="utf-8"), encoding="utf-8")

    payload = {
        "created_at": utcnow_iso(),
        "baseline_submission_pnl": BASELINE_SUBMISSION_PNL,
        "best_variant": {
            **asdict(best.variant),
            "submission_pnl": best.submission_pnl,
            "tutorial_pnl": best.tutorial_pnl,
            "tutorial_worst_day": best.tutorial_worst_day,
            "composite_score": best.composite_score,
            "strategy_path": str(best_path),
        },
        "top_submission": [
            {
                **asdict(result.variant),
                "submission_pnl": result.submission_pnl,
                "strategy_path": str(result.trader_path),
            }
            for result in results[:10]
        ],
        "top_finalists": [
            {
                **asdict(result.variant),
                "submission_pnl": result.submission_pnl,
                "tutorial_pnl": result.tutorial_pnl,
                "tutorial_worst_day": result.tutorial_worst_day,
                "composite_score": result.composite_score,
                "strategy_path": str(result.trader_path),
            }
            for result in finalists
        ],
    }
    (report_dir / "latest.json").write_text(json_dumps(payload), encoding="utf-8")
    return payload
