import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    """
    Round 2 trader with Market Access Fee support.

    Design:
    - ASH_COATED_OSMIUM: stable around a slow long-term moving average just
      above ~10_000. Quote/take tightly around that adaptive anchor with lighter
      inventory skew, which performed better on randomized 80% portal-style
      quote masks.

    - INTARIAN_PEPPER_ROOT: persistent upward drift with a slow mean-reversion
      dampener. Keep the proven accumulation logic, but reduce the fair value
      when price is stretched above its long-term moving average.

    - Market Access Fee: bid for the extra 25% quote access in Round 2. The bid
      is intentionally moderate: high enough to target top-half acceptance
      without donating a large chunk of hidden-round PnL.
    """

    MARKET_ACCESS_FEE_BID: int = 777

    def bid(self):
        return self.MARKET_ACCESS_FEE_BID

    POSITION_LIMITS: Dict[str, int] = {
        "ASH_COATED_OSMIUM": 80,
        "INTARIAN_PEPPER_ROOT": 80,
    }

    # -----------------------------
    # ASH_COATED_OSMIUM parameters
    # -----------------------------
    ASH_ANCHOR: float = 10_002.0
    ASH_SKEW: float = 0.08
    ASH_TAKE_EDGE: int = 1
    ASH_PASSIVE_EDGE: int = 0
    ASH_PASSIVE_SIZE: int = 20
    ASH_LONG_MA_ALPHA: float = 0.020
    ASH_LONG_MA_WEIGHT: float = 0.05

    # -----------------------------
    # INTARIAN_PEPPER_ROOT parameters
    # -----------------------------
    PEPPER_SLOPE_PRIOR: float = 0.001
    PEPPER_SLOPE_ALPHA: float = 0.50
    PEPPER_SLOPE_MIN: float = 0.0
    PEPPER_SLOPE_MAX: float = 0.005
    PEPPER_HORIZON: float = 5000.0
    PEPPER_TAKE_EDGE: int = 10
    PEPPER_PASSIVE_SIZE: int = 40
    PEPPER_LONG_MA_ALPHA: float = 0.020
    PEPPER_REVERSION_WEIGHT: float = 0.020

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
    def _buy_capacity(limit: int, position: int) -> int:
        return max(0, limit - position)

    @staticmethod
    def _sell_capacity(limit: int, position: int) -> int:
        return max(0, limit + position)

    @staticmethod
    def _update_long_ma(memory: Dict[str, float], key: str, value: float, alpha: float) -> float:
        previous = memory.get(key)
        if previous is None:
            long_ma = value
        else:
            long_ma = alpha * value + (1.0 - alpha) * float(previous)
        memory[key] = long_ma
        return long_ma

    def _update_pepper_slope(self, timestamp: int, mid: float, memory: Dict[str, float]) -> float:
        slope = float(memory.get("pep_slope", self.PEPPER_SLOPE_PRIOR))
        prev_ts = memory.get("pep_prev_ts")
        prev_mid = memory.get("pep_prev_mid")

        if prev_ts is not None and prev_mid is not None and timestamp > prev_ts:
            inst_slope = (mid - prev_mid) / (timestamp - prev_ts)
            slope = self.PEPPER_SLOPE_ALPHA * inst_slope + (1.0 - self.PEPPER_SLOPE_ALPHA) * slope
            slope = max(self.PEPPER_SLOPE_MIN, min(self.PEPPER_SLOPE_MAX, slope))

        memory["pep_prev_ts"] = timestamp
        memory["pep_prev_mid"] = mid
        memory["pep_slope"] = slope
        memory["pep_last_mid"] = mid
        return slope

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

        best_bid, best_ask = self._best_bid_ask(order_depth)
        mid = self._mid(best_bid, best_ask, memory.get("pep_last_mid"))
        if mid is None:
            return orders

        long_ma = self._update_long_ma(memory, "pep_long_ma", mid, self.PEPPER_LONG_MA_ALPHA)
        slope = self._update_pepper_slope(state.timestamp, mid, memory)
        trend_fair = mid + slope * self.PEPPER_HORIZON
        reversion_drag = self.PEPPER_REVERSION_WEIGHT * (mid - long_ma)
        fair_value = trend_fair - reversion_drag

        buy_cap = self._buy_capacity(limit, position)
        if buy_cap <= 0:
            return orders

        # Aggressively accumulate by sweeping favorable visible asks.
        for ask in sorted(order_depth.sell_orders):
            if buy_cap <= 0:
                break
            ask_qty = -order_depth.sell_orders[ask]
            if ask <= fair_value + self.PEPPER_TAKE_EDGE:
                qty = min(buy_cap, ask_qty)
                if qty > 0:
                    orders.append(Order(product, ask, qty))
                    buy_cap -= qty

        # Improve the best bid by one tick for additional passive fills.
        if buy_cap > 0:
            bid_price: Optional[int] = None
            if best_bid is not None:
                bid_price = best_bid + 1
                if best_ask is not None:
                    bid_price = min(bid_price, best_ask - 1)
            elif best_ask is not None:
                bid_price = best_ask - 1

            if bid_price is not None and (best_ask is None or bid_price < best_ask):
                qty = min(buy_cap, self.PEPPER_PASSIVE_SIZE)
                if qty > 0:
                    orders.append(Order(product, int(bid_price), qty))

        return orders

    def _trade_ash(self, state: TradingState, order_depth: OrderDepth, memory: Dict[str, float]) -> List[Order]:
        product = "ASH_COATED_OSMIUM"
        limit = self.POSITION_LIMITS[product]
        position = state.position.get(product, 0)
        orders: List[Order] = []

        best_bid, best_ask = self._best_bid_ask(order_depth)
        mid = self._mid(best_bid, best_ask, memory.get("ash_long_ma", self.ASH_ANCHOR))
        long_ma = self._update_long_ma(memory, "ash_long_ma", float(mid or self.ASH_ANCHOR), self.ASH_LONG_MA_ALPHA)
        anchor = (1.0 - self.ASH_LONG_MA_WEIGHT) * self.ASH_ANCHOR + self.ASH_LONG_MA_WEIGHT * long_ma
        reservation = anchor - self.ASH_SKEW * position

        buy_cap = self._buy_capacity(limit, position)
        sell_cap = self._sell_capacity(limit, position)

        # Take stale visible quotes around reservation.
        for ask in sorted(order_depth.sell_orders):
            if buy_cap <= 0:
                break
            ask_qty = -order_depth.sell_orders[ask]
            if ask <= reservation - self.ASH_TAKE_EDGE:
                qty = min(buy_cap, ask_qty)
                if qty > 0:
                    orders.append(Order(product, ask, qty))
                    buy_cap -= qty

        for bid in sorted(order_depth.buy_orders, reverse=True):
            if sell_cap <= 0:
                break
            bid_qty = order_depth.buy_orders[bid]
            if bid >= reservation + self.ASH_TAKE_EDGE:
                qty = min(sell_cap, bid_qty)
                if qty > 0:
                    orders.append(Order(product, bid, -qty))
                    sell_cap -= qty

        # Quote inside the spread with inventory skew.
        if buy_cap > 0 and (best_bid is not None or best_ask is not None):
            if best_bid is not None:
                bid_price = min(int(math.floor(reservation - self.ASH_PASSIVE_EDGE)), best_bid + 1)
            else:
                bid_price = int(math.floor(reservation - self.ASH_PASSIVE_EDGE))

            if best_ask is None or bid_price < best_ask:
                qty = min(buy_cap, self.ASH_PASSIVE_SIZE)
                if qty > 0:
                    orders.append(Order(product, bid_price, qty))

        if sell_cap > 0 and (best_bid is not None or best_ask is not None):
            if best_ask is not None:
                ask_price = max(int(math.ceil(reservation + self.ASH_PASSIVE_EDGE)), best_ask - 1)
            else:
                ask_price = int(math.ceil(reservation + self.ASH_PASSIVE_EDGE))

            if best_bid is None or ask_price > best_bid:
                qty = min(sell_cap, self.ASH_PASSIVE_SIZE)
                if qty > 0:
                    orders.append(Order(product, ask_price, -qty))

        return orders

    def run(self, state: TradingState):
        memory = self._load_memory(state.traderData)
        result: Dict[str, List[Order]] = {}

        for product, order_depth in state.order_depths.items():
            if product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_pepper(state, order_depth, memory)
            elif product == "ASH_COATED_OSMIUM":
                result[product] = self._trade_ash(state, order_depth, memory)
            else:
                result[product] = []

        trader_data = json.dumps(memory, separators=(",", ":"))
        conversions = 0
        return result, conversions, trader_data
