from __future__ import annotations


def mean_reversion_signal(mid: float, fair: float) -> float:
    return fair - mid


def momentum_signal(mid: float, last_mid: float) -> float:
    if last_mid == 0:
        return 0.0
    return mid - last_mid


def imbalance_signal(best_bid_volume: int, best_ask_volume: int) -> float:
    total = best_bid_volume + best_ask_volume
    if total <= 0:
        return 0.0
    return (best_bid_volume - best_ask_volume) / total


def volatility_signal(mid: float, last_mid: float) -> float:
    if last_mid == 0:
        return 0.0
    return abs(mid - last_mid)
