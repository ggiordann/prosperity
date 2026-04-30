from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List


LIMIT = 10

DRIFT_DIR = {
    "OXYGEN_SHAKE_GARLIC": 1,
    "GALAXY_SOUNDS_BLACK_HOLES": 1,
    "PANEL_2X4": 1,
    "UV_VISOR_RED": 1,
    "SNACKPACK_STRAWBERRY": 1,
    "SLEEP_POD_LAMB_WOOL": 1,
    "MICROCHIP_OVAL": -1,
    "PEBBLES_XS": -1,
    "UV_VISOR_AMBER": -1,
    "PEBBLES_S": -1,
    "SNACKPACK_PISTACHIO": -1,
    "SNACKPACK_CHOCOLATE": -1,
}


def clip_target(target: int) -> int:
    return max(-LIMIT, min(LIMIT, int(target)))


def move_to_target(product: str, depth: OrderDepth, position: int, target: int) -> List[Order]:
    target = clip_target(target)
    best_bid = max(depth.buy_orders)
    best_ask = min(depth.sell_orders)
    orders: List[Order] = []

    if target > position:
        qty = min(target - position, LIMIT - position, -int(depth.sell_orders[best_ask]))
        if qty > 0:
            orders.append(Order(product, best_ask, qty))
    elif target < position:
        qty = min(position - target, LIMIT + position, int(depth.buy_orders[best_bid]))
        if qty > 0:
            orders.append(Order(product, best_bid, -qty))
    return orders


class Trader:
    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        for product, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                result[product] = []
                continue

            position = int(state.position.get(product, 0))
            target = 0

            if product in DRIFT_DIR:
                direction = DRIFT_DIR[product]
                target = direction * LIMIT

            result[product] = move_to_target(product, depth, position, target)

        return result, 0, ""
