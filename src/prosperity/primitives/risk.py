from __future__ import annotations


def inventory_skew(position: int, limit: int, coefficient: float) -> float:
    if limit <= 0:
        return 0.0
    return coefficient * (position / limit)


def remaining_capacity(position: int, limit: int) -> tuple[int, int]:
    return max(0, limit - position), max(0, limit + position)
