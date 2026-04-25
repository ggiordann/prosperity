import json
from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    """
    Round 1 strategy for Prosperity 4.

    Products:
      - ASH_COATED_OSMIUM: stationary around a stable anchor.
      - INTARIAN_PEPPER_ROOT: strong linear upward drift with small noise.

    Design goals:
      - low-parameter and regime-based, not path-memorized
      - no day-specific branching
      - no heavy computation
      - safe state handling via traderData only
    """

    POSITION_LIMITS: Dict[str, int] = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    # ASH_COATED_OSMIUM parameters
    ASH_FAIR: float = 10000.0
    ASH_INVENTORY_SKEW: float = 0.12
    ASH_TAKE_EDGE: int = 1

    # INTARIAN_PEPPER_ROOT parameters
    PEPPER_SLOPE: float = 0.001  # 0.1 mid-price points per 100ms step
    PEPPER_TARGET: int = 80
    PEPPER_BUY_TAKE_EDGE: int = 5
    PEPPER_BUY_JOIN_EDGE: int = 0
    PEPPER_SELL_JOIN_EDGE: int = 4

    @staticmethod
    def _best_bid_ask(order_depth: OrderDepth) -> Tuple[int, int] | None:
        if not order_depth.buy_orders or not order_depth.sell_orders:
            return None
        return max(order_depth.buy_orders), min(order_depth.sell_orders)

    @staticmethod
    def _load_memory(trader_data: str) -> Dict[str, float]:
        if not trader_data:
            return {}
        try:
            data = json.loads(trader_data)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    @staticmethod
    def _buy_capacity(limit: int, position: int) -> int:
        return max(0, limit - position)

    @staticmethod
    def _sell_capacity(limit: int, position: int) -> int:
        return max(0, limit + position)

    def _trade_ash(self, state: TradingState, order_depth: OrderDepth) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        limit = self.POSITION_LIMITS[product]
        position = state.position.get(product, 0)
        orders: List[Order] = []

        best = self._best_bid_ask(order_depth)
        if best is None:
            return orders
        best_bid, best_ask = best

        fair = self.ASH_FAIR - self.ASH_INVENTORY_SKEW * position
        buy_cap = self._buy_capacity(limit, position)
        sell_cap = self._sell_capacity(limit, position)

        # 1) Take clearly mispriced visible liquidity.
        for ask in sorted(order_depth.sell_orders):
            if buy_cap <= 0:
                break
            ask_qty = -order_depth.sell_orders[ask]
            if ask <= fair - self.ASH_TAKE_EDGE:
                qty = min(buy_cap, ask_qty)
                if qty > 0:
                    orders.append(Order(product, ask, qty))
                    buy_cap -= qty

        for bid in sorted(order_depth.buy_orders, reverse=True):
            if sell_cap <= 0:
                break
            bid_qty = order_depth.buy_orders[bid]
            if bid >= fair + self.ASH_TAKE_EDGE:
                qty = min(sell_cap, bid_qty)
                if qty > 0:
                    orders.append(Order(product, bid, -qty))
                    sell_cap -= qty

        # 2) Join the best bid/ask when still favorable to capture spread.
        if buy_cap > 0 and best_bid <= fair:
            orders.append(Order(product, best_bid, min(80, buy_cap)))

        if sell_cap > 0 and best_ask >= fair:
            orders.append(Order(product, best_ask, -min(80, sell_cap)))

        return orders

    def _trade_pepper(
        self,
        state: TradingState,
        order_depth: OrderDepth,
        memory: Dict[str, float],
    ) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        limit = self.POSITION_LIMITS[product]
        position = state.position.get(product, 0)
        orders: List[Order] = []

        best = self._best_bid_ask(order_depth)
        if best is None:
            return orders
        best_bid, best_ask = best
        mid = (best_bid + best_ask) / 2.0

        if "pep_base" not in memory:
            memory["pep_base"] = mid - self.PEPPER_SLOPE * state.timestamp

        trend_fair = float(memory["pep_base"]) + self.PEPPER_SLOPE * state.timestamp

        buy_cap = self._buy_capacity(limit, position)
        sell_cap = self._sell_capacity(limit, position)
        target = self.PEPPER_TARGET

        # 1) Build and maintain a core long inventory because of the positive drift.
        if position < target and best_ask <= trend_fair + self.PEPPER_BUY_TAKE_EDGE and buy_cap > 0:
            qty = min(target - position, buy_cap)
            if qty > 0:
                orders.append(Order(product, best_ask, qty))
                buy_cap -= qty

        # 2) Refill passively at the best bid when the book is not expensive versus trend.
        if position < target and best_bid <= trend_fair - self.PEPPER_BUY_JOIN_EDGE and buy_cap > 0:
            qty = min(target - position, buy_cap)
            if qty > 0:
                orders.append(Order(product, best_bid, qty))

        # 3) When the ask is rich to the trend, leave a passive sell to scalp noise
        #    while keeping the directional core.
        if position > 0 and best_ask >= trend_fair + self.PEPPER_SELL_JOIN_EDGE:
            qty = min(position, sell_cap)
            if qty > 0:
                orders.append(Order(product, best_ask, -qty))

        return orders

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData)
        result: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            if product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_ash(state, order_depth)
            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper(state, order_depth, memory)
            else:
                result[product] = []

        trader_data = json.dumps(memory, separators=(",", ":"))
        conversions = 0
        return result, conversions, trader_data
