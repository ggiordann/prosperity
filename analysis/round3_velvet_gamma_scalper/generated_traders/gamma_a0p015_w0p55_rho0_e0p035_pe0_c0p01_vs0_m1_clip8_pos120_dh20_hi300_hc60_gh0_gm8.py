import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    """No-lookahead Round 3 Velvetfruit gamma scalper.

    The strategy buys VEV calls only when a past-only realized-volatility
    forecast is above executable ask IV by enough to pay for option and hedge
    costs.  RV state is updated after orders are created, so the current tick's
    return can only affect the next tick's decision.
    """

    UNDERLYING = "VELVETFRUIT_EXTRACT"
    STRIKES = (5000, 5100, 5200, 5300, 5400, 5500)
    LIMITS: Dict[str, int] = {
        "VELVETFRUIT_EXTRACT": 200,
        "VEV_4000": 300,
        "VEV_4500": 300,
        "VEV_5000": 300,
        "VEV_5100": 300,
        "VEV_5200": 300,
        "VEV_5300": 300,
        "VEV_5400": 300,
        "VEV_5500": 300,
        "VEV_6000": 300,
        "VEV_6500": 300,
    }

    TTE_YEARS = 5.0 / 365.0
    OBSERVATIONS_PER_DAY = 10_000
    ANNUALIZATION = OBSERVATIONS_PER_DAY * 365.0

    RV_ALPHA = 0.015
    RV_WARMUP_RETURNS = 50
    RV_WEIGHT = 0.55
    FORECAST_RHO = 0.0
    MIN_VOL_EDGE = 0.035
    MIN_PRICE_EDGE = 0.0
    COST_BUFFER = 0.01
    EXIT_VOL_EDGE = 0.005
    VEGA_CLIP_SCALE = 0.0

    MONEYNESS_LIMIT = 1.0
    MAX_OPTION_CLIP = 8
    MAX_LONG_OPTION_POSITION = 120
    ALLOW_SHORT_GAMMA = False
    MAX_SHORT_OPTION_POSITION = 0

    DELTA_HEDGE_THRESHOLD = 20
    HEDGE_INTERVAL_TICKS = 300
    MAX_HEDGE_CLIP = 60
    GAMMA_HEDGE_SENSITIVITY = 0.0
    GAMMA_HEDGE_MIN_THRESHOLD = 8

    MIN_IV = 0.01
    MAX_IV = 5.0

    def run(self, state: TradingState):
        orders_by_product: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        data = self.load_state(state.traderData)

        underlying_depth = state.order_depths.get(self.UNDERLYING)
        spot = self.mid_price(underlying_depth)
        if spot is None:
            return orders_by_product, 0, self.dump_state(data)

        rv_forecast = self.rv_forecast(data)
        option_marks = self.option_marks(state.order_depths, spot)
        iv_anchor = self.iv_anchor(option_marks)

        if rv_forecast is not None and iv_anchor is not None:
            raw_forecast_vol = self.RV_WEIGHT * rv_forecast + (1.0 - self.RV_WEIGHT) * iv_anchor
            forecast_vol = self.smoothed_forecast(data, raw_forecast_vol)
            for mark in option_marks:
                product = mark["product"]
                depth = state.order_depths.get(product)
                if depth is None:
                    continue
                position = int(state.position.get(product, 0))
                orders_by_product[product] = self.trade_option(
                    depth=depth,
                    product=product,
                    position=position,
                    ask_iv=mark["ask_iv"],
                    bid_iv=mark["bid_iv"],
                    ask_vega=mark["ask_vega"],
                    bid_vega=mark["bid_vega"],
                    forecast_vol=forecast_vol,
                )

            hedge_orders, hedged = self.hedge_delta(
                state=state,
                underlying_depth=underlying_depth,
                spot=spot,
                vol_for_delta=max(self.MIN_IV, iv_anchor),
                last_hedge_timestamp=int(data.get("last_hedge_timestamp", -10**9)),
            )
            orders_by_product[self.UNDERLYING] = hedge_orders
            if hedged:
                data["last_hedge_timestamp"] = int(state.timestamp)

        self.update_rv_state(data, spot)
        return orders_by_product, 0, self.dump_state(data)

    @staticmethod
    def load_state(raw: str):
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def dump_state(data) -> str:
        return json.dumps(data, separators=(",", ":"))

    @staticmethod
    def best_bid_ask(order_depth: Optional[OrderDepth]) -> Tuple[Optional[int], Optional[int]]:
        if order_depth is None:
            return None, None
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    @classmethod
    def mid_price(cls, order_depth: Optional[OrderDepth]) -> Optional[float]:
        best_bid, best_ask = cls.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None or best_bid >= best_ask:
            return None
        return 0.5 * (best_bid + best_ask)

    @staticmethod
    def normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    @staticmethod
    def normal_pdf(x: float) -> float:
        return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

    @classmethod
    def black_scholes_call(cls, spot: float, strike: float, volatility: float) -> float:
        if volatility <= 0.0:
            return max(spot - strike, 0.0)
        vol_sqrt_t = volatility * math.sqrt(cls.TTE_YEARS)
        if vol_sqrt_t <= 0.0:
            return max(spot - strike, 0.0)
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * cls.TTE_YEARS) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        return spot * cls.normal_cdf(d1) - strike * cls.normal_cdf(d2)

    @classmethod
    def black_scholes_delta(cls, spot: float, strike: float, volatility: float) -> float:
        volatility = max(cls.MIN_IV, volatility)
        vol_sqrt_t = volatility * math.sqrt(cls.TTE_YEARS)
        if vol_sqrt_t <= 0.0:
            return 1.0 if spot > strike else 0.0
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * cls.TTE_YEARS) / vol_sqrt_t
        return cls.normal_cdf(d1)

    @classmethod
    def black_scholes_vega(cls, spot: float, strike: float, volatility: float) -> float:
        volatility = max(cls.MIN_IV, volatility)
        vol_sqrt_t = volatility * math.sqrt(cls.TTE_YEARS)
        if spot <= 0.0 or strike <= 0.0 or vol_sqrt_t <= 0.0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * cls.TTE_YEARS) / vol_sqrt_t
        return spot * math.sqrt(cls.TTE_YEARS) * cls.normal_pdf(d1)

    @classmethod
    def black_scholes_gamma(cls, spot: float, strike: float, volatility: float) -> float:
        volatility = max(cls.MIN_IV, volatility)
        vol_sqrt_t = volatility * math.sqrt(cls.TTE_YEARS)
        if spot <= 0.0 or strike <= 0.0 or vol_sqrt_t <= 0.0:
            return 0.0
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * cls.TTE_YEARS) / vol_sqrt_t
        return cls.normal_pdf(d1) / (spot * vol_sqrt_t)

    @classmethod
    def implied_volatility(cls, call_price: float, spot: float, strike: float) -> float:
        if not all(math.isfinite(value) for value in (call_price, spot, strike)):
            return float("nan")
        if call_price < 0.0 or spot <= 0.0 or strike <= 0.0:
            return float("nan")

        intrinsic = max(spot - strike, 0.0)
        if call_price < intrinsic - 1e-7 or call_price > spot + 1e-7:
            return float("nan")
        if abs(call_price - intrinsic) <= 1e-7:
            return 0.0

        low = 1e-6
        high = cls.MAX_IV
        while cls.black_scholes_call(spot, strike, high) < call_price and high < 20.0:
            high *= 2.0
        if high >= 20.0 and cls.black_scholes_call(spot, strike, high) < call_price:
            return float("nan")

        for _ in range(60):
            mid = 0.5 * (low + high)
            model_price = cls.black_scholes_call(spot, strike, mid)
            if abs(model_price - call_price) <= 1e-7:
                return mid
            if model_price < call_price:
                low = mid
            else:
                high = mid
        return 0.5 * (low + high)

    @classmethod
    def moneyness(cls, spot: float, strike: float) -> float:
        return math.log(strike / spot) / math.sqrt(cls.TTE_YEARS)

    @classmethod
    def option_marks(cls, order_depths: Dict[str, OrderDepth], spot: float) -> List[dict]:
        marks: List[dict] = []
        for strike in cls.STRIKES:
            product = f"VEV_{strike}"
            depth = order_depths.get(product)
            best_bid, best_ask = cls.best_bid_ask(depth)
            if best_bid is None or best_ask is None or best_bid >= best_ask:
                continue
            if abs(cls.moneyness(spot, strike)) > cls.MONEYNESS_LIMIT:
                continue

            bid_iv = cls.implied_volatility(float(best_bid), spot, float(strike))
            ask_iv = cls.implied_volatility(float(best_ask), spot, float(strike))
            mid_iv = cls.implied_volatility(0.5 * (best_bid + best_ask), spot, float(strike))
            if not math.isfinite(bid_iv) or not math.isfinite(ask_iv) or not math.isfinite(mid_iv):
                continue
            bid_vega = cls.black_scholes_vega(spot, float(strike), bid_iv)
            ask_vega = cls.black_scholes_vega(spot, float(strike), ask_iv)

            marks.append(
                {
                    "product": product,
                    "strike": strike,
                    "bid_iv": bid_iv,
                    "ask_iv": ask_iv,
                    "mid_iv": mid_iv,
                    "bid_vega": bid_vega,
                    "ask_vega": ask_vega,
                }
            )
        return marks

    @staticmethod
    def iv_anchor(option_marks: List[dict]) -> Optional[float]:
        vols = sorted(mark["mid_iv"] for mark in option_marks if mark["mid_iv"] > 0.0)
        if not vols:
            return None
        midpoint = len(vols) // 2
        if len(vols) % 2:
            return float(vols[midpoint])
        return 0.5 * (vols[midpoint - 1] + vols[midpoint])

    @classmethod
    def rv_forecast(cls, data) -> Optional[float]:
        returns_seen = int(data.get("returns_seen", 0))
        rv_var = data.get("rv_var")
        if returns_seen < cls.RV_WARMUP_RETURNS or rv_var is None:
            return None
        variance = max(0.0, float(rv_var))
        return math.sqrt(variance * cls.ANNUALIZATION)

    @classmethod
    def smoothed_forecast(cls, data, raw_forecast_vol: float) -> float:
        previous = data.get("forecast_vol")
        forecast = raw_forecast_vol
        if (
            cls.FORECAST_RHO > 0.0
            and previous is not None
            and math.isfinite(float(previous))
            and float(previous) > 0.0
        ):
            rho = max(0.0, min(0.99, cls.FORECAST_RHO))
            forecast = rho * float(previous) + (1.0 - rho) * raw_forecast_vol
        data["forecast_vol"] = float(forecast)
        return float(forecast)

    @classmethod
    def update_rv_state(cls, data, spot: float) -> None:
        previous_mid = data.get("previous_mid")
        if previous_mid is not None and previous_mid > 0.0 and spot > 0.0:
            log_return = math.log(spot / float(previous_mid))
            squared_return = log_return * log_return
            previous_var = data.get("rv_var")
            if previous_var is None:
                data["rv_var"] = squared_return
            else:
                data["rv_var"] = cls.RV_ALPHA * squared_return + (1.0 - cls.RV_ALPHA) * float(previous_var)
            data["returns_seen"] = int(data.get("returns_seen", 0)) + 1
        data["previous_mid"] = float(spot)

    @classmethod
    def buy_capacity(cls, product: str, position: int) -> int:
        return max(0, min(cls.LIMITS[product], cls.MAX_LONG_OPTION_POSITION) - position)

    @classmethod
    def sell_capacity(cls, product: str, position: int) -> int:
        short_limit = min(cls.LIMITS[product], cls.MAX_SHORT_OPTION_POSITION)
        return max(0, position + short_limit)

    @classmethod
    def trade_option(
        cls,
        *,
        depth: OrderDepth,
        product: str,
        position: int,
        ask_iv: float,
        bid_iv: float,
        ask_vega: float,
        bid_vega: float,
        forecast_vol: float,
    ) -> List[Order]:
        orders: List[Order] = []
        vol_edge = forecast_vol - ask_iv
        long_edge = vol_edge - cls.COST_BUFFER
        price_edge = max(0.0, ask_vega * vol_edge)

        if position > 0 and forecast_vol - bid_iv < cls.EXIT_VOL_EDGE:
            sell_qty = min(position, cls.MAX_OPTION_CLIP)
            best_bid = max(depth.buy_orders) if depth.buy_orders else None
            if best_bid is not None and sell_qty > 0:
                bid_qty = max(0, int(depth.buy_orders[best_bid]))
                qty = min(sell_qty, bid_qty)
                if qty > 0:
                    orders.append(Order(product, int(best_bid), -int(qty)))
            return orders

        if long_edge > cls.MIN_VOL_EDGE and price_edge >= cls.MIN_PRICE_EDGE and depth.sell_orders:
            best_ask = min(depth.sell_orders)
            ask_qty = abs(int(depth.sell_orders[best_ask]))
            clip = cls.MAX_OPTION_CLIP
            if cls.VEGA_CLIP_SCALE > 0.0:
                clip = min(clip, max(1, 1 + int(price_edge * cls.VEGA_CLIP_SCALE)))
            qty = min(clip, cls.buy_capacity(product, position), ask_qty)
            if qty > 0:
                orders.append(Order(product, int(best_ask), int(qty)))
            return orders

        if cls.ALLOW_SHORT_GAMMA and bid_iv - forecast_vol - cls.COST_BUFFER > cls.MIN_VOL_EDGE:
            best_bid = max(depth.buy_orders) if depth.buy_orders else None
            if best_bid is not None:
                bid_qty = max(0, int(depth.buy_orders[best_bid]))
                short_price_edge = max(0.0, bid_vega * (bid_iv - forecast_vol))
                if short_price_edge < cls.MIN_PRICE_EDGE:
                    return orders
                qty = min(cls.MAX_OPTION_CLIP, cls.sell_capacity(product, position), bid_qty)
                if qty > 0:
                    orders.append(Order(product, int(best_bid), -int(qty)))
        return orders

    @classmethod
    def option_delta_position(cls, state: TradingState, spot: float, vol_for_delta: float) -> float:
        total = 0.0
        for strike in cls.STRIKES:
            product = f"VEV_{strike}"
            position = int(state.position.get(product, 0))
            if position == 0:
                continue
            total += position * cls.black_scholes_delta(spot, float(strike), vol_for_delta)
        return total

    @classmethod
    def option_abs_gamma_position(cls, state: TradingState, spot: float, vol_for_delta: float) -> float:
        total = 0.0
        for strike in cls.STRIKES:
            product = f"VEV_{strike}"
            position = int(state.position.get(product, 0))
            if position == 0:
                continue
            total += abs(position) * cls.black_scholes_gamma(spot, float(strike), vol_for_delta)
        return total

    @classmethod
    def dynamic_hedge_threshold(cls, abs_gamma_position: float) -> int:
        threshold = cls.DELTA_HEDGE_THRESHOLD
        if cls.GAMMA_HEDGE_SENSITIVITY > 0.0 and abs_gamma_position > 0.0:
            threshold = int(round(threshold / (1.0 + cls.GAMMA_HEDGE_SENSITIVITY * abs_gamma_position)))
        return max(cls.GAMMA_HEDGE_MIN_THRESHOLD, threshold)

    @classmethod
    def hedge_delta(
        cls,
        *,
        state: TradingState,
        underlying_depth: OrderDepth,
        spot: float,
        vol_for_delta: float,
        last_hedge_timestamp: int,
    ) -> Tuple[List[Order], bool]:
        option_delta = cls.option_delta_position(state, spot, vol_for_delta)
        abs_gamma_position = cls.option_abs_gamma_position(state, spot, vol_for_delta)
        underlying_position = int(state.position.get(cls.UNDERLYING, 0))
        target_underlying = int(round(-option_delta))
        target_underlying = max(-cls.LIMITS[cls.UNDERLYING], min(cls.LIMITS[cls.UNDERLYING], target_underlying))
        adjustment = target_underlying - underlying_position

        if abs(adjustment) < cls.dynamic_hedge_threshold(abs_gamma_position):
            return [], False
        if int(state.timestamp) - last_hedge_timestamp < cls.HEDGE_INTERVAL_TICKS:
            return [], False

        orders: List[Order] = []
        if adjustment > 0:
            remaining = min(adjustment, cls.MAX_HEDGE_CLIP, cls.LIMITS[cls.UNDERLYING] - underlying_position)
            for ask_price, ask_volume in sorted(underlying_depth.sell_orders.items()):
                if remaining <= 0:
                    break
                qty = min(remaining, abs(int(ask_volume)))
                if qty > 0:
                    orders.append(Order(cls.UNDERLYING, int(ask_price), int(qty)))
                    remaining -= qty
        elif adjustment < 0:
            remaining = min(-adjustment, cls.MAX_HEDGE_CLIP, cls.LIMITS[cls.UNDERLYING] + underlying_position)
            for bid_price, bid_volume in sorted(underlying_depth.buy_orders.items(), reverse=True):
                if remaining <= 0:
                    break
                qty = min(remaining, max(0, int(bid_volume)))
                if qty > 0:
                    orders.append(Order(cls.UNDERLYING, int(bid_price), -int(qty)))
                    remaining -= qty

        return orders, bool(orders)
