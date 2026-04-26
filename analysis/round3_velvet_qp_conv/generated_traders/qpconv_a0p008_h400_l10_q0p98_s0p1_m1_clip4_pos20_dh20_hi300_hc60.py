import json
import math
from typing import Dict, List, Optional, Tuple

from datamodel import Order, OrderDepth, TradingState


class Trader:
    """Generated QP-conv long-gamma Velvetfruit stat-arb trader."""

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
    MIN_IV = 0.01
    MAX_IV = 5.0

    RV_ALPHA = 0.008
    MONEYNESS_LIMIT = 1.0
    MAX_OPTION_CLIP = 4
    MAX_LONG_OPTION_POSITION = 20
    DELTA_HEDGE_THRESHOLD = 20
    HEDGE_INTERVAL_TICKS = 300
    MAX_HEDGE_CLIP = 60
    THRESHOLD = 0.1
    EXIT_THRESHOLD = 0.025
    FEATURE_MEANS = [0.0, 0.1235311697579501, -0.009319342436741176, -0.0011670476495054172, 0.0105373745782509, 0.23765308367444274, 0.49110657947162684, 43500.81063298922, 163.39893052097145, 2.859920308189746, -4.184614522456796e-07, -1.9168586692093303e-07, -2.516636714340993e-07, 0.00016356791367335127, 0.2766182302710259, 0.12447483052629625, 7.638490668443846e-06]
    FEATURE_SCALES = [1.0, 0.035931751408607146, 0.013366614655725353, 0.008405921476089744, 0.2719697545499749, 0.13266346698697526, 0.3097855584565884, 16169.34690386845, 60.25168332161815, 1.6986508208064297, 0.00012093082009857173, 5.245485107027529e-05, 9.389005770672807e-05, 4.4193250355731536e-05, 0.017368955235118638, 0.0078675139791236, 0.0031355313674559246]
    FEATURE_WEIGHTS = [-1.3539776659966132, 0.031564336679654456, -0.29097513046354667, -0.23515097629694343, 0.6374229435582079, -0.35571207735177385, 0.6201110109399333, 0.5872297453485665, -0.8383890520996952, -1.0048006009983077, 0.07056425041843545, -0.016639182141130974, -0.03413389197028327, -0.02044170281505613, 1.5734857568176603, -1.4782983327746995, -0.13355684185098723]
    KERNELS = {'ret_k3': [0.5, 0.3, 0.2], 'ret_k12': [0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333], 'ret_fast_slow': [0.35, 0.25, 0.15, 0.1, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05], 'absret_k12': [0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333, 0.08333333333333333], 'anchor_k3': [0.5, 0.3, 0.2], 'anchor_fast_slow': [0.35, 0.25, 0.15, 0.1, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05], 'anchor_momo': [1.0, -1.0]}

    def run(self, state: TradingState):
        orders_by_product: Dict[str, List[Order]] = {product: [] for product in state.order_depths}
        data = self.load_state(state.traderData)

        underlying_depth = state.order_depths.get(self.UNDERLYING)
        spot = self.mid_price(underlying_depth)
        if spot is None:
            return orders_by_product, 0, self.dump_state(data)

        self.update_spot_state(data, spot)
        option_marks = self.option_marks(state.order_depths, spot)
        anchor = self.iv_anchor(option_marks)
        if anchor is None:
            return orders_by_product, 0, self.dump_state(data)
        self.update_anchor_state(data, anchor)

        rv = self.rv_forecast(data)
        if rv is not None:
            for mark in option_marks:
                if abs(mark["moneyness"]) > self.MONEYNESS_LIMIT:
                    continue
                product = mark["product"]
                depth = state.order_depths.get(product)
                if depth is None:
                    continue
                position = int(state.position.get(product, 0))
                score = self.score_mark(data, mark, rv, anchor)
                orders_by_product[product] = self.trade_option(depth, product, position, score)

            hedge_orders, hedged = self.hedge_delta(
                state=state,
                underlying_depth=underlying_depth,
                spot=spot,
                vol_for_delta=max(self.MIN_IV, anchor),
                last_hedge_timestamp=int(data.get("last_hedge_timestamp", -10**9)),
            )
            orders_by_product[self.UNDERLYING] = hedge_orders
            if hedged:
                data["last_hedge_timestamp"] = int(state.timestamp)

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
        for _ in range(50):
            mid = 0.5 * (low + high)
            price = cls.black_scholes_call(spot, strike, mid)
            if abs(price - call_price) <= 1e-7:
                return mid
            if price < call_price:
                low = mid
            else:
                high = mid
        return 0.5 * (low + high)

    @classmethod
    def update_spot_state(cls, data, spot: float) -> None:
        previous_mid = data.get("previous_mid")
        log_return = 0.0
        if previous_mid is not None and previous_mid > 0.0 and spot > 0.0:
            log_return = math.log(spot / float(previous_mid))
            squared = log_return * log_return
            previous_var = data.get("rv_var")
            if previous_var is None:
                data["rv_var"] = squared
            else:
                data["rv_var"] = cls.RV_ALPHA * squared + (1.0 - cls.RV_ALPHA) * float(previous_var)
            data["returns_seen"] = int(data.get("returns_seen", 0)) + 1
        data["previous_mid"] = float(spot)
        returns = data.get("returns", [])
        returns.append(float(log_return))
        data["returns"] = returns[-32:]

    @classmethod
    def update_anchor_state(cls, data, anchor: float) -> None:
        anchors = data.get("anchors", [])
        anchors.append(float(anchor))
        data["anchors"] = anchors[-32:]

    @classmethod
    def rv_forecast(cls, data) -> Optional[float]:
        if int(data.get("returns_seen", 0)) < 50 or data.get("rv_var") is None:
            return None
        return math.sqrt(max(0.0, float(data["rv_var"])) * cls.ANNUALIZATION)

    @classmethod
    def moneyness(cls, spot: float, strike: float) -> float:
        return math.log(strike / spot) / math.sqrt(cls.TTE_YEARS)

    @classmethod
    def option_marks(cls, order_depths: Dict[str, OrderDepth], spot: float) -> List[dict]:
        marks = []
        for strike in cls.STRIKES:
            product = f"VEV_{strike}"
            depth = order_depths.get(product)
            best_bid, best_ask = cls.best_bid_ask(depth)
            if best_bid is None or best_ask is None or best_bid >= best_ask:
                continue
            bid_iv = cls.implied_volatility(float(best_bid), spot, float(strike))
            ask_iv = cls.implied_volatility(float(best_ask), spot, float(strike))
            mid_iv = cls.implied_volatility(0.5 * (best_bid + best_ask), spot, float(strike))
            if not math.isfinite(bid_iv) or not math.isfinite(ask_iv) or not math.isfinite(mid_iv):
                continue
            delta = cls.black_scholes_delta(spot, float(strike), mid_iv)
            gamma = cls.black_scholes_gamma(spot, float(strike), mid_iv)
            vega = cls.black_scholes_vega(spot, float(strike), mid_iv)
            marks.append(
                {
                    "product": product,
                    "strike": strike,
                    "best_bid": int(best_bid),
                    "best_ask": int(best_ask),
                    "bid_iv": bid_iv,
                    "ask_iv": ask_iv,
                    "mid_iv": mid_iv,
                    "delta": delta,
                    "gamma": gamma,
                    "vega": vega,
                    "moneyness": cls.moneyness(spot, float(strike)),
                    "spread": float(best_ask - best_bid),
                    "spot": spot,
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
    def conv(cls, values, kernel_name: str) -> float:
        kernel = cls.KERNELS[kernel_name]
        out = 0.0
        for offset, weight in enumerate(kernel):
            index = len(values) - 1 - offset
            if index < 0:
                break
            out += float(values[index]) * float(weight)
        return out

    @classmethod
    def score_mark(cls, data, mark: dict, rv: float, anchor: float) -> float:
        returns = data.get("returns", [])
        anchors = data.get("anchors", [])
        features = [
            1.0,
            rv - mark["ask_iv"],
            anchor - mark["ask_iv"],
            mark["mid_iv"] - anchor,
            mark["moneyness"],
            abs(mark["moneyness"]),
            mark["delta"],
            mark["gamma"] * mark["spot"] * mark["spot"],
            mark["vega"],
            mark["spread"],
            cls.conv(returns, "ret_k3"),
            cls.conv(returns, "ret_k12"),
            cls.conv(returns, "ret_fast_slow"),
            cls.conv([abs(value) for value in returns], "absret_k12"),
            cls.conv(anchors, "anchor_k3"),
            cls.conv(anchors, "anchor_fast_slow"),
            cls.conv(anchors, "anchor_momo"),
        ]
        score = 0.0
        for value, mean, scale, weight in zip(features, cls.FEATURE_MEANS, cls.FEATURE_SCALES, cls.FEATURE_WEIGHTS):
            score += ((value - mean) / scale) * weight
        return float(score)

    @classmethod
    def buy_capacity(cls, product: str, position: int) -> int:
        return max(0, min(cls.LIMITS[product], cls.MAX_LONG_OPTION_POSITION) - position)

    @classmethod
    def trade_option(cls, depth: OrderDepth, product: str, position: int, score: float) -> List[Order]:
        orders = []
        if position > 0 and score < cls.EXIT_THRESHOLD and depth.buy_orders:
            best_bid = max(depth.buy_orders)
            qty = min(position, cls.MAX_OPTION_CLIP, max(0, int(depth.buy_orders[best_bid])))
            if qty > 0:
                orders.append(Order(product, int(best_bid), -int(qty)))
            return orders
        if score <= cls.THRESHOLD or not depth.sell_orders:
            return orders
        best_ask = min(depth.sell_orders)
        qty = min(cls.MAX_OPTION_CLIP, cls.buy_capacity(product, position), abs(int(depth.sell_orders[best_ask])))
        if qty > 0:
            orders.append(Order(product, int(best_ask), int(qty)))
        return orders

    @classmethod
    def option_delta_position(cls, state: TradingState, spot: float, vol_for_delta: float) -> float:
        total = 0.0
        for strike in cls.STRIKES:
            product = f"VEV_{strike}"
            position = int(state.position.get(product, 0))
            if position:
                total += position * cls.black_scholes_delta(spot, float(strike), vol_for_delta)
        return total

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
        underlying_position = int(state.position.get(cls.UNDERLYING, 0))
        target_underlying = int(round(-option_delta))
        target_underlying = max(-cls.LIMITS[cls.UNDERLYING], min(cls.LIMITS[cls.UNDERLYING], target_underlying))
        adjustment = target_underlying - underlying_position
        if abs(adjustment) < cls.DELTA_HEDGE_THRESHOLD:
            return [], False
        if int(state.timestamp) - last_hedge_timestamp < cls.HEDGE_INTERVAL_TICKS:
            return [], False
        orders = []
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
