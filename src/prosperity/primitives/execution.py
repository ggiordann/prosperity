from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SimpleOrder:
    symbol: str
    price: int
    quantity: int


def take_if_edge(
    product: str,
    fair_value: float,
    best_bid: int,
    best_bid_volume: int,
    best_ask: int,
    best_ask_volume: int,
    position: int,
    position_limit: int,
    min_edge: float,
    max_size: int,
) -> list[SimpleOrder]:
    orders: list[SimpleOrder] = []
    if best_ask <= fair_value - min_edge:
        buy_size = min(best_ask_volume, max_size, position_limit - position)
        if buy_size > 0:
            orders.append(SimpleOrder(product, best_ask, buy_size))
    if best_bid >= fair_value + min_edge:
        sell_size = min(best_bid_volume, max_size, position_limit + position)
        if sell_size > 0:
            orders.append(SimpleOrder(product, best_bid, -sell_size))
    return orders


def clear_inventory(
    product: str,
    fair_value: float,
    buy_orders: dict[int, int],
    sell_orders: dict[int, int],
    position: int,
    buy_volume: int,
    sell_volume: int,
    position_limit: int,
) -> list[SimpleOrder]:
    orders: list[SimpleOrder] = []
    fair_level = round(fair_value)
    position_after_take = position + buy_volume - sell_volume
    if position_after_take > 0 and fair_level in buy_orders:
        quantity = min(buy_orders[fair_level], position_after_take, position_limit + position - sell_volume)
        if quantity > 0:
            orders.append(SimpleOrder(product, fair_level, -quantity))
    elif position_after_take < 0 and fair_level in sell_orders:
        quantity = min(abs(sell_orders[fair_level]), -position_after_take, position_limit - position - buy_volume)
        if quantity > 0:
            orders.append(SimpleOrder(product, fair_level, quantity))
    return orders


def make_layered_quotes(
    product: str,
    reservation_price: float,
    best_bid: int,
    best_ask: int,
    position: int,
    position_limit: int,
    layers: list[dict],
) -> list[SimpleOrder]:
    orders: list[SimpleOrder] = []
    buy_remaining = max(0, position_limit - position)
    sell_remaining = max(0, position_limit + position)
    for layer in layers:
        offset = layer["offset"]
        size = layer["size"]
        side = layer["side"]
        if side == "buy":
            price = min(best_ask - 1, int(round(reservation_price - offset)))
            quantity = min(size, buy_remaining)
            if quantity > 0 and price < best_ask:
                orders.append(SimpleOrder(product, price, quantity))
                buy_remaining -= quantity
        else:
            price = max(best_bid + 1, int(round(reservation_price + offset)))
            quantity = min(size, sell_remaining)
            if quantity > 0 and price > best_bid:
                orders.append(SimpleOrder(product, price, -quantity))
                sell_remaining -= quantity
    return orders
