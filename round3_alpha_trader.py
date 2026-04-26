import math
from datamodel import Order, OrderDepth, TradingState
from typing import Dict, List, Optional


class Trader:
    """Round 3 trader using the Velvetfruit volatility smile."""

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

    OPTION_STRIKES = (5000, 5100, 5200, 5300, 5400, 5500)
    DEFAULT_OPTION_SIZE = 3
    OPTION_SIZES = {
        5100: 2,
        5300: 16,
        5400: 8,
    }
    TTE_YEARS = 5.0 / 365.0

    # Quadratic IV smile in normalized log-moneyness:
    # x = log(K / S) / sqrt(T). Fitted from the historical surface at TTE=5
    # using strikes 5000/5100/5200/5300/5500 and excluding the depressed 5400
    # point. The residual is the useful Round 3 options edge.
    SMILE_A = 0.011355
    SMILE_B = 0.013274
    SMILE_C = 0.276731

    # Per-strike sizes follow the advisor's "volume by conviction" clue.
    # Edge-scaled sizing and minimum-edge filters were backtested and lost PnL;
    # these stable strike-level overrides improved all three historical days.
    HYDROGEL_SIZE = 8

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {product: [] for product in state.order_depths}

        velvet_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        velvet_mid = self.mid_price(velvet_depth)
        if velvet_mid is not None:
            for strike in self.OPTION_STRIKES:
                product = f"VEV_{strike}"
                order_depth = state.order_depths.get(product)
                if order_depth is None:
                    continue
                position = int(state.position.get(product, 0))
                result[product] = self.trade_voucher(
                    product,
                    strike,
                    velvet_mid,
                    order_depth,
                    position,
                )

        hydrogel_depth = state.order_depths.get("HYDROGEL_PACK")
        if hydrogel_depth is not None:
            position = int(state.position.get("HYDROGEL_PACK", 0))
            result["HYDROGEL_PACK"] = self.passive_hydrogel(hydrogel_depth, position)

        return result, 0, ""

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
        if best_bid is not None and best_ask is not None:
            return (best_bid + best_ask) / 2.0
        return None

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
        volatility = self.SMILE_A * x * x + self.SMILE_B * x + self.SMILE_C
        return max(0.01, volatility)

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
        orders: List[Order] = []

        if buy_capacity > 0:
            for ask_price, ask_volume in sorted(order_depth.sell_orders.items()):
                if buy_capacity <= 0:
                    break
                if ask_price <= fair_value:
                    order_size = self.option_size(strike)
                    quantity = min(order_size, buy_capacity, -int(ask_volume))
                    if quantity > 0:
                        orders.append(Order(product, ask_price, quantity))
                        buy_capacity -= quantity

        if sell_capacity > 0:
            for bid_price, bid_volume in sorted(order_depth.buy_orders.items(), reverse=True):
                if sell_capacity <= 0:
                    break
                if bid_price >= fair_value:
                    order_size = self.option_size(strike)
                    quantity = min(order_size, sell_capacity, int(bid_volume))
                    if quantity > 0:
                        orders.append(Order(product, bid_price, -quantity))
                        sell_capacity -= quantity

        return orders

    def option_size(self, strike: int) -> int:
        return self.OPTION_SIZES.get(strike, self.DEFAULT_OPTION_SIZE)

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
