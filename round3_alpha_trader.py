import json
import math
import os
from collections import deque
from datamodel import Order, OrderDepth, TradingState
from typing import Deque, Dict, List, Optional, Tuple


TUNER_ENV_VAR = "ROUND3_ALPHA_TUNER_JSON"


def load_tuner_config() -> Dict[str, float]:
    raw = os.environ.get(TUNER_ENV_VAR, "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


TUNER_CONFIG = load_tuner_config()


def cfg_float(name: str, default: float) -> float:
    value = TUNER_CONFIG.get(name, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


class Trader:
    """Round 3 trader built around the strongest Velvetfruit signals.

    Signal stack:
    - Underlying microprice, imbalance, wall skew, and book slope
    - Voucher microprice and book-shape signals
    - A conservative strike-level residual prior from the option scan
    - Short-horizon mean reversion on the richer voucher strikes
    """

    LIMITS: Dict[str, int] = {
        "HYDROGEL_PACK": 200,
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

    UNDERLYING_PRODUCT = "VELVETFRUIT_EXTRACT"
    OPTION_STRIKES = (4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500)

    # The round-3 fit was trained around a 5-day expiry.
    TTE_YEARS = 5.0 / 365.0

    # Baseline volatility smile used as the pricing anchor.
    SMILE_A = 0.011355
    SMILE_B = 0.013274
    SMILE_C = 0.276731

    # Conservative historical mean residuals from
    # analysis/round3_alpha_sweep/option_price_residuals.csv.
    # Positive means the market traded rich versus the BS fit; negative means cheap.
    RESIDUAL_PRIOR_WEIGHT = 0.20
    OPTION_RESIDUAL_PRIOR: Dict[str, float] = {
        "VEV_4000": -48.325257,
        "VEV_4500": 112.584775,
        "VEV_5000": 21.133109,
        "VEV_5100": -10.994245,
        "VEV_5200": -33.326557,
        "VEV_5300": -39.968616,
        "VEV_5400": -35.045811,
        "VEV_5500": -14.703712,
        "VEV_6000": 46.627911,
        "VEV_6500": 2.018402,
    }

    UNDERLYING_PROFILE = {
        "micro_l3": 1.15,
        "micro_l1": 0.65,
        "imb_l1": 0.75,
        "imb_l3": -0.45,
        "wall": 0.40,
        "depth": -0.25,
        "slope": -0.30,
        "reversion": 0.10,
        "take_size": 12,
        "quote_size": 10,
    }

    HYDROGEL_PROFILE = {
        "micro_l3": 1.35,
        "micro_l1": 0.75,
        "imb_l1": 0.65,
        "imb_l3": -0.75,
        "wall": 0.55,
        "depth": -0.45,
        "slope": 0.55,
        "reversion": 0.10,
        "take_size": 18,
        "quote_size": 12,
    }

    OPTION_PROFILES: Dict[str, Dict[str, float]] = {
        "VEV_4000": {
            "micro_l3": 1.45,
            "micro_l1": 1.00,
            "imb_l1": 0.90,
            "imb_l3": -0.65,
            "wall": 0.80,
            "depth": -0.45,
            "slope": -0.60,
            "reversion": 0.15,
            "take_size": 16,
            "quote_size": 12,
        },
        "VEV_4500": {
            "micro_l3": 1.30,
            "micro_l1": 0.90,
            "imb_l1": 0.80,
            "imb_l3": -0.55,
            "wall": 0.72,
            "depth": -0.40,
            "slope": -0.55,
            "reversion": 0.15,
            "take_size": 14,
            "quote_size": 10,
        },
        "VEV_5000": {
            "micro_l3": 1.10,
            "micro_l1": 0.75,
            "imb_l1": 0.55,
            "imb_l3": -0.30,
            "wall": 0.55,
            "depth": -0.25,
            "slope": -0.35,
            "reversion": 0.20,
            "take_size": 10,
            "quote_size": 8,
        },
        "VEV_5100": {
            "micro_l3": 1.00,
            "micro_l1": 0.70,
            "imb_l1": 0.50,
            "imb_l3": -0.25,
            "wall": 0.50,
            "depth": -0.22,
            "slope": -0.32,
            "reversion": 0.20,
            "take_size": 8,
            "quote_size": 8,
        },
        "VEV_5200": {
            "micro_l3": 1.00,
            "micro_l1": 0.70,
            "imb_l1": 0.55,
            "imb_l3": -0.25,
            "wall": 0.55,
            "depth": -0.22,
            "slope": -0.32,
            "reversion": 0.20,
            "take_size": 8,
            "quote_size": 8,
        },
        "VEV_5300": {
            "micro_l3": 1.10,
            "micro_l1": 0.75,
            "imb_l1": 0.60,
            "imb_l3": -0.30,
            "wall": 0.60,
            "depth": -0.25,
            "slope": -0.38,
            "reversion": 0.20,
            "take_size": 10,
            "quote_size": 8,
        },
        "VEV_5400": {
            "micro_l3": 0.95,
            "micro_l1": 0.65,
            "imb_l1": 0.45,
            "imb_l3": -0.20,
            "wall": 0.55,
            "depth": -0.20,
            "slope": -0.28,
            "reversion": 0.45,
            "take_size": 6,
            "quote_size": 6,
        },
        "VEV_5500": {
            "micro_l3": 0.85,
            "micro_l1": 0.55,
            "imb_l1": 0.35,
            "imb_l3": -0.15,
            "wall": 0.50,
            "depth": -0.18,
            "slope": -0.24,
            "reversion": 0.55,
            "take_size": 4,
            "quote_size": 4,
        },
        "VEV_6000": {
            "micro_l3": 0.35,
            "micro_l1": 0.20,
            "imb_l1": 0.10,
            "imb_l3": -0.05,
            "wall": 0.10,
            "depth": -0.05,
            "slope": -0.05,
            "reversion": 0.05,
            "take_size": 2,
            "quote_size": 2,
        },
        "VEV_6500": {
            "micro_l3": 0.20,
            "micro_l1": 0.10,
            "imb_l1": 0.05,
            "imb_l3": -0.03,
            "wall": 0.05,
            "depth": -0.03,
            "slope": -0.03,
            "reversion": 0.03,
            "take_size": 1,
            "quote_size": 1,
        },
    }

    HISTORY_WINDOW = 12
    REVERSION_WINDOW = 5
    HYDROGEL_SIZE = 8

    def __init__(self):
        self.mid_history: Dict[str, Deque[float]] = {}
        self.residual_prior_weight = cfg_float("residual_prior_weight", self.RESIDUAL_PRIOR_WEIGHT)
        self.underlying_profile = self.apply_profile_scales(
            self.UNDERLYING_PROFILE,
            micro_scale=cfg_float("underlying_micro_scale", 1.0),
            structure_scale=cfg_float("underlying_structure_scale", 1.0),
            reversion_scale=cfg_float("underlying_reversion_scale", 1.0),
            take_scale=cfg_float("underlying_take_scale", 1.0),
            quote_scale=cfg_float("underlying_quote_scale", 1.0),
        )
        self.hydrogel_signal_enabled = cfg_float("hydrogel_signal_enabled", 0.0) >= 0.5
        self.hydrogel_profile = self.apply_profile_scales(
            self.HYDROGEL_PROFILE,
            micro_scale=cfg_float("hydrogel_micro_scale", 1.0),
            structure_scale=cfg_float("hydrogel_structure_scale", 1.0),
            reversion_scale=cfg_float("hydrogel_reversion_scale", 1.0),
            take_scale=cfg_float("hydrogel_take_scale", 1.0),
            quote_scale=cfg_float("hydrogel_quote_scale", 1.0),
        )
        self.option_profiles = {
            product: self.apply_profile_scales(
                profile,
                micro_scale=cfg_float("option_micro_scale", 1.0),
                structure_scale=cfg_float("option_structure_scale", 1.0),
                reversion_scale=cfg_float("option_reversion_scale", 1.0),
                take_scale=cfg_float("option_take_scale", 1.0),
                quote_scale=cfg_float("option_quote_scale", 1.0),
            )
            for product, profile in self.OPTION_PROFILES.items()
        }

    @staticmethod
    def apply_profile_scales(
        profile: Dict[str, float],
        *,
        micro_scale: float,
        structure_scale: float,
        reversion_scale: float,
        take_scale: float,
        quote_scale: float,
    ) -> Dict[str, float]:
        scaled = dict(profile)
        for key in ("micro_l3", "micro_l1"):
            scaled[key] = float(scaled.get(key, 0.0)) * micro_scale
        for key in ("imb_l1", "imb_l3", "wall", "depth", "slope"):
            scaled[key] = float(scaled.get(key, 0.0)) * structure_scale
        scaled["reversion"] = float(scaled.get("reversion", 0.0)) * reversion_scale
        scaled["take_size"] = max(1, int(round(float(scaled.get("take_size", 1)) * take_scale)))
        scaled["quote_size"] = max(1, int(round(float(scaled.get("quote_size", 1)) * quote_scale)))
        return scaled

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {product: [] for product in state.order_depths}

        spot_reference = None
        underlying_depth = state.order_depths.get(self.UNDERLYING_PRODUCT)
        if underlying_depth is not None:
            position = int(state.position.get(self.UNDERLYING_PRODUCT, 0))
            underlying_orders, spot_reference = self.trade_spot(
                self.UNDERLYING_PRODUCT,
                underlying_depth,
                position,
                self.underlying_profile,
            )
            result[self.UNDERLYING_PRODUCT] = underlying_orders

        if spot_reference is None and underlying_depth is not None:
            spot_reference = self.mid_price(underlying_depth)

        if spot_reference is not None:
            for strike in self.OPTION_STRIKES:
                product = f"VEV_{strike}"
                order_depth = state.order_depths.get(product)
                if order_depth is None:
                    continue
                position = int(state.position.get(product, 0))
                result[product] = self.trade_voucher(
                    product,
                    strike,
                    spot_reference,
                    order_depth,
                    position,
                    self.option_profile(product),
                )

        hydrogel_depth = state.order_depths.get("HYDROGEL_PACK")
        if hydrogel_depth is not None:
            position = int(state.position.get("HYDROGEL_PACK", 0))
            if self.hydrogel_signal_enabled:
                hydrogel_orders, _ = self.trade_spot(
                    "HYDROGEL_PACK",
                    hydrogel_depth,
                    position,
                    self.hydrogel_profile,
                )
                result["HYDROGEL_PACK"] = hydrogel_orders
            else:
                result["HYDROGEL_PACK"] = self.passive_hydrogel(hydrogel_depth, position)

        return result, 0, ""

    @staticmethod
    def clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def best_bid_ask(order_depth: Optional[OrderDepth]) -> Tuple[Optional[int], Optional[int]]:
        if order_depth is None:
            return None, None
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    @staticmethod
    def top_levels(order_dict: Dict[int, int], reverse: bool, depth: int) -> List[Tuple[int, int]]:
        prices = sorted(order_dict, reverse=reverse)
        levels: List[Tuple[int, int]] = []
        for price in prices[:depth]:
            volume = int(order_dict[price])
            if volume == 0:
                continue
            levels.append((int(price), abs(volume)))
        return levels

    @classmethod
    def mid_price(cls, order_depth: Optional[OrderDepth]) -> Optional[float]:
        best_bid, best_ask = cls.best_bid_ask(order_depth)
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        return None

    @staticmethod
    def normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes_call(self, spot: float, strike: int, volatility: float) -> float:
        spot = max(spot, 1e-6)
        if volatility <= 0.0:
            return max(spot - strike, 0.0)
        vol_sqrt_t = volatility * math.sqrt(self.TTE_YEARS)
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * self.TTE_YEARS) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        return spot * self.normal_cdf(d1) - strike * self.normal_cdf(d2)

    def smile_volatility(self, spot: float, strike: int) -> float:
        spot = max(spot, 1e-6)
        x = math.log(strike / spot) / math.sqrt(self.TTE_YEARS)
        volatility = self.SMILE_A * x * x + self.SMILE_B * x + self.SMILE_C
        return max(0.01, volatility)

    def option_fair_value(self, spot: float, strike: int) -> float:
        return self.black_scholes_call(spot, strike, self.smile_volatility(spot, strike))

    def history(self, product: str) -> Deque[float]:
        if product not in self.mid_history:
            self.mid_history[product] = deque(maxlen=self.HISTORY_WINDOW)
        return self.mid_history[product]

    def record_mid(self, product: str, mid: float) -> None:
        self.history(product).append(mid)

    def rolling_reversion(self, product: str, mid: float, spread: float) -> float:
        mids = list(self.history(product))
        if not mids:
            return 0.0
        window = mids[-min(self.REVERSION_WINDOW, len(mids)) :]
        mean = sum(window) / len(window)
        return self.clamp((mean - mid) / max(spread, 1.0), -2.0, 2.0)

    def microprice(self, order_depth: OrderDepth, levels: int) -> float:
        mid = self.mid_price(order_depth)
        if mid is None:
            return 0.0
        bid_levels = self.top_levels(order_depth.buy_orders, True, levels)
        ask_levels = self.top_levels(order_depth.sell_orders, False, levels)
        if not bid_levels or not ask_levels:
            return mid
        numerator = 0.0
        denominator = 0.0
        for (bid_price, bid_qty), (ask_price, ask_qty) in zip(bid_levels, ask_levels):
            numerator += ask_price * bid_qty + bid_price * ask_qty
            denominator += bid_qty + ask_qty
        if denominator <= 0.0:
            return mid
        return numerator / denominator

    def imbalance(self, order_depth: OrderDepth, levels: int) -> float:
        bid_levels = self.top_levels(order_depth.buy_orders, True, levels)
        ask_levels = self.top_levels(order_depth.sell_orders, False, levels)
        bid_total = sum(volume for _, volume in bid_levels)
        ask_total = sum(volume for _, volume in ask_levels)
        total = bid_total + ask_total
        if total <= 0:
            return 0.0
        return self.clamp((bid_total - ask_total) / total, -1.0, 1.0)

    def depth_ratio(self, order_depth: OrderDepth, levels: int) -> float:
        bid_levels = self.top_levels(order_depth.buy_orders, True, levels)
        ask_levels = self.top_levels(order_depth.sell_orders, False, levels)
        bid_total = sum(volume for _, volume in bid_levels)
        ask_total = sum(volume for _, volume in ask_levels)
        return self.clamp(math.log((bid_total + 1.0) / (ask_total + 1.0)), -2.0, 2.0)

    def wall_skew(self, order_depth: OrderDepth, levels: int) -> float:
        bid_levels = self.top_levels(order_depth.buy_orders, True, levels)
        ask_levels = self.top_levels(order_depth.sell_orders, False, levels)
        if not bid_levels or not ask_levels:
            return 0.0
        bid_total = sum(volume for _, volume in bid_levels)
        ask_total = sum(volume for _, volume in ask_levels)
        if bid_total <= 0 or ask_total <= 0:
            return 0.0
        bid_wall = bid_levels[0][1] / bid_total
        ask_wall = ask_levels[0][1] / ask_total
        return self.clamp(bid_wall - ask_wall, -1.0, 1.0)

    def book_slope_skew(self, order_depth: OrderDepth, levels: int) -> float:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return 0.0
        bid_levels = self.top_levels(order_depth.buy_orders, True, levels)
        ask_levels = self.top_levels(order_depth.sell_orders, False, levels)
        if len(bid_levels) < 2 or len(ask_levels) < 2:
            return 0.0
        bid_prices = [price for price, _ in bid_levels]
        ask_prices = [price for price, _ in ask_levels]
        bid_gap = (bid_prices[0] - bid_prices[-1]) / max(1, len(bid_prices) - 1)
        ask_gap = (ask_prices[-1] - ask_prices[0]) / max(1, len(ask_prices) - 1)
        spread = max(1.0, float(best_ask - best_bid))
        return self.clamp((ask_gap - bid_gap) / spread, -2.0, 2.0)

    def book_adjustment(self, product: str, order_depth: OrderDepth, mid: float, profile: Dict[str, float]) -> float:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return 0.0
        spread = max(1.0, float(best_ask - best_bid))
        micro_l1 = self.microprice(order_depth, 1) - mid
        micro_l3 = self.microprice(order_depth, 3) - mid
        imb_l1 = self.imbalance(order_depth, 1)
        imb_l3 = self.imbalance(order_depth, 3)
        depth = self.depth_ratio(order_depth, 3)
        wall = self.wall_skew(order_depth, 3)
        slope = self.book_slope_skew(order_depth, 3)
        reversion = self.rolling_reversion(product, mid, spread)

        micro_adjustment = profile.get("micro_l3", 0.0) * micro_l3 + profile.get("micro_l1", 0.0) * micro_l1
        structural_adjustment = spread * (
            profile.get("imb_l1", 0.0) * imb_l1
            + profile.get("imb_l3", 0.0) * imb_l3
            + profile.get("wall", 0.0) * wall
            + profile.get("depth", 0.0) * depth
            + profile.get("slope", 0.0) * slope
            + profile.get("reversion", 0.0) * reversion
        )

        adjustment = micro_adjustment + structural_adjustment
        cap = max(2.0, 1.25 * spread)
        return self.clamp(adjustment, -cap, cap)

    def option_profile(self, product: str) -> Dict[str, float]:
        return self.option_profiles.get(product, self.option_profiles["VEV_5200"])

    def trade_spot(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        profile: Dict[str, float],
    ) -> Tuple[List[Order], Optional[float]]:
        mid = self.mid_price(order_depth)
        if mid is None:
            return [], None

        fair = mid + self.book_adjustment(product, order_depth, mid, profile)
        self.record_mid(product, mid)
        orders = self.trade_from_fair(
            product,
            order_depth,
            position,
            fair,
            int(profile.get("take_size", 8)),
            int(profile.get("quote_size", 8)),
        )
        return orders, fair

    def trade_voucher(
        self,
        product: str,
        strike: int,
        spot_reference: float,
        order_depth: OrderDepth,
        position: int,
        profile: Dict[str, float],
    ) -> List[Order]:
        mid = self.mid_price(order_depth)
        if mid is None:
            return []

        iv = self.smile_volatility(spot_reference, strike)
        base_fair = self.black_scholes_call(spot_reference, strike, iv)
        residual_prior = self.OPTION_RESIDUAL_PRIOR.get(product, 0.0) * self.residual_prior_weight
        book_adjustment = self.book_adjustment(product, order_depth, mid, profile)
        fair = base_fair + residual_prior + book_adjustment

        self.record_mid(product, mid)
        return self.trade_from_fair(
            product,
            order_depth,
            position,
            fair,
            int(profile.get("take_size", 8)),
            int(profile.get("quote_size", 8)),
        )

    def trade_from_fair(
        self,
        product: str,
        order_depth: OrderDepth,
        position: int,
        fair: float,
        take_size: int,
        quote_size: int,
    ) -> List[Order]:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None or best_bid >= best_ask:
            return []

        spread = max(1.0, float(best_ask - best_bid))
        take_threshold = max(1.0, 0.15 * spread)
        quote_threshold = max(1.0, 0.10 * spread)

        buy_capacity = self.buy_capacity(self.LIMITS[product], position)
        sell_capacity = self.sell_capacity(self.LIMITS[product], position)
        orders: List[Order] = []

        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            if buy_capacity <= 0:
                break
            ask_qty = max(0, -int(ask_volume))
            if ask_qty <= 0 or fair - ask_price < take_threshold:
                continue
            quantity = min(ask_qty, buy_capacity, take_size)
            if quantity > 0:
                orders.append(Order(product, int(ask_price), int(quantity)))
                buy_capacity -= quantity

        for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
            if sell_capacity <= 0:
                break
            bid_qty = max(0, int(bid_volume))
            if bid_qty <= 0 or bid_price - fair < take_threshold:
                continue
            quantity = min(bid_qty, sell_capacity, take_size)
            if quantity > 0:
                orders.append(Order(product, int(bid_price), -int(quantity)))
                sell_capacity -= quantity

        mid = (best_bid + best_ask) / 2.0
        if fair - mid > quote_threshold and buy_capacity > 0:
            bid_price = self.directional_bid(best_bid, best_ask, fair)
            if bid_price < best_ask:
                quantity = min(quote_size, buy_capacity)
                if quantity > 0:
                    orders.append(Order(product, int(bid_price), int(quantity)))
        elif mid - fair > quote_threshold and sell_capacity > 0:
            ask_price = self.directional_ask(best_bid, best_ask, fair)
            if ask_price > best_bid:
                quantity = min(quote_size, sell_capacity)
                if quantity > 0:
                    orders.append(Order(product, int(ask_price), -int(quantity)))

        return orders

    @staticmethod
    def directional_bid(best_bid: int, best_ask: int, fair: float) -> int:
        if best_ask - best_bid > 1:
            inside = best_bid + 1
        else:
            inside = best_bid
        fair_bid = int(math.floor(fair))
        return max(best_bid, min(best_ask - 1, max(inside, fair_bid)))

    @staticmethod
    def directional_ask(best_bid: int, best_ask: int, fair: float) -> int:
        if best_ask - best_bid > 1:
            inside = best_ask - 1
        else:
            inside = best_ask
        fair_ask = int(math.ceil(fair))
        return min(best_ask, max(best_bid + 1, min(inside, fair_ask)))

    @staticmethod
    def buy_capacity(limit: int, position: int) -> int:
        return max(0, limit - position)

    @staticmethod
    def sell_capacity(limit: int, position: int) -> int:
        return max(0, limit + position)

    def passive_hydrogel(self, order_depth: OrderDepth, position: int) -> List[Order]:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None or best_bid >= best_ask:
            return []

        if best_ask - best_bid > 1:
            bid_price = best_bid + 1
            ask_price = best_ask - 1
        else:
            bid_price = best_bid
            ask_price = best_ask

        buy_size = min(self.HYDROGEL_SIZE, self.buy_capacity(self.LIMITS["HYDROGEL_PACK"], position))
        sell_size = min(self.HYDROGEL_SIZE, self.sell_capacity(self.LIMITS["HYDROGEL_PACK"], position))

        orders: List[Order] = []
        if buy_size > 0:
            orders.append(Order("HYDROGEL_PACK", bid_price, buy_size))
        if sell_size > 0:
            orders.append(Order("HYDROGEL_PACK", ask_price, -sell_size))
        return orders
