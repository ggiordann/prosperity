"""Round 3 tuned trader from v24_partial_hedge.

This is the best config found by the local v24 tuner for total round-3 PnL:

  - hedge_gain = 0.0
  - hp_fair_static = 10030
  - hp_mr_gain = 1000
  - hp_take_max_pay = -6
  - hp_quote_edge = 3
  - hp_quote_size = 30
  - vfe_fair_static = 5275
  - vfe_mr_gain = 2000
  - vfe_take_max_pay = -2
  - vfe_quote_edge = 1
  - vfe_quote_size = 30
  - informed_gain_s = 10

The resulting backtest PnL was 714,767.00 on round 3.
"""

import json
import math

from datamodel import Order, TradingState

TAKE_WIDTH = 1
ANCHOR_WARMUP = 100
DIVERGENCE_TAKE_SIZE = 30

INFORMED_SIZE_VFE = 11
INFORMED_GAIN_S = 10
INFORMED_DECAY = 0.998

TIME_TO_EXPIRY_TICKS = 30_000
TIMESTAMP_STEP = 100
SIGMA_SMILE_BY_STRIKE = {
    4000: 0.0008960,
    4500: 0.0004921,
    5000: 0.0002616,
    5100: 0.0002558,
    5200: 0.0002671,
    5300: 0.0002705,
    5400: 0.0002515,
    5500: 0.0002697,
    6000: 0.0004283,
    6500: 0.0006470,
}
HEDGE_GAIN = 0.0
HP_FAIR_STATIC = 10030
HP_MR_GAIN = 1000
HP_TAKE_MAX_PAY = -6
HP_QUOTE_EDGE = 3
HP_QUOTE_SIZE = 30
VFE_FAIR_STATIC = 5275
VFE_MR_GAIN = 2000
VFE_TAKE_MAX_PAY = -2
VFE_QUOTE_EDGE = 1
VFE_QUOTE_SIZE = 30


def iter_sell_levels(order_depth):
    for price in sorted(order_depth.sell_orders):
        yield price, -order_depth.sell_orders[price]


def iter_buy_levels(order_depth):
    for price in sorted(order_depth.buy_orders, reverse=True):
        yield price, order_depth.buy_orders[price]


def volume_weighted_book_mid(order_depth):
    bid_levels = list(iter_buy_levels(order_depth))
    ask_levels = list(iter_sell_levels(order_depth))
    total_bid_volume = sum(volume for _, volume in bid_levels)
    total_ask_volume = sum(volume for _, volume in ask_levels)
    if total_bid_volume <= 0 or total_ask_volume <= 0:
        return (max(order_depth.buy_orders) + min(order_depth.sell_orders)) / 2
    bid_vwap = sum(price * volume for price, volume in bid_levels) / total_bid_volume
    ask_vwap = sum(price * volume for price, volume in ask_levels) / total_ask_volume
    return (bid_vwap + ask_vwap) / 2


def top_of_book_microprice(order_depth):
    best_bid = max(order_depth.buy_orders)
    best_ask = min(order_depth.sell_orders)
    best_bid_volume = order_depth.buy_orders[best_bid]
    best_ask_volume = -order_depth.sell_orders[best_ask]
    total_volume = best_bid_volume + best_ask_volume
    if total_volume <= 0:
        return (best_bid + best_ask) / 2.0
    return (best_bid * best_ask_volume + best_ask * best_bid_volume) / total_volume


def divergence_take_orders(config, order_depth, product_store, current_position, anchor_price, mid_price):
    threshold = config.get("diverge_threshold", 0)
    if threshold <= 0 or product_store.get("anchor_n", 0) < ANCHOR_WARMUP:
        return [], 0, 0

    divergence = mid_price - anchor_price
    if abs(divergence) < threshold:
        return [], 0, 0

    product = config["product"]
    position_limit = config["position_limit"]
    max_divergence_position = config.get("max_diverge_position", 60)
    orders = []
    bought = 0
    sold = 0

    if divergence > 0 and current_position > -max_divergence_position:
        remaining_room = current_position + max_divergence_position
        for price, quantity in iter_buy_levels(order_depth):
            capacity = min(
                position_limit + current_position - sold,
                DIVERGENCE_TAKE_SIZE - sold,
                remaining_room - sold,
            )
            if capacity <= 0:
                break
            trade_size = min(quantity, capacity)
            orders.append(Order(product, price, -trade_size))
            sold += trade_size
    elif divergence < 0 and current_position < max_divergence_position:
        remaining_room = max_divergence_position - current_position
        for price, quantity in iter_sell_levels(order_depth):
            capacity = min(
                position_limit - current_position - bought,
                DIVERGENCE_TAKE_SIZE - bought,
                remaining_room - bought,
            )
            if capacity <= 0:
                break
            trade_size = min(quantity, capacity)
            orders.append(Order(product, price, trade_size))
            bought += trade_size

    return orders, bought, sold


def take_orders(config, order_depth, fair_price, effective_position):
    product = config["product"]
    position_limit = config["position_limit"]
    orders = []
    bought = 0
    sold = 0

    for price, quantity in iter_sell_levels(order_depth):
        if price >= fair_price - TAKE_WIDTH:
            break
        capacity = position_limit - effective_position - bought
        if capacity <= 0:
            break
        trade_size = min(quantity, capacity)
        orders.append(Order(product, price, trade_size))
        bought += trade_size

    for price, quantity in iter_buy_levels(order_depth):
        if price <= fair_price + TAKE_WIDTH:
            break
        capacity = position_limit + effective_position - sold
        if capacity <= 0:
            break
        trade_size = min(quantity, capacity)
        orders.append(Order(product, price, -trade_size))
        sold += trade_size

    return orders, bought, sold


def make_quote_orders(
    config,
    fair_price,
    best_bid,
    best_ask,
    current_position,
    already_bought,
    already_sold,
):
    product = config["product"]
    position_limit = config["position_limit"]
    quote_size = config.get("quote_size", 20)
    bid_quote = min(math.floor((fair_price + best_bid) / 2), best_ask - 1)
    ask_quote = max(math.ceil((fair_price + best_ask) / 2), best_bid + 1)
    buy_size = max(0, min(quote_size, position_limit - current_position - already_bought))
    sell_size = max(0, min(quote_size, position_limit + current_position - already_sold))

    orders = []
    if buy_size > 0 and bid_quote < ask_quote:
        orders.append(Order(product, bid_quote, buy_size))
    if sell_size > 0 and ask_quote > bid_quote:
        orders.append(Order(product, ask_quote, -sell_size))
    return orders


def zscore_orders(config, trading_state, product_store):
    order_depth = trading_state.order_depths.get(config["product"])
    if not order_depth or not order_depth.buy_orders or not order_depth.sell_orders:
        return []

    best_bid = max(order_depth.buy_orders)
    best_ask = min(order_depth.sell_orders)
    mid_price = (best_bid + best_ask) / 2
    fair_price = volume_weighted_book_mid(order_depth)

    anchor_count = product_store.get("anchor_n", 0) + 1
    anchor_sum = product_store.get("anchor_sum", 0.0) + mid_price
    product_store["anchor_n"] = anchor_count
    product_store["anchor_sum"] = anchor_sum
    anchor_price = anchor_sum / anchor_count

    current_position = trading_state.position.get(config["product"], 0)
    divergence_orders, divergence_bought, divergence_sold = divergence_take_orders(
        config,
        order_depth,
        product_store,
        current_position,
        anchor_price,
        mid_price,
    )

    effective_position = current_position + divergence_bought - divergence_sold
    taking_orders, bought, sold = take_orders(config, order_depth, fair_price, effective_position)
    bought += divergence_bought
    sold += divergence_sold
    quote_orders = make_quote_orders(
        config,
        fair_price,
        best_bid,
        best_ask,
        current_position,
        bought,
        sold,
    )
    return divergence_orders + taking_orders + quote_orders


def kalman_mean_reversion_orders(config, order_depth, current_position, product_store, target_bias=0):
    if not order_depth or not order_depth.buy_orders or not order_depth.sell_orders:
        return []

    product = config["product"]
    position_limit = config["position_limit"]
    best_bid = max(order_depth.buy_orders)
    best_ask = min(order_depth.sell_orders)
    microprice = top_of_book_microprice(order_depth)
    mid_price = (best_bid + best_ask) / 2.0

    kalman_step = config["k_ss"]
    fair_price = product_store.get("_f", microprice)
    innovation = microprice - fair_price
    error_ema = product_store.get("_err", abs(innovation))
    error_ema += kalman_step * (abs(innovation) - error_ema)
    fair_price += (kalman_step / (1.0 + error_ema)) * innovation
    product_store["_f"] = fair_price
    product_store["_err"] = error_ema

    variance_count = product_store.get("_n", 0) + 1
    variance_sum = product_store.get("_s2", 0.0) + (mid_price - fair_price) ** 2
    product_store["_n"] = variance_count
    product_store["_s2"] = variance_sum
    sigma = max(1.0, (variance_sum / variance_count) ** 0.5) if variance_count > 50 else config["sigma_init"]

    anchor_price = config["fair_static"]
    raw_target = round(config["mr_gain"] * (anchor_price - mid_price) / sigma) + target_bias
    target_position = max(-position_limit, min(position_limit, raw_target))

    take_max_pay = config["take_max_pay"]
    quote_edge = config["quote_edge"]
    quote_size = config["quote_size"]

    orders = []
    bought = 0
    sold = 0
    target_delta = target_position - current_position

    if target_delta > 0:
        for ask_price in sorted(order_depth.sell_orders):
            if ask_price > fair_price + take_max_pay:
                break
            available = -order_depth.sell_orders[ask_price]
            capacity = min(available, target_delta - bought, position_limit - current_position - bought)
            if capacity <= 0:
                break
            orders.append(Order(product, ask_price, capacity))
            bought += capacity
    elif target_delta < 0:
        needed = -target_delta
        for bid_price in sorted(order_depth.buy_orders, reverse=True):
            if bid_price < fair_price - take_max_pay:
                break
            available = order_depth.buy_orders[bid_price]
            capacity = min(available, needed - sold, position_limit + current_position - sold)
            if capacity <= 0:
                break
            orders.append(Order(product, bid_price, -capacity))
            sold += capacity

    nearest_ask_at_fair = min(
        (price for price in order_depth.sell_orders if price >= fair_price + quote_edge),
        default=None,
    )
    nearest_bid_at_fair = max(
        (price for price in order_depth.buy_orders if price <= fair_price - quote_edge),
        default=None,
    )

    if nearest_bid_at_fair is not None:
        buy_size = min(quote_size, position_limit - current_position - bought)
        if buy_size > 0:
            orders.append(Order(product, nearest_bid_at_fair + 1, buy_size))
    if nearest_ask_at_fair is not None:
        sell_size = min(quote_size, position_limit + current_position - sold)
        if sell_size > 0:
            orders.append(Order(product, nearest_ask_at_fair - 1, -sell_size))

    return orders


KALMAN_MR_PRODUCTS = [
    {
        "product": "HYDROGEL_PACK",
        "position_limit": 200,
        "k_ss": 0.02,
        "fair_static": HP_FAIR_STATIC,
        "mr_gain": HP_MR_GAIN,
        "sigma_init": 30.0,
        "take_max_pay": HP_TAKE_MAX_PAY,
        "quote_edge": HP_QUOTE_EDGE,
        "quote_size": HP_QUOTE_SIZE,
    },
    {
        "product": "VELVETFRUIT_EXTRACT",
        "position_limit": 200,
        "k_ss": 0.02,
        "fair_static": VFE_FAIR_STATIC,
        "mr_gain": VFE_MR_GAIN,
        "sigma_init": 15.0,
        "take_max_pay": VFE_TAKE_MAX_PAY,
        "quote_edge": VFE_QUOTE_EDGE,
        "quote_size": VFE_QUOTE_SIZE,
    },
]

ZSCORE_PRODUCTS = [
    {"product": "VEV_4000", "position_limit": 300, "quote_size": 30, "diverge_threshold": 18, "max_diverge_position": 295},
    {"product": "VEV_4500", "position_limit": 300, "quote_size": 30, "diverge_threshold": 18, "max_diverge_position": 295},
    {"product": "VEV_5000", "position_limit": 300, "quote_size": 30, "diverge_threshold": 15, "max_diverge_position": 295},
    {"product": "VEV_5100", "position_limit": 300, "quote_size": 30, "diverge_threshold": 13, "max_diverge_position": 295},
    {"product": "VEV_5200", "position_limit": 300, "quote_size": 30, "diverge_threshold": 10, "max_diverge_position": 295},
    {"product": "VEV_5300", "position_limit": 300, "quote_size": 30, "diverge_threshold": 7, "max_diverge_position": 295},
    {"product": "VEV_5400", "position_limit": 300, "quote_size": 30, "diverge_threshold": 4, "max_diverge_position": 295},
    {"product": "VEV_5500", "position_limit": 300, "quote_size": 30, "diverge_threshold": 2, "max_diverge_position": 295},
]


def update_informed_signal(signal_store, market_trades, best_bid, best_ask):
    signal_value = signal_store.get("_inf", 0.0) * INFORMED_DECAY
    for trade in market_trades or []:
        if trade.quantity < INFORMED_SIZE_VFE:
            continue
        if trade.price >= best_ask:
            signal_value += trade.quantity
        elif trade.price <= best_bid:
            signal_value -= trade.quantity
    signal_store["_inf"] = signal_value
    return signal_value


def normal_cdf(value):
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def black_scholes_call_delta(underlying_price, strike, time_to_expiry, sigma):
    if time_to_expiry <= 0 or sigma <= 0 or underlying_price <= 0:
        return 1.0 if underlying_price > strike else 0.0
    sqrt_t = math.sqrt(time_to_expiry)
    d1 = (
        math.log(underlying_price / strike) + 0.5 * sigma * sigma * time_to_expiry
    ) / (sigma * sqrt_t)
    return normal_cdf(d1)


def total_option_delta(trading_state, vfe_microprice, time_to_expiry):
    total_delta = 0.0
    for strike, sigma in SIGMA_SMILE_BY_STRIKE.items():
        symbol = f"VEV_{strike}"
        position = trading_state.position.get(symbol, 0)
        if position == 0:
            continue
        total_delta += position * black_scholes_call_delta(vfe_microprice, strike, time_to_expiry, sigma)
    return total_delta


def vfe_target_bias(trading_state, order_depth, root_store):
    best_bid = max(order_depth.buy_orders)
    best_ask = min(order_depth.sell_orders)
    microprice = top_of_book_microprice(order_depth)

    informed_signal = update_informed_signal(
        root_store.setdefault("_inf_store", {}),
        trading_state.market_trades.get("VELVETFRUIT_EXTRACT", []),
        best_bid,
        best_ask,
    )
    informed_bias = int(round(INFORMED_GAIN_S * informed_signal))

    time_to_expiry = max(1.0, TIME_TO_EXPIRY_TICKS - trading_state.timestamp / TIMESTAMP_STEP)
    option_delta = total_option_delta(trading_state, microprice, time_to_expiry)
    hedge_bias = int(round(HEDGE_GAIN * option_delta))

    return informed_bias - hedge_bias


class Trader:
    def bid(self):
        return 0

    def run(self, state: TradingState):
        try:
            root_store = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            root_store = {}

        orders_by_product: dict[str, list[Order]] = {}

        for config in KALMAN_MR_PRODUCTS:
            product = config["product"]
            order_depth = state.order_depths.get(product)
            target_bias = 0
            if (
                product == "VELVETFRUIT_EXTRACT"
                and order_depth
                and order_depth.buy_orders
                and order_depth.sell_orders
            ):
                target_bias = vfe_target_bias(state, order_depth, root_store)

            product_orders = kalman_mean_reversion_orders(
                config,
                order_depth,
                state.position.get(product, 0),
                root_store.setdefault(product, {}),
                target_bias=target_bias,
            )
            if product_orders:
                orders_by_product[product] = product_orders

        for config in ZSCORE_PRODUCTS:
            product_orders = zscore_orders(config, state, root_store.setdefault(config["product"], {}))
            if product_orders:
                orders_by_product[config["product"]] = product_orders

        return orders_by_product, 0, json.dumps(root_store)
