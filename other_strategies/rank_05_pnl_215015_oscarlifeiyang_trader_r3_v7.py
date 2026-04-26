"""Round 3 improved trader v7 — best backtest result: 158,098.

Updated best backtest result: 216,732. The first line is stale because of mojibake in the original header.

Key changes vs baseline (133,168):
1. VEV_5300 EDGE = 4 (was 1): stops systematic losses (-6,530 baseline)
2. VEV_5100 SIZE = 35 (was 20): grab larger fills when book is deep
3. Delta hedge REMOVED: delta hedge cost the strategy -11,628 over 3 days.
4. HYDROGEL_PACK uses EMA regime switching between fair 10009 and 10000.
5. VELVETFRUIT_EXTRACT uses a slower EMA and tighter taker edge for mean reversion.
   VelvetMM earns spread on VELVETFRUIT_EXTRACT by itself; adding a taker
   hedge on top paid spread twice and neutralized long-delta option gains
   during the underlying's upward trend.

RISK NOTE: Without delta hedging, the strategy carries long delta from
option positions (~100-200 units). If VELVETFRUIT_EXTRACT falls significantly
on a given day, that unhedged delta will produce losses proportional to
position_delta × price_move. In this backtest's 3 days the underlying
trended flat to slightly up, making this profitable. If the actual R3
submission data has a large downward move, losses will be larger.
"""

import json
import math

try:
    from datamodel import Order, OrderDepth, TradingState
except ImportError:
    from prosperity4bt.datamodel import Order, OrderDepth, TradingState


VEV_STRIKES = {
    "VEV_4000": 4000,
    "VEV_4500": 4500,
    "VEV_5000": 5000,
    "VEV_5100": 5100,
    "VEV_5200": 5200,
    "VEV_5300": 5300,
    "VEV_5400": 5400,
    "VEV_5500": 5500,
    "VEV_6000": 6000,
    "VEV_6500": 6500,
}

LIMITS = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    **{sym: 300 for sym in VEV_STRIKES},
}

STRIKE_EDGE = {sym: 1 for sym in VEV_STRIKES}
STRIKE_EDGE["VEV_5300"] = 4
STRIKE_EDGE["VEV_5100"] = 2

STRIKE_SIZE = {sym: 20 for sym in VEV_STRIKES}
STRIKE_SIZE["VEV_5100"] = 35

LIVE_R3_TTE_DAYS = 5
HISTORICAL_R3_START_TTE_DAYS = 8


def _ncdf(x: float) -> float:
    sign = 1.0 if x >= 0 else -1.0
    x = abs(x)
    t = 1.0 / (1.0 + 0.2316419 * x)
    p = t * (0.319381530 + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))))
    return (1.0 + sign) / 2.0 - sign * math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi) * p


def bs_call(S: float, K: float, T: float, sigma: float) -> float:
    if T <= 0:
        return max(0.0, S - K)
    if sigma <= 0 or S <= 0:
        return max(0.0, S - K)
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    return S * _ncdf(d1) - K * _ncdf(d2)


def bs_delta(S: float, K: float, T: float, sigma: float) -> float:
    if T <= 0:
        return 1.0 if S > K else 0.0
    if sigma <= 0 or S <= 0:
        return 1.0 if S > K else 0.0
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * sqrt_T)
    return _ncdf(d1)


def bs_iv(price: float, S: float, K: float, T: float) -> float | None:
    intrinsic = max(0.0, S - K)
    if T <= 0 or price < intrinsic - 1e-6:
        return None
    lo, hi = 1e-6, 5.0
    for _ in range(50):
        mid = (lo + hi) / 2.0
        val = bs_call(S, K, T, mid)
        if abs(val - price) < 1e-4:
            return mid
        if val < price:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def mid_price(depth: OrderDepth) -> float | None:
    if not depth.buy_orders or not depth.sell_orders:
        return None
    return (max(depth.buy_orders) + min(depth.sell_orders)) / 2.0


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def current_tte_days() -> int:
    try:
        os = __import__("os")
        backtest_day = os.environ.get("PROSPERITY4BT_DAY")
    except Exception:
        backtest_day = None

    if backtest_day is None:
        return LIVE_R3_TTE_DAYS

    try:
        day = int(backtest_day)
    except ValueError:
        return LIVE_R3_TTE_DAYS

    return max(1, HISTORICAL_R3_START_TTE_DAYS - day)


class HydrogelMM:
    PRODUCT = "HYDROGEL_PACK"
    FAIR = 10009
    NEUTRAL_FAIR = 10005
    DEFENSIVE_FAIR = 10000
    FAST_ALPHA = 0.20
    SLOW_ALPHA = 0.03
    REGIME_GAP = 1.25
    TAKE_EDGE = 4
    QUOTE_EDGE = 6
    SIZE = 25

    @classmethod
    def fair_value(cls, depth: OrderDepth, td: dict) -> float:
        mid = mid_price(depth)
        if mid is None:
            return cls.FAIR

        fast = cls.FAST_ALPHA * mid + (1.0 - cls.FAST_ALPHA) * td.get("hydrogel_fast", mid)
        slow = cls.SLOW_ALPHA * mid + (1.0 - cls.SLOW_ALPHA) * td.get("hydrogel_slow", mid)
        td["hydrogel_fast"] = fast
        td["hydrogel_slow"] = slow

        trend = fast - slow
        if trend < -cls.REGIME_GAP:
            return cls.DEFENSIVE_FAIR
        if trend > cls.REGIME_GAP:
            return cls.FAIR
        return cls.NEUTRAL_FAIR

    @classmethod
    def trade(cls, depth: OrderDepth, position: int, td: dict) -> list[Order]:
        orders: list[Order] = []
        limit = LIMITS[cls.PRODUCT]
        buy_cap = max(0, limit - position)
        sell_cap = max(0, limit + position)
        fair = cls.fair_value(depth, td)

        for ask in sorted(depth.sell_orders):
            if ask >= fair - cls.TAKE_EDGE or buy_cap <= 0:
                break
            qty = min(-depth.sell_orders[ask], buy_cap, 30)
            orders.append(Order(cls.PRODUCT, ask, qty))
            buy_cap -= qty

        for bid in sorted(depth.buy_orders, reverse=True):
            if bid <= fair + cls.TAKE_EDGE or sell_cap <= 0:
                break
            qty = min(depth.buy_orders[bid], sell_cap, 30)
            orders.append(Order(cls.PRODUCT, bid, -qty))
            sell_cap -= qty

        if buy_cap > 0:
            orders.append(Order(cls.PRODUCT, int(round(fair - cls.QUOTE_EDGE)), min(buy_cap, cls.SIZE)))
        if sell_cap > 0:
            orders.append(Order(cls.PRODUCT, int(round(fair + cls.QUOTE_EDGE)), -min(sell_cap, cls.SIZE)))

        return orders


class VelvetMM:
    """Market maker on VELVETFRUIT_EXTRACT. No delta hedge — VelvetMM alone is profitable."""
    PRODUCT = "VELVETFRUIT_EXTRACT"
    ALPHA = 0.175
    TAKE_EDGE = 1
    QUOTE_EDGE = 5
    SIZE = 20

    @classmethod
    def fair_value(cls, depth: OrderDepth, td: dict) -> float | None:
        mid = mid_price(depth)
        if mid is None:
            return td.get("velvet_fair")
        prev = td.get("velvet_fair", mid)
        fair = cls.ALPHA * mid + (1.0 - cls.ALPHA) * prev
        td["velvet_fair"] = fair
        return fair

    @classmethod
    def trade(cls, depth: OrderDepth, position: int, td: dict) -> list[Order]:
        fair = cls.fair_value(depth, td)
        if fair is None:
            return []
        orders: list[Order] = []
        limit = LIMITS[cls.PRODUCT]
        buy_cap = max(0, limit - position)
        sell_cap = max(0, limit + position)

        for ask in sorted(depth.sell_orders):
            if ask >= fair - cls.TAKE_EDGE or buy_cap <= 0:
                break
            qty = min(-depth.sell_orders[ask], buy_cap, 25)
            orders.append(Order(cls.PRODUCT, ask, qty))
            buy_cap -= qty

        for bid in sorted(depth.buy_orders, reverse=True):
            if bid <= fair + cls.TAKE_EDGE or sell_cap <= 0:
                break
            qty = min(depth.buy_orders[bid], sell_cap, 25)
            orders.append(Order(cls.PRODUCT, bid, -qty))
            sell_cap -= qty

        bid_q = int(round(fair - cls.QUOTE_EDGE))
        ask_q = int(round(fair + cls.QUOTE_EDGE))
        if buy_cap > 0:
            orders.append(Order(cls.PRODUCT, bid_q, min(buy_cap, cls.SIZE)))
        if sell_cap > 0:
            orders.append(Order(cls.PRODUCT, ask_q, -min(sell_cap, cls.SIZE)))

        return orders


class VEVOptionTaker:
    SIGMA_ALPHA = 0.08
    DEFAULT_SIGMA = 0.40

    @classmethod
    def calibrate_sigma(cls, order_depths: dict, S: float, T: float, td: dict) -> float:
        ivs: list[float] = []
        for sym, K in VEV_STRIKES.items():
            depth = order_depths.get(sym)
            opt_mid = mid_price(depth) if depth is not None else None
            if opt_mid is None:
                continue
            if abs(K - S) > 450:
                continue
            iv = bs_iv(opt_mid, S, K, T)
            if iv is not None and 0.05 <= iv <= 2.0:
                ivs.append(iv)
        snap_sigma = sorted(ivs)[len(ivs) // 2] if ivs else td.get("sigma", cls.DEFAULT_SIGMA)
        prev = td.get("sigma", snap_sigma)
        sigma = cls.SIGMA_ALPHA * snap_sigma + (1.0 - cls.SIGMA_ALPHA) * prev
        td["sigma"] = sigma
        return sigma

    @classmethod
    def trade_all(cls, order_depths: dict, positions: dict, td: dict) -> dict[str, list[Order]]:
        S = td.get("velvet_fair", 5250.0)
        T = current_tte_days() / 252.0
        sigma = cls.calibrate_sigma(order_depths, S, T, td)

        result: dict[str, list[Order]] = {}

        for sym, K in VEV_STRIKES.items():
            depth = order_depths.get(sym)
            if depth is None:
                result[sym] = []
                continue

            fair = bs_call(S, K, T, sigma)
            edge = STRIKE_EDGE[sym]
            size = STRIKE_SIZE[sym]
            pos = positions.get(sym, 0)
            limit = LIMITS[sym]
            buy_cap = max(0, limit - pos)
            sell_cap = max(0, limit + pos)
            orders: list[Order] = []

            for ask in sorted(depth.sell_orders):
                if ask >= fair - edge or buy_cap <= 0:
                    break
                qty = min(-depth.sell_orders[ask], buy_cap, size)
                orders.append(Order(sym, ask, qty))
                buy_cap -= qty

            for bid in sorted(depth.buy_orders, reverse=True):
                if bid <= fair + edge or sell_cap <= 0:
                    break
                qty = min(depth.buy_orders[bid], sell_cap, size)
                orders.append(Order(sym, bid, -qty))
                sell_cap -= qty

            result[sym] = orders

        return result


class Trader:
    def run(self, state: TradingState):
        try:
            td: dict = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            td = {}

        orders: dict[str, list[Order]] = {}

        if "HYDROGEL_PACK" in state.order_depths:
            orders["HYDROGEL_PACK"] = HydrogelMM.trade(
                state.order_depths["HYDROGEL_PACK"],
                state.position.get("HYDROGEL_PACK", 0),
                td,
            )

        if "VELVETFRUIT_EXTRACT" in state.order_depths:
            orders["VELVETFRUIT_EXTRACT"] = VelvetMM.trade(
                state.order_depths["VELVETFRUIT_EXTRACT"],
                state.position.get("VELVETFRUIT_EXTRACT", 0),
                td,
            )

        vev_orders = VEVOptionTaker.trade_all(state.order_depths, state.position, td)
        orders.update(vev_orders)

        return orders, 0, json.dumps(td, separators=(",", ":"))
