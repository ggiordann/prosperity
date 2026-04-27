import math
from typing import Dict, List, Optional

from datamodel import Order, OrderDepth, TradingState


class Trader:
    """Round 3 Velvet voucher relative-value trader.

    The edge is the cross-sectional IV smile residual from the VEV graph:
    use a fixed no-lookahead smile, convert it to a Black-Scholes fair value,
    and trade only when the live book is materially away from that fair.
    """

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

    ACTIVE_STRIKES = (4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500)
    TTE_YEARS = 5.0 / 365.0

    # Fitted from the historical Round 3 VEV smile using only same-tick data.
    # We keep this static in live trading so the strategy never uses future RV.
    SMILE_A = 0.01305220
    SMILE_B = 0.01281602
    SMILE_C = 0.27669756

    # Tuned against smile-residual alpha, with a robustness penalty for bad days.
    STRIKE_SIZE = {
        4000: 6,
        4500: 6,
        5000: 3,
        5100: 48,
        5200: 48,
        5300: 24,
        5400: 6,
        5500: 6,
    }
    STRIKE_MIN_EDGE = {
        4000: 0.0,
        4500: 0.0,
        5000: 0.0,
        5100: 0.5,
        5200: 4.0,
        5300: 5.0,
        5400: 1.0,
        5500: 2.0,
    }

    def run(self, state: TradingState):
        orders_by_product: Dict[str, List[Order]] = {product: [] for product in state.order_depths}

        velvet_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        velvet_mid = self.mid_price(velvet_depth)
        if velvet_mid is None:
            return orders_by_product, 0, ""

        for strike in self.ACTIVE_STRIKES:
            product = f"VEV_{strike}"
            order_depth = state.order_depths.get(product)
            if order_depth is None:
                continue
            position = int(state.position.get(product, 0))
            orders_by_product[product] = self.trade_voucher(
                product=product,
                strike=strike,
                velvet_mid=velvet_mid,
                order_depth=order_depth,
                position=position,
            )

        return orders_by_product, 0, ""

    @staticmethod
    def best_bid_ask(order_depth: Optional[OrderDepth]):
        if order_depth is None:
            return None, None
        best_bid = max(order_depth.buy_orders) if order_depth.buy_orders else None
        best_ask = min(order_depth.sell_orders) if order_depth.sell_orders else None
        return best_bid, best_ask

    @classmethod
    def mid_price(cls, order_depth: Optional[OrderDepth]) -> Optional[float]:
        best_bid, best_ask = cls.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return None
        return (best_bid + best_ask) / 2.0

    @staticmethod
    def normal_cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

    def black_scholes_call(self, spot: float, strike: int, volatility: float) -> float:
        if volatility <= 0.0:
            return max(spot - strike, 0.0)
        vol_sqrt_t = volatility * math.sqrt(self.TTE_YEARS)
        d1 = (math.log(spot / strike) + 0.5 * volatility * volatility * self.TTE_YEARS) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
        return spot * self.normal_cdf(d1) - strike * self.normal_cdf(d2)

    def smile_volatility(self, spot: float, strike: int) -> float:
        x = math.log(strike / spot) / math.sqrt(self.TTE_YEARS)
        return max(0.01, self.SMILE_A * x * x + self.SMILE_B * x + self.SMILE_C)

    def option_fair_value(self, spot: float, strike: int) -> float:
        return self.black_scholes_call(spot, strike, self.smile_volatility(spot, strike))

    @staticmethod
    def buy_capacity(limit: int, position: int) -> int:
        return max(0, limit - position)

    @staticmethod
    def sell_capacity(limit: int, position: int) -> int:
        return max(0, limit + position)

    def trade_voucher(
        self,
        product: str,
        strike: int,
        velvet_mid: float,
        order_depth: OrderDepth,
        position: int,
    ) -> List[Order]:
        best_bid, best_ask = self.best_bid_ask(order_depth)
        if best_bid is None or best_ask is None:
            return []

        fair_value = self.option_fair_value(velvet_mid, strike)
        buy_capacity = self.buy_capacity(self.LIMITS[product], position)
        sell_capacity = self.sell_capacity(self.LIMITS[product], position)
        max_clip = self.STRIKE_SIZE[strike]
        min_edge = self.STRIKE_MIN_EDGE[strike]
        orders: List[Order] = []

        for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
            if buy_capacity <= 0:
                break
            if ask_price + min_edge <= fair_value:
                quantity = min(max_clip, buy_capacity, -int(ask_volume))
                if quantity > 0:
                    orders.append(Order(product, ask_price, quantity))
                    buy_capacity -= quantity

        for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
            if sell_capacity <= 0:
                break
            if bid_price - min_edge >= fair_value:
                quantity = min(max_clip, sell_capacity, int(bid_volume))
                if quantity > 0:
                    orders.append(Order(product, bid_price, -quantity))
                    sell_capacity -= quantity

        return orders
