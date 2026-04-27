import json
from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional


class Trader:
    """Standalone Round 3 trader for VELVETFRUIT_EXTRACT only."""

    PRODUCT = "VELVETFRUIT_EXTRACT"
    POSITION_LIMIT = 200

    WINDOW = 2000
    ORDER_SIZE = 80
    ENTRY_EDGE = 8.0
    EXIT_EDGE = 3.0
    MEAN_REVERSION_COEF = 0.5

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        order_depth = state.order_depths.get(self.PRODUCT)
        if order_depth is None:
            return result, 0, state.traderData or ""

        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None or best_bid >= best_ask:
            return result, 0, state.traderData or ""

        mid = (best_bid + best_ask) / 2.0
        data = self.load_state(state.traderData)
        mids = data.get("mids", [])
        mids.append(mid)
        if len(mids) > self.WINDOW:
            mids = mids[-self.WINDOW:]
        data["mids"] = mids

        position = int(state.position.get(self.PRODUCT, 0))
        fair_value = self.fair_value(mid, mids)
        result[self.PRODUCT] = self.trade_mispricing(order_depth, fair_value, position)

        trader_data = json.dumps(data, separators=(",", ":"))
        return result, 0, trader_data

    @staticmethod
    def best_bid_ask(order_depth: Optional[OrderDepth]):
        if order_depth is None:
            return None, None
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    @staticmethod
    def load_state(raw: str):
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def fair_value(self, mid: float, mids: List[float]) -> float:
        # Velvetfruit's short-horizon edge is mean reversion, not trend.
        rolling_mean = sum(mids) / len(mids)
        return mid + self.MEAN_REVERSION_COEF * (rolling_mean - mid)

    @classmethod
    def buy_capacity(cls, position: int) -> int:
        return max(0, cls.POSITION_LIMIT - position)

    @classmethod
    def sell_capacity(cls, position: int) -> int:
        return max(0, cls.POSITION_LIMIT + position)

    def trade_mispricing(
        self,
        order_depth: OrderDepth,
        fair_value: float,
        position: int,
    ) -> List[Order]:
        orders: List[Order] = []
        buy_capacity = self.buy_capacity(position)
        sell_capacity = self.sell_capacity(position)

        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            if buy_capacity <= 0:
                break
            if ask_price <= fair_value - self.ENTRY_EDGE:
                quantity = min(self.ORDER_SIZE, buy_capacity, -int(ask_volume))
                if quantity > 0:
                    orders.append(Order(self.PRODUCT, ask_price, quantity))
                    buy_capacity -= quantity

        for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
            if sell_capacity <= 0:
                break
            if bid_price >= fair_value + self.EXIT_EDGE:
                quantity = min(self.ORDER_SIZE, sell_capacity, int(bid_volume))
                if quantity > 0:
                    orders.append(Order(self.PRODUCT, bid_price, -quantity))
                    sell_capacity -= quantity

        return orders
