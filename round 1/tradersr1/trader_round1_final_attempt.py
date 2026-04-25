
import json
import math
from typing import Dict, List, Optional, Tuple
from datamodel import Order, OrderDepth, TradingState

class Trader:
    POSITION_LIMITS: Dict[str, int] = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    ASH_ANCHOR = 10000.0
    ASH_MICRO_ALPHA = 0.25
    ASH_SKEW = 0.08
    ASH_TAKE_EDGE = 1
    ASH_PASSIVE_EDGE = 0
    ASH_PASSIVE_SIZE = 20
    ASH_IMPROVE = 0
    ASH_USE_BEST_QUOTES = False

    PEPPER_SLOPE = 0.001
    PEPPER_MICRO_ALPHA = 0.0
    PEPPER_TARGET = 80
    PEPPER_BUY_TAKE_EDGE = 3
    PEPPER_BUY_JOIN_EDGE = 0
    PEPPER_BUY_IMPROVE = 0
    PEPPER_SELL_JOIN_EDGE = 5
    PEPPER_SELL_CORE = 20

    PEPPER_EARLY_TS = 20000
    PEPPER_EARLY_CORE = 60
    PEPPER_EARLY_TAKE_EDGE = 8
    PEPPER_EARLY_IMPROVE = 1
    PEPPER_EARLY_TOP_ONLY = True
    PEPPER_EARLY_PASSIVE_SIZE = 80
    PEPPER_EARLY_NO_SELL = True
    PEPPER_TAKE_ALL_ASKS = False

    @staticmethod
    def _load_memory(raw: str) -> Dict[str, float]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    @staticmethod
    def _best_bid_ask(order_depth: OrderDepth) -> Tuple[Optional[int], Optional[int]]:
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    @staticmethod
    def _mid(best_bid: Optional[int], best_ask: Optional[int], fallback: Optional[float]) -> Optional[float]:
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        if best_bid is not None:
            return float(best_bid)
        if best_ask is not None:
            return float(best_ask)
        return fallback

    @staticmethod
    def _micro(best_bid: Optional[int], best_ask: Optional[int], best_bid_qty: int, best_ask_qty: int, fallback: float) -> float:
        if best_bid is None or best_ask is None:
            return fallback
        tot = best_bid_qty + best_ask_qty
        if tot <= 0:
            return fallback
        return (best_ask * best_bid_qty + best_bid * best_ask_qty) / tot

    @staticmethod
    def _buy_capacity(limit: int, position: int) -> int:
        return max(0, limit - position)

    @staticmethod
    def _sell_capacity(limit: int, position: int) -> int:
        return max(0, limit + position)

    def _trade_ash(self, state: TradingState, order_depth: OrderDepth, memory: Dict[str, float]) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        limit = self.POSITION_LIMITS[product]
        position = state.position.get(product, 0)
        orders: List[Order] = []
        best_bid, best_ask = self._best_bid_ask(order_depth)
        mid = self._mid(best_bid, best_ask, memory.get("ash_last_mid"))
        if mid is None:
            return orders
        memory["ash_last_mid"] = mid
        best_bid_qty = order_depth.buy_orders[best_bid] if best_bid is not None else 0
        best_ask_qty = -order_depth.sell_orders[best_ask] if best_ask is not None else 0
        micro = self._micro(best_bid, best_ask, best_bid_qty, best_ask_qty, mid)
        fair = self.ASH_ANCHOR + self.ASH_MICRO_ALPHA * (micro - mid) - self.ASH_SKEW * position
        buy_cap = self._buy_capacity(limit, position)
        sell_cap = self._sell_capacity(limit, position)

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

        if buy_cap > 0 and (best_bid is not None or best_ask is not None):
            if self.ASH_USE_BEST_QUOTES:
                if best_bid is not None:
                    bid_price = best_bid + self.ASH_IMPROVE
                    if best_ask is not None:
                        bid_price = min(bid_price, best_ask - 1)
                else:
                    bid_price = int(math.floor(fair - self.ASH_PASSIVE_EDGE))
            else:
                if best_bid is not None:
                    bid_price = min(int(math.floor(fair - self.ASH_PASSIVE_EDGE)), best_bid + self.ASH_IMPROVE)
                else:
                    bid_price = int(math.floor(fair - self.ASH_PASSIVE_EDGE))
            if best_ask is None or bid_price < best_ask:
                qty = min(buy_cap, self.ASH_PASSIVE_SIZE)
                if qty > 0:
                    orders.append(Order(product, int(bid_price), qty))

        if sell_cap > 0 and (best_bid is not None or best_ask is not None):
            if self.ASH_USE_BEST_QUOTES:
                if best_ask is not None:
                    ask_price = best_ask - self.ASH_IMPROVE
                    if best_bid is not None:
                        ask_price = max(ask_price, best_bid + 1)
                else:
                    ask_price = int(math.ceil(fair + self.ASH_PASSIVE_EDGE))
            else:
                if best_ask is not None:
                    ask_price = max(int(math.ceil(fair + self.ASH_PASSIVE_EDGE)), best_ask - self.ASH_IMPROVE)
                else:
                    ask_price = int(math.ceil(fair + self.ASH_PASSIVE_EDGE))
            if best_bid is None or ask_price > best_bid:
                qty = min(sell_cap, self.ASH_PASSIVE_SIZE)
                if qty > 0:
                    orders.append(Order(product, int(ask_price), -qty))
        return orders

    def _trade_pepper(self, state: TradingState, order_depth: OrderDepth, memory: Dict[str, float]) -> List[Order]:
        product = "INTARIAN_PEPPER_ROOT"
        limit = self.POSITION_LIMITS[product]
        position = state.position.get(product, 0)
        orders: List[Order] = []

        best_bid, best_ask = self._best_bid_ask(order_depth)
        mid = self._mid(best_bid, best_ask, memory.get("pep_last_mid"))
        if mid is None:
            return orders

        memory["pep_last_mid"] = mid
        if "pep_base" not in memory:
            memory["pep_base"] = mid - self.PEPPER_SLOPE * state.timestamp

        best_bid_qty = order_depth.buy_orders[best_bid] if best_bid is not None else 0
        best_ask_qty = -order_depth.sell_orders[best_ask] if best_ask is not None else 0
        micro = self._micro(best_bid, best_ask, best_bid_qty, best_ask_qty, mid)
        trend_fair = float(memory["pep_base"]) + self.PEPPER_SLOPE * state.timestamp + self.PEPPER_MICRO_ALPHA * (micro - mid)

        buy_cap = self._buy_capacity(limit, position)
        sell_cap = self._sell_capacity(limit, position)
        early = state.timestamp < self.PEPPER_EARLY_TS

        if early and position < self.PEPPER_EARLY_CORE and buy_cap > 0:
            core_left = self.PEPPER_EARLY_CORE - position
            if self.PEPPER_EARLY_TOP_ONLY:
                if best_ask is not None and best_ask <= trend_fair + self.PEPPER_EARLY_TAKE_EDGE:
                    ask_qty = -order_depth.sell_orders[best_ask]
                    qty = min(buy_cap, core_left, ask_qty)
                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))
                        buy_cap -= qty
                        core_left -= qty
            else:
                for ask in sorted(order_depth.sell_orders):
                    if buy_cap <= 0 or core_left <= 0:
                        break
                    ask_qty = -order_depth.sell_orders[ask]
                    if ask <= trend_fair + self.PEPPER_EARLY_TAKE_EDGE:
                        qty = min(buy_cap, core_left, ask_qty)
                        if qty > 0:
                            orders.append(Order(product, ask, qty))
                            buy_cap -= qty
                            core_left -= qty
            if buy_cap > 0 and core_left > 0:
                bid_price = None
                if best_bid is not None:
                    bid_price = best_bid + self.PEPPER_EARLY_IMPROVE
                    if best_ask is not None:
                        bid_price = min(bid_price, best_ask - 1)
                elif best_ask is not None:
                    bid_price = best_ask - 1
                if bid_price is not None and (best_ask is None or bid_price < best_ask):
                    qty = min(buy_cap, core_left, self.PEPPER_EARLY_PASSIVE_SIZE)
                    if qty > 0:
                        orders.append(Order(product, int(bid_price), qty))
                        buy_cap -= qty

        remaining_target = self.PEPPER_TARGET - position - sum(o.quantity for o in orders if o.quantity > 0)
        if remaining_target > 0 and buy_cap > 0:
            if self.PEPPER_TAKE_ALL_ASKS:
                for ask in sorted(order_depth.sell_orders):
                    if buy_cap <= 0 or remaining_target <= 0:
                        break
                    ask_qty = -order_depth.sell_orders[ask]
                    if ask <= trend_fair + self.PEPPER_BUY_TAKE_EDGE:
                        qty = min(buy_cap, remaining_target, ask_qty)
                        if qty > 0:
                            orders.append(Order(product, ask, qty))
                            buy_cap -= qty
                            remaining_target -= qty
            else:
                if best_ask is not None and best_ask <= trend_fair + self.PEPPER_BUY_TAKE_EDGE:
                    qty = min(buy_cap, remaining_target)
                    if qty > 0:
                        orders.append(Order(product, best_ask, qty))
                        buy_cap -= qty
                        remaining_target -= qty

        if remaining_target > 0 and buy_cap > 0 and best_bid is not None and best_bid <= trend_fair - self.PEPPER_BUY_JOIN_EDGE:
            bid_price = best_bid + self.PEPPER_BUY_IMPROVE
            if best_ask is not None:
                bid_price = min(bid_price, best_ask - 1)
            if best_ask is None or bid_price < best_ask:
                qty = min(buy_cap, remaining_target)
                if qty > 0:
                    orders.append(Order(product, int(bid_price), qty))

        if (not early or not self.PEPPER_EARLY_NO_SELL) and position > self.PEPPER_SELL_CORE and best_ask is not None and best_ask >= trend_fair + self.PEPPER_SELL_JOIN_EDGE:
            qty = min(position - self.PEPPER_SELL_CORE, sell_cap)
            if qty > 0:
                orders.append(Order(product, best_ask, -qty))
        return orders

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData)
        result: Dict[str, List[Order]] = {}
        for product, order_depth in state.order_depths.items():
            if product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_ash(state, order_depth, memory)
            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper(state, order_depth, memory)
            else:
                result[product] = []
        return result, 0, json.dumps(memory, separators=(",", ":"))
