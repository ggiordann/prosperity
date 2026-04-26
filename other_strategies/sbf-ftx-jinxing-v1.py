import json
import math

from datamodel import Order, TradingState

TAKE_WIDTH = 1
ANCHOR_WARMUP = 100
DIVERGE_TAKE_SIZE = 30


def search_sells(order_depth):
    for price in sorted(order_depth.sell_orders):
        yield price, -order_depth.sell_orders[price]


def search_buys(order_depth):
    for price in sorted(order_depth.buy_orders, reverse=True):
        yield price, order_depth.buy_orders[price]


def full_depth_mid(order_depth):
    bid_levels = list(search_buys(order_depth))
    ask_levels = list(search_sells(order_depth))
    bid_volume = sum(volume for _, volume in bid_levels)
    ask_volume = sum(volume for _, volume in ask_levels)
    if bid_volume <= 0 or ask_volume <= 0:
        return (max(order_depth.buy_orders) + min(order_depth.sell_orders)) / 2
    bid_value = sum(price * volume for price, volume in bid_levels) / bid_volume
    ask_value = sum(price * volume for price, volume in ask_levels) / ask_volume
    return (bid_value + ask_value) / 2


def divergence_take_orders(settings, order_depth, memory, current_position, anchor_mid, current_mid):
    divergence_threshold = settings.get("diverge_threshold", 0)
    if divergence_threshold <= 0 or memory.get("anchor_n", 0) < ANCHOR_WARMUP:
        return [], 0, 0
    divergence = current_mid - anchor_mid
    if abs(divergence) < divergence_threshold:
        return [], 0, 0

    symbol = settings["product"]
    position_limit = settings["position_limit"]
    max_divergence_position = settings.get("max_diverge_position", 60)
    generated_orders = []
    buy_volume = 0
    sell_volume = 0
    if divergence > 0 and current_position > -max_divergence_position:
        inventory_room = current_position + max_divergence_position
        for price, available_volume in search_buys(order_depth):
            capacity = min(
                position_limit + current_position - sell_volume,
                DIVERGE_TAKE_SIZE - sell_volume,
                inventory_room - sell_volume,
            )
            if capacity <= 0:
                break
            trade_size = min(available_volume, capacity)
            generated_orders.append(Order(symbol, price, -trade_size))
            sell_volume += trade_size
    elif divergence < 0 and current_position < max_divergence_position:
        inventory_room = max_divergence_position - current_position
        for price, available_volume in search_sells(order_depth):
            capacity = min(
                position_limit - current_position - buy_volume,
                DIVERGE_TAKE_SIZE - buy_volume,
                inventory_room - buy_volume,
            )
            if capacity <= 0:
                break
            trade_size = min(available_volume, capacity)
            generated_orders.append(Order(symbol, price, trade_size))
            buy_volume += trade_size
    return generated_orders, buy_volume, sell_volume


def take_orders(settings, order_depth, fair_value, current_position):
    symbol = settings["product"]
    position_limit = settings["position_limit"]
    generated_orders = []
    buy_volume = 0
    sell_volume = 0
    for price, available_volume in search_sells(order_depth):
        if price >= fair_value - TAKE_WIDTH:
            break
        capacity = position_limit - current_position - buy_volume
        if capacity <= 0:
            break
        trade_size = min(available_volume, capacity)
        generated_orders.append(Order(symbol, price, trade_size))
        buy_volume += trade_size
    for price, available_volume in search_buys(order_depth):
        if price <= fair_value + TAKE_WIDTH:
            break
        capacity = position_limit + current_position - sell_volume
        if capacity <= 0:
            break
        trade_size = min(available_volume, capacity)
        generated_orders.append(Order(symbol, price, -trade_size))
        sell_volume += trade_size
    return generated_orders, buy_volume, sell_volume


def make_quote(
    settings,
    fair_value,
    top_bid,
    top_ask,
    current_position,
    buy_volume,
    sell_volume,
):
    symbol = settings["product"]
    position_limit = settings["position_limit"]
    quote_size = settings.get("quote_size", 20)
    bid_price = min(math.floor((fair_value + top_bid) / 2), top_ask - 1)
    ask_price = max(math.ceil((fair_value + top_ask) / 2), top_bid + 1)
    buy_quantity = max(0, min(quote_size, position_limit - current_position - buy_volume))
    sell_quantity = max(0, min(quote_size, position_limit + current_position - sell_volume))
    generated_orders = []
    if buy_quantity > 0 and bid_price < ask_price:
        generated_orders.append(Order(symbol, bid_price, buy_quantity))
    if sell_quantity > 0 and ask_price > bid_price:
        generated_orders.append(Order(symbol, ask_price, -sell_quantity))
    return generated_orders


def zscore_orders(settings, state, memory):
    order_depth = state.order_depths.get(settings["product"])
    if not order_depth or not order_depth.buy_orders or not order_depth.sell_orders:
        return []

    top_bid = max(order_depth.buy_orders)
    top_ask = min(order_depth.sell_orders)
    current_mid = (top_bid + top_ask) / 2
    fair_value = full_depth_mid(order_depth)

    anchor_count = memory.get("anchor_n", 0) + 1
    anchor_sum = memory.get("anchor_sum", 0.0) + current_mid
    memory["anchor_n"] = anchor_count
    memory["anchor_sum"] = anchor_sum
    anchor_mid = anchor_sum / anchor_count
    current_position = state.position.get(settings["product"], 0)

    divergence_orders, divergence_bought, divergence_sold = divergence_take_orders(
        settings,
        order_depth,
        memory,
        current_position,
        anchor_mid,
        current_mid,
    )
    effective_position = current_position + divergence_bought - divergence_sold
    take_order_list, buy_volume, sell_volume = take_orders(
        settings,
        order_depth,
        fair_value,
        effective_position,
    )
    buy_volume += divergence_bought
    sell_volume += divergence_sold
    quote_orders = make_quote(
        settings,
        fair_value,
        top_bid,
        top_ask,
        current_position,
        buy_volume,
        sell_volume,
    )
    return divergence_orders + take_order_list + quote_orders


def kalman_mr_orders(settings, order_depth, current_position, memory):
    if not order_depth or not order_depth.buy_orders or not order_depth.sell_orders:
        return []
    symbol = settings["product"]
    position_limit = settings["position_limit"]
    best_bid = max(order_depth.buy_orders)
    best_ask = min(order_depth.sell_orders)
    top_bid_volume = order_depth.buy_orders[best_bid]
    top_ask_volume = -order_depth.sell_orders[best_ask]
    total_top_volume = top_bid_volume + top_ask_volume
    micro_price = (
        (best_bid * top_ask_volume + best_ask * top_bid_volume) / total_top_volume
        if total_top_volume > 0
        else (best_bid + best_ask) / 2.0
    )
    mid_price = (best_bid + best_ask) / 2.0

    kalman_gain = settings["k_ss"]
    fair_value = memory.get("_f", micro_price)
    innovation = micro_price - fair_value
    error_ema = memory.get("_err", abs(innovation))
    error_ema += kalman_gain * (abs(innovation) - error_ema)
    fair_value += (kalman_gain / (1.0 + error_ema)) * innovation
    memory["_f"] = fair_value
    memory["_err"] = error_ema

    sample_count = memory.get("_n", 0) + 1
    squared_error_sum = memory.get("_s2", 0.0) + (mid_price - fair_value) ** 2
    memory["_n"] = sample_count
    memory["_s2"] = squared_error_sum
    sigma_estimate = (
        max(1.0, (squared_error_sum / sample_count) ** 0.5)
        if sample_count > 50
        else settings["sigma_init"]
    )

    static_fair = settings["fair_static"]
    target_position = max(
        -position_limit,
        min(
            position_limit,
            round(settings["mr_gain"] * (static_fair - mid_price) / sigma_estimate),
        ),
    )

    take_max_pay = settings["take_max_pay"]
    quote_edge = settings["quote_edge"]
    quote_size = settings["quote_size"]

    generated_orders = []
    buy_volume = 0
    sell_volume = 0
    target_delta = target_position - current_position

    if target_delta > 0:
        for ask_price in sorted(order_depth.sell_orders):
            if ask_price > fair_value + take_max_pay:
                break
            order_quantity = min(
                -order_depth.sell_orders[ask_price],
                target_delta - buy_volume,
                position_limit - current_position - buy_volume,
            )
            if order_quantity <= 0:
                break
            generated_orders.append(Order(symbol, ask_price, order_quantity))
            buy_volume += order_quantity
    elif target_delta < 0:
        sell_need = -target_delta
        for bid_price in sorted(order_depth.buy_orders, reverse=True):
            if bid_price < fair_value - take_max_pay:
                break
            order_quantity = min(
                order_depth.buy_orders[bid_price],
                sell_need - sell_volume,
                position_limit + current_position - sell_volume,
            )
            if order_quantity <= 0:
                break
            generated_orders.append(Order(symbol, bid_price, -order_quantity))
            sell_volume += order_quantity

    ask_anchor_price = min(
        (price for price in order_depth.sell_orders if price >= fair_value + quote_edge),
        default=None,
    )
    bid_anchor_price = max(
        (price for price in order_depth.buy_orders if price <= fair_value - quote_edge),
        default=None,
    )
    if bid_anchor_price is not None:
        buy_quantity = min(quote_size, position_limit - current_position - buy_volume)
        if buy_quantity > 0:
            generated_orders.append(Order(symbol, bid_anchor_price + 1, buy_quantity))
    if ask_anchor_price is not None:
        sell_quantity = min(quote_size, position_limit + current_position - sell_volume)
        if sell_quantity > 0:
            generated_orders.append(Order(symbol, ask_anchor_price - 1, -sell_quantity))

    return generated_orders


KALMAN_MR_PRODUCTS = [
    {
        "product": "HYDROGEL_PACK",
        "position_limit": 200,
        "k_ss": 0.02,
        "fair_static": 10030,
        "mr_gain": 2000,
        "sigma_init": 30.0,
        "take_max_pay": -6,
        "quote_edge": 3,
        "quote_size": 30,
    },
    {
        "product": "VELVETFRUIT_EXTRACT",
        "position_limit": 200,
        "k_ss": 0.02,
        "fair_static": 5275,
        "mr_gain": 2000,
        "sigma_init": 15.0,
        "take_max_pay": -2,
        "quote_edge": 1,
        "quote_size": 30,
    },
]

ZSCORE_PRODUCTS = [
    {"product": "VEV_4000", "position_limit": 300, "quote_size": 30, "diverge_threshold": 20, "max_diverge_position": 295},
    {"product": "VEV_4500", "position_limit": 300, "quote_size": 30, "diverge_threshold": 20, "max_diverge_position": 295},
    {"product": "VEV_5000", "position_limit": 300, "quote_size": 30, "diverge_threshold": 18, "max_diverge_position": 295},
    {"product": "VEV_5100", "position_limit": 300, "quote_size": 30, "diverge_threshold": 14, "max_diverge_position": 295},
    {"product": "VEV_5200", "position_limit": 300, "quote_size": 30, "diverge_threshold": 11, "max_diverge_position": 295},
    {"product": "VEV_5300", "position_limit": 300, "quote_size": 30, "diverge_threshold": 8, "max_diverge_position": 295},
    {"product": "VEV_5400", "position_limit": 300, "quote_size": 30, "diverge_threshold": 4, "max_diverge_position": 295},
    {"product": "VEV_5500", "position_limit": 300, "quote_size": 30, "diverge_threshold": 2, "max_diverge_position": 295},
]


class Trader:
    def bid(self):
        return 0

    def run(self, state: TradingState):
        try:
            memory_store = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            memory_store = {}

        orders_by_product: dict[str, list[Order]] = {}

        for settings in KALMAN_MR_PRODUCTS:
            order_depth = state.order_depths.get(settings["product"])
            product_orders = kalman_mr_orders(
                settings,
                order_depth,
                state.position.get(settings["product"], 0),
                memory_store.setdefault(settings["product"], {}),
            )
            if product_orders:
                orders_by_product[settings["product"]] = product_orders

        for settings in ZSCORE_PRODUCTS:
            product_orders = zscore_orders(
                settings,
                state,
                memory_store.setdefault(settings["product"], {}),
            )
            if product_orders:
                orders_by_product[settings["product"]] = product_orders

        return orders_by_product, 0, json.dumps(memory_store)
