from __future__ import annotations


def constant_fair(value: float) -> float:
    return value


def mid_price(best_bid: int, best_ask: int) -> float:
    return 0.5 * (best_bid + best_ask)


def microprice(best_bid: int, bid_volume: int, best_ask: int, ask_volume: int) -> float:
    total = bid_volume + ask_volume
    if total <= 0:
        return mid_price(best_bid, best_ask)
    return (best_ask * bid_volume + best_bid * ask_volume) / total


def wall_mid(buy_orders: dict[int, int], sell_orders: dict[int, int], threshold: int) -> float:
    wall_bid = max((price for price, volume in buy_orders.items() if volume >= threshold), default=max(buy_orders))
    wall_ask = min((price for price, volume in sell_orders.items() if abs(volume) >= threshold), default=min(sell_orders))
    return 0.5 * (wall_bid + wall_ask)


def ema(previous: float, new_value: float, alpha: float) -> float:
    if previous == 0.0:
        return new_value
    return alpha * new_value + (1.0 - alpha) * previous
