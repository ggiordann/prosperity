import json
import math

from datamodel import Order, TradingState

EDGE_OFFSET = 1
ANCHOR_DELAY = 100
DIVERGENCE_CLIP = 25
FLOW_SIZE_GATE = 11
FLOW_TARGET_SCALE = 10
FLOW_MEMORY = 0.998


def walk_asks(book_snapshot):
    for ask_level in sorted(book_snapshot.sell_orders):
        yield ask_level, -book_snapshot.sell_orders[ask_level]


def walk_bids(book_snapshot):
    for bid_level in sorted(book_snapshot.buy_orders, reverse=True):
        yield bid_level, book_snapshot.buy_orders[bid_level]


def blended_book_mid(book_snapshot):
    bid_stack = list(walk_bids(book_snapshot))
    ask_stack = list(walk_asks(book_snapshot))
    bid_weight = sum(units for _, units in bid_stack)
    ask_weight = sum(units for _, units in ask_stack)
    if bid_weight <= 0 or ask_weight <= 0:
        return (max(book_snapshot.buy_orders) + min(book_snapshot.sell_orders)) / 2
    bid_mark = sum(level * units for level, units in bid_stack) / bid_weight
    ask_mark = sum(level * units for level, units in ask_stack) / ask_weight
    return (bid_mark + ask_mark) / 2


def build_divergence_takes(plan, book_snapshot, ledger, inventory, reference_mid, live_mid):
    trigger_gap = plan.get("diverge_threshold", 0)
    if trigger_gap <= 0 or ledger.get("anchor_n", 0) < ANCHOR_DELAY:
        return [], 0, 0
    mid_gap = live_mid - reference_mid
    if abs(mid_gap) < trigger_gap:
        return [], 0, 0

    symbol_name = plan["product"]
    hard_limit = plan["position_limit"]
    divergence_limit = plan.get("max_diverge_position", 60)
    proposed_orders = []
    filled_buys = 0
    filled_sells = 0
    if mid_gap > 0 and inventory > -divergence_limit:
        short_room = inventory + divergence_limit
        for bid_price, bid_quantity in walk_bids(book_snapshot):
            trade_cap = min(
                hard_limit + inventory - filled_sells,
                DIVERGENCE_CLIP - filled_sells,
                short_room - filled_sells,
            )
            if trade_cap <= 0:
                break
            trade_quantity = min(bid_quantity, trade_cap)
            proposed_orders.append(Order(symbol_name, bid_price, -trade_quantity))
            filled_sells += trade_quantity
    elif mid_gap < 0 and inventory < divergence_limit:
        long_room = divergence_limit - inventory
        for ask_price, ask_quantity in walk_asks(book_snapshot):
            trade_cap = min(
                hard_limit - inventory - filled_buys,
                DIVERGENCE_CLIP - filled_buys,
                long_room - filled_buys,
            )
            if trade_cap <= 0:
                break
            trade_quantity = min(ask_quantity, trade_cap)
            proposed_orders.append(Order(symbol_name, ask_price, trade_quantity))
            filled_buys += trade_quantity
    return proposed_orders, filled_buys, filled_sells


def build_edge_takes(plan, book_snapshot, fair_mark, inventory):
    symbol_name = plan["product"]
    hard_limit = plan["position_limit"]
    proposed_orders = []
    filled_buys = 0
    filled_sells = 0
    for ask_price, ask_quantity in walk_asks(book_snapshot):
        if ask_price >= fair_mark - EDGE_OFFSET:
            break
        trade_cap = hard_limit - inventory - filled_buys
        if trade_cap <= 0:
            break
        trade_quantity = min(ask_quantity, trade_cap)
        proposed_orders.append(Order(symbol_name, ask_price, trade_quantity))
        filled_buys += trade_quantity
    for bid_price, bid_quantity in walk_bids(book_snapshot):
        if bid_price <= fair_mark + EDGE_OFFSET:
            break
        trade_cap = hard_limit + inventory - filled_sells
        if trade_cap <= 0:
            break
        trade_quantity = min(bid_quantity, trade_cap)
        proposed_orders.append(Order(symbol_name, bid_price, -trade_quantity))
        filled_sells += trade_quantity
    return proposed_orders, filled_buys, filled_sells


def build_passive_quotes(
    plan,
    fair_mark,
    touch_bid,
    touch_ask,
    inventory,
    filled_buys,
    filled_sells,
):
    symbol_name = plan["product"]
    hard_limit = plan["position_limit"]
    display_size = plan.get("quote_size", 20)
    bid_quote = min(math.floor((fair_mark + touch_bid) / 2), touch_ask - 1)
    ask_quote = max(math.ceil((fair_mark + touch_ask) / 2), touch_bid + 1)
    bid_size = max(0, min(display_size, hard_limit - inventory - filled_buys))
    ask_size = max(0, min(display_size, hard_limit + inventory - filled_sells))
    proposed_orders = []
    if bid_size > 0 and bid_quote < ask_quote:
        proposed_orders.append(Order(symbol_name, bid_quote, bid_size))
    if ask_size > 0 and ask_quote > bid_quote:
        proposed_orders.append(Order(symbol_name, ask_quote, -ask_size))
    return proposed_orders


def build_anchor_orders(plan, market_state, ledger):
    book_snapshot = market_state.order_depths.get(plan["product"])
    if not book_snapshot or not book_snapshot.buy_orders or not book_snapshot.sell_orders:
        return []

    touch_bid = max(book_snapshot.buy_orders)
    touch_ask = min(book_snapshot.sell_orders)
    live_mid = (touch_bid + touch_ask) / 2
    fair_mark = blended_book_mid(book_snapshot)

    anchor_count = ledger.get("anchor_n", 0) + 1
    anchor_total = ledger.get("anchor_sum", 0.0) + live_mid
    ledger["anchor_n"] = anchor_count
    ledger["anchor_sum"] = anchor_total
    reference_mid = anchor_total / anchor_count
    inventory = market_state.position.get(plan["product"], 0)

    divergence_orders, divergence_buys, divergence_sells = build_divergence_takes(
        plan,
        book_snapshot,
        ledger,
        inventory,
        reference_mid,
        live_mid,
    )
    adjusted_inventory = inventory + divergence_buys - divergence_sells
    edge_orders, edge_buys, edge_sells = build_edge_takes(
        plan,
        book_snapshot,
        fair_mark,
        adjusted_inventory,
    )
    edge_buys += divergence_buys
    edge_sells += divergence_sells
    passive_orders = build_passive_quotes(
        plan,
        fair_mark,
        touch_bid,
        touch_ask,
        inventory,
        edge_buys,
        edge_sells,
    )
    return divergence_orders + edge_orders + passive_orders


def build_reversion_orders(plan, book_snapshot, inventory, ledger, target_adjustment=0):
    if not book_snapshot or not book_snapshot.buy_orders or not book_snapshot.sell_orders:
        return []
    symbol_name = plan["product"]
    hard_limit = plan["position_limit"]
    touch_bid = max(book_snapshot.buy_orders)
    touch_ask = min(book_snapshot.sell_orders)
    touch_bid_quantity = book_snapshot.buy_orders[touch_bid]
    touch_ask_quantity = -book_snapshot.sell_orders[touch_ask]
    touch_quantity = touch_bid_quantity + touch_ask_quantity
    micro_mark = (
        (touch_bid * touch_ask_quantity + touch_ask * touch_bid_quantity) / touch_quantity
        if touch_quantity > 0
        else (touch_bid + touch_ask) / 2.0
    )
    mid_mark = (touch_bid + touch_ask) / 2.0

    smoothing_gain = plan["k_ss"]
    fair_mark = ledger.get("_f", micro_mark)
    fair_error = micro_mark - fair_mark
    error_memory = ledger.get("_err", abs(fair_error))
    error_memory += smoothing_gain * (abs(fair_error) - error_memory)
    fair_mark += (smoothing_gain / (1.0 + error_memory)) * fair_error
    ledger["_f"] = fair_mark
    ledger["_err"] = error_memory

    sample_count = ledger.get("_n", 0) + 1
    variance_total = ledger.get("_s2", 0.0) + (mid_mark - fair_mark) ** 2
    ledger["_n"] = sample_count
    ledger["_s2"] = variance_total
    dispersion = max(1.0, (variance_total / sample_count) ** 0.5) if sample_count > 50 else plan["sigma_init"]

    anchor_mark = plan["fair_static"]
    target_inventory = max(
        -hard_limit,
        min(
            hard_limit,
            round(plan["mr_gain"] * (anchor_mark - mid_mark) / dispersion) + target_adjustment,
        ),
    )

    crossing_edge = plan["take_max_pay"]
    passive_edge = plan["quote_edge"]
    display_size = plan["quote_size"]

    proposed_orders = []
    buy_fill = 0
    sell_fill = 0
    inventory_gap = target_inventory - inventory

    if inventory_gap > 0:
        for ask_price in sorted(book_snapshot.sell_orders):
            if ask_price > fair_mark + crossing_edge:
                break
            order_size = min(
                -book_snapshot.sell_orders[ask_price],
                inventory_gap - buy_fill,
                hard_limit - inventory - buy_fill,
            )
            if order_size <= 0:
                break
            proposed_orders.append(Order(symbol_name, ask_price, order_size))
            buy_fill += order_size
    elif inventory_gap < 0:
        sell_need = -inventory_gap
        for bid_price in sorted(book_snapshot.buy_orders, reverse=True):
            if bid_price < fair_mark - crossing_edge:
                break
            order_size = min(
                book_snapshot.buy_orders[bid_price],
                sell_need - sell_fill,
                hard_limit + inventory - sell_fill,
            )
            if order_size <= 0:
                break
            proposed_orders.append(Order(symbol_name, bid_price, -order_size))
            sell_fill += order_size

    ask_reference = min(
        (level for level in book_snapshot.sell_orders if level >= fair_mark + passive_edge),
        default=None,
    )
    bid_reference = max(
        (level for level in book_snapshot.buy_orders if level <= fair_mark - passive_edge),
        default=None,
    )
    if bid_reference is not None:
        bid_quantity = min(display_size, hard_limit - inventory - buy_fill)
        if bid_quantity > 0:
            proposed_orders.append(Order(symbol_name, bid_reference + 1, bid_quantity))
    if ask_reference is not None:
        ask_quantity = min(display_size, hard_limit + inventory - sell_fill)
        if ask_quantity > 0:
            proposed_orders.append(Order(symbol_name, ask_reference - 1, -ask_quantity))

    return proposed_orders


REVERSION_PLANS = [
    {
        "product": "HYDROGEL_PACK",
        "position_limit": 200,
        "k_ss": 0.02,
        "fair_static": 10030,
        "mr_gain": 1000,
        "sigma_init": 30.0,
        "take_max_pay": -10,
        "quote_edge": 1,
        "quote_size": 30,
    },
    {
        "product": "VELVETFRUIT_EXTRACT",
        "position_limit": 200,
        "k_ss": 0.02,
        "fair_static": 5275,
        "mr_gain": 3500,
        "sigma_init": 15.0,
        "take_max_pay": -3,
        "quote_edge": 1,
        "quote_size": 15,
    },
]

ANCHOR_PLANS = [
    {"product": "VEV_4000", "position_limit": 300, "quote_size": 30, "diverge_threshold": 22, "max_diverge_position": 295},
    {"product": "VEV_4500", "position_limit": 300, "quote_size": 30, "diverge_threshold": 18, "max_diverge_position": 295},
    {"product": "VEV_5000", "position_limit": 300, "quote_size": 30, "diverge_threshold": 13, "max_diverge_position": 295},
    {"product": "VEV_5100", "position_limit": 300, "quote_size": 30, "diverge_threshold": 12, "max_diverge_position": 295},
    {"product": "VEV_5200", "position_limit": 300, "quote_size": 30, "diverge_threshold": 9, "max_diverge_position": 295},
    {"product": "VEV_5300", "position_limit": 300, "quote_size": 30, "diverge_threshold": 7, "max_diverge_position": 295},
    {"product": "VEV_5400", "position_limit": 300, "quote_size": 30, "diverge_threshold": 3, "max_diverge_position": 295},
    {"product": "VEV_5500", "position_limit": 300, "quote_size": 30, "diverge_threshold": 2, "max_diverge_position": 295},
]


def refresh_flow_state(flow_memory, tape_events, current_bid, current_ask):
    flow_score = flow_memory.get("_inf", 0.0) * FLOW_MEMORY
    for trade_event in tape_events or []:
        if trade_event.quantity < FLOW_SIZE_GATE:
            continue
        if trade_event.price >= current_ask:
            flow_score += trade_event.quantity
        elif trade_event.price <= current_bid:
            flow_score -= trade_event.quantity
    flow_memory["_inf"] = flow_score
    return flow_score


class Trader:
    def bid(self):
        return 0

    def run(self, state: TradingState):
        try:
            state_cache = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            state_cache = {}

        order_map: dict[str, list[Order]] = {}

        for plan in REVERSION_PLANS:
            book_snapshot = state.order_depths.get(plan["product"])
            target_adjustment = 0
            if plan["product"] == "VELVETFRUIT_EXTRACT" and book_snapshot and book_snapshot.buy_orders and book_snapshot.sell_orders:
                vfe_bid = max(book_snapshot.buy_orders)
                vfe_ask = min(book_snapshot.sell_orders)
                flow_score = refresh_flow_state(
                    state_cache.setdefault("_inf_store", {}),
                    state.market_trades.get("VELVETFRUIT_EXTRACT", []),
                    vfe_bid,
                    vfe_ask,
                )
                target_adjustment = int(round(FLOW_TARGET_SCALE * flow_score))
            product_orders = build_reversion_orders(
                plan,
                book_snapshot,
                state.position.get(plan["product"], 0),
                state_cache.setdefault(plan["product"], {}),
                target_adjustment=target_adjustment,
            )
            if product_orders:
                order_map[plan["product"]] = product_orders

        for plan in ANCHOR_PLANS:
            product_orders = build_anchor_orders(
                plan,
                state,
                state_cache.setdefault(plan["product"], {}),
            )
            if product_orders:
                order_map[plan["product"]] = product_orders

        return order_map, 0, json.dumps(state_cache)
