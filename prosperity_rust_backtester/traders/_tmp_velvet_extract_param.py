import json
import os
from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional


class Trader:
    PRODUCT = "VELVETFRUIT_EXTRACT"
    LIMIT = 200

    def __init__(self):
        self.mode = os.environ.get("MODE", "passive")
        self.size = int(os.environ.get("SIZE", "5"))
        self.window = int(os.environ.get("WINDOW", "100"))
        self.edge = float(os.environ.get("EDGE", "0"))
        self.inv_skew = float(os.environ.get("INV_SKEW", "0"))
        self.imb_coef = float(os.environ.get("IMB_COEF", "0"))
        self.mr_coef = float(os.environ.get("MR_COEF", "0"))
        self.trend_coef = float(os.environ.get("TREND_COEF", "0"))
        self.max_take_levels = int(os.environ.get("MAX_TAKE_LEVELS", "3"))
        self.passive_offset = int(os.environ.get("PASSIVE_OFFSET", "1"))
        self.one_side_threshold = float(os.environ.get("ONE_SIDE_THRESHOLD", "0"))

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        depth = state.order_depths.get(self.PRODUCT)
        if depth is None:
            return result, 0, state.traderData or ""

        position = int(state.position.get(self.PRODUCT, 0))
        best_bid, best_ask = self.best_bid_ask(depth)
        if best_bid is None or best_ask is None or best_bid >= best_ask:
            return result, 0, state.traderData or ""

        mid = (best_bid + best_ask) / 2.0
        data = self.load_state(state.traderData)
        mids = data.get("mids", [])
        mids.append(mid)
        max_len = max(self.window + 10, 50)
        if len(mids) > max_len:
            mids = mids[-max_len:]
        data["mids"] = mids

        fair = self.fair_value(depth, mid, mids, position)
        orders: List[Order] = []
        if self.mode in ("take", "hybrid"):
            orders.extend(self.take_orders(depth, fair, position))
            position += sum(order.quantity for order in orders if order.symbol == self.PRODUCT)
        if self.mode in ("passive", "hybrid", "one_side"):
            orders.extend(self.passive_orders(depth, fair, position))

        result[self.PRODUCT] = orders
        return result, 0, json.dumps(data, separators=(",", ":"))

    @staticmethod
    def best_bid_ask(order_depth: Optional[OrderDepth]):
        if order_depth is None:
            return None, None
        bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return bid, ask

    @staticmethod
    def load_state(raw: str):
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def fair_value(self, depth: OrderDepth, mid: float, mids: List[float], position: int) -> float:
        fair = mid
        bid_volume = sum(int(v) for v in depth.buy_orders.values())
        ask_volume = -sum(int(v) for v in depth.sell_orders.values())
        denom = bid_volume + ask_volume
        if denom > 0:
            imbalance = (bid_volume - ask_volume) / denom
            fair += self.imb_coef * imbalance

        if len(mids) >= max(5, min(self.window, len(mids))):
            sample = mids[-self.window:]
            mean = sum(sample) / len(sample)
            fair += self.mr_coef * (mean - mid)

        if len(mids) >= 2:
            fair += self.trend_coef * (mids[-1] - mids[-2])

        fair -= self.inv_skew * (position / self.LIMIT)
        return fair

    @staticmethod
    def buy_capacity(position: int) -> int:
        return max(0, Trader.LIMIT - position)

    @staticmethod
    def sell_capacity(position: int) -> int:
        return max(0, Trader.LIMIT + position)

    def take_orders(self, depth: OrderDepth, fair: float, position: int) -> List[Order]:
        orders: List[Order] = []
        buy_capacity = self.buy_capacity(position)
        sell_capacity = self.sell_capacity(position)
        levels = 0
        for price, volume in sorted(depth.sell_orders.items()):
            if levels >= self.max_take_levels or buy_capacity <= 0:
                break
            if price <= fair - self.edge:
                qty = min(self.size, buy_capacity, -int(volume))
                if qty > 0:
                    orders.append(Order(self.PRODUCT, price, qty))
                    buy_capacity -= qty
                    levels += 1
        levels = 0
        for price, volume in sorted(depth.buy_orders.items(), reverse=True):
            if levels >= self.max_take_levels or sell_capacity <= 0:
                break
            if price >= fair + self.edge:
                qty = min(self.size, sell_capacity, int(volume))
                if qty > 0:
                    orders.append(Order(self.PRODUCT, price, -qty))
                    sell_capacity -= qty
                    levels += 1
        return orders

    def passive_orders(self, depth: OrderDepth, fair: float, position: int) -> List[Order]:
        best_bid, best_ask = self.best_bid_ask(depth)
        if best_bid is None or best_ask is None:
            return []
        if best_ask - best_bid > 1:
            bid_price = best_bid + self.passive_offset
            ask_price = best_ask - self.passive_offset
            if bid_price >= ask_price:
                bid_price = best_bid
                ask_price = best_ask
        else:
            bid_price = best_bid
            ask_price = best_ask

        buy_size = min(self.size, self.buy_capacity(position))
        sell_size = min(self.size, self.sell_capacity(position))
        orders: List[Order] = []

        buy_ok = bid_price <= fair - self.edge
        sell_ok = ask_price >= fair + self.edge
        if self.mode == "passive":
            buy_ok = sell_ok = True
        elif self.mode == "one_side":
            if fair - (best_bid + best_ask) / 2.0 > self.one_side_threshold:
                sell_ok = False
            elif (best_bid + best_ask) / 2.0 - fair > self.one_side_threshold:
                buy_ok = False

        if buy_size > 0 and buy_ok:
            orders.append(Order(self.PRODUCT, int(bid_price), buy_size))
        if sell_size > 0 and sell_ok:
            orders.append(Order(self.PRODUCT, int(ask_price), -sell_size))
        return orders
