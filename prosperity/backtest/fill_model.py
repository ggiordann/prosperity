from __future__ import annotations

import math
from typing import Dict, Iterable, List

from prosperity.backtest.types import RestingOrder
from prosperity.datamodel import OrderDepth, Trade


def simulate_resting_fills(
    resting_orders: Iterable[RestingOrder],
    current_depths: Dict[str, OrderDepth],
    next_depths: Dict[str, OrderDepth] | None,
    next_market_trades: Dict[str, List[Trade]] | None,
    timestamp: int,
    submission_id: str,
    passive_fill_fraction: float,
) -> List[Trade]:
    """
    Approximate Prosperity's within-iteration passive fills.

    The real exchange hides queue position and bot logic, so this model uses
    deterministic heuristics:
    - Full fill if the next snapshot moves through the resting price.
    - Partial fill if the order improves the current top of book.
    - Partial fill scaled by next-step market activity near the resting price.
    """
    if not next_depths:
        return []

    fills: List[Trade] = []
    next_market_trades = next_market_trades or {}

    for resting in resting_orders:
        current_depth = current_depths.get(resting.symbol, OrderDepth())
        next_depth = next_depths.get(resting.symbol, OrderDepth())
        trades = next_market_trades.get(resting.symbol, [])

        if resting.quantity > 0:
            fill_qty = _estimate_buy_fill(
                quantity=resting.quantity,
                price=resting.price,
                current_depth=current_depth,
                next_depth=next_depth,
                next_market_trades=trades,
                passive_fill_fraction=passive_fill_fraction,
            )
            if fill_qty > 0:
                fills.append(
                    Trade(
                        symbol=resting.symbol,
                        price=resting.price,
                        quantity=fill_qty,
                        buyer=submission_id,
                        seller="",
                        timestamp=timestamp,
                    )
                )
        elif resting.quantity < 0:
            fill_qty = _estimate_sell_fill(
                quantity=-resting.quantity,
                price=resting.price,
                current_depth=current_depth,
                next_depth=next_depth,
                next_market_trades=trades,
                passive_fill_fraction=passive_fill_fraction,
            )
            if fill_qty > 0:
                fills.append(
                    Trade(
                        symbol=resting.symbol,
                        price=resting.price,
                        quantity=fill_qty,
                        buyer="",
                        seller=submission_id,
                        timestamp=timestamp,
                    )
                )

    return fills


def _estimate_buy_fill(
    quantity: int,
    price: int,
    current_depth: OrderDepth,
    next_depth: OrderDepth,
    next_market_trades: List[Trade],
    passive_fill_fraction: float,
) -> int:
    current_best_bid = max(current_depth.buy_orders) if current_depth.buy_orders else None
    next_best_bid = max(next_depth.buy_orders) if next_depth.buy_orders else None
    next_best_ask = min(next_depth.sell_orders) if next_depth.sell_orders else None

    fill_qty = 0
    if next_best_ask is not None and price >= next_best_ask:
        return quantity

    if current_best_bid is not None and price > current_best_bid:
        improvement = price - current_best_bid
        fill_qty = max(fill_qty, math.ceil(quantity * min(0.85, 0.2 * improvement)))

    if next_best_bid is not None and price >= next_best_bid:
        fill_qty = max(fill_qty, math.ceil(quantity * 0.25))

    market_volume = sum(trade.quantity for trade in next_market_trades if trade.price <= price)
    if market_volume > 0:
        fill_qty = max(fill_qty, min(quantity, math.ceil(market_volume * passive_fill_fraction)))

    return min(quantity, fill_qty)


def _estimate_sell_fill(
    quantity: int,
    price: int,
    current_depth: OrderDepth,
    next_depth: OrderDepth,
    next_market_trades: List[Trade],
    passive_fill_fraction: float,
) -> int:
    current_best_ask = min(current_depth.sell_orders) if current_depth.sell_orders else None
    next_best_bid = max(next_depth.buy_orders) if next_depth.buy_orders else None
    next_best_ask = min(next_depth.sell_orders) if next_depth.sell_orders else None

    fill_qty = 0
    if next_best_bid is not None and price <= next_best_bid:
        return quantity

    if current_best_ask is not None and price < current_best_ask:
        improvement = current_best_ask - price
        fill_qty = max(fill_qty, math.ceil(quantity * min(0.85, 0.2 * improvement)))

    if next_best_ask is not None and price <= next_best_ask:
        fill_qty = max(fill_qty, math.ceil(quantity * 0.25))

    market_volume = sum(trade.quantity for trade in next_market_trades if trade.price >= price)
    if market_volume > 0:
        fill_qty = max(fill_qty, min(quantity, math.ceil(market_volume * passive_fill_fraction)))

    return min(quantity, fill_qty)

